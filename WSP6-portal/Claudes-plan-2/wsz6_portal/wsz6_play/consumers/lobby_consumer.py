"""
wsz6_play/consumers/lobby_consumer.py

Lobby WebSocket consumer.

Handles everything before the game starts (or before a paused game resumes):
  - Players connect and register a display name.
  - Session owner assigns players to roles.
  - Session owner assigns bot players to roles.
  - Session owner clicks "Start Game" / "Resume" once roles are filled.
  - On start, the PFF is loaded, GDM dirs are created, a PlayThrough DB
    record is written, and a GameRunner is initialised.
  - On resume, the latest checkpoint is loaded and the existing PlayThrough
    is continued (same log.jsonl, same playthrough_id).

WebSocket URL:  ws://<host>/ws/lobby/<session_key>/

── Messages from client ──────────────────────────────────────────────────
  {type: "join",        name: "<player name>"}
  {type: "assign_role", token: "<hex>", role_num: <int>}   (owner only)
  {type: "assign_bot",  role_num: <int>, strategy: "random"|"first"} (owner only)
  {type: "start_game"}                                       (owner only)

── Messages to client ────────────────────────────────────────────────────
  {type: "connected",     player_token: "…", is_owner: bool}
  {type: "lobby_state",   game_name, game_slug, status,
                          roles: {roles:[…], unassigned:[…]},
                          min_players_to_start: int}
  {type: "game_starting", game_page_url: "/play/game/<key>/<token>/"}
  {type: "error",         message: "…"}
"""

import asyncio
import logging
import uuid

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer
from django.conf import settings

from wsz6_play import session_store
from wsz6_play.engine.bot_player import BotPlayer
from wsz6_play.engine.game_runner import GameRunner
from wsz6_play.engine.pff_loader import PFFLoadError, load_formulation
from wsz6_play.engine.role_manager import PlayerInfo, RoleManager
from wsz6_play.persistence.checkpoint import load_checkpoint
from wsz6_play.persistence.gdm_writer import (
    GDMWriter,
    ensure_gdm_dirs,
    make_gdm_playthrough_path,
)
from wsz6_play.persistence.session_sync import push_session_status

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_roles_spec():
    """Minimal single-role spec used when the PFF has none."""
    class _Role:
        def __init__(self, name, description=''):
            self.name        = name
            self.description = description
    class _Spec:
        def __init__(self):
            self.roles                 = [_Role('Player', 'The sole player/solver.')]
            self.min_players_to_start  = 1
    return _Spec()


@database_sync_to_async
def _create_playthrough_record(session_key, game_slug, playthrough_id, log_path):
    """Write a PlayThrough row to the GDM database."""
    try:
        from wsz6_play.models import PlayThrough
        PlayThrough.objects.using('gdm').create(
            playthrough_id=playthrough_id,
            session_key=session_key,
            game_slug=game_slug,
            log_path=log_path,
        )
    except Exception as exc:
        logger.warning("Could not create PlayThrough record: %s", exc)


# ---------------------------------------------------------------------------
# Consumer
# ---------------------------------------------------------------------------

