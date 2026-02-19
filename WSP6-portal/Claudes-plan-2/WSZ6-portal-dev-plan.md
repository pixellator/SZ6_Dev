# WSZ6-Portal Development Plan

**Prepared by:** Claude Code (claude-sonnet-4-6)
**Date:** 2026-02-18
**Working directory:** `WSP6-portal/Claudes-plan-2/`

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Component: WSZ6-admin](#3-component-wsz6-admin)
4. [Component: WSZ6-play](#4-component-wsz6-play)
5. [Admin–Play Interface](#5-adminplay-interface)
6. [Databases](#6-databases)
7. [Games Repository](#7-games-repository)
8. [Key Workflows](#8-key-workflows)
9. [Scaling Strategy](#9-scaling-strategy)
10. [Development Phases and Milestones](#10-development-phases-and-milestones)
11. [Technology Stack Summary](#11-technology-stack-summary)
12. [Open Questions and Risks](#12-open-questions-and-risks)

---

## 1. System Overview

WSZ6-portal is a web-based platform that hosts **SOLUZION6 games** for online multiplayer play. The portal combines user-account management with a real-time game engine. Games are represented as **Problem Formulation Files (PFFs)**: Python source files that subclass `SZ_Formulation`, `SZ_State`, `SZ_Operator_Set`, `SZ_Roles_Spec`, and related classes from `soluzion6_02.py`.

The portal equation:

```
WSZ6-portal = WSZ6-admin  +  WSZ6-play
```

| Component | Technology | Primary concerns |
|-----------|-----------|-----------------|
| WSZ6-admin | Django (standard) | User accounts, auth, game catalogue, admin UI |
| WSZ6-play | Django Channels (ASGI/WebSocket) | Real-time game sessions, PFF execution, state persistence |

The system is designed so that **each component can be updated independently** without breaking the other. All cross-component communication goes through a well-defined **Internal API** (see Section 5).

---

## 2. High-Level Architecture

```
Browser Clients
      │ HTTPS
      ▼
┌─────────────────────────────────────────────────────────────┐
│                      ASGI Server (Daphne / Uvicorn)         │
│                                                             │
│   ┌─────────────────────┐   ┌──────────────────────────┐   │
│   │    WSZ6-admin        │   │       WSZ6-play           │   │
│   │  (Django HTTP views) │   │  (Django Channels /WS)   │   │
│   │  Auth, accounts,     │   │  Game sessions, PFF       │   │
│   │  game catalogue,     │   │  engine, role mgmt,       │   │
│   │  admin dashboard     │   │  real-time state push     │   │
│   └──────────┬──────────┘   └────────────┬─────────────┘   │
│              │   Internal REST/Signal API  │                 │
│              └────────────────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
  ┌──────────────┐             ┌─────────────────────┐
  │  UARD (DB 1) │             │  GDM (DB 2 + Files) │
  │  PostgreSQL  │             │  PostgreSQL + FS     │
  │  User accts  │             │  Session logs,       │
  │  Session     │             │  artifacts, checkpts │
  │  summaries   │             │                      │
  │  Game catalog│             └─────────────────────┘
  └──────────────┘
         │
         ▼
  ┌──────────────────┐
  │  Games Repository│
  │  (File System)   │
  │  /games/<name>/  │
  │  PFF + resources │
  └──────────────────┘
```

A **Channel Layer** (Redis-backed) carries messages between Channels consumers in WSZ6-play, and between WSZ6-admin and WSZ6-play. A **Celery** task queue (also Redis-backed) handles asynchronous operations such as sending invitation emails.

---

## 3. Component: WSZ6-admin

### 3.1 Django Project Structure

```
wsz6_admin/
├── manage.py
├── wsz6_admin/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── asgi.py          ← mounts both HTTP and WS routing
│   └── celery.py
├── accounts/            ← user/admin account management
├── games_catalog/       ← game installation and metadata
├── sessions_log/        ← lightweight session summary records
├── research/            ← data access for researchers
└── templates/
```

### 3.2 User Model and Roles

Extend Django's `AbstractUser` to add a `user_type` field and permissions. Five account types are defined:

| Type | Code | Capabilities |
|------|------|-------------|
| General Admin | `ADMIN_GENERAL` | Everything |
| User-Account Admin | `ADMIN_ACCOUNTS` | Manage user accounts |
| Game Admin | `ADMIN_GAMES` | Install / retire games |
| Research Admin | `ADMIN_RESEARCH` | Read game-session data |
| Game-Session Owner | `SESSION_OWNER` | Start sessions, invite players |
| Individual Game Owner | `GAME_OWNER` | Install own games, invite to own games |
| Individual Player | `PLAYER` | Join sessions to which invited |

Guest players (no account) are handled by a session token issued by WSZ6-play.

```python
# accounts/models.py (sketch)
class WSZUser(AbstractUser):
    USER_TYPE_CHOICES = [...]
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    is_active_account = models.BooleanField(default=True)
    game_access_level = models.CharField(
        max_length=20,
        choices=[('published','Published'), ('beta','Beta'),
                 ('all','All'), ('custom','Custom')],
        default='published'
    )
    allowed_games = models.ManyToManyField('games_catalog.Game', blank=True)
```

### 3.3 Game Catalogue Model

```python
# games_catalog/models.py (sketch)
class Game(models.Model):
    name            = models.CharField(max_length=200, unique=True)
    slug            = models.SlugField(unique=True)
    brief_desc      = models.TextField()
    status          = models.CharField(
        max_length=20,
        choices=[('dev','Dev'), ('beta','Beta'), ('published','Published'),
                 ('deprecated','Deprecated')],
        default='dev'
    )
    installed_at    = models.DateTimeField(auto_now_add=True)
    beta_at         = models.DateTimeField(null=True, blank=True)
    published_at    = models.DateTimeField(null=True, blank=True)
    pff_path        = models.CharField(max_length=500)  # path in games repo
    min_players     = models.IntegerField(default=1)
    max_players     = models.IntegerField(default=10)
    owner           = models.ForeignKey(WSZUser, null=True, on_delete=models.SET_NULL)
    metadata_json   = models.JSONField(default=dict)   # from PFF SZ_Metadata
```

### 3.4 Session Summary Model (UARD side)

```python
# sessions_log/models.py (sketch)
class GameSession(models.Model):
    owner           = models.ForeignKey(WSZUser, on_delete=models.PROTECT)
    game            = models.ForeignKey(Game, on_delete=models.PROTECT)
    session_key     = models.UUIDField(unique=True, default=uuid.uuid4)
    started_at      = models.DateTimeField(auto_now_add=True)
    ended_at        = models.DateTimeField(null=True, blank=True)
    status          = models.CharField(
        max_length=20,
        choices=[('open','Open'), ('in_progress','In Progress'),
                 ('paused','Paused'), ('completed','Completed'),
                 ('interrupted','Interrupted')]
    )
    summary_json    = models.JSONField(default=dict)
    gdm_path        = models.CharField(max_length=500)  # pointer into GDM
    parent_session  = models.ForeignKey('self', null=True, blank=True,
                                        on_delete=models.SET_NULL)   # for continuations
```

### 3.5 Admin Dashboard Views

**List views** for Users and Games with search and filter.

**User detail view:**
- Change account type and game access level.
- View session history (list of `GameSession` records owned by the user).
- Click into a session to redirect to the GDM viewer.

**Game detail view:**
- Lifecycle controls (promote to beta → published → deprecated).
- Stats: total sessions, total play-through count, total hours.
- Timeline view: horizontal time axis; each session shown as a colored bar. Color encodes game popularity (most popular = red, cooler colors descending, top-5+ = gray).

**Live sessions panel:**
- WebSocket-fed list of currently open / in-progress sessions.
- Recently ended sessions shown grayed out.
- "Join as observer" button available for each live session.

### 3.6 Game Installation Workflow (Admin)

1. Admin navigates to **Games → Install New Game**.
2. Admin fills out a form: name, description, status, access level, min/max players.
3. Admin uploads a **zip archive** containing:
   - The PFF Python file (e.g., `Tic_Tac_Toe_SZ6.py`)
   - Optional support files (images, helper Python modules, prompt files)
4. Server-side:
   a. Validates the zip (no path traversal, size limits).
   b. Extracts to `GAMES_REPO_ROOT/<game-slug>/`.
   c. Imports the PFF module in a subprocess sandbox; extracts `SZ_Metadata` fields and validates the formulation class is a valid `SZ_Formulation` subclass.
   d. Writes a `Game` record to UARD.
   e. Sends a `game_installed` signal/event over the internal API to WSZ6-play.

### 3.7 Password Reset and Standard Account Features

Follow Django's built-in `PasswordResetView` / email-based reset flow. Use Celery for sending emails asynchronously.

---

## 4. Component: WSZ6-play

### 4.1 Django App Structure

```
wsz6_play/
├── consumers/
│   ├── lobby_consumer.py     ← session setup before game start
│   ├── game_consumer.py      ← in-game WebSocket consumer
│   └── observer_consumer.py  ← admin/observer WebSocket consumer
├── engine/
│   ├── pff_loader.py         ← dynamically imports PFF modules
│   ├── game_runner.py        ← runs game loop logic (async-safe)
│   ├── state_serializer.py   ← JSON-serializes/deserializes SZ_State
│   ├── bot_player.py         ← placeholder bot (random / first-option)
│   └── role_manager.py       ← role-assignment logic
├── persistence/
│   ├── gdm_writer.py         ← writes log files to GDM
│   ├── checkpoint.py         ← saves/loads game checkpoints
│   └── session_sync.py       ← pushes session summaries to UARD
├── routing.py                ← WS URL routing
├── models.py                 ← GDM-side DB models
└── views.py                  ← HTTP views (session join page, debug mode)
```

### 4.2 WebSocket Routing

```python
# wsz6_play/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/lobby/(?P<session_key>[0-9a-f-]+)/$',
            consumers.LobbyConsumer.as_asgi()),
    re_path(r'ws/game/(?P<session_key>[0-9a-f-]+)/(?P<role_token>[^/]+)/$',
            consumers.GameConsumer.as_asgi()),
    re_path(r'ws/observe/(?P<session_key>[0-9a-f-]+)/$',
            consumers.ObserverConsumer.as_asgi()),
]
```

### 4.3 PFF Loader

The PFF loader dynamically imports a game's formulation file. To avoid namespace collisions between games (the bug mentioned in the old SZ5 system), **each game import uses a unique module name** based on the game's slug and session key.

```python
# engine/pff_loader.py (sketch)
import importlib.util, sys

def load_formulation(game_slug, game_repo_root):
    pff_path = os.path.join(game_repo_root, game_slug, f"{game_slug}_pff.py")
    unique_module_name = f"_pff_{game_slug}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(unique_module_name, pff_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_module_name] = module
    spec.loader.exec_module(module)
    # Find the SZ_Formulation instance
    for attr in dir(module):
        obj = getattr(module, attr)
        if isinstance(obj, sz.SZ_Formulation):
            return obj
    raise ValueError(f"No SZ_Formulation found in {pff_path}")
```

**Critical:** Each active game play-through gets its **own formulation instance** (not shared). This prevents the role-mixing bugs of the SZ5 system. The formulation is instantiated fresh per play-through.

### 4.4 State Serialization

Game states (`SZ_State` subclasses) must be JSON-serializable for:
- Persisting checkpoints to disk.
- Sending state updates over WebSocket.

Strategy:
- PFFs are encouraged to implement `to_dict()` / `from_dict(cls, d)` on their State class.
- The engine provides a fallback using `__dict__` copy (for simple states).
- A registration mechanism lets PFFs declare their State class for deserialization.

```python
# engine/state_serializer.py (sketch)
def serialize_state(state):
    if hasattr(state, 'to_dict'):
        return state.to_dict()
    return {'__class__': type(state).__qualname__, '__dict__': vars(state)}

def deserialize_state(data, formulation):
    state_cls = formulation.get_state_class()   # new method on SZ_Formulation
    if hasattr(state_cls, 'from_dict'):
        return state_cls.from_dict(data)
    # Fallback: create blank instance and restore __dict__
    obj = object.__new__(state_cls)
    obj.__dict__.update(data['__dict__'])
    return obj
```

### 4.5 Game Consumer (Core Logic)

`GameConsumer` is an `AsyncJsonWebsocketConsumer`. Each connected player (or bot) has one consumer instance. All consumers for a single play-through are members of the same **Channel group** (keyed by play-through ID).

**Message types sent to clients:**
| Message type | Payload | When sent |
|---|---|---|
| `state_update` | serialized state, applicable operators for this role, step number | After every operator application |
| `role_cue` | whose turn it is, role name | At role transitions |
| `transition_msg` | jit_transition text | After operator with transition |
| `goal_reached` | goal_message | When `is_goal()` returns True |
| `game_paused` | checkpoint ID | On pause |
| `game_ended` | summary | On game completion |
| `player_joined` | player name, role | When a new player connects |
| `player_left` | player name | On disconnect |
| `error` | message | On validation error |

**Message types received from clients:**
| Message type | Payload | Action |
|---|---|---|
| `apply_operator` | operator index, args | Apply op, broadcast new state |
| `request_undo` | — | Roll back one step |
| `request_pause` | — | Save checkpoint, pause session |
| `request_help` | — | Return instructions message |

### 4.6 Lobby Consumer

Before game play begins, the lobby consumer handles:
- Session owner creates a session → gets a session URL and invite link.
- Invited players arrive at the lobby → choose or are assigned a role.
- Session owner assigns bots to unfilled roles.
- Session owner clicks "Start Game" (once `min_players` threshold is met).
- System broadcasts a `game_starting` message to all lobby members, which redirects their browsers to the game WebSocket URL with their role token.

### 4.7 Bot Player

A `BotPlayer` runs as an async task within the game consumer. Two modes:
1. **Random**: picks a random applicable operator.
2. **First-option**: always picks the first applicable operator.

The bot is triggered when it is the bot's role's turn (`state.current_role_num` matches the bot's assigned role number). After a configurable brief delay (default 1–2 seconds, to feel natural), the bot applies its chosen operator.

### 4.8 Game Runner (async-safe loop)

The `game_runner.py` module encapsulates the game loop logic in a form that cooperates with Django Channels' async event loop:

```python
# engine/game_runner.py (sketch)
class GameRunner:
    def __init__(self, formulation, role_assignments, broadcast_func):
        self.formulation = formulation
        self.role_assignments = role_assignments
        self.broadcast = broadcast_func      # async func to push to WS group
        self.state_stack = []
        self.current_state = None
        self.step = 0

    async def start(self, initial_state):
        self.current_state = initial_state
        self.state_stack = [initial_state]
        await self._broadcast_state()

    async def apply_operator(self, op_index, args=None):
        op = self.formulation.operators.operators[op_index]
        state = self.current_state
        applicable = op.precond_func(state)
        if not applicable:
            raise ValueError("Operator not applicable")
        if args:
            new_state = op.state_xition_func(state, args)
        else:
            new_state = op.state_xition_func(state)
        self.state_stack.append(new_state)
        self.current_state = new_state
        self.step += 1
        await self._broadcast_state()
        return new_state

    async def undo(self):
        if len(self.state_stack) > 1:
            self.state_stack.pop()
            self.current_state = self.state_stack[-1]
            self.step += 1
            await self._broadcast_state()

    async def _broadcast_state(self):
        state = self.current_state
        payload = {
            'type': 'state_update',
            'step': self.step,
            'state': serialize_state(state),
            'is_goal': state.is_goal() if hasattr(state,'is_goal') else False,
            'operators': self._get_op_list(state),
            'current_role_num': getattr(state, 'current_role_num', 0),
        }
        await self.broadcast(payload)
```

### 4.9 Session Persistence and Checkpointing

When a game is **paused** or **interrupted**, the runner saves a checkpoint:

```
GDM_ROOT/
  <game-slug>/
    sessions/
      <session-key>/
        session_meta.json      ← session owner, game, timestamps, status
        playthroughs/
          <playthrough-id>/
            log.jsonl          ← append-only event log (replay-complete)
            checkpoints/
              <checkpoint-id>.json  ← serialized state + role assignments
            artifacts/         ← player-written documents, LLM outputs
```

The **log.jsonl** file records every event in JSONL format:
```json
{"t": "2026-03-01T14:23:01Z", "event": "game_started", "role_assignments": {...}}
{"t": "2026-03-01T14:23:15Z", "event": "operator_applied", "step": 1, "op_index": 3, "args": [], "state": {...}}
{"t": "2026-03-01T14:23:45Z", "event": "game_ended", "outcome": "goal_reached", "goal_message": "..."}
```

This log is **replay-complete**: every event is recorded with enough information that the entire session can be reconstructed for research or evaluation purposes.

After a session ends, `session_sync.py` pushes a summary to the UARD `GameSession` model (step count, outcome, duration, player list, play-through count).

### 4.10 Debug Mode

When a game admin installs or updates a game and clicks **"Start in Debug Mode"**:
1. WSZ6-admin sends a debug-launch request to WSZ6-play's internal API.
2. WSZ6-play creates a temporary game session with the game's `min_players` number of simulated players.
3. The browser is directed to a debug view that opens **multiple iframes or browser tabs**, one per simulated player, each showing that player's game view.
4. All simulated player connections go through the same `GameConsumer` pipeline, so role-specific display bugs are immediately visible.

### 4.11 Observer Mode

An admin can join a live session from the live-sessions panel:
- Connects to `ObserverConsumer`.
- Receives all state-update messages (full state, no role filtering).
- Can choose a specific player's perspective via a UI dropdown (applies the same role-specific `text_view_for_role` / web equivalent).
- Cannot apply operators unless they are given an active role (advanced option for general admins only).

---

## 5. Admin–Play Interface

To allow WSZ6-admin and WSZ6-play to be updated independently, all inter-component communication uses a **versioned internal API** (not direct function calls or shared model imports).

### 5.1 Internal API Design

The internal API is a lightweight **Django REST Framework** (DRF) endpoint set accessible only on localhost (or via a private network interface). Both components are in the same Django project but are kept in separate Django apps that do not import each other's models directly.

| Endpoint | Method | Called by | Purpose |
|----------|--------|-----------|---------|
| `/internal/v1/games/installed/` | POST | admin → play | Notify play that a new game is available |
| `/internal/v1/games/<slug>/retired/` | POST | admin → play | Notify play to stop accepting sessions for a game |
| `/internal/v1/sessions/<key>/summary/` | POST | play → admin | Send session summary when a session ends |
| `/internal/v1/sessions/<key>/status/` | PATCH | play → admin | Update session status (paused, in_progress, etc.) |
| `/internal/v1/sessions/active/` | GET | admin → play | Get list of currently active session keys |
| `/internal/v1/sessions/<key>/observe/` | POST | admin → play | Request observer token for a session |
| `/internal/v1/launch/` | POST | admin → play | Launch a new session (includes game slug, owner ID) |
| `/internal/v1/launch/debug/` | POST | admin → play | Launch debug session |

All requests include a shared secret token (`INTERNAL_API_KEY` in settings) for authentication. API contract changes are versioned in the URL (currently `/v1/`). When WSZ6-play is updated to `/v2/` endpoints, WSZ6-admin continues to call `/v1/` until admin is updated; a compatibility shim on the play side bridges them during the transition.

### 5.2 Channel Layer Signals (Real-time)

For live session status updates (new session started, session ended, player count changes), WSZ6-play publishes events to a **dedicated Redis channel group** (`admin-monitor`). The admin dashboard subscribes via a Django Channels WebSocket consumer to receive these in real time for the live sessions panel.

### 5.3 Shared Data Contract (Session Summary)

The session summary JSON schema is the shared contract between the two components. It is defined in a standalone file `wsz6_shared/session_summary_schema.py` that is importable by both components without creating circular dependencies.

```python
# wsz6_shared/session_summary_schema.py
SESSION_SUMMARY_V1 = {
    "version": "1",
    "session_key": "<uuid>",
    "game_slug": "<str>",
    "owner_id": "<int>",
    "started_at": "<ISO8601>",
    "ended_at": "<ISO8601>",
    "status": "<completed|interrupted|paused>",
    "playthrough_count": "<int>",
    "completed_playthroughs": "<int>",
    "interrupted_playthroughs": "<int>",
    "players": [{"name": "<str>", "role": "<str>", "is_guest": "<bool>"}],
    "gdm_path": "<str>",
}
```

---

## 6. Databases

### 6.1 Database 1: UARD (User Accounts Relational Database)

**Engine:** PostgreSQL
**Managed by:** WSZ6-admin (Django ORM)

Key tables:
- `accounts_wszuser` — user accounts
- `games_catalog_game` — game catalogue entries
- `sessions_log_gamesession` — session summaries (one row per session)
- Standard Django tables: auth, contenttypes, sessions, migrations

The UARD contains **no detailed game-play data**, only the lightweight session summary row and a pointer (`gdm_path`) into the GDM file system.

### 6.2 Database 2: GDM (Game Data Management)

**Engine:** PostgreSQL (for indexed metadata) + file system (for logs and artifacts)
**Managed by:** WSZ6-play

PostgreSQL tables in GDM database:
- `playthrough` — one row per game play-through (links to GDM file paths)
- `checkpoint` — one row per checkpoint, with JSON snapshot reference
- `artifact` — metadata for documents/artifacts created during games

File system layout described in Section 4.9.

The GDM database is accessed **exclusively** by WSZ6-play. WSZ6-admin accesses GDM data only through the internal API and/or through a read-only research role that queries the GDM database directly (for research admin workflows).

---

## 7. Games Repository

```
GAMES_REPO_ROOT/           (e.g., /srv/wsz6/games/)
├── tic-tac-toe/
│   ├── Tic_Tac_Toe_SZ6.py   ← main PFF
│   └── metadata.json        ← auto-generated at install time
├── missionaries-and-cannibals/
│   ├── Missionaries_SZ6.py
│   └── metadata.json
├── fox-and-hounds/
│   ├── FoxAndHounds.py
│   ├── fox.png
│   └── hound.png
└── trivial-writing-game/
    ├── Trivial_Writing_Game_SZ6.py
    └── prompts/
        └── socrates_role_prompt.txt
```

The games repository is **read-only** during play (never written to at run time). Updates come only via the game-installation workflow (zip upload and extraction, administered by a game admin).

The repository location is configured in `settings.py` via `GAMES_REPO_ROOT`. Symbolic links or a mount point can redirect this to network storage if needed.

---

## 8. Key Workflows

### 8.1 Game Setup Workflow

```
Game Admin logs in
  → Navigate to Games → Install New Game
  → Fill metadata form + upload zip
  → Server: validate zip, extract to games repo
  → Server: sandbox-import PFF, extract SZ_Metadata, validate
  → Write Game record to UARD
  → POST /internal/v1/games/installed/ to WSZ6-play
  → WSZ6-play: cache formulation path, mark game as available
  → Admin sees success page with option "Start in Debug Mode"
```

### 8.2 Game Play Workflow

```
Session Owner logs in
  → Sees list of accessible games
  → Selects game → clicks "New Session"
  → POST /internal/v1/launch/ → WSZ6-play creates GameSession record + GDM folder
  → Owner is redirected to Lobby page (WebSocket)
  → Owner shares invite URL (system generates token-based URL)
  → Guests click URL → arrive at lobby → enter name → are shown available roles
  → Owner assigns roles to players / bots
  → Owner clicks "Start Game" (if min_players met)
  → WSZ6-play loads formulation, initializes state, creates play-through log
  → GameConsumer broadcasts initial state to all players
  → Players take turns applying operators
  → On goal: congratulations message, option to start new play-through or end session
  → On session end: GDM log is finalized; summary is POSTed to UARD
```

### 8.3 Game Interruption and Continuation

```
Owner clicks "Pause" (or disconnect timeout fires)
  → GameRunner saves checkpoint (JSON state + role assignments to GDM)
  → GameConsumer sends game_paused to all clients
  → Session status → 'paused' (PATCH /internal/v1/sessions/<key>/status/)
  → Later: Owner logs back in → clicks "Continue Session"
  → System looks up prior session; finds paused play-through
  → Owner can re-invite same or different players
  → Clicking "Resume" loads checkpoint state; play continues
```

### 8.4 Debug Mode Workflow

```
Game Admin installs game
  → Clicks "Start in Debug Mode"
  → POST /internal/v1/launch/debug/ with game slug + simulated player count
  → WSZ6-play creates a temporary debug session
  → WSZ6-play generates N player tokens (N = game's min_players)
  → Browser receives N URLs and opens them as separate tabs/iframes
  → Each tab shows one player's view; admin can test all role-specific displays
  → Debug session is flagged; its logs are stored separately and auto-deleted after 7 days
```

### 8.5 Admin Joins Workflow

```
General Admin views Live Sessions panel
  → Sees list of ongoing sessions (fed by WS subscription to admin-monitor group)
  → Clicks "Join as Observer"
  → POST /internal/v1/sessions/<key>/observe/ → receives observer token
  → Browser redirects to ObserverConsumer URL
  → Admin sees full game state; can select a player perspective from dropdown
  → Optionally: Admin clicks "Take Role" (if game allows it and admin has permission)
    → Existing player/bot is removed from role; admin takes it over
```

### 8.6 Research Data Access Workflow

```
Research Admin logs in
  → Sees research dashboard: list of all games, all sessions
  → Can filter by date range, game, user
  → Click into a session: view session summary (from UARD) and
    link to detailed log viewer (from GDM)
  → Log viewer renders log.jsonl as a timeline / step-by-step replay
  → "Export" button downloads the raw log.jsonl for offline analysis
  → Future: integration with analytics dashboards (e.g., Jupyter, Grafana)
```

---

## 9. Scaling Strategy

### 9.1 Near-term Target (10–50 simultaneous sessions)

The initial deployment targets **10 simultaneous sessions** with a stretch goal of **50**. This is achievable with:

- A single application server running Daphne (ASGI) with multiple worker processes.
- Redis as the Channel Layer backend.
- PostgreSQL for both databases.
- The games repository on local disk.

Estimated resources for 50 simultaneous sessions:
- ~50–200 active WebSocket connections (1–4 players per session).
- Memory: each GameRunner holds a game state in RAM. Most SOLUZION6 states are small Python objects; 50 sessions will use well under 1 GB.
- CPU: game logic is Python-bound but async I/O means waiting for player input most of the time. A 4-core server handles this comfortably.

### 9.2 Scaling Steps (if demand grows)

When load exceeds single-server capacity, apply the following steps in order:

1. **Horizontal scaling of WSZ6-play consumers:** Add more Daphne workers behind a load balancer (nginx). Because the Channel Layer (Redis) is shared, all workers can handle any session. This alone can multiply capacity by the number of cores/workers.

2. **Separate the databases:** Move UARD and GDM to dedicated PostgreSQL instances. Add read replicas for UARD (research queries are read-heavy).

3. **Redis clustering:** For very high WebSocket counts, switch from a single Redis instance to Redis Cluster.

4. **Games repository on shared network storage:** If multiple server nodes need access to the games repository, mount it as NFS or use object storage (S3-compatible) with a thin local cache layer.

5. **WSZ6-admin scaling:** Admin traffic is low; it can run as a lightweight process on the same or a separate host. Stateless Django views scale horizontally with a standard reverse proxy.

6. **Containerization:** Package WSZ6-admin and WSZ6-play as Docker containers for reproducible deployment and easy horizontal scaling via Kubernetes or Docker Swarm.

---

## 10. Development Phases and Milestones

### Phase 0: Infrastructure Setup (1–2 weeks)

- [ ] Set up Django project with ASGI configuration (Daphne / Uvicorn).
- [ ] Configure PostgreSQL (two databases), Redis, Celery.
- [ ] Set up Django Channels with Redis Channel Layer.
- [ ] Establish project layout: `wsz6_admin/`, `wsz6_play/`, `wsz6_shared/`.
- [ ] Create development and production settings files.
- [ ] Verify end-to-end WebSocket echo test.
- [ ] Set up version control (Git), CI pipeline.

### Phase 1: WSZ6-admin Core (3–4 weeks)

- [ ] Implement `WSZUser` model with all user types and permissions.
- [ ] Standard Django auth: login, logout, password reset (email-based via Celery).
- [ ] Admin dashboard: user list + search, user detail with editable fields.
- [ ] `Game` model and game catalogue view (list + search).
- [ ] Game installation: zip upload, validation, extraction to games repository.
- [ ] PFF sandbox validation on install (subprocess import, metadata extraction).
- [ ] `GameSession` model (summary only; no game data).
- [ ] Internal API skeleton (`/internal/v1/` endpoints) with shared-secret auth.

**Milestone 1:** Admin can log in, install a game, and see it in the catalogue.

### Phase 2: WSZ6-play Core (4–6 weeks)

- [ ] PFF loader (`pff_loader.py`) with per-session unique module names.
- [ ] `GameRunner` class (async, state stack, operator application, undo).
- [ ] State serializer with `to_dict`/`from_dict` protocol.
- [ ] `LobbyConsumer`: session creation, player join, role assignment, game start.
- [ ] `GameConsumer`: receive operator commands, apply via GameRunner, broadcast state.
- [ ] Role cueing logic (who moves next, role-filtered operator views).
- [ ] Transition messages (`jit_transition` support).
- [ ] Goal detection and end-of-game flow.
- [ ] GDM log writer (JSONL append-only log).
- [ ] Session summary sync to UARD via internal API.
- [ ] Verify all six sample formulations (Tic-Tac-Toe, Missionaries, Fox-and-Hounds, Guess-My-Age, Rock-Paper-Scissors, Trivial-Writing-Game) can be loaded and played through.

**Milestone 2:** Full end-to-end play session: owner creates session, 2 players join, play Tic-Tac-Toe to completion, log is written, summary appears in admin.

### Phase 3: Game Persistence and Bots (2–3 weeks)

- [ ] Checkpoint save and load (GDM file + GDM DB record).
- [ ] Pause/resume flow with re-invitation.
- [ ] Continuation session linking (parent_session FK).
- [ ] Bot player (random and first-option modes).
- [ ] Bot assignment in lobby UI.

**Milestone 3:** Owner can pause a game mid-session, log out, log back in, resume from checkpoint with a bot filling a role.

### Phase 4: Debug Mode and Observer Mode (2 weeks)

- [ ] Debug-mode launch endpoint and multi-tab debug view.
- [ ] `ObserverConsumer` with full-state broadcast.
- [ ] Observer perspective switching (view as player N).
- [ ] Admin-joins live sessions panel (Channel Layer subscription).

**Milestone 4:** Game admin installs a new game, launches debug mode, sees all role views simultaneously.

### Phase 5: Research and Analytics (2 weeks)

- [ ] Research admin dashboard: session list with filters.
- [ ] Log viewer: renders `log.jsonl` as paginated step-by-step replay.
- [ ] Export endpoint: download raw JSONL.
- [ ] GDM read-only access for research admin role.
- [ ] Session timeline admin view (color-coded by game popularity).

**Milestone 5:** Research admin can find a specific session, replay it step by step, and export the log.

### Phase 6: Open-World Features (2–3 weeks)

- [ ] File-edit operator support in WebSocket mode (open external editor or embedded web editor).
- [ ] Per-session artifact storage in GDM.
- [ ] LLM agent role support: proxy API calls to configured LLM endpoint from within a game consumer.
- [ ] Session context management for open-world documents.

**Milestone 6:** Trivial Writing Game and other open-world formulations run successfully in the web engine.

### Phase 7: Production Hardening (2–3 weeks)

- [ ] HTTPS/WSS via nginx reverse proxy and TLS certificate.
- [ ] Rate limiting on WebSocket connections and API endpoints.
- [ ] Input validation on all PFF zip uploads (security audit).
- [ ] Subprocess sandboxing for PFF code execution (separate process with restricted permissions).
- [ ] Automated tests: unit tests for game engine core, integration tests for lobby + game flow.
- [ ] Load test: simulate 50 concurrent sessions.
- [ ] Monitoring: Django logging, Sentry for errors, Redis and PostgreSQL metrics.
- [ ] Deployment documentation and CLAUDE.md for the project.

**Milestone 7:** System passes load test of 50 simultaneous sessions and passes security review.

---

## 11. Technology Stack Summary

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Web framework | Django 5.x | Mature, well-supported; built-in auth and admin |
| Real-time / WS | Django Channels 4.x + Daphne | Official async/WebSocket support for Django |
| Channel Layer | Redis (channels-redis) | Low-latency pub/sub; same Redis for Celery |
| Task queue | Celery + Redis | Async email sending, background jobs |
| Databases | PostgreSQL 16 | UARD and GDM; JSON field support; strong reliability |
| REST API | Django REST Framework | Internal API between admin and play |
| Game logic | Python 3.11+ | Same language as PFFs; no translation layer |
| Reverse proxy | nginx | TLS termination, static file serving, WS upgrade |
| Container | Docker + Docker Compose | Reproducible dev and production environments |
| CI | GitHub Actions (or GitLab CI) | Automated test runs on push |
| Monitoring | Sentry + structlog | Error tracking and structured logging |
| Frontend | Django templates + HTMX + vanilla JS | Low JS complexity; HTMX for live updates in admin views |
| WS client | Native browser WebSocket API | No framework dependency for game client |

---

## 12. Open Questions and Risks

### 12.1 PFF Code Execution Security

**Risk:** Loading and executing arbitrary Python code from uploaded PFFs could allow malicious code to run on the server.

**Mitigation options (in increasing security):**
1. **(Near-term)** Run PFF loading in a subprocess with restricted OS-level permissions (e.g., a separate Unix user with no write access to the application directory). Use Python's `resource` module to limit CPU/memory.
2. **(Medium-term)** Use a container or `seccomp` profile to sandbox PFF execution.
3. **(Long-term)** Implement a safe Python subset evaluator or use PyPy sandboxing.

For an initial deployment where only trusted admins install games, option 1 is sufficient.

### 12.2 State Serialization Compatibility

**Risk:** PFF state classes may use objects that are not trivially JSON-serializable (e.g., custom data structures, lambdas stored in state).

**Mitigation:** Require PFFs to implement `to_dict()` / `from_dict()` for checkpoint support. Provide detailed documentation and a validation tool. Warn at game-install time if the state class does not implement these methods.

### 12.3 Role Confusion Across Sessions (SZ5 Bug Prevention)

The SZ5 web engine had a bug where role assignments from one session leaked into another. In WSZ6-play, each play-through gets its own **freshly instantiated** formulation object and role-assignment object (never shared between sessions). Each session runs in its own Channel group. Session keys and role tokens are UUID-based and unique.

### 12.4 Reconnection and Disconnect Handling

**Risk:** A player's browser disconnects mid-game (network drop, page refresh).

**Mitigation:**
- On disconnect, the GameConsumer removes the player from the group but does NOT end the game.
- A configurable reconnect window (default: 3 minutes) allows the player to rejoin using the same role token.
- If the window expires without reconnect, the game is automatically paused and checkpointed, and the session owner is notified.

### 12.5 Parallel Input Games

The SOLUZION6 spec (`SZ6-spec-5-session-timing.txt`) mentions parallel session behavior, where multiple players submit moves simultaneously. The current textual engine is turn-based. For WSZ6-play:
- States with `state.parallel = True` indicate a parallel input phase.
- The GameConsumer collects one move per role before advancing the state.
- A timeout applies: if a role does not respond within the configured time, the bot (if assigned) or a default action is used.

### 12.6 LLM Agent Integration

Games like the Socratic Method game or LLM-based open-world games require calling an external LLM API during play. This is handled by:
- A dedicated `llm_client.py` module in WSZ6-play with configurable API keys and endpoints.
- LLM calls are made asynchronously within the game consumer using `httpx.AsyncClient`.
- Timeout and retry logic prevents a slow LLM response from blocking other sessions.

### 12.7 Email Delivery

Player invitations and password resets require email. The initial deployment can use a simple SMTP configuration (e.g., UW's mail relay or Gmail SMTP for development). For production, consider a transactional email service (SendGrid, Mailgun) for reliability and deliverability tracking.

---

*This development plan will be updated as implementation proceeds and new requirements emerge.*
