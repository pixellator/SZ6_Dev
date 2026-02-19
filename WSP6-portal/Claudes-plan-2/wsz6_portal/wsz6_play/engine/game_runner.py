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
    ):
        """
        Args:
            formulation:    Loaded SZ_Formulation instance (unique per play-through).
            role_manager:   RoleManager with the final role assignments.
            broadcast_func: ``async callable(payload: dict)`` that sends a
                            message to the entire Channel group for this
                            play-through.
        """
        self.formulation   = formulation
        self.role_manager  = role_manager
        self.broadcast     = broadcast_func
        self.state_stack:  List[Any] = []
        self.current_state = None
        self.step          = 0
        self.finished      = False

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

        Raises:
            GameError: if the index is out of range, the precondition fails,
                       or the state-transition function raises an exception.
        """
        if self.finished:
            raise GameError("Game is already over.")

        operators = self.formulation.operators.operators
        if not (0 <= op_index < len(operators)):
            raise GameError(f"No operator with index {op_index}.")

        op    = operators[op_index]
        state = self.current_state
        if not op.precond_func(state):
            raise GameError("That operator is not applicable in the current state.")

        # Use the operator's params list (not the supplied args) to decide
        # the calling convention.  Textual_SOLUZION6 uses the same rule:
        #   if op.params → state_xition_func(state, args)
        #   else         → state_xition_func(state)
        # Run in a thread so blocking I/O (e.g. an LLM HTTP call) never
        # stalls the async event loop.
        has_params = bool(getattr(op, 'params', None))
        try:
            if has_params:
                new_state = await asyncio.to_thread(op.state_xition_func, state, args)
            else:
                new_state = await asyncio.to_thread(op.state_xition_func, state)
        except Exception as exc:
            raise GameError(f"Operator execution failed: {exc}") from exc

        self.state_stack.append(new_state)
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
        """Roll back one step by popping the state stack."""
        if self.finished:
            raise GameError("Cannot undo after the game has ended.")
        if len(self.state_stack) <= 1:
            raise GameError("Already at the initial state; cannot undo further.")
        self.state_stack.pop()
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

    async def _broadcast_state(self) -> None:
        state    = self.current_state
        ops_info = self.get_ops_info(state)
        try:
            at_goal = state.is_goal()
        except Exception:
            at_goal = False
        payload = {
            'type':             'state_update',
            'step':             self.step,
            'state':            serialize_state(state),
            'state_text':       str(state),
            'is_goal':          at_goal,
            'operators':        ops_info,
            'current_role_num': getattr(state, 'current_role_num', 0),
        }
        await self.broadcast(payload)
