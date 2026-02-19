"""
wsz6_play/consumers/game_consumer.py

In-game WebSocket consumer.

Handles the live game loop for one player connection:
  - Authenticates the player via their role_token.
  - Receives operator-apply, undo, pause, help, and rematch commands.
  - Forwards commands to the shared GameRunner.
  - Receives state_update / transition_msg / goal_reached / game_paused /
    new_session_ready broadcasts from the GameRunner via the Channel group
    and relays them to the browser (filtering operators to the player's role).

WebSocket URL:  ws://<host>/ws/game/<session_key>/<role_token>/

── Messages from client ──────────────────────────────────────────────────
  {type: "apply_operator",  op_index: <int>, args: [...]}
  {type: "request_undo"}
  {type: "request_pause"}                                    (owner only)
  {type: "request_rematch"}                                  (owner only)
  {type: "request_help"}

── Messages to client (from channel group) ───────────────────────────────
  {type: "state_update",      step, state, state_text, is_goal,
                               operators (role-filtered), current_role_num,
                               your_role_num}
  {type: "transition_msg",    message, step}
  {type: "goal_reached",      step, goal_message}
  {type: "game_paused",       checkpoint_id, step}
  {type: "new_session_ready", lobby_url}
  {type: "error",             message}
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings

from wsz6_play import session_store
from wsz6_play.engine.game_runner import GameError
from wsz6_play.engine.pff_loader import PFFLoadError, load_formulation
from wsz6_play.engine.role_manager import RoleManager
from wsz6_play.engine.state_serializer import serialize_state
from wsz6_play.persistence.checkpoint import save_checkpoint
from wsz6_play.persistence.gdm_writer import make_gdm_session_path
from wsz6_play.persistence.session_sync import (
    push_playthrough_ended,
    push_playthrough_step,
    push_session_ended,
    push_session_status,
)

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

        # Determine owner status for this connection (used for pause permission).
        user     = self.scope.get('user')
        is_auth  = user and getattr(user, 'is_authenticated', False)
        self.is_owner = is_auth and (user.id == session.get('owner_id'))

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
            'is_owner':         self.is_owner,
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
        if   msg_type == 'apply_operator':  await self._handle_apply(content, session)
        elif msg_type == 'request_undo':    await self._handle_undo(session)
        elif msg_type == 'request_pause':   await self._handle_pause(session)
        elif msg_type == 'request_rematch': await self._handle_rematch(session)
        elif msg_type == 'request_help':
            await self.send_json({
                'type':    'help',
                'message': (
                    'Click an applicable operator to apply it. '
                    '"Undo" rolls back one step. '
                    '"Pause" saves progress and suspends the session. '
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
            op_name = _get_op_name(runner, op_index)
            await gdm_writer.write_event(
                'operator_applied',
                step=runner.step, op_index=op_index, op_name=op_name,
                args=args, role_num=self.role_num,
            )

        if runner.finished:
            await self._on_game_ended(session, runner, gdm_writer)
        else:
            # Trigger any bots whose turn it now is.
            await self._trigger_bots(session, runner)

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
        # Undo can land back on a bot's turn; trigger them if so.
        await self._trigger_bots(session, runner)

    async def _handle_pause(self, session):
        if not self.is_owner:
            await self.send_json({
                'type': 'error', 'message': 'Only the session owner can pause the game.'
            })
            return

        runner = session.get('game_runner')
        if runner is None or runner.finished:
            await self.send_json({
                'type': 'error', 'message': 'Cannot pause: game not running.'
            })
            return

        # Save checkpoint and update session state.
        checkpoint_id = await save_checkpoint(session, runner, label='pause')
        session_store.update_session(self.session_key, {
            'status':                'paused',
            'latest_checkpoint_id':  checkpoint_id,
        })

        # Update UARD status and PlayThrough step count.
        playthrough_id = session.get('playthrough_id', '')
        await push_session_status(self.session_key, 'paused')
        if playthrough_id:
            await push_playthrough_step(playthrough_id, runner.step)

        # Write game_paused event to GDM log.
        gdm_writer = session.get('gdm_writer')
        if gdm_writer:
            await gdm_writer.write_event(
                'game_paused',
                checkpoint_id=checkpoint_id,
                step=runner.step,
            )

        # Broadcast to all players in the game group.
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type':          'game_paused',
                'checkpoint_id': checkpoint_id,
                'step':          runner.step,
            },
        )

    async def _handle_rematch(self, session):
        if not self.is_owner:
            await self.send_json({
                'type': 'error', 'message': 'Only the session owner can start a rematch.'
            })
            return

        if session.get('status') != 'ended':
            await self.send_json({
                'type': 'error', 'message': 'Rematch is only available after a game has ended.'
            })
            return

        game_slug = session['game_slug']
        game_name = session['game_name']
        owner_id  = session['owner_id']
        old_rm    = session['role_manager']

        # Load the formulation to get roles_spec for the new RoleManager.
        try:
            formulation = await asyncio.to_thread(
                load_formulation, game_slug, settings.GAMES_REPO_ROOT
            )
        except PFFLoadError as exc:
            await self.send_json({'type': 'error', 'message': f'Could not start rematch: {exc}'})
            return

        roles_spec = getattr(formulation, 'roles_spec', None)
        if roles_spec is None:
            from wsz6_play.consumers.lobby_consumer import _default_roles_spec
            roles_spec = _default_roles_spec()

        new_rm = RoleManager(roles_spec)

        # Pre-populate with the same players in the same roles.
        for p in old_rm.get_assigned_players():
            token = new_rm.add_player(p.name, user_id=p.user_id)
            player = new_rm.get_player(token)
            if p.is_bot:
                player.is_bot   = True
                player.strategy = p.strategy
            new_rm.assign_role(token, p.role_num)

        # Derive the GDM root from the existing session directory.
        # session_dir = <gdm_root>/<game_slug>/sessions/<old_key>
        old_session_dir = session['session_dir']
        gdm_root = os.path.dirname(os.path.dirname(os.path.dirname(old_session_dir)))

        new_key     = str(uuid.uuid4())
        session_dir = make_gdm_session_path(gdm_root, game_slug, new_key)
        await asyncio.to_thread(os.makedirs, session_dir, exist_ok=True)

        # Register new session in the store.
        session_store.create_session(new_key, {
            'session_key':          new_key,
            'game_slug':            game_slug,
            'game_name':            game_name,
            'owner_id':             owner_id,
            'pff_path':             session.get('pff_path', ''),
            'status':               'lobby',
            'role_manager':         new_rm,
            'game_runner':          None,
            'gdm_writer':           None,
            'playthrough_id':       None,
            'latest_checkpoint_id': None,
            'bots':                 [],
            'session_dir':          session_dir,
            'started_at':           datetime.now(timezone.utc).isoformat(),
        })

        # Create the UARD GameSession record for the new session.
        await _create_rematch_db_record(new_key, game_slug, owner_id)

        # Redirect all connected players to the new lobby.
        await self.channel_layer.group_send(
            self.group_name,
            {'type': 'new_session_ready', 'lobby_url': f'/play/join/{new_key}/'},
        )

    # ----------------------------------------------------------------
    # Bot triggering  (thin wrappers over module-level functions)
    # ----------------------------------------------------------------

    async def _trigger_bots(self, session, runner):
        await trigger_bots_for_session(self.session_key)

    # ----------------------------------------------------------------
    # Game-ended helper  (thin wrapper over module-level function)
    # ----------------------------------------------------------------

    async def _on_game_ended(self, session, runner, gdm_writer, _already_logged=False):
        await _run_game_ended(self.session_key, session, runner, gdm_writer, _already_logged)

    # ----------------------------------------------------------------
    # Channel layer message handlers (called by group_send)
    # ----------------------------------------------------------------

    async def state_update(self, event):
        filtered = _filter_ops_for_role(event.get('operators', []), self.role_num)
        await self.send_json({**event, 'operators': filtered, 'your_role_num': self.role_num})

    async def transition_msg(self, event):
        await self.send_json(event)

    async def goal_reached(self, event):
        await self.send_json(event)

    async def game_paused(self, event):
        await self.send_json(event)

    async def new_session_ready(self, event):
        await self.send_json(event)


# ---------------------------------------------------------------------------
# Module-level async helpers (also called by lobby_consumer at game start)
# ---------------------------------------------------------------------------

async def _run_game_ended(
    session_key: str,
    session: dict,
    runner,
    gdm_writer,
    _already_logged: bool = False,
) -> None:
    """Write GDM events, update PlayThrough and UARD, mark session ended."""
    if not _already_logged and gdm_writer:
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

    playthrough_id = session.get('playthrough_id', '')
    if playthrough_id:
        await push_playthrough_ended(playthrough_id, runner.step, 'completed')

    summary = _build_summary(session, runner, 'completed')
    await push_session_ended(session_key, summary)
    session_store.update_session(session_key, {'status': 'ended'})


async def trigger_bots_for_session(session_key: str) -> None:
    """Drive all pending bot moves for a session.

    Loops until it is a human's turn or the game ends.  Safe to call with
    ensure_future from lobby_consumer (when a bot goes first) or directly
    from game_consumer after a human move or undo.
    """
    session = session_store.get_session(session_key)
    if not session:
        return
    runner = session.get('game_runner')
    bots   = session.get('bots', [])
    if not runner or not bots:
        return

    gdm_writer = session.get('gdm_writer')

    for _ in range(20):   # safety limit
        if runner.finished:
            await _run_game_ended(session_key, session, runner, gdm_writer,
                                  _already_logged=True)
            break

        current_role = getattr(runner.current_state, 'current_role_num', -1)
        did_move = False
        for bot in bots:
            op_index = await bot.maybe_move(runner, current_role)
            if op_index is not None:
                if gdm_writer:
                    op_name = _get_op_name(runner, op_index)
                    await gdm_writer.write_event(
                        'operator_applied',
                        step=runner.step, op_index=op_index, op_name=op_name,
                        args=None, role_num=bot.role_num,
                    )
                did_move = True
                break   # re-evaluate after this bot's move

        if not did_move:
            break   # human's turn (or no applicable ops)

        if runner.finished:
            await _run_game_ended(session_key, session, runner, gdm_writer)
            break


# ---------------------------------------------------------------------------
# Module-level sync helpers
# ---------------------------------------------------------------------------

def _filter_ops_for_role(ops: list, role_num: int) -> list:
    """Return operators visible to the player with role_num.

    - Operators with ``op.role == None`` are shown to all roles.
    - Operators with ``op.role == role_num`` are shown only to that role.
    - All other role-specific operators are hidden.
    """
    return [op for op in ops if op.get('role') in (None, role_num)]


def _get_op_name(runner, op_index: int) -> str:
    """Return the display name of an operator by index."""
    ops = runner.formulation.operators.operators
    op  = ops[op_index] if 0 <= op_index < len(ops) else None
    if op is None:
        return '?'
    return op.name(runner.current_state) if callable(op.name) else op.name


@database_sync_to_async
def _create_rematch_db_record(session_key: str, game_slug: str, owner_id: int) -> None:
    """Create a UARD GameSession row for a rematch session."""
    try:
        import uuid as _uuid
        from wsz6_admin.games_catalog.models import Game
        from wsz6_admin.sessions_log.models import GameSession
        game = Game.objects.get(slug=game_slug)
        GameSession.objects.create(
            session_key=_uuid.UUID(session_key),
            owner_id=owner_id,
            game=game,
            status=GameSession.STATUS_OPEN,
        )
    except Exception as exc:
        logger.warning("Could not create rematch GameSession record: %s", exc)


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
