# WSZ6-Portal: Phase 1 Completion Summary

**Date:** 2026-02-18
**Git repo:** `pixellator/SZ6_Dev` (GitHub)
**Working directory:** `SZ6_Dev/WSP6-portal/Claudes-plan-2/`
**Django project root:** `…/Claudes-plan-2/wsz6_portal/`

---

## What Was Accomplished This Session

### Background: Dev Plan and Architecture

Before Phase 1, the session began by reading `Dev-plan-prompt.txt` and all
referenced spec/source files (`WSP6-web-portal-v2.txt`, `SZ6-specification-overview.txt`,
`What-is-a-problem-formulation.txt`, `Textual_SOLUZION6.py`, sample PFFs, etc.)
and producing a full 12-section development plan saved as:

```
Claudes-plan-2/WSZ6-portal-dev-plan.md
```

The plan established two-component architecture:

```
WSZ6-portal = WSZ6-admin (Django HTTP) + WSZ6-play (Django Channels/WebSocket)
```

with two databases (UARD for user/admin data, GDM for game session logs),
a games file-system repository, and a versioned internal REST API
(`/internal/v1/`) as the sole interface between the two components.

---

### Phase 0 (also completed this session)

Full Django project skeleton created at `wsz6_portal/` with:

- Split settings: `base.py` / `development.py` / `production.py`
- ASGI entry point (`asgi.py`) routing HTTP → Django, WebSocket → Channels
- Four Django apps stubbed: `accounts`, `games_catalog`, `sessions_log`, `wsz6_play`
- WebSocket echo consumer (`EchoConsumer`) at `ws://localhost:8000/ws/echo/`
- Echo test HTML page at `http://localhost:8000/play/echo-test/`
- `requirements.txt`, `.env.dev`, `.gitignore`, `setup_dev.sh`, `pytest.ini`

#### Phase 0 Fix: daphne must be first in INSTALLED_APPS

**Problem:** After running `setup_dev.sh` and `python manage.py runserver`,
visiting the echo test page gave WebSocket error code **1006** (abnormal closure).

**Root cause:** Django's `runserver` command defaults to WSGI, which silently
drops WebSocket connections. Django Channels replaces `runserver` with an
ASGI-capable version only when `'daphne'` is the **first** entry in
`INSTALLED_APPS`.

**Fix:** Added `'daphne'` as the first item in `INSTALLED_APPS` in `base.py`.
After restarting the server, the echo test connected successfully.

---

### Phase 1: WSZ6-admin Core

**Milestone achieved:** An admin can log in, install a SOLUZION6 game from a ZIP
archive, see it in the game catalogue, and manage user accounts.

#### New files and modules

| File | Purpose |
|------|---------|
| `wsz6_portal/db_router.py` | Routes `wsz6_play` models to `gdm` DB; everything else to `default` |
| `wsz6_admin/dashboard/` | New Django app: admin dashboard home, user list/detail, live sessions |
| `wsz6_admin/accounts/forms.py` | `UserEditForm` for changing user type, access level, allowed games |
| `wsz6_admin/games_catalog/forms.py` | `GameInstallForm` (zip upload + metadata) and `GameEditForm` |
| `wsz6_admin/games_catalog/installer.py` | ZIP validation, extraction, PFF sandbox validation |
| `wsz6_admin/games_catalog/views.py` | `game_list`, `game_detail`, `game_install` (full implementation) |
| `wsz6_admin/sessions_log/views.py` | `session_list` with search |
| `templates/base.html` | Shared nav/layout; self-contained CSS (no external framework) |
| All other templates | Login, password reset, dashboard, game catalogue, sessions |

#### Settings changes in `base.py`

- `DATABASE_ROUTERS = ['wsz6_portal.db_router.GDMRouter']`
- `LOGIN_URL`, `LOGIN_REDIRECT_URL`, `LOGOUT_REDIRECT_URL`
- `GAME_ZIP_MAX_SIZE = 50 MB`
- `'wsz6_admin.dashboard'` added to `INSTALLED_APPS`

#### URL structure (as of Phase 1)

| URL | View |
|-----|------|
| `/` | → redirect to `/dashboard/` |
| `/accounts/login/` | Login |
| `/accounts/logout/` | Logout |
| `/accounts/password-reset/` | Password reset flow |
| `/dashboard/` | Admin home (stat cards, active sessions, recent games) |
| `/dashboard/users/` | Searchable user list |
| `/dashboard/users/<id>/` | User detail + edit |
| `/dashboard/sessions-live/` | Live sessions panel |
| `/games/` | Game catalogue (filtered by access level) |
| `/games/install/` | Game installation form |
| `/games/<slug>/` | Game detail + metadata edit |
| `/sessions/` | Session list |
| `/research/` | Research dashboard (stub, Phase 5) |
| `/play/join/<uuid>/` | Session join page (stub, Phase 2) |
| `/play/echo-test/` | WebSocket echo test (Phase 0 verification) |
| `/internal/v1/…` | Internal REST API (shared-secret protected stubs) |
| `/admin/` | Django built-in admin site |

#### Game Installation Workflow

1. Admin visits `/games/install/`, fills out metadata and uploads a `.zip`.
2. Server validates: size ≤ 50 MB, no path-traversal entries, contains `.py`.
3. ZIP is extracted to `GAMES_REPO_ROOT/<slug>/` (configured via `.env`).
4. A temporary subprocess runs the validator script against each `.py` file,
   looking for an object with a `.metadata.name` attribute (duck-typed
   `SZ_Formulation`). On success, returns `name`, `version`, `desc`,
   `authors`, `min_players`, `max_players` as JSON.
