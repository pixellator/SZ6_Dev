# Phase 2 Completed Handoff

**Date:** 2026-02-19
**Status:** All Phase 2 code written, syntax-checked, `manage.py check` passes (0 issues).
**Target milestone:** Owner creates session → two players join lobby → play Tic-Tac-Toe to completion → log.jsonl written → GameSession updated.

---

## What was built in Phase 2

### Engine layer (`wsz6_play/engine/`)

| File | Purpose |
|------|---------|
| `pff_loader.py` | Dynamically loads a PFF via `importlib.util.spec_from_file_location` with a unique module name per call (prevents SZ5 role-mixing bug). Also adds the game directory to `sys.path` so PFF-bundled helpers (`soluzion6_02.py`) are importable. |
| `state_serializer.py` | Converts SZ_State ↔ JSON-compatible dicts. Uses `to_dict()`/`from_dict()` if present, falls back to `__dict__` copy with type coercion. |
| `role_manager.py` | `PlayerInfo` + `RoleManager` — manages token→role assignments, validates min-player constraints, provides lobby serialization for WS broadcast. |
| `game_runner.py` | Async game loop: holds state stack, applies operators, handles undo, broadcasts via caller-supplied `async broadcast(payload)` coroutine. `GameError` raised for invalid actions. |

### Persistence layer (`wsz6_play/persistence/`)

| File | Purpose |
|------|---------|
| `gdm_writer.py` | Path helpers + `GDMWriter` — async-safe append-only JSONL event log, protected by `asyncio.Lock`. Layout: `<gdm_root>/<slug>/sessions/<key>/playthroughs/<id>/log.jsonl`. |
| `session_sync.py` | `push_session_ended()` / `push_session_status()` — updates UARD `GameSession` via direct ORM (same process, `asyncio.to_thread`). |

### Session store (`wsz6_play/session_store.py`)

Module-level `dict` + `threading.Lock`. Callable from both sync HTTP views and async WS consumers. Tracks: `session_key`, `game_slug`, `game_name`, `owner_id`, `pff_path`, `status` ('lobby'|'in_progress'|'ended'), `role_manager`, `game_runner`, `gdm_writer`, `playthrough_id`, `session_dir`, `started_at`.

### WebSocket consumers

| File | Purpose |
|------|---------|
| `consumers/lobby_consumer.py` | Full lobby: lazy-loads PFF on first connection, handles join/assign-role/start-game, broadcasts `lobby_state` and `game_starting` via Channel group `lobby_<session_key>`. |
| `consumers/game_consumer.py` | In-game: validates role_token on connect, dispatches apply/undo/help commands to `GameRunner`, relays state_update/transition_msg/goal_reached from Channel group `game_<session_key>`. Role-filters operator list per player. |

### HTTP views and URLs

| Location | Change |
|----------|--------|
| `wsz6_play/views.py` | Added `join_session()` (lobby page) and `game_page()` (game page). |
| `wsz6_play/urls.py` | Added `game/<uuid:session_key>/<str:role_token>/` → `game_page`. |
| `wsz6_play/internal_api/views.py` | Wired `launch_session`, `session_summary`, `session_status`, `active_sessions`. Phase-4 stubs kept. |
| `games_catalog/views.py` | Added `start_session()` — creates GDM dir + session store entry + `GameSession` record, redirects to `/play/join/<uuid>/`. |
| `games_catalog/urls.py` | Added `<slug:slug>/start-session/` → `start_session`. |

### Templates

| Template | Purpose |
|----------|---------|
| `wsz6_play/join.html` | Full lobby UI. Two-column layout: role table with assign buttons (left) + connected/unassigned player list (right). WS client opens `/ws/lobby/<key>/`. Owner gets "Start Game" button. |
| `wsz6_play/game.html` | In-game UI. Two-column: monospace state display (left) + operator buttons (right). WS client opens `/ws/game/<key>/<token>/`. "Your turn!" / "Waiting…" banner. |
| `wsz6_play/session_not_found.html` | Simple 404-style page for missing sessions. |
| `games_catalog/detail.html` | Added "Start a Session" card with `▶ New Session` button (shown if `user.can_start_sessions`). |
| `base.html` | Added `{% block extra_scripts %}{% endblock %}` before `</body>`. |

### Settings

`wsz6_portal/settings/base.py` — added `GDM_ROOT` setting (defaults to `SZ6_Dev/gdm/`).

### Dev tooling

| Command | Purpose |
|---------|---------|
| `manage.py install_test_game` | Copies `Tic_Tac_Toe_SZ6.py` + `soluzion6_02.py` from Textual_SZ6 into `GAMES_REPO_ROOT/tic-tac-toe/` and creates the `Game` record. |
| `manage.py create_dev_users` | Creates dev users: admin, gameadm, owner1, owner2, player1, player2 (all with password `pass1234`). |

