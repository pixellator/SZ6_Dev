# WSZ6-portal Implementation Audit

**Date:** 2026-02-20
**Auditor:** Claude Sonnet 4.6
**Scope:** `Dev-plan-prompt.txt`, `WSZ6-portal-dev-plan.md`, and the actual implementation in `wsz6_portal/` and `games_repo/`

---

## Part I — Design Objectives: Status by Category

---

### 1. Dual-Component Architecture (WSZ6-admin + WSZ6-play)

**Design intent:** Separate administrative and game-play concerns so each component can be updated independently. Cross-component communication through a versioned internal REST API.

**Implemented:** Largely yes, structurally. The project has distinct Django app groups (`wsz6_admin.*` and `wsz6_play`), separate databases (UARD and GDM), and a `wsz6_shared/` module for the shared session-summary schema. A `wsz6_play/internal_api/` URL set exists.

**Implementation decision:** The internal REST API (`/internal/v1/…`) is a structural artifact but is *barely used in practice*. Session creation is performed directly in an HTTP view (`games_catalog/views.py`) that writes to `session_store` and the ORM simultaneously. The `games_installed` signal POST and the `session_sync.py` pushes to UARD are the only real cross-component calls in flight. There is no versioning enforcement in practice — both sides are one Django process.

**Technical debt:**
- The internal API versioning benefit is theoretical. Since both components are in a single process and can import each other's models (they do: `game_consumer.py` imports `games_catalog.models.Game`), the "independence" guarantee is not enforced.
- If WSZ6-play is ever extracted to a separate process or service, the direct ORM imports in `game_consumer.py` and `lobby_consumer.py` would break. A genuine refactoring would require routing all cross-component DB access through the internal API.

---

### 2. User Model and Account Types

**Design intent:** Seven account types with differentiated permissions (`ADMIN_GENERAL`, `ADMIN_ACCOUNTS`, `ADMIN_GAMES`, `ADMIN_RESEARCH`, `SESSION_OWNER`, `GAME_OWNER`, `PLAYER`). Guest players handled by session tokens.

**Implemented:** Fully. `WSZUser(AbstractUser)` has exactly the seven types with `is_any_admin()`, `can_install_games()`, `can_access_research()`, and `can_start_sessions()` convenience helpers. The `game_access_level` (published/beta/all/custom) and `allowed_games` M2M are present.

**Implementation decision:** `user_type` defaults to `SESSION_OWNER`, which is appropriate for self-registration. The permission helpers are convenience methods rather than Django group-based permissions — simpler for this scale, but mixing `user_type` with Django's `is_staff`/`is_superuser` creates two overlapping permission systems.

