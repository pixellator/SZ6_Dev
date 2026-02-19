"""
wsz6_play/consumers/game_consumer.py

In-game WebSocket consumer.

Handles the live game loop for one player connection:
  - Authenticates the player via their role_token.
  - Receives operator-apply and undo commands.
  - Forwards commands to the shared GameRunner.
  - Receives state_update / transition_msg / goal_reached broadcasts
    from the GameRunner via the Channel group and relays them to the
    browser (filtering operators to the player's role).

WebSocket URL:  ws://<host>/ws/game/<session_key>/<role_token>/

── Messages from client ──────────────────────────────────────────────────
  {type: "apply_operator", op_index: <int>, args: [...]}
  {type: "request_undo"}
  {type: "request_help"}

── Messages to client (from channel group) ───────────────────────────────
  {type: "state_update",   step, state, state_text, is_goal,
                           operators (role-filtered), current_role_num,
                           your_role_num}
  {type: "transition_msg", message, step}
  {type: "goal_reached",   step, goal_message}
  {type: "error",          message}
"""

import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from wsz6_play import session_store
from wsz6_play.engine.game_runner import GameError
from wsz6_play.engine.state_serializer import serialize_state
from wsz6_play.persistence.session_sync import push_session_ended

logger = logging.getLogger(__name__)


class GameConsumer(AsyncJsonWebsocketConsumer):

    # ----------------------------------------------------------------
    # Connection lifecycle
    # ----------------------------------------------------------------

    async def connect(self):
        self.session_key = self.scope['url_route']['kwargs']['session_key']
        self.role_token  = self.scope['url_route']['kwargs']['role_token']
        self.group_name  = f"game_{self.session_key}"

        session = session_store.get_session(self.session_key)
        if session is None or session['status'] != 'in_progress':
            await self.close(code=4404)
            return

        rm = session.get('role_manager')
        if rm is None:
            await self.close(code=4404)
            return

        player = rm.get_player(self.role_token)
        if player is None:
            await self.close(code=4403)
            return

        self.role_num = player.role_num

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send the current game state directly to this player on connect.
        runner = session['game_runner']
        state  = runner.current_state
        ops    = runner.get_ops_info(state)
        try:
            at_goal = state.is_goal()
        except Exception:
            at_goal = False

        await self.send_json({
            'type':             'state_update',
            'step':             runner.step,
            'state':            serialize_state(state),
            'state_text':       str(state),
            'is_goal':          at_goal,
            'operators':        _filter_ops_for_role(ops, self.role_num),
            'current_role_num': getattr(state, 'current_role_num', 0),
            'your_role_num':    self.role_num,
        })

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # ----------------------------------------------------------------
    # Message dispatch
    # ----------------------------------------------------------------

    async def receive_json(self, content):
        session = session_store.get_session(self.session_key)
        if session is None:
            await self.send_json({'type': 'error', 'message': 'Session not found.'})
            return

        msg_type = content.get('type')
        if   msg_type == 'apply_operator': await self._handle_apply(content, session)
        elif msg_type == 'request_undo':   await self._handle_undo(session)
        elif msg_type == 'request_help':
            await self.send_json({
                'type':    'help',
                'message': (
                    'Click an applicable operator to apply it. '
                    '"Undo" rolls back one step. '
                    'Only operators available on your turn are highlighted.'
                ),
            })
        else:
            await self.send_json({
                'type': 'error', 'message': f'Unknown message type: {msg_type!r}'
            })

    # ----------------------------------------------------------------
    # Message handlers
    # ----------------------------------------------------------------

    async def _handle_apply(self, content, session):
        runner = session.get('game_runner')
        if runner is None:
            await self.send_json({'type': 'error', 'message': 'Game engine not ready.'})
            return

        # Role-turn check.
        state = runner.current_state
        if getattr(state, 'current_role_num', 0) != self.role_num:
            await self.send_json({'type': 'error', 'message': "It is not your turn."})
            return

        try:
            op_index = int(content.get('op_index', -1))
        except (TypeError, ValueError):
            await self.send_json({'type': 'error', 'message': 'op_index must be an integer.'})
            return

        args = content.get('args') or None

        try:
            await runner.apply_operator(op_index, args)
        except GameError as exc:
            await self.send_json({'type': 'error', 'message': str(exc)})
            return

        # Log the event.
        gdm_writer = session.get('gdm_writer')
        if gdm_writer:
            ops     = runner.formulation.operators.operators
            op      = ops[op_index] if 0 <= op_index < len(ops) else None
            op_name = (
                op.name(runner.current_state) if op and callable(op.name)
                else (op.name if op else '?')
            )
            await gdm_writer.write_event(
                'operator_applied',
                step=runner.step, op_index=op_index, op_name=op_name,
                args=args, role_num=self.role_num,
            )
            if runner.finished:
                try:
                    goal_msg = runner.current_state.goal_message()
                except Exception:
                    goal_msg = "Goal reached!"
                await gdm_writer.write_event(
                    'game_ended',
                    outcome='goal_reached',
                    goal_message=goal_msg,
                    step=runner.step,
                )
                summary = _build_summary(session, runner, 'completed')
                await push_session_ended(self.session_key, summary)
                session_store.update_session(self.session_key, {'status': 'ended'})

    async def _handle_undo(self, session):
        runner = session.get('game_runner')
        if runner is None:
            await self.send_json({'type': 'error', 'message': 'Game engine not ready.'})
            return
        try:
            await runner.undo()
        except GameError as exc:
            await self.send_json({'type': 'error', 'message': str(exc)})
            return
        gdm_writer = session.get('gdm_writer')
        if gdm_writer:
            await gdm_writer.write_event('undo_applied', step=runner.step)

    # ----------------------------------------------------------------
    # Channel layer message handlers
    # ----------------------------------------------------------------

    async def state_update(self, event):
        filtered = _filter_ops_for_role(event.get('operators', []), self.role_num)
        await self.send_json({**event, 'operators': filtered, 'your_role_num': self.role_num})

    async def transition_msg(self, event):
        await self.send_json(event)

    async def goal_reached(self, event):
        await self.send_json(event)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _filter_ops_for_role(ops: list, role_num: int) -> list:
    """Return operators visible to the player with role_num.

    - Operators with ``op.role == None`` are shown to all roles.
    - Operators with ``op.role == role_num`` are shown only to that role.
    - All other role-specific operators are hidden.
    """
    return [op for op in ops if op.get('role') in (None, role_num)]


def _build_summary(session: dict, runner, outcome: str) -> dict:
    rm      = session.get('role_manager')
    players = []
    if rm:
        for p in rm.get_all_players():
            role_name = ''
            if rm.roles_spec and p.role_num >= 0:
                roles = rm.roles_spec.roles
                if p.role_num < len(roles):
                    role_name = roles[p.role_num].name
            players.append({
                'name':     p.name,
                'role':     role_name,
                'role_num': p.role_num,
                'is_bot':   p.is_bot,
            })
    return {
        'version':        '1',
        'session_key':    session.get('session_key', ''),
        'game_slug':      session.get('game_slug', ''),
        'outcome':        outcome,
        'step_count':     runner.step,
        'players':        players,
        'gdm_path':       session.get('session_dir', ''),
        'playthrough_id': session.get('playthrough_id', ''),
    }