---

## Key design decisions

1. **Unique PFF module names** — `_pff_<slug>_<uuid32hex>` per call; each play-through gets its own module instance, preventing concurrent sessions from sharing class-level state.

2. **sys.path injection** — `pff_loader` adds the game directory to `sys.path` before loading so `import soluzion6_02 as sz` in PFFs resolves without packaging `soluzion6_02` separately.

3. **start_session calls session_store directly** — No HTTP self-call (avoids potential single-threaded WSGI deadlock). The admin view imports and calls `session_store.create_session()` in-process.

4. **Lazy PFF load on first WS connection** — The `LobbyConsumer` loads the PFF (via `asyncio.to_thread`) on the first lobby WebSocket connection, keeping the HTTP start-session response fast.

5. **threading.Lock session store** — Module-level dict protects with `threading.Lock`. Safe from both sync HTTP views and async consumers without blocking the event loop.

6. **Role-filtered operator display** — `_filter_ops_for_role()` hides operators where `op.role not in (None, role_num)`. TTT operators have `role=None` so all 18 are shown (9 applicable per turn); role filtering is for future multi-role games with hidden information.

7. **same-process session_sync** — `push_session_ended` and `push_session_status` use direct ORM imports + `asyncio.to_thread`, avoiding an HTTP round-trip back to the same process.

---

## How to test (quick start)

```bash
cd wsz6_portal
source .venv/bin/activate
export DJANGO_SETTINGS_MODULE=wsz6_portal.settings.development

# 1. Apply migrations (already done)
python manage.py migrate

# 2. Create dev users
python manage.py create_dev_users

# 3. Install Tic-Tac-Toe
python manage.py install_test_game

# 4. Start the server
python manage.py runserver

# 5. Browser A: log in as owner1 (pass1234)
#    Go to /games/tic-tac-toe/ → click "New Session"
#    You land on the lobby page; your player-name is pre-filled.

# 6. Browser B: log in as owner2 (pass1234)
#    Paste the lobby URL from Browser A → you appear in "Connected Players"

# 7. Browser A (owner): click a player chip to select them, then "Assign here" for role X.
#    Repeat for O. Click "▶ Start Game".

# 8. Both browsers are redirected to their game pages.
#    Play Tic-Tac-Toe; the board updates live.

# 9. After the game ends, check:
#    - GDM_ROOT/tic-tac-toe/sessions/<key>/playthroughs/<id>/log.jsonl
#    - Admin "Sessions" page shows the session as "Completed"
```

---

## Files changed / created in Phase 2

```
wsz6_play/
  engine/
    pff_loader.py         (NEW)
    state_serializer.py   (NEW)
    role_manager.py       (NEW)
    game_runner.py        (NEW)
  persistence/
    gdm_writer.py         (NEW)
    session_sync.py       (NEW)
  session_store.py        (NEW)
  consumers/
    lobby_consumer.py     (replaced stub)
    game_consumer.py      (replaced stub)
  internal_api/
    views.py              (wired)
  views.py                (updated)
  urls.py                 (updated)
wsz6_admin/
  games_catalog/
    views.py              (start_session added)
    urls.py               (start_session URL added)
    management/
      commands/
        install_test_game.py  (NEW)
        create_dev_users.py   (NEW)
wsz6_portal/settings/
  base.py                 (GDM_ROOT added)
templates/
  base.html               (extra_scripts block added)
  wsz6_play/
    join.html             (replaced stub)
    game.html             (NEW)
    session_not_found.html (NEW)
  games_catalog/
    detail.html           (start_session button added)
Phase_2_completed.md      (THIS FILE)
```

---

## What comes next (Phase 3+)

**Phase 3 – GDM Persistence & Checkpoints**
- Checkpoint writes (state serialization → disk) on every N steps
- Session resume (reload state from checkpoint on reconnect)
- `PlayThrough.status` tracking (started → ended, interrupted)

**Phase 4 – Observer Mode & Debug Launcher**
- `ObserverConsumer` (read-only, no operator buttons)
- Debug launcher: single-player session with all roles run by one user
- The `launch_debug` internal API endpoint needs implementation

**Phase 5 – Parameterized Operators**
- UI for collecting operator parameters before applying
- Parameter spec parsing from `op.params`

**Phase 6 – Research / GDM Analytics**
- Admin "Research" tab: browse GDM logs, aggregate stats
- Download session data as ZIP

**Phase 7 – Production hardening**
- Replace `InMemoryChannelLayer` + `session_store` dict with Redis
- Scale to multiple Daphne workers
- Proper secrets management, HTTPS, etc.