**Technical debt:**
- The `game_access_level` filter is modeled but not enforced in any view (the games catalog list shows all published games regardless of the user's access level). The `allowed_games` M2M is populated but never queried.
- `GAME_OWNER` is in the model but `create_dev_users` only creates `SESSION_OWNER` users — the distinction between session owner and game owner is not exercised in development.

---

### 3. Game Catalogue and Installation

**Design intent:** Admin uploads a zip, server validates, extracts to `GAMES_REPO_ROOT/<slug>/`, sandbox-imports PFF, extracts metadata, creates `Game` record.

**Implemented:** Fully for the zip-upload path (`games_catalog/installer.py`). Path traversal blocked, Python file required, single-top-directory prefix stripped, subprocess sandbox validation with `_VALIDATOR_SCRIPT`.

**For development:** A `install_test_game` management command replaces the zip workflow and correctly handles PFFs, vis files, and image directories. It supports a `source_dir` override per game to allow sources from `Vis-Features-Dev/game_sources/`.

**Implementation decision:** The `Game.pff_path` field stores the *game directory* path, not the path to the specific PFF file. This is correct (since the loader scans the directory), but contradicts the field name.

**Technical debt:**
- The `Game` lifecycle controls (dev → beta → published → deprecated) are modeled but there is no view or UI to trigger these transitions. All games are installed directly at the chosen status.
- The plan's `metadata.json` auto-generation to the game directory was not implemented; metadata lives only in `Game.metadata_json` in the database. The game directory is not self-documenting.
- PFF sandbox validation runs in a subprocess, which is correct, but the `_VALIDATOR_SCRIPT` inlines the validation code as a string. If the validation logic needs to evolve, it is harder to test and version.
- The zip upload interface in `games_catalog/views.py` exists, but the install button on the game detail page does not include a "Start in Debug Mode" post-install option. It redirects to the detail page only.

---

### 4. Game-Play Core (Lobby, Roles, Game Engine)

**Design intent:** Lobby WebSocket for role assignment, `GameConsumer` for the game loop, `GameRunner` for state management, per-session isolated formulation instances (no SZ5 role-mixing bug), role-filtered operator delivery.

**Implemented:** Fully and correctly. This is the most complete part of the system.

Key correctness properties verified:
- Each play-through gets a fresh `load_formulation()` call with a unique module name in `sys.modules`. The SZ5 role-mixing bug is structurally impossible.
- `GameRunner` holds an `asyncio.Lock` that serializes `apply_operator` calls — concurrent moves during parallel-input phases are safely serialized.
- Operator role filtering is enforced in two places: `_filter_ops_for_role()` limits what operators are sent to the client, and `_handle_apply()` checks `current_role_num == self.role_num` before forwarding to the runner.
- Bot moves go through the same `runner.apply_operator()` code path as human moves, so logs are consistent.
- The parallel-input guard on undo (checking `prev_state.parallel`) prevents a player from backing out of a secret commitment.

**Implementation decisions (notable):**
- `_broadcast_state()` sends a *base payload with no `vis_html`*; each `GameConsumer` instance independently calls `render_vis_for_role(state, role_num)` to compute and attach its own role-specific HTML before forwarding to the browser. This is the correct solution to the role-specific visualization problem and avoids broadcasting separate payloads per role.
- `inspect.signature` is used to detect whether a vis module's `render_state` accepts `role_num` and/or `instance_data`, providing backward compatibility without requiring vis files to be updated.
- `trigger_bots_for_session()` is module-level with a safety-limit loop (max 20 iterations) and uses `asyncio.ensure_future` from the lobby at game start to avoid scheduling bots before `game_starting` messages reach browsers.

**Technical debt:**
- **L1 (Parameterized operators — biggest gap):** `get_ops_info()` includes `params` in the operator dict, but `game.html`'s `renderOps()` renders every operator as a plain `<button>` regardless. Any game requiring parameter input (e.g., Guess My Age, Missionaries) will have broken operator UX or silent failures.
- **L3 (No role roster on game page):** The `state_update` carries `current_role_num` and `your_role_num` but no role names or player names. Players cannot see who is playing which role.
- **L4 (No new play-through within session):** After a goal, only "New Session with Same Players" (full session recreation) is available. The plan and the Phase 3 handoff both describe a lighter `request_new_playthrough` path that reuses the same session and GDM directory. The `parent_session` FK exists on the DB model but is unused.
- **L5 (No disconnect/reconnect handling):** `GameConsumer.disconnect()` removes the player from the Channel group but takes no other action. A disconnected player stalls the game. No reconnect window, no auto-pause, no owner notification.
- **L6 (No operator description display):** Operator `description` attributes are not returned by `get_ops_info()` and not rendered in the UI.

---

### 5. Game Persistence and Checkpointing

**Design intent:** JSONL append-only log (`log.jsonl`), checkpoint JSON files, pause/resume flow, continuous log across pause/resume cycles.

**Implemented:** Fully. One `log.jsonl` per play-through, continuous across `game_paused` / `game_resumed` events. `save_checkpoint` / `load_checkpoint` save/restore the game state and step. The `PlayThrough` DB record is updated on step, pause, and completion. The session store tracks `latest_checkpoint_id`.

**Implementation decisions:**
- `state_stack` is *not* checkpointed. On resume, undo history before the pause is lost. This is documented and accepted for the current phase.
- The GDM log uses a flat `events` structure. The schema is simple but the operator-applied event carries `op_name` redundantly (it could be derived from the game's `operators` list), which adds robustness to replay without the PFF.

**Technical debt:**
- No continuation-session linking: the `parent_session` FK on `GameSession` exists but `_handle_rematch()` does not set it. The chain of session lineages is not preserved in the database.
- The `session_dir` is derived from the old session's path in `_handle_rematch()` using `os.path.dirname` three levels up — brittle if the GDM directory structure ever changes.
- No cleanup of ended sessions from `session_store`. Over a long server uptime the in-memory dict grows indefinitely.

---

### 6. Debug Mode

**Design intent:** Game admin clicks "Start in Debug Mode"; server creates a session with simulated players; browser opens multiple tabs/iframes, one per role.

**Implemented:** Stub only. `views.debug_launch()` renders `debug.html` which exists but has no multi-iframe logic — it's a static placeholder page. The Phase 3 handoff documented the complete implementation plan for Phase 4 but it was not executed.

**Technical debt:** This is a complete gap for its intended users (game developers testing role-specific visualizations). The detailed implementation plan in `Phase_3_completed_and_Phase_4_handoff.md` §5.2 is ready to implement.

---

### 7. Observer Mode

**Design intent:** Admin connects to `ObserverConsumer`, joins the game group, receives unfiltered state updates, can switch player perspectives.

**Implemented:** Stub only. `observer_consumer.py` accepts the WebSocket connection and sends `{type: 'observer_stub', ...}`, then does nothing. The `routing.py` URL is in place. All the detailed behavior spec is in the Phase 4 handoff.

**Technical debt:** A complete gap. The implementation is straightforward since the `game_<session_key>` Channel group already carries all the needed events. The Phase 4 handoff §5.1 is ready to implement.

---

### 8. Research Data Access

**Design intent:** Research admin dashboard with session list/filter, log viewer rendering `log.jsonl` step-by-step, export endpoint.

**Implemented:** Placeholder only. `research/views.py` has a `dashboard` view and `research/dashboard.html` template exists, but they contain no real functionality beyond a link to the sessions list. No log viewer, no export, no analytics.

**Technical debt:** This is Phase 5 in the original plan, not yet started. All the structural prerequisites (GDM log files, `PlayThrough` DB records, session summaries) are in place — the research views just need to be written.

---

### 9. Scaling

**Design intent:** Single server handles 10–50 simultaneous sessions today; path to horizontal scaling documented.

**Current state:** The implementation correctly notes in `session_store.py` that the module-level dict is single-process only and references the Phase 7 Redis upgrade path. The InMemoryChannelLayer is also single-process. For development and small deployments this is fine.

**Technical debt:**
- No Redis channel layer in production configuration.
- No session persistence across worker restarts.
- No load testing has been done.
- Celery is configured (settings has `CELERY_BROKER_URL`) but no Celery tasks exist — it would need to be started if email is required.

---

### 10. Visualization System (Vis-Features milestones)

**Design intent (VIS_DEV_PLAN.md):** Eight milestones M0–M8 for visualization rendering, image resources, interactive vis, full-screen, previous-state toggle, transitions, audio, and vis-debug mode.

| Milestone | Status |
|---|---|
| M0 — Transition History | **Complete** |
| M1 — Basic Vis Rendering | **Complete** (SVG board, text fallback, role-aware rendering added in "Role-Specific Vis" session) |
| M2 — Image Resources | **Complete** (`game_asset` view, path-traversal protection, `Cache-Control`) |
| M3 — Interactive Vis | **Complete** (Tier-1 SVG `data-op-index`, Tier-2 canvas regions with `#wsz6-regions` JSON script block) |
| M4 — Full-Screen Mode | **Complete** (confirmed committed before M5 plan was written) |
| M5 — Previous-State Toggle | **Plan written** (`Vis-M5-Plan.md`); implementation not yet confirmed committed |
| M6 — Visual Transitions | **Not started** |
| M7 — Audio Support | **Not started** |
| M8 — Vis-Debug Mode | **Not started** |

**Implementation decision (vis module connection):** The VIS_DEV_PLAN described auto-discovery via filename convention (`<slug>_WSZ6_VIS.py` loaded by `pff_loader`). The actual implementation is PFF-driven: the PFF sets `self.vis_module = imported_vis_module` explicitly. This was chosen for explicitness (no magic scanning). The downside is that every PFF must be modified to add vis — you cannot add visualization to a game without touching its PFF. This creates two separate game catalog entries (`tic-tac-toe` and `tic-tac-toe-vis`) for what is logically one game.

**Implementation decision (Tier-2 canvas):** For hit-testing on raster images (Pixel Probe, Click-the-Word), a `<script id="wsz6-regions" type="application/json">` element embedded in the vis HTML defines clickable regions in normalized coordinates. The game.html JavaScript parses this and draws an invisible `<canvas>` overlay for hit-testing. This is clever and avoids requiring vis modules to generate JavaScript directly, but the protocol (the JSON schema for `wsz6-regions`) is only defined implicitly by these two games.

**Technical debt:**
- The `instance_data` protocol — how a PFF sets `formulation.instance_data` for the vis renderer to read per-game-instance constants (e.g., OCCLUEdo's dealt cards) — is informal and undocumented. It works because `initialize_problem()` can set attributes on `self` (the formulation), but there is no stated contract.
- No auto-discovery of vis modules by filename convention means every PFF must be modified to use vis.
- M6–M8 not started, so visual polish (transitions, audio, development iteration speed) is missing.
- No `game_asset_url()` helper for vis files to construct asset URLs portably — vis authors must hard-code the URL pattern `/play/game-asset/<slug>/<path>`.

---

## Part II — Major Implementation Decisions (Summary)

| Decision | What was chosen | Rationale | Trade-off |
|---|---|---|---|
| Single Django process | Admin + play in one project | Simpler dev setup, no inter-service auth | Cannot deploy components independently; some cross-imports exist |
| SQLite in dev | Zero-dependency dev setup | Fast onboarding | Must migrate to PostgreSQL before production |
| InMemory channel layer | No Redis needed in dev | Fast setup | Single-process; sessions lost on restart |
| `session_store` dict | Module-level dict + Lock | Simple, fast, no DB overhead for hot state | Not production-scalable; no persistence |
| PFF-driven vis loading | `self.vis_module = …` in PFF | Explicit, verifiable | Requires PFF modification; separate catalog entries for vis/no-vis variants |
| Role-specific vis per consumer | Each consumer calls `render_vis_for_role()` | Correct and efficient (one broadcast, N renders) | Vis rendering runs N times per move (once per connected player) |
| `inspect.signature` for vis compat | Detect `role_num`/`instance_data` params | Backward compat without requiring vis file updates | Slight overhead; fragile if vis authors use `*args`/`**kwargs` |
| Tier-2 JSON regions | Embedded `<script type="application/json">` | No JS in vis files; vis is pure HTML/SVG | Protocol not formally specified; only two games use it |

---

## Part III — Storage Organization: Issues and Recommendations

### Current state

The game files are spread across three separate locations with no clear principle governing what goes where:

```
SZ6_Dev/
├── Textual_SZ6/               ← SOLUZION6 base library + original game PFFs
│   ├── soluzion6_02.py        ← shared base library (source of truth)
│   ├── Tic_Tac_Toe_SZ6.py
│   ├── Missionaries_SZ6.py
│   ├── Tic_Tac_Toe_SZ6_with_vis.py   ← web-specific wrapper PFF
│   └── Tic_Tac_Toe_WSZ6_VIS.py       ← vis module
├── games_repo/                ← installed runtime copies
│   ├── tic-tac-toe/
│   │   ├── Tic_Tac_Toe_SZ6.py
│   │   └── soluzion6_02.py    ← copied here (1 of N copies)
│   ├── tic-tac-toe-vis/
│   │   ├── Tic_Tac_Toe_SZ6_with_vis.py
│   │   ├── Tic_Tac_Toe_WSZ6_VIS.py
│   │   └── soluzion6_02.py    ← another copy
│   ├── occluedo/
│   │   ├── OCCLUEdo_SZ6.py
│   │   ├── OCCLUEdo_WSZ6_VIS.py
│   │   ├── OCCLUEdo_images/   ← ~25 image files
│   │   └── soluzion6_02.py
│   └── ...  (10 game dirs, each with its own soluzion6_02.py)
└── WSP6-portal/Claudes-plan-2/
    └── Vis-Features-Dev/
        └── game_sources/      ← newer game sources (split from Textual_SZ6)
            ├── OCCLUEdo_SZ6.py
            ├── OCCLUEdo_WSZ6_VIS.py
            └── OCCLUEdo_images/
```

### Specific problems

**Problem 1 — Game sources are split across two directories based on development history, not any logical principle.**
`Tic_Tac_Toe_SZ6.py` is authored in `Textual_SZ6/`; `OCCLUEdo_SZ6.py` is in `Vis-Features-Dev/game_sources/`. The `install_test_game` command has a `source_dir` override per game entry to handle this. This is accidental organization: as new games are created in future dev sessions they will go wherever that session's working directory happens to be.

**Problem 2 — `soluzion6_02.py` is copied into every game directory (currently 10+ copies).**
The `pff_loader` adds the game directory to `sys.path` so PFFs can do `from soluzion6_02 import ...`. The easiest way to satisfy this was to copy the base library into every game's directory. This means: (a) any bug fix in `soluzion6_02.py` requires reinstalling every game, and (b) different game sessions can be running against slightly different versions of the base library.

**Problem 3 — Vis files and PFFs are in the same flat game directory but associated only by PFF import, not by naming.**
There is no enforced layout within a game directory. Vis files, images, and the base library sit alongside the PFF without structure. For a game like OCCLUEdo with 25 images this already feels crowded.

**Problem 4 — Two catalog entries for games that differ only by having a vis module.**
`tic-tac-toe` and `tic-tac-toe-vis` are separate `Game` records, separate game directories, and separate PFF files — because adding vis requires a new PFF that imports the vis module. The game is logically one game with an optional visual layer.

**Problem 5 — No canonical `game_asset_url()` for vis authors.**
Vis files must hard-code the URL pattern `/play/game-asset/<slug>/<filename>`. If the URL structure changes, every vis file breaks. The VIS_DEV_PLAN described a `game_asset_url("filename.png")` helper injected by the loader, but this was not implemented.

---

### Recommended reorganization

#### A. Separate source tree from runtime tree (already partially done)

Create a `SZ6_Dev/game_sources/` directory as the single canonical home for all authored game files:

```
SZ6_Dev/
├── game_sources/              ← all authored game files (source of truth)
│   ├── tic_tac_toe/
│   │   ├── Tic_Tac_Toe_SZ6.py
│   │   └── Tic_Tac_Toe_WSZ6_VIS.py
│   ├── missionaries/
│   │   └── Missionaries_SZ6.py
│   ├── occluedo/
│   │   ├── OCCLUEdo_SZ6.py
│   │   ├── OCCLUEdo_WSZ6_VIS.py
│   │   └── OCCLUEdo_images/
│   └── ...
├── games_repo/                ← installed runtime copies (generated; git-ignored)
└── Textual_SZ6/               ← textual engine only; no web game files
    ├── Textual_SOLUZION6.py
    └── soluzion6_02.py        ← single source of truth for the base library
```

Update `install_test_game` to source all games from `game_sources/` rather than `Textual_SZ6/` and `Vis-Features-Dev/game_sources/`. Remove the `source_dir` override per game.

#### B. Solve the `soluzion6_02.py` duplication problem

The cleanest fix is to add the `Textual_SZ6/` directory (or a dedicated `shared_lib/` directory) to `sys.path` in `pff_loader.load_formulation()` *before* adding the game directory:

```python
# pff_loader.py — add once, near the top of load_formulation()
shared_lib_dir = str(Path(settings.BASE_DIR).parent.parent.parent / 'Textual_SZ6')
if os.path.isdir(shared_lib_dir) and shared_lib_dir not in sys.path:
    sys.path.insert(0, shared_lib_dir)
```

This means `soluzion6_02.py` does not need to be in each game directory. The `install_test_game` command stops copying it. The `games_repo/` directories become leaner — just the game-specific files.

If portability to environments where `Textual_SZ6/` is not present is required, a better option is to package `soluzion6_02.py` as a proper Python package (`soluzion6`) installed into the virtualenv. Games would then `from soluzion6 import ...` rather than `from soluzion6_02 import ...`.

#### C. Enable auto-discovery of vis modules (optional but impactful)

Add `load_vis_module()` to `pff_loader.py` that looks for `<slug>_WSZ6_VIS.py` (or the PFF filename with `_WSZ6_VIS` suffix) in the game directory. The lobby consumer would call it after loading the PFF and attach `formulation.vis_module` if found. This eliminates the need to create wrapper PFFs (`Tic_Tac_Toe_SZ6_with_vis.py`) and collapses `tic-tac-toe` and `tic-tac-toe-vis` back to a single catalog entry.

The PFF-set `self.vis_module` would take precedence, preserving backward compatibility. The convention-based discovery is the fallback.

#### D. Add a `game_asset_url()` helper

In the lobby consumer, after loading the formulation and vis module, set a module-level attribute on the vis module:

```python
vis_module._game_asset_base = f"/play/game-asset/{game_slug}/"
```

Vis files can then call:

```python
def _asset(filename):
    return getattr(_vis_module_ref, '_game_asset_base', '/') + filename
```

Or, more elegantly, accept a `base_url` keyword argument in `render_state` (detected via `inspect.signature`, consistent with the `role_num` pattern already in place).

#### E. Add a `metadata.json` file to each game directory at install time

The `validate_and_extract` installer (or `install_test_game`) should write a `metadata.json` to the game directory:

```json
{
  "slug": "tic-tac-toe",
  "name": "Tic-Tac-Toe",
  "version": "1.0",
  "min_players": 2,
  "max_players": 27,
  "installed_at": "2026-02-20T...",
  "vis_module": "Tic_Tac_Toe_WSZ6_VIS.py"
}
```

This makes the game directory self-contained and self-documenting. It also provides a manifest that a future "bulk install from directory scan" workflow could use without needing a running database.

---

## Part IV — Summary of Technical Debt by Priority

### High priority (affects current usability)

| Issue | Location | Effort |
|---|---|---|
| Parameterized operator UI (L1) | `game.html` renderOps() + `game_consumer` | Medium |
| Disconnect/reconnect handling (L5) | `game_consumer.disconnect()` + new auto-pause timer | Medium |
| `soluzion6_02.py` duplication | `pff_loader.py` + `install_test_game.py` | Low |
| M5 previous-state toggle | `game.html` only | Low (plan complete) |

### Medium priority (affects developer experience and feature completeness)

| Issue | Location | Effort |
|---|---|---|
| Observer consumer (Phase 4) | `observer_consumer.py` (plan is complete) | Medium |
| Debug launcher (Phase 4) | `views.debug_launch` + `debug.html` | Medium |
| Role roster on game page (L3) | `game_runner._build_base_payload()` + `game.html` | Low |
| New play-through within session (L4) | `game_consumer` + `game.html` | Medium |
| Operator description display (L6) | `get_ops_info()` + `game.html` | Trivial |
| Auto-discovery of vis modules | `pff_loader.py` + `lobby_consumer.py` | Low |
| `game_asset_url()` helper for vis authors | `pff_loader.py` or `lobby_consumer.py` | Low |
| `parent_session` FK not set on rematch | `game_consumer._handle_rematch()` | Trivial |
| Game source tree consolidation | `install_test_game.py` + filesystem | Low |

### Lower priority (production hardening)

| Issue | Location | Effort |
|---|---|---|
| Redis channel layer + session store | `settings/production.py` + `session_store.py` | Medium |
| Research dashboard (Phase 5) | `research/` app | High |
| `game_access_level` enforcement | `games_catalog/views.py` | Low |
| Session store cleanup (GC ended sessions) | `game_consumer._run_game_ended()` | Low |
| M6 transitions, M7 audio | `game.html` + `game_runner.py` | Medium each |
| Production settings / HTTPS | `settings/production.py` + nginx | High |
| `soluzion6_02.py` as proper package | venv + all PFFs | Medium |
| Live sessions panel real-time update | `dashboard/views.py` + template | Low |
