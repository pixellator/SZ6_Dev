# WSZ6 Portal — User Manual

**Version:** 1.0
**Date:** 2026-02-21
**System:** WSZ6-portal (Claudes-plan-2)

---

## Table of Contents

1. [What the Portal Is — and Its Relation to SOLUZION6](#1-what-the-portal-is)
2. [Writing Games for the Portal](#2-writing-games-for-the-portal)
3. [Installing and Running Games](#3-installing-and-running-games)
4. [The Player Interface](#4-the-player-interface)
5. [The Researcher Panel](#5-the-researcher-panel)
6. [System Installation Guide](#6-system-installation-guide)
7. [Administering the System](#7-administering-the-system)
8. [Architecture](#8-architecture)
9. [Design Decisions](#9-design-decisions)
10. [Pending Development and Future Work](#10-pending-development-and-future-work)

---

## 1. What the Portal Is

### 1.1 Overview

**WSZ6-portal** is a web-based platform that hosts multi-player, real-time games
whose logic is defined entirely in Python using the **SOLUZION6** framework.
The portal lets session owners invite players to structured problem-solving
sessions from any web browser, records every move in a tamper-evident log, and
gives researchers a dedicated panel for browsing, annotating, and exporting
those logs.

The portal equation is:

```
WSZ6-portal = WSZ6-admin  +  WSZ6-play
```

**WSZ6-admin** handles user accounts, game installation, and the administrative
dashboard. **WSZ6-play** is the real-time game engine: it loads Python
formulation files at runtime, runs game logic inside WebSocket consumers, and
writes detailed session logs to a separate data store.

### 1.2 The SOLUZION6 Framework

SOLUZION6 (version 6 of the SOLUZION system developed at the University of
Washington) is a Python framework for representing **problems and games** as
formal state-space search instances. A game (or problem) is described by a
**Problem Formulation File (PFF)** — an ordinary Python source file that
subclasses SOLUZION6 base classes:

| Class | Role |
|-------|------|
| `SZ_Formulation` | Top-level object; holds metadata, operators, roles, and a reference to the vis module |
| `SZ_State` | A snapshot of the game world at one point in time |
| `SZ_Operator_Set` | The set of all legal moves |
| `SZ_Operator` | One legal move: a name, a precondition function, and a transition function |
| `SZ_Roles_Spec` | Defines the player roles and how many are needed |
| `SZ_Metadata` | Name, description, player counts, version information |

A well-formed PFF can be used in multiple contexts without modification:

- The **Textual_SZ6 engine** — a terminal-based single-user player.
- The **WSZ6-portal engine** — a web-based multi-user player.
- Future engines (e.g. a Jupyter notebook player, a simulation harness).

This portability is intentional: the PFF describes *what* the game is, not *how*
it is displayed or *how* players connect. WSZ6-portal adds web rendering,
real-time WebSocket communication, role-based access, and research logging on
top of the formulation without requiring the PFF author to think about any of
those concerns.

### 1.3 Sessions and Play-Throughs

WSZ6-portal distinguishes two concepts that are often confused:

**Session** — A named encounter created by a session owner for a specific game.
A session has a permanent invite URL that can be re-used across many play-
throughs. Sessions can be paused and resumed.

**Play-through** — One continuous run of the game from initial state to a goal
(or interruption). A session may contain many play-throughs (e.g. a rematch
after a completed game uses the same session but starts a new play-through).

Every play-through has its own append-only `log.jsonl` file; the session is
the organisational unit visible to session owners and researchers.

### 1.4 User Roles in the Portal

The portal defines seven account types:

| Type | Description |
|------|-------------|
| `ADMIN_GENERAL` | Full access to everything |
| `ADMIN_ACCOUNTS` | Can create and manage user accounts |
| `ADMIN_GAMES` | Can install, update, and retire games |
| `ADMIN_RESEARCH` | Can access the Researcher Panel |
| `SESSION_OWNER` | Can create game sessions and invite players |
| `GAME_OWNER` | Can install their own games and create sessions for them |
| `PLAYER` | Can join sessions to which they are invited |

Guest players (no portal account) can also join sessions using the invite URL;
they choose a display name at the lobby. Admins choose which account types are
privileged enough to see games in `dev`, `beta`, or `published` status.

---

## 2. Writing Games for the Portal

### 2.1 Minimum PFF Structure

A working game for WSZ6-portal requires two files:

| File | Naming convention | Purpose |
|------|-------------------|---------|
| Problem Formulation File | `GameName_SZ6.py` | Game logic: state, operators, roles |
| Visualization file (optional) | `GameName_WSZ6_VIS.py` | Web rendering of each state |

The portal can run games without a vis file; it falls back to displaying the
state's `__str__` representation as monospace text.

**Minimum PFF skeleton:**

```python
"""MyGame_SZ6.py"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from soluzion6_02 import (
    SZ_Formulation, SZ_State, SZ_Operator_Set, SZ_Operator,
    SZ_Roles_Spec, SZ_Role, SZ_Metadata, SZ_Common_Data,
    SZ_Problem_Instance_Data,
)

# ── Metadata ───────────────────────────────────────────────────────────────

class MyGame_Metadata(SZ_Metadata):
    def __init__(self):
        super().__init__()
        self.name        = 'My Game'
        self.description = 'A brief description.'
        self.min_players = 1
        self.max_players = 2

# ── State ──────────────────────────────────────────────────────────────────

class MyGame_State(SZ_State):
    def __init__(self, old=None):
        if old is None:
            self.score            = 0
            self.current_role_num = 0   # required: which role moves next
        else:
            self.score            = old.score
            self.current_role_num = old.current_role_num

    def is_goal(self):
        return self.score >= 10

    def goal_message(self):
        return f'Goal reached with score {self.score}!'

    def __str__(self):
        return f'Score: {self.score}  |  Role to move: {self.current_role_num}'

# ── Operators ──────────────────────────────────────────────────────────────

def _score_point(state):
    ns = MyGame_State(old=state)
    ns.score += 1
    ns.current_role_num = 1 - state.current_role_num  # alternate turns
    ns.jit_transition = f'Player {state.current_role_num} scored!'
    return ns

class MyGame_Operator_Set(SZ_Operator_Set):
    def __init__(self):
        self.operators = [
            SZ_Operator(
                name='Score a point',
                precond_func=lambda s: not s.is_goal(),
                state_xition_func=_score_point,
                role=None,  # role=None means any role can use this operator
            ),
        ]

# ── Roles ──────────────────────────────────────────────────────────────────

class MyGame_Roles_Spec(SZ_Roles_Spec):
    def __init__(self):
        self.roles = [
            SZ_Role(name='Player A', description='Goes first'),
            SZ_Role(name='Player B', description='Goes second'),
        ]

# ── Formulation ────────────────────────────────────────────────────────────

class MyGame_Formulation(SZ_Formulation):
    def __init__(self):
        self.metadata    = MyGame_Metadata()
        self.operators   = MyGame_Operator_Set()
        self.roles_spec  = MyGame_Roles_Spec()
        self.common_data = SZ_Common_Data()

    def initialize_problem(self, config={}):
        initial = MyGame_State()
        self.instance_data = SZ_Problem_Instance_Data(
            d={'initial_state': initial}
        )
        return initial

MY_GAME = MyGame_Formulation()   # module-level entry point (required)
```

**Critical requirements:**
- The state must have a `current_role_num` attribute (integer) that the engine
  reads to determine whose turn it is.
- The formulation module must expose a module-level `SZ_Formulation` instance
  (any name). The PFF loader discovers it by duck-typing.
- `jit_transition` is an optional attribute you can set on a returned state;
  if present, its value is broadcast to all players as a transition message.

### 2.2 Multi-Role Games

For turn-based games, set `state.current_role_num` in each transition to the
role that moves next. The portal filters the operator list so each player only
sees operators whose `role` attribute matches their assigned role number (or
`None` for universal operators).

For parallel games (all players move simultaneously), set
`state.is_parallel = True` on the state. The portal collects one operator
application per active role before advancing.

### 2.3 Parameterized Operators

Operators can require numerical or text input from players. Declare parameters
on the operator using a list of dicts:

```python
SZ_Operator(
    name='Set value',
    precond_func=lambda s: True,
    state_xition_func=lambda s, args: _set_value(s, args[0]),
    params=[
        {'name': 'New value', 'type': 'int', 'min': 0, 'max': 100},
    ],
)
```

Supported parameter types: `'int'`, `'float'`, `'str'`, `'file_edit'`.

The `file_edit` type opens a full-page text editor modal in the browser;
the typed text is passed as `args[0]` to the transition function. This is
used by open-world games that involve writing essays, stories, or other
longer-form text.

### 2.4 Writing a Visualization Module

A vis module is a Python file (`*_WSZ6_VIS.py`) that contains a single
function:

```python
def render_state(state, base_url='') -> str:
    """Return an HTML string representing the current state."""
    ...
```

The portal calls `render_state` after every state transition and injects the
returned HTML into the game page. If the function raises an exception or is
absent, the portal falls back to `str(state)`.

The `base_url` parameter is injected by the portal and contains the URL prefix
for serving game assets (images, etc.) via the `/play/game-asset/<slug>/`
endpoint. Use it as:

```python
img_url = f'{base_url}/images/board.png'
```

#### Tier 1 — SVG / HTML interaction (zero extra code)

Any element inside the returned HTML can be made interactive by adding
`data-*` attributes. The portal's `game.html` automatically handles them:

| Attribute | Effect on left-click |
|-----------|---------------------|
| `data-op-index="N"` | Applies operator N |
| `data-op-args='[...]'` | JSON array passed as args (optional, with `data-op-index`) |
| `data-info="text"` | Shows an info popup near the cursor |
| `data-context='[...]'` | Right-click context menu; items: `{label, op_index?, op_args?, info?}` |

Elements with these attributes get a gold highlight on hover and a pointer
cursor automatically.

**Example — clickable SVG cells:**

```python
def render_state(state, base_url=''):
    cells = []
    for i, cell in enumerate(state.board):
        color = '#fff' if cell is None else ('#faa' if cell == 0 else '#aaf')
        x, y = (i % 3) * 60 + 10, (i // 3) * 60 + 10
        attrs = f'data-op-index="{i}"' if cell is None else ''
        cells.append(
            f'<rect x="{x}" y="{y}" width="58" height="58" '
            f'fill="{color}" stroke="#333" stroke-width="2" {attrs}/>'
        )
    return f'<svg width="200" height="200">{"".join(cells)}</svg>'
```

#### Tier 2 — Canvas region hit-testing (for raster images)

When the scene is a photograph or any image where click targets are geometric
regions rather than DOM elements, embed a JSON region manifest in the returned
HTML:

```python
import json

def render_state(state, base_url=''):
    img_url = f'{base_url}/images/room.jpg'
    scene_html = (
        '<div id="wsz6-scene" style="display:inline-block; line-height:0;">'
        f'<img src="{img_url}" width="800" height="600" style="display:block;">'
        '</div>'
    )
    manifest = {
        "container_id":  "wsz6-scene",
        "scene_width":   800,   # natural image width (not CSS display width)
        "scene_height":  600,
        "regions": [
            {"op_index": 0, "shape": "rect",
             "x": 100, "y": 200, "w": 80, "h": 60,
             "hover_label": "door"},
            {"op_index": 1, "shape": "circle",
             "cx": 400, "cy": 300, "r": 40,
             "hover_label": "lamp"},
        ]
    }
    return scene_html + (
        '<script type="application/json" id="wsz6-regions">'
        + json.dumps(manifest, separators=(',', ':'))
        + '</script>'
    )
```

The portal overlays a transparent canvas on the scene and performs point-in-
region hit testing on every click. Shapes supported: `"rect"`, `"circle"`,
`"polygon"`. Regions are tested in array order; list smaller/specific regions
before larger containing regions.

To forward the exact click coordinates to the server (e.g. for a pixel-probe
game), add `"send_click_coords": true` to the region and declare
`params=[{'name':'x','type':'int',...}, {'name':'y','type':'int',...}]` on
the operator.

### 2.5 State Serialization for Checkpoints

For pause/resume to work, the game state must be serializable. The portal
attempts to serialize states using `__dict__` by default, which works for
states containing only basic Python types (int, float, str, list, dict).

If your state contains custom objects, implement:

```python
class MyState(SZ_State):
    def to_dict(self):
        return {'score': self.score, 'current_role_num': self.current_role_num}

    @classmethod
    def from_dict(cls, d):
        s = cls.__new__(cls)
        s.score            = d['score']
        s.current_role_num = d['current_role_num']
        return s
```

### 2.6 LLM-Assisted Games

Games that call external language models use Python's `os.environ` to read API
keys at runtime. The portal injects `GEMINI_API_KEY`, `OPENAI_API_KEY`, and
other keys configured in `.env` into the process environment; no PFF-specific
setup is required. Call the LLM API synchronously inside the transition
function (the portal's async layer wraps it in `asyncio.to_thread`).

---

## 3. Installing and Running Games

### 3.1 Game Registration via `install_test_game`

During development, games are registered by adding an entry to the `GAME_DEFS`
list in:

```
wsz6_portal/wsz6_admin/games_catalog/management/commands/install_test_game.py
```

Each entry is a dict:

```python
{
    'slug':        'my-game',          # URL-safe identifier (unique)
    'name':        'My Game',          # display name
    'pff_file':    'MyGame_SZ6.py',    # filename of the PFF
    'vis_file':    'MyGame_WSZ6_VIS.py',  # filename of the vis module (optional)
    'source_dir':  'Vis-Features-Dev/game_sources',  # relative to SZ6_Dev/
    'brief_desc':  'A brief description.',
    'min_players': 1,
    'max_players': 2,
    'status':      'published',        # 'dev', 'beta', or 'published'
    # 'images_dir': 'MyGame_images',   # subfolder to copy alongside the PFF
},
```

After adding the entry, run:

```bash
source .venv/bin/activate
export DJANGO_SETTINGS_MODULE=wsz6_portal.settings.development
python manage.py install_test_game
```

This copies the PFF and vis file (and any images) into `games_repo/<slug>/`
and creates or updates the `Game` record in the database.

### 3.2 Game Lifecycle (Status)

Each installed game has a status:

| Status | Meaning |
|--------|---------|
| `dev` | Only `ADMIN_GENERAL` and `ADMIN_GAMES` users can start sessions |
| `beta` | Users with `game_access_level` of `beta`, `all`, or `custom` (with this game allowed) can play |
| `published` | All users can play |
| `deprecated` | No new sessions can be started; existing sessions continue |

Admins promote games through the Games Catalog page in the dashboard.

### 3.3 Serving Game Assets (Images)

Images and other static files in the game directory are served through:

```
/play/game-asset/<slug>/<optional-subdirectory>/<filename>
```

In the vis module, build asset URLs using the injected `base_url` parameter:

```python
def render_state(state, base_url=''):
    img_url = f'{base_url}/images/board.png'
    ...
```

`base_url` is set to `/play/game-asset/<slug>` by the portal.

### 3.4 Starting a Session

A user with `SESSION_OWNER` or higher privileges can start a session:

1. Navigate to **Games** in the portal navigation.
2. Click the name of the game to open the Game Detail page.
3. Click **Start a Session**.
4. The portal creates a session record and redirects to the Lobby.
5. The Lobby URL (shown at the top of the page) is the invite link to share
   with other players.

### 3.5 The Lobby

The Lobby is a real-time page (WebSocket-based) that shows the game's roles
and the connected players. The session owner sees the full role-assignment UI;
other players see a read-only view while they wait.

**Lobby workflow:**

1. Each player opens the invite URL and enters their display name, then clicks
   **Set name**.
2. Connected players appear in the **Connected Players** panel on the right.
3. The session owner selects a player from the panel (the player's name becomes
   highlighted) then clicks **Assign here** next to the desired role.
4. For unfilled roles, the owner can click **+ Bot** to assign a computer
   player (random or first-option strategy).
5. Once all required roles are filled (indicated by the "Min. players required"
   count), the owner clicks **Start Game**.
6. All browsers redirect automatically to the Game page.

For a **paused** session, the Lobby shows a yellow banner and the **Resume
Session** button in place of **Start Game**.

---

## 4. The Player Interface

### 4.1 Layout

The Game page uses a two-column layout:

- **Left column** — Game state display (visualization or text fallback) plus
  the transition message bar, turn banner, and move history.
- **Right column** — Operator buttons, parameter input form, and session
  controls (Undo, Help, Pause, New Session with Same Players).

### 4.2 State Display

When the game provides a visualization module, the state is shown as rendered
HTML (SVG, images, or arbitrary HTML). When no vis module is present (or it
fails to render), the portal displays the state as monospace text using
`str(state)`.

The **Full Screen** button (⛶) is shown when a visualization is active. It
moves the vis area to a full-screen dark overlay. Moving the pointer to the
bottom of the overlay reveals a slide-up tray with the same operator buttons.
Press **Esc** or click the × button to exit full screen.

The **Show Previous** button (⇔) lets a player compare the current state with
the state from the previous step. A banner reading PREVIOUS STATE appears over
the visualization when looking at a prior state. The button becomes **Show
Current** (↩); clicking again restores the current state.

### 4.3 Turn Indicator

A banner below the state display shows:
- **"Your turn!"** (green) — when it is this player's turn to move.
- **"Waiting for another player…"** (amber) — during other roles' turns.
- In **parallel mode** games, the banner shows "Make your choice!" or "Choice
  submitted — waiting for other player…" as appropriate.

### 4.4 Operator Buttons

The **Operators** panel lists the moves available for the current game state.
Applicable operators (those whose precondition is satisfied and whose role
matches the current player) appear in green with an active cursor. Inapplicable
operators are greyed out.

Operators that require typed input are marked with a ▸ icon. Clicking them
opens an inline form with one field per parameter. Operators of type
`file_edit` are marked with a ✎ icon; clicking opens a full-page text editor
modal with a word count and a Ctrl+Enter shortcut to save.

### 4.5 Transition History

Every transition message (emitted by setting `jit_transition` on the returned
state) is stored in a collapsible **Transition History** panel. The most recent
message is always shown in a purple bar above the turn indicator. Clicking any
historical item re-displays it in that bar (with a visual recall indicator);
the bar returns to live updates when the next move is made.

### 4.6 Interactive Visualization

When the game vis module produces clickable elements (Tier 1 or Tier 2), the
player interacts directly with the visual scene:

- **Hover** — Eligible elements glow with a gold highlight; a small tooltip
  appears for Tier 2 canvas regions.
- **Left-click** — Applies the operator linked to the element, or shows an info
  popup if no operator is attached.
- **Right-click** — Opens a context menu when `data-context` or a Tier 2
  `context` array is defined on the element.

Clicking an applicable element has the same effect as clicking the corresponding
button in the Operators panel.

### 4.7 Session Controls (Owner Only)

The session owner sees two additional buttons:

- **⏸ Pause** — Saves a checkpoint and disconnects all players from the game
  page. A confirmation dialog is shown first. Players can rejoin the lobby from
  the paused-game banner link.
- **↺ New Session with Same Players** — Shown only after the goal is reached.
  Creates a new session with the same game, redirects all connected browsers to
  the new lobby.

### 4.8 Undo

The **↩ Undo** button rolls back one step. It is disabled at step 0, after the
goal is reached, and during parallel-mode phases (where undo would be ambiguous).

### 4.9 Help

The **? Help** button sends a help request to the server. The server returns
the game's help text (defined in the formulation) and displays it below the
operator panel.

---

## 5. The Researcher Panel

Access: users with account type `ADMIN_RESEARCH` or `ADMIN_GENERAL`.
URL: `/research/`

### 5.1 R1 — Session List Dashboard

The dashboard is the entry point to all session data. It shows a paginated,
filterable list of all game sessions in the system.

**Filters:**
- **Game** — dropdown of all installed games.
- **Status** — open / in_progress / paused / completed / interrupted.
- **Date from / Date to** — session start date range.
- **Owner** — partial-match search on the session owner's username.

Each row shows: game name, owner, status, start/end times, and the number of
play-throughs in that session (queried live from the GDM database).

Clicking a session opens the **Session Detail** page.

### 5.2 R2 — Session Detail

The session detail page shows:

- **Metadata** — game, owner, status, session key, start/end timestamps,
  parent session (if this is a continuation).
- **Play-throughs** — a numbered list of all play-throughs in the session
  with start time and outcome. Each links to its Log Viewer.
- **Session-level annotations** — notes that the researcher has attached at
  the session level (not tied to any specific step). An inline form lets the
  researcher add new session-level notes.
- **Export** — a button to download the entire session as a ZIP archive
  (all play-throughs, optionally including annotations).

### 5.3 R3 — Log Viewer

The log viewer shows a play-through's `log.jsonl` file as a paginated,
step-by-step replay (50 entries per page).

**Each log entry shows:**
- Timestamp and event type (e.g. `game_started`, `operator_applied`,
  `game_paused`, `goal_reached`, `artifact_created`).
- For `operator_applied` events: the operator name, step number, and the
  resulting state (formatted as indented JSON, collapsible).
- For artifact events: a link to view the artifact content.
- Per-frame annotation form — the researcher can type a note and attach it
  to this specific log frame.

Navigation between play-throughs within the same session is provided by
**← Previous Play-through** and **Next Play-through →** links at the top.

### 5.4 R4 — Artifact Viewer

Artifacts are text files created by players during open-world games (e.g.
essays written using the `file_edit` operator). The artifact viewer displays
the content of one artifact file, with version navigation if the artifact was
saved multiple times.

URL pattern: `/research/<session_key>/<playthrough_id>/artifact/<name>/`

Query parameters:
- `version=N` — view a specific saved version.
- `format=json` — return `{"name", "content", "version", "path"}` as JSON
  (for AJAX loading from the log viewer).

### 5.5 R5 — Export

Three export endpoints are available:

| Button | What is downloaded |
|--------|-------------------|
| **Download JSONL** | The raw `log.jsonl` for one play-through |
| **Download JSONL + Annotations** | ZIP: `log.jsonl` + `annotations.json` |
| **Download Play-through ZIP** | ZIP: `log.jsonl` + `artifacts/` + `checkpoints/` (+ optional `annotations.json`) |
| **Download Session ZIP** | ZIP: all play-throughs in one archive with `session_meta.json` |

The session ZIP has this layout:

```
session_meta.json
pt1/
    log.jsonl
    artifacts/
    checkpoints/
    annotations.json   (if requested)
pt2/
    ...
session_annotations.json  (if requested)
```

### 5.6 R6 — Researcher Annotations

Annotations are private to each researcher (one researcher cannot see another's
notes). They can be created at three levels:

| Level | How to create | When to use |
|-------|---------------|-------------|
| Session | Form on Session Detail page | General notes about the session as a whole |
| Play-through | Form on Log Viewer (top of page) | Notes about one specific play-through |
| Frame | Form on each log entry in Log Viewer | Notes about a specific move or event |

All of a researcher's annotations (across all sessions) can be listed at
`/research/annotations/`.

Annotations can be deleted from the detail page or the annotation list. Each
annotation download (JSONL with annotations, or ZIP) includes only the
requesting researcher's annotations.

### 5.7 R7 — Research API Token

Researchers can generate a bearer token for programmatic access to session data
(e.g. from a Jupyter notebook or analytics script). The token is shown on the
**API Token** page at `/research/api-token/`.

Click **Generate / Regenerate Token** to create or rotate the token. The token
can then be used in external requests:

```http
Authorization: Bearer <token>
```

The API itself (endpoints and schema) is planned for a future development phase;
the token infrastructure is in place.

---

## 6. System Installation Guide

### 6.1 Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11.x | `python3.11 --version` |
| git | any recent | `git --version` |

For shared/multi-user deployment only:

| Requirement | Version |
|-------------|---------|
| PostgreSQL | 14+ |
| Redis | 6+ |

### 6.2 Clone the Repository

```bash
git clone https://github.com/pixellator/SZ6_Dev.git SZ6_Dev
cd SZ6_Dev/WSP6-portal/Claudes-plan-2
```

Repository layout:

```
SZ6_Dev/
  WSP6-portal/
    Claudes-plan-2/           ← repo root
      wsz6_portal/            ← Django project
      start_server.sh         ← dev launcher
      Vis-Features-Dev/       ← web game source files
  Textual_SZ6/                ← textual game source files
  games_repo/                 ← installed game directories (auto-created)
  gdm/                        ← session log storage (auto-created)
```

### 6.3 Run the Setup Script

```bash
cd wsz6_portal
bash setup_dev.sh
```

This script:
1. Creates `.venv/` (Python 3.11 virtual environment)
2. Installs all packages from `requirements.txt`
3. Copies `.env.dev` → `.env`
4. Runs initial database migrations (creates `db_uard.sqlite3`)

### 6.4 Configure `.env`

Edit `wsz6_portal/.env`. For local development the defaults work; for any
shared deployment change these values:

```ini
# Generate a real secret key:
#   python3.11 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
DJANGO_SECRET_KEY=<paste-key-here>

# Leave true only on a private dev machine.
DJANGO_DEBUG=true

# Add your server's hostname or IP.
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,your-server.cs.washington.edu

# Override only if you want games/logs in non-default locations:
# GAMES_REPO_ROOT=/data/wsz6/games_repo
# GDM_ROOT=/data/wsz6/gdm
```

### 6.5 Create User Accounts

```bash
source .venv/bin/activate
export DJANGO_SETTINGS_MODULE=wsz6_portal.settings.development

# Creates admin, gameadm, owner1, owner2, player1, player2 (all password: pass1234)
python manage.py create_dev_users
```

For production, create individual accounts through the admin dashboard or via
the Django shell.

### 6.6 Install the Built-in Games

```bash
python manage.py install_test_game
```

This copies all game files into `games_repo/` and registers them in the
database. Re-run whenever you add or update a game source file.

Built-in games include Tic-Tac-Toe, Missionaries & Cannibals, Pixel Probe
(UW aerial image), Click-the-Word (French vocabulary), OCCLUEdo, Show Mt.
Rainier, and others.

### 6.7 Start the Server

**Dev / single-user:**

```bash
cd ..   # back to Claudes-plan-2/
bash start_server.sh
```

The script activates the venv, prints a credentials panel, starts the ASGI
server on port 8000, and opens the browser. Options:

```bash
bash start_server.sh --port 8080 --no-browser
```

### 6.8 LLM API Keys

Add API keys to `.env` before starting the server:

```ini
GEMINI_API_KEY=your-key-here
OPENAI_API_KEY=your-key-here
```

Install the relevant client libraries:

```bash
pip install google-genai   # for Gemini
```

### 6.9 Shared / Multi-User Deployment (PostgreSQL + Redis)

#### Create databases

```bash
sudo -u postgres psql <<'SQL'
CREATE USER wsz6 WITH PASSWORD 'strong-password';
CREATE DATABASE wsz6_uard OWNER wsz6;
CREATE DATABASE wsz6_gdm  OWNER wsz6;
SQL
```

#### Update `.env`

```ini
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<generated-key>
DJANGO_ALLOWED_HOSTS=your-server.cs.washington.edu

USE_POSTGRES=true
USE_REDIS=true

UARD_DB_NAME=wsz6_uard
UARD_DB_USER=wsz6
UARD_DB_PASSWORD=strong-password
UARD_DB_HOST=localhost
UARD_DB_PORT=5432

GDM_DB_NAME=wsz6_gdm
GDM_DB_USER=wsz6
GDM_DB_PASSWORD=strong-password
GDM_DB_HOST=localhost
GDM_DB_PORT=5432

REDIS_URL=redis://127.0.0.1:6379
INTERNAL_API_KEY=<another-random-string>
```

#### Migrate and collect static files

```bash
export DJANGO_SETTINGS_MODULE=wsz6_portal.settings.production
python manage.py migrate
python manage.py collectstatic --no-input
python manage.py create_dev_users
python manage.py install_test_game
```

#### Run Daphne (ASGI server)

```bash
daphne -b 127.0.0.1 -p 8000 wsz6_portal.asgi:application
```

For a persistent service, create a systemd unit file:

```ini
[Unit]
Description=WSZ6 Portal (Daphne ASGI)
After=network.target postgresql.service redis.service

[Service]
User=www-data
WorkingDirectory=/opt/SZ6_Dev/WSP6-portal/Claudes-plan-2/wsz6_portal
EnvironmentFile=/opt/SZ6_Dev/WSP6-portal/Claudes-plan-2/wsz6_portal/.env
Environment=DJANGO_SETTINGS_MODULE=wsz6_portal.settings.production
ExecStart=/opt/SZ6_Dev/WSP6-portal/Claudes-plan-2/wsz6_portal/.venv/bin/daphne \
          -b 127.0.0.1 -p 8000 wsz6_portal.asgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now wsz6
```

#### nginx Reverse Proxy (HTTPS)

```nginx
server {
    listen 443 ssl;
    server_name your-server.cs.washington.edu;

    ssl_certificate     /etc/ssl/certs/your-cert.pem;
    ssl_certificate_key /etc/ssl/private/your-key.pem;

    location /static/ {
        alias /opt/SZ6_Dev/WSP6-portal/Claudes-plan-2/wsz6_portal/staticfiles/;
    }

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_read_timeout 3600;
    }
}

server {
    listen 80;
    server_name your-server.cs.washington.edu;
    return 301 https://$host$request_uri;
}
```

### 6.10 Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: No module named 'django'` | venv not active | `source .venv/bin/activate` |
| `ALLOWED_HOSTS` error in browser | Hostname not in `.env` | Add to `DJANGO_ALLOWED_HOSTS`, restart |
| WebSocket connects then immediately drops | Debug=false but no Redis | Set `USE_REDIS=true` and start Redis |
| Game page shows text fallback instead of visualization | Vis file missing or import error | Check `games_repo/<slug>/`; re-run `install_test_game` |
| LLM game returns "API error" | Missing or invalid API key | Add key to `.env`, restart server |
| `django.db.utils.OperationalError` on first run | Migrations not applied | `python manage.py migrate` |
| Port 8000 already in use | Previous server still running | `pkill -f daphne` |

---

## 7. Administering the System

All admin functions require login as a user with an `ADMIN_*` account type.
The admin dashboard is at `/dashboard/`.

### 7.1 Dashboard Home

The home page shows summary statistics (user count, game count, session count)
and two panels:

- **Active Sessions** — the 10 most recently started open or in-progress
  sessions, with game name, owner, and start time.
- **Recently Installed Games** — the 5 most recently installed games.

### 7.2 User Management

**URL:** `/dashboard/users/`

The user list shows all portal accounts with columns for username, full name,
email, account type, game access level, session count, and active status.
A search box filters by username, email, first name, or last name. The
**+ Add User** button opens the user creation form.

**Creating a user:** Fill in username, password (twice), first name, last name,
email, account type, and game access level. The new user can log in immediately.

**Editing a user:** Click the username or the **Edit** button to open the user
detail page. Fields editable by admins:
- First name, last name, email
- Account type (`user_type`)
- Game access level (`game_access_level`)
- Custom game list (`allowed_games`) — used when access level is "Custom list"
- Active status (`is_active`) — deactivating prevents login

The user detail page also shows the user's session history (the 20 most recent
sessions they owned).

**Account types** (set via `user_type`):

| Type | Can do |
|------|--------|
| `ADMIN_GENERAL` | Everything |
| `ADMIN_ACCOUNTS` | Manage users |
| `ADMIN_GAMES` | Install / retire games |
| `ADMIN_RESEARCH` | Access Researcher Panel |
| `SESSION_OWNER` | Create sessions, invite players |
| `GAME_OWNER` | Install their own games, create sessions |
| `PLAYER` | Join invited sessions |

**Game access levels** (set via `game_access_level`):

| Level | Can access |
|-------|-----------|
| `published` | Published games only (default) |
| `beta` | Beta and published games |
| `all` | All games including dev-status games |
| `custom` | Only games listed in `allowed_games` |

### 7.3 Games Catalog

**URL:** `/games/`

The games catalog lists all installed games with their status, player counts,
and install date. Clicking a game opens its detail page.

**Game detail page:**
- Description, player count range, and current status.
- Lifecycle buttons to promote the game: **Promote to Beta**, **Publish**,
  **Deprecate**. Transitions are logged with timestamps.
- **Start a Session** button (for session owners and above).
- Session count and play-through statistics.

**Installing a new game (production workflow, not yet implemented):**
The planned flow is to upload a ZIP archive through the admin interface. During
the current development phase, games are installed via `install_test_game` (see
§3.1).

### 7.4 Sessions Log

**URL:** `/sessions/`

The sessions log lists all game sessions with their owner, game, status, and
timestamps. Clicking a session shows its `summary_json` (a JSON blob written
by the play engine when the session ends) and links to the GDM log viewer via
the Researcher Panel.

### 7.5 Live Sessions Panel

**URL:** `/dashboard/sessions-live/`

Shows all currently open or in-progress sessions (updated on page load). A
second panel shows sessions completed or interrupted within the last hour.

Each row shows: game, owner, status, started time. (Observer-join functionality
is planned but not yet implemented.)

### 7.6 Django Admin Panel

The standard Django admin UI is available at `/admin/`. Use it for database-
level operations not exposed in the custom dashboard, such as:
- Bulk user creation or modification.
- Directly editing `GameSession` records.
- Viewing migration history.

Log in as `admin` (or any user with `is_staff = True`).

---

## 8. Architecture

### 8.1 High-Level Design

```
Browser Clients
      │ HTTPS / WSS
      ▼
┌─────────────────────────────────────────────────────────┐
│                 ASGI Server (Daphne)                    │
│                                                         │
│   ┌─────────────────────┐   ┌────────────────────────┐  │
│   │     WSZ6-admin      │   │      WSZ6-play          │  │
│   │  (Django HTTP views)│   │  (Django Channels / WS) │  │
│   │  Auth, accounts,    │   │  Game engine, PFF load, │  │
│   │  games catalog,     │   │  real-time state push,  │  │
│   │  admin dashboard,   │   │  session persistence    │  │
│   │  researcher panel   │   │                        │  │
│   └──────────┬──────────┘   └──────────┬─────────────┘  │
│              │  Internal REST API       │                 │
│              └─────────────────────────┘                 │
└─────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
  ┌─────────────┐              ┌────────────────────┐
  │  UARD (DB1) │              │  GDM (DB2 + Files) │
  │  SQLite /   │              │  SQLite / PostgreSQL│
  │  PostgreSQL │              │  + File System      │
  │  Users,     │              │  Playthroughs,      │
  │  Games,     │              │  checkpoints,       │
  │  Sessions   │              │  artifacts, logs    │
  └─────────────┘              └────────────────────┘
         │
         ▼
  ┌─────────────────┐
  │  Games Repo     │
  │  (File System)  │
  │  games_repo/    │
  │  <slug>/        │
  │  PFF + assets   │
  └─────────────────┘
```

### 8.2 Two Databases

**UARD (User Accounts Relational Database)** — Managed by WSZ6-admin. Contains:
- `accounts_wszuser` — user accounts and permissions
- `games_catalog_game` — game catalogue entries and lifecycle state
- `sessions_log_gamesession` — lightweight session summaries (one row per
  session; written by WSZ6-play via the Internal API after a session ends)

**GDM (Game Data Management)** — Managed by WSZ6-play. Contains:
- A PostgreSQL database with tables for `PlayThrough`, `Checkpoint`, and
  `Artifact` (metadata rows only).
- A file system tree rooted at `GDM_ROOT`:
  ```
  <GDM_ROOT>/
    <game-slug>/
      sessions/
        <session-key>/
          session_meta.json
          playthroughs/
            <playthrough-id>/
              log.jsonl          ← append-only event log
              checkpoints/
                <checkpoint-id>.json
              artifacts/
                essay.txt, essay.v2.txt, …
  ```

### 8.3 Games Repository

The Games Repository (`GAMES_REPO_ROOT`, default: `SZ6_Dev/games_repo/`) holds
one directory per installed game:

```
games_repo/
  tic-tac-toe/
    Tic_Tac_Toe_SZ6.py
    Tic_Tac_Toe_WSZ6_VIS.py
    soluzion6_02.py         ← shared library (bundled per game)
  missionaries-and-cannibals/
    ...
```

The repository is **read-only at runtime** — game files are never modified
during play. Updates come only through the install process.

### 8.4 WebSocket Consumers

Three WebSocket consumers handle real-time connections:

| Consumer | WS URL pattern | Purpose |
|----------|---------------|---------|
| `LobbyConsumer` | `ws/lobby/<session_key>/` | Pre-game: player join, role assignment, game start |
| `GameConsumer` | `ws/game/<session_key>/<role_token>/` | In-game: operator apply, state broadcast, pause, rematch |
| `ObserverConsumer` | `ws/observe/<session_key>/` | Admin observer (stub, not yet fully implemented) |

All consumers in a session share a Channel group (keyed by session key) so that
state updates broadcast to all connected clients simultaneously.

### 8.5 PFF Loader

`wsz6_play/engine/pff_loader.py` dynamically imports PFF files at game-start
time. Each import uses a globally unique module name (`_pff_<slug>_<uuid32hex>`)
to prevent namespace collisions between concurrent sessions. This solves the
"role mixing bug" present in the earlier SZ5 web engine, where a shared module
name could cause role assignments from one session to overwrite those in another.

### 8.6 Game Runner

`wsz6_play/engine/game_runner.py` contains the game loop: it maintains a state
stack, calls operator precondition and transition functions, evaluates goal
conditions, and sends `state_update` and `transition_msg` events to the Channel
group after each move.

### 8.7 Session Store

In-memory session state (the `GameRunner` object and role assignments for active
sessions) lives in a module-level dict protected by a `threading.Lock` in
`wsz6_play/session_store.py`. This is appropriate for single-process dev
deployments; a Redis-backed approach is planned for multi-process production
(see §10.4).

### 8.8 Internal API

WSZ6-play exposes a set of internal HTTP endpoints at `/internal/v1/` for
communication with WSZ6-admin. These are authenticated with a shared secret key
(`INTERNAL_API_KEY` in settings). Key endpoints:

| Endpoint | Direction | Purpose |
|----------|-----------|---------|
| `POST /internal/v1/sessions/<key>/status/` | play → admin | Update session status |
| `POST /internal/v1/sessions/<key>/summary/` | play → admin | Push summary on session end |

### 8.9 Technology Stack

| Layer | Technology |
|-------|-----------|
| Web framework | Django 5.2 |
| Real-time / WebSocket | Django Channels 4.x + Daphne ASGI |
| Channel layer (dev) | `InMemoryChannelLayer` |
| Channel layer (prod) | Redis (`channels-redis`) |
| Databases (dev) | SQLite (UARD) + SQLite (GDM) |
| Databases (prod) | PostgreSQL 16 (UARD) + PostgreSQL 16 (GDM) |
| Game logic | Python 3.11 |
| Frontend | Django templates + vanilla JavaScript (native WebSocket API) |
| Reverse proxy (prod) | nginx |

---

## 9. Design Decisions

This section documents the key architectural choices made during development
and the reasoning behind them.

### 9.1 Single Django Process (ASGI)

Rather than running two separate Django processes (one for HTTP, one for
WebSocket), the portal runs as a single ASGI application under Daphne. Django
Channels' `ProtocolTypeRouter` routes HTTP requests to the normal Django WSGI
app and WebSocket connections to the Channels consumers. This simplifies
deployment significantly: one process, one port, one configuration.

### 9.2 Dual-Database Architecture

The decision to store user data and play data in separate databases (UARD and
GDM) was motivated by:

- **Separation of concerns** — User account data has very different access
  patterns and retention requirements than raw game logs.
- **Independent scaling** — The GDM database grows with every session; the
  UARD grows only with new users and games. Separate databases can be
  independently sized, backed up, and replicated.
- **Researcher access** — Researchers need read access to GDM data but should
  not have access to raw user account data. The two-database split enforces
  this boundary structurally.

### 9.3 Append-Only JSONL Logs

All game events are written to `log.jsonl` files using append-only writes.
Logs are never modified after a line is written; instead, new events (including
paused/resumed markers) are appended. This design:

- Makes logs **replay-complete**: every session can be reconstructed from its
  log without any other data source.
- Provides a natural audit trail with timestamps.
- Is simple to implement and highly durable (no partial-write corruption risk).
- Is easy to process with standard tools (`jq`, Pandas, etc.).

### 9.4 Per-Session Unique Module Names for PFFs

Each PFF import uses a UUID-derived module name so that two concurrent sessions
running the same game each get their own independent module and formulation
instance. This prevents the namespace-collision bugs that plagued the SZ5 web
engine (shared module names led to role-assignment data leaking between
sessions).

### 9.5 Role Token Authentication

Players are identified in the WebSocket layer by opaque role tokens (random
hex strings assigned at lobby time) rather than by Django session cookies.
This allows guests (players without portal accounts) to participate in sessions,
and means the WebSocket URL is self-authenticating: knowing the URL implies
having been invited to that role in that session.

### 9.6 Visualization as Returned HTML

The vis module returns plain HTML rather than a structured data format (e.g.
JSON describing board positions). This gives game authors maximum flexibility —
they can use SVG, `<canvas>`, images, CSS, HTML tables, or any combination.
The portal adds interactivity on top of whatever HTML the vis module returns,
through standardized `data-*` attributes (Tier 1) and the JSON region manifest
convention (Tier 2).

### 9.7 In-Memory Session Store for Dev

For development, active game state is stored in a Python dict in the server
process. This is intentionally simple: no Redis dependency, no serialization
overhead, instant setup. The planned production upgrade (§10.4) will move this
to Redis, but the API between the session store and the consumers is designed
to make that migration straightforward.

### 9.8 File-Edit Operator for Open-World Games

Rather than building a separate text-editing application, the portal provides
a `file_edit` parameter type that opens a full-page text editor modal directly
in the game page. The editor has:
- Ctrl+Enter to save (keyboard-shortcut save).
- Word count display.
- Click-outside-to-cancel (with an overlay backdrop).
- Spell-checking (browser-native via `spellcheck="true"`).

The content is transmitted over the existing WebSocket as operator arguments,
keeping the open-world text-editing flow fully within the game protocol.

---

## 10. Pending Development and Future Work

### 10.1 Phase 4 — Debug Mode and Observer Mode

**Debug mode** (planned, not yet implemented): A game admin clicks "Start in
Debug Mode" on a newly installed game. The server creates a temporary session
with simulated players (one per role) and opens multiple browser tabs, each
showing one role's view. This allows game authors to test all role-specific
displays and interactions without needing real human testers. Debug sessions
are automatically flagged and their logs auto-deleted after 7 days.

**Observer mode** (stub present): An admin can join a live session as an observer
through the `ObserverConsumer`. The observer receives all state updates (full
state, no role filtering) and can select any player's perspective from a
dropdown. The infrastructure exists but the consumer logic and UI are not yet
complete.

### 10.2 Phase 5 — Research Dashboard Enhancements

The researcher panel (R1–R7) is fully implemented. Planned additions:

- **Session timeline view** — A horizontal time-axis visualization in the game
  detail admin page showing all sessions for that game as colored bars,
  color-encoded by outcome or play-through count.
- **Export API** — Programmatic access to session lists and log downloads using
  the existing `ResearchAPIToken` infrastructure.
- **Jupyter integration** — Example notebooks for analyzing exported JSONL logs.

### 10.3 Phase 6 — Open-World Features

- **Per-session artifacts** — The file system layout and database model for
  artifacts are in place. The GDM writer already appends `artifact_created`
  and `artifact_saved` events. The artifact viewer in the researcher panel is
  implemented. The remaining work is richer support in the game engine and
  better UI on the game page for viewing current artifacts.
- **LLM agent role** — A bot that uses an external LLM API (e.g. Gemini,
  OpenAI) as its decision-making backend, replacing the random/first-option
  strategies. This enables games where one role is played by an AI model.
- **Parameterized problem instances** — A config form before game start that
  lets the session owner configure game-level parameters (scenario selection,
  difficulty, etc.) without requiring a separate PFF file for each variant.

### 10.4 Phase 7 — Production Hardening

The following items are required before a large-scale (50+ simultaneous session)
production deployment:

#### Session Store (Redis)

The current in-memory session store (`session_store.py`) does not survive
process restarts and cannot be shared across multiple Daphne worker processes.
For production, this must be replaced with a Redis-backed store:

- `GameRunner` instances serialized to Redis at each step (using a compact
  checkpoint format).
- Role assignments stored per-session in Redis.
- A configurable TTL so stale entries from crashed sessions are cleaned up
  automatically.

#### PFF Code Execution Security

PFF files are arbitrary Python code uploaded by users with `ADMIN_GAMES`
privilege. The current approach runs them in the same process as the web
server. Near-term mitigation: run PFF loading in a subprocess with reduced OS
permissions. Medium-term: use a container or `seccomp` profile to sandbox PFF
execution. Long-term: consider a restricted Python subset evaluator.

Even in trusted environments (where all game admins are staff or faculty),
sandboxing prevents accidental server damage from bugs in game code (e.g.
infinite loops, memory exhaustion).

#### Reconnect Handling

When a player's browser disconnects mid-game (network drop, page reload), the
`GameConsumer.disconnect()` handler currently removes the player from the group
but does not save a checkpoint or set a reconnect window. The planned behavior:
- A configurable reconnect window (default: 3 minutes) allows the player to
  rejoin using the same role token and resume play.
- If the window expires without reconnect and the session owner is also
  disconnected, the game is automatically paused and checkpointed.

#### Rate Limiting and Input Validation

- Rate-limit WebSocket message rates per connection (to prevent flooding).
- Validate all PFF ZIP uploads for path traversal, executable permissions,
  and size limits.
- Add CSRF and authentication checks to all internal API endpoints.

#### Automated Tests

- Unit tests for the game engine core (`game_runner.py`, `pff_loader.py`,
  `state_serializer.py`).
- Integration tests for the lobby-to-game flow (WebSocket, operator apply,
  pause/resume).
- Load test simulating 50 concurrent sessions.

#### Monitoring and Logging

- Structured logging with `structlog` for all WebSocket events.
- Sentry integration for error tracking.
- Redis and PostgreSQL health-check metrics.
- Alerting on session-store miss (indicator that a process restart lost
  in-flight game state).

### 10.5 Scaling Strategy

The system is designed to scale horizontally when load exceeds single-server
capacity. Apply these steps in order:

1. **Multiple Daphne workers** — Run several Daphne processes behind nginx with
   a Redis channel layer. Because all workers share the same Redis, any worker
   can handle any session.

2. **Separate database hosts** — Move UARD and GDM to dedicated PostgreSQL
   instances. Add read replicas for UARD (research queries are read-heavy and
   can be served from replicas).

3. **Redis clustering** — For very high WebSocket counts, switch from a single
   Redis instance to Redis Cluster.

4. **Games repository on shared storage** — Mount the games repo as NFS or use
   S3-compatible object storage with a local cache layer when multiple server
   nodes need access to game files.

5. **Containerization** — Package WSZ6-admin and WSZ6-play as Docker containers
   for reproducible deployment and easy horizontal scaling via Kubernetes or
   Docker Swarm.

### 10.6 Visualization Roadmap (M5–M8)

| Milestone | Feature | Status |
|-----------|---------|--------|
| M5 | Previous-state toggle | **Complete** — toggle button in game page and full-screen tray |
| M6 | Visual transitions | Not started — CSS/SVG animations between states |
| M7 | Audio support | Not started — audio file playback + optional TTS |
| M8 | Vis-debug mode | Not started — debug flag, auto-tab-open, live-reload |

### 10.7 Game Source Tree Consolidation

Currently, game source files live in two locations:
- `Textual_SZ6/` — original textual games
- `Vis-Features-Dev/game_sources/` — newer web games

And `soluzion6_02.py` is copied into each installed game's directory, creating
10+ redundant copies. The recommended consolidation:

```
SZ6_Dev/
  game_sources/          ← single home for all authored games
    tic_tac_toe/
    missionaries/
    occluedo/
    ...
  Textual_SZ6/           ← textual engine only
    Textual_SOLUZION6.py
    soluzion6_02.py      ← single source of truth
  games_repo/            ← installed copies (runtime, git-ignored)
```

The PFF loader should add `SOLUZION_LIB_DIR` to `sys.path` and serve
`soluzion6_02.py` from a shared location rather than bundling it per game.

---

## Quick-Reference Command Sheet

```bash
# Activate the virtual environment (do this first in every shell)
source wsz6_portal/.venv/bin/activate
export DJANGO_SETTINGS_MODULE=wsz6_portal.settings.development

# First-time setup
bash wsz6_portal/setup_dev.sh

# Create built-in user accounts (password: pass1234)
python manage.py create_dev_users

# Install / re-install all built-in games
python manage.py install_test_game

# Start the dev server (opens browser on port 8000)
bash start_server.sh

# Start on a different port, no browser
bash start_server.sh --port 8080 --no-browser

# Apply migrations after git pull
python manage.py migrate

# Open Django shell
python manage.py shell

# Verify configuration
python manage.py check
```

Login credentials (dev mode):

| Username | Password | Type |
|----------|----------|------|
| `admin` | `pass1234` | General Admin |
| `gameadm` | `pass1234` | Games Admin |
| `owner1` | `pass1234` | Session Owner |
| `owner2` | `pass1234` | Session Owner |
| `player1` | `pass1234` | Player |
| `player2` | `pass1234` | Player |