class LobbyConsumer(AsyncJsonWebsocketConsumer):

    # ----------------------------------------------------------------
    # Connection lifecycle
    # ----------------------------------------------------------------

    async def connect(self):
        self.session_key = self.scope['url_route']['kwargs']['session_key']
        session = session_store.get_session(self.session_key)
        if session is None:
            await self.close(code=4404)
            return

        # Lazy-load the formulation on the very first connection so we
        # have roles_spec to build the RoleManager.
        if session.get('role_manager') is None:
            await self._init_role_manager(session)
            session = session_store.get_session(self.session_key)
            if session is None:
                await self.close(code=4404)
                return

        status = session['status']
        if status not in ('lobby', 'paused'):
            await self.accept()
            await self.send_json({'type': 'error', 'message': 'Game has already started.'})
            return

        user    = self.scope.get('user')
        is_auth = user and getattr(user, 'is_authenticated', False)

        rm      = session['role_manager']
        name    = user.username if is_auth else f"Guest-{uuid.uuid4().hex[:6]}"
        user_id = user.id if is_auth else None

        # If this authenticated user already has a slot in the RoleManager
        # (pre-assigned for a rematch, or preserved from a paused session),
        # restore their existing token so their game URL stays valid.
        if is_auth and user_id:
            existing_token = next(
                (p.token for p in rm.get_all_players() if p.user_id == user_id),
                None,
            )
            self.player_token = existing_token or rm.add_player(name, user_id=user_id)
        else:
            self.player_token = rm.add_player(name, user_id=user_id)

        self.group_name = f"lobby_{self.session_key}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        is_owner = is_auth and (user_id == session.get('owner_id'))
        await self.send_json({
            'type':         'connected',
            'player_token': self.player_token,
            'is_owner':     is_owner,
        })
        await self._broadcast_lobby_state(session)

    async def disconnect(self, close_code):
        if not hasattr(self, 'player_token'):
            return
        session = session_store.get_session(self.session_key)
        if session and session.get('role_manager'):
            # Only remove unassigned players when the lobby is open.
            # Pre-assigned players (e.g. rematch carry-over) keep their slot
            # so their role is ready when they reconnect.
            rm = session['role_manager']
            if session['status'] == 'lobby':
                player = rm.get_player(self.player_token)
                if player is not None and player.role_num < 0:
                    rm.remove_player(self.player_token)
                    await self._broadcast_lobby_state(session)
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
        if   msg_type == 'join':          await self._handle_join(content, session)
        elif msg_type == 'assign_role':   await self._handle_assign_role(content, session)
        elif msg_type == 'unassign_role': await self._handle_unassign_role(content, session)
        elif msg_type == 'assign_bot':    await self._handle_assign_bot(content, session)
        elif msg_type == 'start_game':    await self._handle_start_game(session)
        else:
            await self.send_json({
                'type': 'error', 'message': f'Unknown message type: {msg_type!r}'
            })

    # ----------------------------------------------------------------
    # Message handlers
    # ----------------------------------------------------------------

    async def _handle_join(self, content, session):
        name = str(content.get('name', '')).strip()
        if name:
            rm     = session['role_manager']
            player = rm.get_player(self.player_token)
            if player:
                player.name = name
        await self._broadcast_lobby_state(session)

    async def _handle_assign_role(self, content, session):
        if not self._is_owner(session):
            await self.send_json({
                'type': 'error', 'message': 'Only the session owner can assign roles.'
            })
            return
        token    = content.get('token', '')
        role_num = content.get('role_num')
        if role_num is None:
            await self.send_json({'type': 'error', 'message': 'role_num is required.'})
            return
        try:
            role_num = int(role_num)
        except (TypeError, ValueError):
            await self.send_json({'type': 'error', 'message': 'role_num must be an integer.'})
            return
        rm  = session['role_manager']
        err = rm.assign_role(token, role_num)
        if err:
            await self.send_json({'type': 'error', 'message': err})
        else:
            await self._broadcast_lobby_state(session)

    async def _handle_unassign_role(self, content, session):
        if not self._is_owner(session):
            await self.send_json({
                'type': 'error', 'message': 'Only the session owner can unassign roles.'
            })
            return
        role_num = content.get('role_num')
        try:
            role_num = int(role_num)
        except (TypeError, ValueError):
            await self.send_json({'type': 'error', 'message': 'role_num must be an integer.'})
            return

        rm    = session['role_manager']
        token = rm.get_token_for_role(role_num)
        if token is None:
            await self._broadcast_lobby_state(session)
            return

        player = rm.get_player(token)
        if player and player.is_bot:
            # Bots have no browser — remove them from the RM entirely.
            rm.remove_player(token)
        else:
            # Human player: unassign (they return to the unassigned list).
            player.role_num = -1

        await self._broadcast_lobby_state(session)

    async def _handle_assign_bot(self, content, session):
        if not self._is_owner(session):
            await self.send_json({
                'type': 'error', 'message': 'Only the session owner can assign a bot.'
            })
            return

        role_num = content.get('role_num')
        if role_num is None:
            await self.send_json({'type': 'error', 'message': 'role_num is required.'})
            return
        try:
            role_num = int(role_num)
        except (TypeError, ValueError):
            await self.send_json({'type': 'error', 'message': 'role_num must be an integer.'})
            return

        strategy = content.get('strategy', 'random')
        if strategy not in ('random', 'first'):
            strategy = 'random'

        rm    = session['role_manager']
        roles = rm.roles_spec.roles
        if not (0 <= role_num < len(roles)):
            await self.send_json({
                'type': 'error', 'message': f'Role number {role_num} is out of range.'
            })
            return

        role_name = roles[role_num].name
        bot_name  = f"Bot-{role_name} ({strategy})"
        bot_token = rm.add_player(bot_name, user_id=None)

        # Mark as bot and set strategy directly on the PlayerInfo.
        player          = rm.get_player(bot_token)
        player.is_bot   = True
        player.strategy = strategy

        err = rm.assign_role(bot_token, role_num)
        if err:
            rm.remove_player(bot_token)
            await self.send_json({'type': 'error', 'message': err})
        else:
            await self._broadcast_lobby_state(session)

    async def _handle_start_game(self, session):
        if not self._is_owner(session):
            await self.send_json({
                'type': 'error', 'message': 'Only the session owner can start the game.'
            })
            return

        # ── Resume path ────────────────────────────────────────────────
        if session['status'] == 'paused' and session.get('latest_checkpoint_id'):
            await self._resume_from_checkpoint(session)
            return

        # ── Fresh start ────────────────────────────────────────────────
        rm  = session['role_manager']
        err = rm.validate_for_start()
        if err:
            await self.send_json({'type': 'error', 'message': err})
            return

        # Load a fresh formulation (unique module name per play-through).
        try:
            formulation = await asyncio.to_thread(
                load_formulation, session['game_slug'], settings.GAMES_REPO_ROOT
            )
        except PFFLoadError as exc:
            await self.send_json({'type': 'error', 'message': f'Failed to load game: {exc}'})
            return

        # Set up GDM directories and writer.
        playthrough_id = uuid.uuid4().hex
        session_dir    = session['session_dir']
        pt_dir         = make_gdm_playthrough_path(session_dir, playthrough_id)
        await asyncio.to_thread(ensure_gdm_dirs, pt_dir)
        gdm_writer = GDMWriter(pt_dir)

        # Create PlayThrough DB record.
        await _create_playthrough_record(
            session_key    = self.session_key,
            game_slug      = session['game_slug'],
            playthrough_id = playthrough_id,
            log_path       = gdm_writer.log_path,
        )

        # Build the broadcast function for GameRunner.
        runner, bots = self._make_runner_and_bots(
            formulation, rm, self.session_key
        )

        # Persist to session store before starting the runner.
        session_store.update_session(self.session_key, {
            'status':                'in_progress',
            'game_runner':           runner,
            'gdm_writer':            gdm_writer,
            'playthrough_id':        playthrough_id,
            'latest_checkpoint_id':  None,
            'bots':                  bots,
        })

        # Log game_started.
        await gdm_writer.write_event(
            'game_started',
            role_assignments=rm.to_dict(),
            session_key=self.session_key,
        )

        # Update UARD GameSession status → in_progress.
        await push_session_status(self.session_key, 'in_progress')

        # Initialise game state (broadcasts initial state_update to the game group;
        # players haven't joined that group yet but the state is ready when they do).
        # initialize_problem() runs inside a thread (see game_runner.start), so
        # failures here (missing API key, broken PFF, etc.) surface as exceptions.
        try:
            await runner.start()
        except Exception as exc:
            # Revert to lobby so the owner can fix the problem and try again.
            session_store.update_session(self.session_key, {
                'status':     'lobby',
                'game_runner': None,
                'bots':        [],
            })
            await push_session_status(self.session_key, 'open')
            logger.error("runner.start() failed for session %s: %s", self.session_key, exc)
            await self.send_json({
                'type':    'error',
                'message': f'Failed to start game: {exc}',
            })
            return

        # If the very first turn belongs to a bot, schedule its moves now.
        # Uses ensure_future so game_starting redirects reach browsers first.
        if bots:
            initial_role = getattr(runner.current_state, 'current_role_num', -1)
            if any(b.role_num == initial_role for b in bots):
                from wsz6_play.consumers.game_consumer import trigger_bots_for_session
                asyncio.ensure_future(trigger_bots_for_session(self.session_key))

        await self._broadcast_game_starting(rm)

    async def _resume_from_checkpoint(self, session):
        """Resume a paused session from its latest checkpoint."""
        checkpoint_id  = session['latest_checkpoint_id']
        playthrough_id = session['playthrough_id']
        gdm_writer     = session['gdm_writer']
        rm             = session['role_manager']

        # Load a fresh formulation for the runner.
        try:
            formulation = await asyncio.to_thread(
                load_formulation, session['game_slug'], settings.GAMES_REPO_ROOT
            )
        except PFFLoadError as exc:
            await self.send_json({'type': 'error', 'message': f'Failed to load game: {exc}'})
            return

        # Restore state from checkpoint.
        try:
            state, step = await load_checkpoint(checkpoint_id, formulation)
        except Exception as exc:
            logger.error("Could not load checkpoint %s: %s", checkpoint_id, exc)
            await self.send_json({'type': 'error', 'message': f'Could not load checkpoint: {exc}'})
            return

        # Build a new runner with the restored state.
        runner, bots = self._make_runner_and_bots(
            formulation, rm, self.session_key
        )
        runner.state_stack  = [state]
        runner.current_state = state
        runner.step          = step
        runner.finished      = False

        # Update session store.
        session_store.update_session(self.session_key, {
            'status':     'in_progress',
            'game_runner': runner,
            'bots':        bots,
        })

        # Write game_resumed to the SAME log (append-only, continuous).
        await gdm_writer.write_event(
            'game_resumed',
            checkpoint_id=checkpoint_id,
            step=step,
            role_assignments=rm.to_dict(),
        )

        # Update UARD status.
        await push_session_status(self.session_key, 'in_progress')

        # Broadcast the current state to the (empty) game group so it is
        # ready when players connect.
        await runner._broadcast_state()

        # If the resumed state is a bot's turn, schedule their moves.
        if bots:
            current_role = getattr(runner.current_state, 'current_role_num', -1)
            if any(b.role_num == current_role for b in bots):
                from wsz6_play.consumers.game_consumer import trigger_bots_for_session
                asyncio.ensure_future(trigger_bots_for_session(self.session_key))

        await self._broadcast_game_starting(rm)

    # ----------------------------------------------------------------
    # Channel layer message handlers (called by group_send)
    # ----------------------------------------------------------------

    async def lobby_state(self, event):
        await self.send_json(event)

    async def game_starting_event(self, event):
        my_url = event['player_game_urls'].get(self.player_token)
        await self.send_json({
            'type':          'game_starting',
            'game_page_url': my_url or f'/play/join/{self.session_key}/',
            'session_key':   event['session_key'],
        })

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    def _is_owner(self, session) -> bool:
        user = self.scope.get('user')
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        return user.id == session.get('owner_id')

    def _make_runner_and_bots(self, formulation, rm, session_key) -> tuple:
        """Create a GameRunner and collect BotPlayer instances from the RM."""
        game_group    = f"game_{session_key}"
        channel_layer = get_channel_layer()

        async def broadcast(payload: dict):
            await channel_layer.group_send(game_group, payload)

        runner = GameRunner(formulation, rm, broadcast)

        bots = [
            BotPlayer(role_num=p.role_num, strategy=p.strategy)
            for p in rm.get_assigned_players()
            if p.is_bot
        ]
        return runner, bots

    async def _broadcast_game_starting(self, rm):
        """Send game_starting_event to all lobby members with their game URLs."""
        assigned = rm.get_assigned_players()
        player_game_urls = {
            p.token: f'/play/game/{self.session_key}/{p.token}/'
            for p in assigned
            if not p.is_bot   # bots have no browser to redirect
        }
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type':             'game_starting_event',
                'player_game_urls': player_game_urls,
                'session_key':      self.session_key,
            }
        )

    async def _broadcast_lobby_state(self, session):
        rm = session['role_manager']
        await self.channel_layer.group_send(
            f"lobby_{self.session_key}",
            {
                'type':                  'lobby_state',
                'game_name':             session['game_name'],
                'game_slug':             session['game_slug'],
                'status':                session['status'],
                'roles':                 rm.to_dict(),
                'min_players_to_start':  getattr(rm.roles_spec, 'min_players_to_start', 1),
            }
        )

    async def _init_role_manager(self, session):
        """Load the PFF and create the RoleManager (once per session)."""
        try:
            formulation = await asyncio.to_thread(
                load_formulation, session['game_slug'], settings.GAMES_REPO_ROOT
            )
            roles_spec = getattr(formulation, 'roles_spec', None) or _default_roles_spec()
            rm = RoleManager(roles_spec)
        except PFFLoadError as exc:
            logger.error("LobbyConsumer: failed to load PFF for %s: %s", session['game_slug'], exc)
            rm = RoleManager(_default_roles_spec())
        session_store.update_session(self.session_key, {'role_manager': rm})