5. `Game` record is written to the UARD database.
6. A POST is made to `/internal/v1/games/installed/` (internal API) to notify
   WSZ6-play. Currently a stub; will be wired in Phase 2.
7. Admin is redirected to the game detail page (or debug launch if they clicked
   "Install & Start in Debug Mode").

#### Phase 1 Fix: Stale SQLite databases after adding custom AUTH_USER_MODEL

**Problem:** `setup_dev.sh` (Phase 0) ran `manage.py migrate` using the default
Django `auth.User`. When Phase 1 added `AUTH_USER_MODEL = 'accounts.WSZUser'`
and generated new migrations, running `migrate` again failed with:

```
InconsistentMigrationHistory: Migration admin.0001_initial is applied before
its dependency accounts.0001_initial on database 'default'.
```

**Fix:** Since we are in early development with no real data, the SQLite files
were deleted and all migrations were re-applied from scratch:

```bash
rm -f db_uard.sqlite3 db_gdm.sqlite3
python manage.py migrate
python manage.py migrate --database=gdm
```

Both databases are now clean and consistent.

#### Development superuser

A default admin account was created for development use:

- **Username:** `admin`
- **Password:** `admin123`
- **User type:** `ADMIN_GENERAL` (can do everything)

Change this password before any public exposure.

---

## Current State of Each Phase

| Phase | Status | Notes |
|-------|--------|-------|
| 0 – Infrastructure | ✅ Complete | daphne fix applied; echo test verified |
| 1 – WSZ6-admin core | ✅ Complete | Milestone 1 achieved |
| 2 – WSZ6-play core | ⬜ Not started | Next up |
| 3 – Persistence & bots | ⬜ Not started | |
| 4 – Debug & observer modes | ⬜ Not started | |
| 5 – Research & analytics | ⬜ Not started | |
| 6 – Open-world features | ⬜ Not started | |
| 7 – Production hardening | ⬜ Not started | |

---

## Starting Phase 2

Phase 2 implements the WSZ6-play game engine. Key tasks from the dev plan:

- `engine/pff_loader.py` — dynamically import PFF modules with unique names per session
- `engine/game_runner.py` — async `GameRunner` class (state stack, operator application, undo)
- `engine/state_serializer.py` — JSON serialize/deserialize `SZ_State` subclasses
- `engine/role_manager.py` — role-assignment validation
- `consumers/lobby_consumer.py` — session creation, player join, role assignment, game start
- `consumers/game_consumer.py` — operator application, state broadcast, goal detection
- GDM log writer — JSONL append-only replay-complete log
- Session summary sync to UARD via internal API
- Verify all six sample formulations run:
  `Tic_Tac_Toe_SZ6`, `Missionaries_SZ6`, `FoxAndHounds`, `Guess_My_Age_SZ6`,
  `Rock_Paper_Scissors_SZ6`, `Trivial_Writing_Game_SZ6`

**Milestone 2 target:** Owner creates session, two players join, play
Tic-Tac-Toe to completion via the web, log written, session summary
appears in the admin dashboard.

### Key files to know for Phase 2

| Path | Description |
|------|-------------|
| `wsz6_play/consumers/lobby_consumer.py` | Stub — replace with full lobby logic |
| `wsz6_play/consumers/game_consumer.py` | Stub — replace with full game loop |
| `wsz6_play/routing.py` | WebSocket URL routing (already wired) |
| `wsz6_play/engine/` | Empty `__init__.py` only — all engine modules to be written here |
| `wsz6_play/persistence/` | Empty `__init__.py` only — GDM writer to be written here |
| `wsz6_play/internal_api/views.py` | Stubs returning 200 OK — flesh out `session_summary`, `launch_session` |
| `wsz6_play/models.py` | `PlayThrough` and `Checkpoint` models already defined and migrated |
| `wsz6_shared/session_summary_schema.py` | Shared JSON contract; v1 schema + `validate_summary()` |
| `SZ6_Dev/Textual_SZ6/Textual_SOLUZION6.py` | Reference textual engine to adapt |
| `SZ6_Dev/Textual_SZ6/soluzion6_02.py` | SZ6 base classes (`SZ_Formulation`, `SZ_State`, etc.) |
| `SZ6_Dev/Textual_SZ6/Tic_Tac_Toe_SZ6.py` | Primary test formulation for Phase 2 |

### Important architectural reminders for Phase 2

1. **Each play-through gets its own freshly instantiated formulation object** —
   never share a formulation instance between sessions (this was the SZ5 bug).
2. **PFF module names must be unique per session** — use
   `f"_pff_{game_slug}_{uuid4().hex}"` as the module name to prevent namespace collisions.
3. **State serialization** — PFFs should implement `to_dict()` / `from_dict(cls, d)`
   on their State class. Provide a fallback using `__dict__` for simple states.
4. **Channel groups** — each play-through gets its own group named
   `f"game_{playthrough_id}"`. All consumers for that play-through join this group.
5. **Log format** — append-only JSONL at
   `GDM_ROOT/<game-slug>/sessions/<session-key>/playthroughs/<id>/log.jsonl`.
   Every event (game_started, operator_applied, game_ended, etc.) timestamped in ISO 8601.
