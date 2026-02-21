"""
wsz6_play/engine/game_runner.py

Async-safe game runner that wraps a SOLUZION6 formulation instance.

Owns the state stack, applies operators, handles undo, and broadcasts
state / event messages to all consumers in the Channel group via the
caller-supplied ``broadcast_func``.

Usage (inside a Django Channels consumer):

    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    group_name = f"game_{session_key}"

    async def broadcast(payload: dict):
        await channel_layer.group_send(group_name, payload)

    runner = GameRunner(formulation, role_manager, broadcast)
    await runner.start()
    await runner.apply_operator(op_index)
    await runner.undo()

SZ5-bug prevention note:
    Each play-through gets its **own** formulation instance, loaded fresh
    from the PFF by pff_loader.load_formulation().  Never share a
    formulation between sessions.
"""

import asyncio
import inspect
import logging
from typing import Any, Callable, Coroutine, List, Optional

from .state_serializer import serialize_state

logger = logging.getLogger(__name__)


class GameError(Exception):
    """Raised for invalid operator applications, undo beyond start, etc."""


class GameRunner:
    """Manages game state for one play-through of a SOLUZION6 formulation."""

    def __init__(
        self,
        formulation,
        role_manager,
        broadcast_func: Callable[..., Coroutine],
        game_slug: str = '',
    ):
        """
        Args:
            formulation:    Loaded SZ_Formulation instance (unique per play-through).
            role_manager:   RoleManager with the final role assignments.
            broadcast_func: ``async callable(payload: dict)`` that sends a
                            message to the entire Channel group for this
                            play-through.
            game_slug:      The game's URL slug (e.g. ``'tic-tac-toe'``).
                            Used to build the ``base_url`` passed to vis
                            modules that declare a ``base_url`` parameter in
                            their ``render_state`` signature.
        """
        self.formulation   = formulation
        self.role_manager  = role_manager
        self.broadcast     = broadcast_func
        self.game_slug     = game_slug
        self.state_stack:  List[Any] = []
        self.op_history:   List[Optional[int]] = [None]  # op_index used at each step; None = initial
        self.current_state = None
        self.step          = 0
        self.finished      = False
        self._lock         = asyncio.Lock()  # serialises concurrent apply_operator calls

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialise the formulation and broadcast the initial state.

        initialize_problem() runs in a thread so package imports and any
        setup I/O (e.g. creating an LLM client) don't block the event loop.
        """
        initial_state     = await asyncio.to_thread(self.formulation.initialize_problem)
        self.state_stack  = [initial_state]
        self.current_state = initial_state
        self.step          = 0
        self.finished      = False
        await self._broadcast_state()

    async def apply_operator(self, op_index: int, args: Optional[list] = None) -> None:
        """Apply the operator at ``op_index`` to the current state.

        The entire operation runs inside an asyncio.Lock so that concurrent
        applies from different players (e.g. during a parallel-input phase)
        are serialised correctly — each one reads the up-to-date state that
        the previous one produced.

        Raises:
            GameError: if the index is out of range, the precondition fails,
                       or the state-transition function raises an exception.
        """
        async with self._lock:
            if self.finished:
                raise GameError("Game is already over.")

            operators = self.formulation.operators.operators
            if not (0 <= op_index < len(operators)):
                raise GameError(f"No operator with index {op_index}.")

            op    = operators[op_index]
            state = self.current_state          # read inside the lock for consistency
            if not op.precond_func(state):
                raise GameError("That operator is not applicable in the current state.")

            # Use the operator's params list (not the supplied args) to decide
            # the calling convention.  Textual_SOLUZION6 uses the same rule:
            #   if op.params → state_xition_func(state, args)
            #   else         → state_xition_func(state)
            # Run in a thread so blocking I/O (e.g. an LLM HTTP call) never
            # stalls the async event loop.  The asyncio.Lock remains held while
            # the thread runs; other applies will queue behind it.
            has_params = bool(getattr(op, 'params', None))
            try:
                if has_params:
                    new_state = await asyncio.to_thread(op.state_xition_func, state, args)
                else:
                    new_state = await asyncio.to_thread(op.state_xition_func, state)
            except Exception as exc:
                raise GameError(f"Operator execution failed: {exc}") from exc

            self.state_stack.append(new_state)
            self.op_history.append(op_index)
            self.current_state = new_state
            self.step += 1

            # Transition message attached to the new state by the PFF.
            jit = getattr(new_state, 'jit_transition', None)
            if jit:
                await self.broadcast({
                    'type':    'transition_msg',
                    'message': jit,
                    'step':    self.step,
                })

            # Check for goal.
            try:
                at_goal = new_state.is_goal()
            except Exception:
                at_goal = False

            if at_goal:
                self.finished = True
                try:
                    goal_msg = new_state.goal_message()
                except Exception:
                    goal_msg = "Goal reached!"
                await self._broadcast_state()
                await self.broadcast({
                    'type':         'goal_reached',
                    'step':         self.step,
                    'goal_message': goal_msg,
                })
            else:
                await self._broadcast_state()

    async def undo(self) -> None:
        """Roll back one step by popping the state stack.

        Undo is blocked when the state we would revert *to* had
        ``parallel == True``, unless the operator that produced the current
        state explicitly sets ``allow_undo = True``.  This prevents players
        from backing out of a secret commitment after seeing another player's
        hidden choice.
        """
        async with self._lock:
            if self.finished:
                raise GameError("Cannot undo after the game has ended.")
            if len(self.state_stack) <= 1:
                raise GameError("Already at the initial state; cannot undo further.")

            # Parallel-phase undo guard.
            prev_state = self.state_stack[-2]
            if getattr(prev_state, 'parallel', False):
                # Default: block.  Override: operator carries allow_undo = True.
                last_op_index = self.op_history[-1]
                allow = False
                if last_op_index is not None:
                    ops = self.formulation.operators.operators
                    if 0 <= last_op_index < len(ops):
                        allow = getattr(ops[last_op_index], 'allow_undo', False)
                if not allow:
                    raise GameError(
                        "Undo is not allowed after a move made during a parallel input phase."
                    )

            self.state_stack.pop()
            self.op_history.pop()
            self.current_state = self.state_stack[-1]
            self.step += 1
            await self._broadcast_state()

    # ------------------------------------------------------------------
    # Introspection helpers (also called directly by GameConsumer)
    # ------------------------------------------------------------------

    def get_ops_info(self, state) -> list:
        """Return a list of operator info dicts for ``state``."""
        operators = self.formulation.operators.operators
        result = []
        for i, op in enumerate(operators):
            try:
                applicable = op.precond_func(state)
            except Exception:
                applicable = False
            name = op.name(state) if callable(op.name) else op.name
            result.append({
                'index':      i,
                'name':       name,
                'applicable': applicable,
                'role':       op.role,         # role_num constraint or None
                'params':     list(op.params) if op.params else [],
            })
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_base_payload(self) -> dict:
        """Build a ``state_update`` payload without vis_html (synchronous).

        Used by ``_broadcast_state`` to send an identical base payload to the
        channel group.  Each consumer then calls ``render_vis_for_role()``
        separately to add its own role-specific vis_html before forwarding to
        the browser.
        """
        state    = self.current_state
        ops_info = self.get_ops_info(state)
        try:
            at_goal = state.is_goal()
        except Exception:
            at_goal = False
        return {
            'type':             'state_update',
            'step':             self.step,
            'state':            serialize_state(state),
            'state_text':       str(state),
            'is_goal':          at_goal,
            'is_parallel':      getattr(state, 'parallel', False),
            'operators':        ops_info,
            'current_role_num': getattr(state, 'current_role_num', 0),
        }

    async def render_vis_for_role(self, state, role_num=None):
        """Render vis_html for a specific viewing role.

        Inspects the VIS module's ``render_state`` signature and passes only
        the keyword arguments it declares, for backward compatibility:

          - ``role_num``      — the viewing player's role (for private data)
          - ``instance_data`` — the formulation's instance_data object, which
                                carries per-game-instance constants (e.g. dealt
                                hands, crime solution) that never change during
                                a session but are re-computed on each new game
                                (including rematches).

        Returns None if no vis module is loaded or rendering fails.
        """
        vis_module = getattr(self.formulation, 'vis_module', None)
        if vis_module is None or not callable(getattr(vis_module, 'render_state', None)):
            return None
        try:
            sig    = inspect.signature(vis_module.render_state)
            params = sig.parameters
            kwargs = {}
            if 'role_num' in params:
                kwargs['role_num'] = role_num
            if 'instance_data' in params:
                kwargs['instance_data'] = getattr(self.formulation, 'instance_data', None)
            if 'base_url' in params:
                kwargs['base_url'] = f"/play/game-asset/{self.game_slug}/"
            return await asyncio.to_thread(vis_module.render_state, state, **kwargs)
        except Exception:
            logger.exception("render_vis_for_role() failed at step %s", self.step)
            return None

    async def build_state_payload(self, role_num=None) -> dict:
        """Build a complete ``state_update`` payload for the current state.

        Used by the ``GameConsumer.connect`` handler (direct send to a new
        connection) so that the initial render includes role-specific vis_html.
        Pass ``role_num`` to get a role-aware visualization; omit it for a
        generic (non-role-filtered) render.
        """
        payload  = self._build_base_payload()
        vis_html = await self.render_vis_for_role(self.current_state, role_num)
        if vis_html is not None:
            payload['vis_html'] = vis_html
        return payload

    async def _broadcast_state(self) -> None:
        """Broadcast base state payload (no vis_html) to the channel group.

        Each GameConsumer's state_update handler adds its own role-specific
        vis_html before forwarding to the browser.
        """
        payload = self._build_base_payload()
        await self.broadcast(payload)
