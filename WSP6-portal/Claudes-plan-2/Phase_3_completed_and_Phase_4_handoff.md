# Phase 3 Completed — Phase 3B and Phase 4 Handoff

**Date:** 2026-02-19
**Prepared by:** Claude Sonnet 4.6
**Branch:** `master` — all work committed and pushed to `origin/master`
**Last commit:** `e21e19c Fix hung game when bot plays first or all roles are bots`

---

## 1. What Phase 3 Delivered (fully complete and verified)

All items from the Phase 3 spec are done, plus several unplanned additions made
while resolving bugs and user-reported issues.

### 3.1 Core Phase 3 spec items

| Feature | Status | Key files |
|---------|--------|-----------|
| Checkpoint save/load | ✓ | `wsz6_play/persistence/checkpoint.py` |
| Pause flow (owner-only, broadcasts `game_paused`) | ✓ | `game_consumer._handle_pause` |
| Resume flow (lobby shows "Resume" mode, owner clicks "Resume Session") | ✓ | `lobby_consumer._resume_from_checkpoint`, `views.join_session` |
| Continuous GDM log across pause/resume | ✓ | Same `log.jsonl`, `game_paused` + `game_resumed` events appended |
| Bot player (`'random'` and `'first'` strategies) | ✓ | `wsz6_play/engine/bot_player.py` |
| Bot assignment in lobby (owner sees "+ Bot" per empty role) | ✓ | `lobby_consumer._handle_assign_bot`, `join.html` |
| PlayThrough DB record updated on game end and pause | ✓ | `session_sync.push_playthrough_ended`, `push_playthrough_step` |
| Resume/Join/Rejoin links in all session-listing views | ✓ | `templates/sessions_log/list.html`, `games_catalog/detail.html` |
| GDM database migrated correctly in setup script | ✓ | `run_phase2_tests.sh` (explicit `--database gdm` step) |

### 3.2 Additions made beyond the Phase 3 spec

| Addition | Motivation | Key files |
|----------|-----------|-----------|
| "New Session with Same Players" rematch button | User request after game end | `game_consumer._handle_rematch`, `game.html` |
| Role unassignment (× button on every chip) | Bug: bot assignments were irreversible in rematch lobby | `lobby_consumer._handle_unassign_role`, `join.html` |
| Role reassignment from role table (click chip → "Assign here") | Bug: no way to change a pre-assigned role in rematch lobby | `role_manager.assign_role` (bot eviction), `join.html` |
| Bot-first move triggering fix | Bug: game hung when bot holds role 0 | `trigger_bots_for_session()` + `asyncio.ensure_future` in lobby |
| Undo-to-bot triggering | Bug: undo could land on bot's turn with no trigger | `game_consumer._handle_undo` now calls `_trigger_bots` |
| Django 5 logout fix (POST form) | Bug: `LogoutView` requires POST; nav had a GET link | `templates/base.html` |
| Non-owner hint text hidden | UX: non-owners saw instructions for owner-only actions | `join.html` (hidden until `isOwner` confirmed over WS) |
| Undo button disabled when nothing to undo | UX: button was always enabled | `game.html` (disabled at load; toggled per `msg.step`) |
| Copy URL to Clipboard button in lobby | UX: easier URL sharing | `join.html` (`navigator.clipboard.writeText`) |
| No "Your turn!" after game ends | UX: banner persisted incorrectly after last move | `game.html` (`!msg.is_goal` guard) |

---

## 2. Exact current codebase state

### Directory tree (wsz6_portal/wsz6_play only — modified in Phase 3)

```
wsz6_play/
├── consumers/
│   ├── lobby_consumer.py     ← full Phase 3 lobby: bots, unassign, pause resume, bot-first trigger
│   └── game_consumer.py      ← full Phase 3 game: pause, rematch, trigger_bots_for_session()
├── engine/
│   ├── pff_loader.py         ← unchanged from Phase 2
│   ├── game_runner.py        ← unchanged from Phase 2
│   ├── state_serializer.py   ← unchanged from Phase 2
│   ├── bot_player.py         ← NEW: BotPlayer (random, first; asyncio.sleep delay)
│   └── role_manager.py       ← MODIFIED: strategy slot; assign_role evicts bots cleanly
├── persistence/
│   ├── checkpoint.py         ← NEW: save_checkpoint / load_checkpoint
│   ├── gdm_writer.py         ← unchanged from Phase 2
│   └── session_sync.py       ← MODIFIED: push_playthrough_ended, push_playthrough_step added
├── session_store.py          ← unchanged; has latest_checkpoint_id, bots fields documented
├── models.py                 ← unchanged; PlayThrough + Checkpoint models already migrated
├── routing.py                ← unchanged; observer stub URL is present
└── views.py                  ← MODIFIED: paused branch, is_owner in game_page; debug_launch stub
```

### Session store fields (complete current list)

```
session_key             str                 UUID string
game_slug               str
game_name               str
owner_id                int | None
pff_path                str
status                  str                 'lobby' | 'in_progress' | 'paused' | 'ended'
role_manager            RoleManager | None
game_runner             GameRunner | None
gdm_writer              GDMWriter | None
playthrough_id          str | None
latest_checkpoint_id    str | None          UUID hex of most recent checkpoint
bots                    list                BotPlayer instances (empty if no bots)
session_dir             str                 Absolute path to GDM session directory
started_at              str                 ISO 8601 UTC timestamp
```

### Key module-level functions added to game_consumer.py

```python
# Standalone — called by lobby_consumer via deferred import + ensure_future
async def trigger_bots_for_session(session_key: str) -> None: ...

# Standalone — called by both GameConsumer._on_game_ended and trigger_bots_for_session
async def _run_game_ended(session_key, session, runner, gdm_writer,
                          _already_logged=False) -> None: ...
```

### Known stubs (not yet implemented)

- `views.debug_launch` — renders `wsz6_play/debug.html` which does not exist yet
- `ObserverConsumer` — referenced in `routing.py` but the class is not implemented
- `wsz6_play/consumers/observer_consumer.py` — file does not exist

---

## 3. Current limitations to address in Phase 3B and Phase 4

### L1 — Parameterized operators (no UI input form)
`GameRunner.get_ops_info()` returns `'params': list(op.params)` for every operator.
The game page's `renderOps()` ignores `params` entirely and emits a plain `<button>`.
When a player clicks, `applyOp(index)` sends `{type:'apply_operator', op_index}` with no
`args`. `game_consumer._handle_apply` calls `runner.apply_operator(op_index, args=None)`.
Any operator that requires parameters will either crash or silently produce wrong output.
**This is the single biggest functional gap for any game beyond Tic-Tac-Toe.**

### L2 — State displayed as plain text only
`state_update` sends `state_text: str(state)` (rendered in a monospace `<pre>`).
There is no hook for PFF-defined HTML rendering (e.g., a visual grid, colored squares,
styled table). Games that define `state.to_html()` or `state.html_view_for_role(n)` can't
use it.

### L3 — No player roster on the game page
The game page shows "Your turn!" / "Waiting for another player…" but gives no view of
who is playing which role. The `state_update` message carries `current_role_num` and
`your_role_num` but no role-name or player-name list. Players have no way to know
who else is in the session.

### L4 — No new play-through within a session
After a goal, the only option is "New Session with Same Players" (creates an entirely new
session, new session key, new lobby). The original plan envisioned multiple play-throughs
within one session (the `parent_session` FK already exists on `GameSession` and the GDM
directory structure supports multiple `playthroughs/<id>/` subdirs). A lighter
"New Play-through" option would reuse the existing session and lobby, avoiding the need
to navigate away.

### L5 — No disconnect/reconnect handling
If a player's browser disconnects during a game, the game simply stalls on that player's
turn. The GameConsumer's `disconnect()` removes the player from the Channel group but does
nothing else. No reconnect window, no auto-pause, no notification to owner.

### L6 — Operator description not displayed
Operators may have a `description` attribute. It is not in the `get_ops_info()` output and
not shown in the UI (only `op.name` is visible).

---

## 4. Phase 3B — Game-playing UI Affordances

**Goal:** Make the game page rich enough to support the full range of SOLUZION6 games, not
just Tic-Tac-Toe. No new backend consumers or database models are needed — all changes are
in the game loop between `game_consumer.py`, `game_runner.py`, and `game.html`.

### 4.1 Parameterized operators (highest priority)

#### What a param looks like in the PFF
```python
class SZ_Operator:
    params = [SZ_Param(name='x', type='int', min=0, max=2),
              SZ_Param(name='y', type='int', min=0, max=2)]
```

#### Changes needed

**`game_runner.get_ops_info()`** — add param metadata to each operator dict:
```python
result.append({
    ...
    'params': [
        {'name': p.name, 'type': p.type,
         'min': getattr(p,'min',None), 'max': getattr(p,'max',None),
         'options': list(p.options) if getattr(p,'options',None) else None}
        for p in (op.params or [])
    ],
})
```
(Check the actual `SZ_Param` attribute names against `soluzion6_02.py` — they may differ.)

**`game.html` — `renderOps()`** — when `op.params` is non-empty, render input widgets
instead of a plain button:
- `int` / `float` → `<input type="number">`
- `str` → `<input type="text">`
- options list → `<select>`
- Submit with a small "Apply" button that collects param values and calls
  `applyOp(op.index, [val1, val2, ...])`

**`window.applyOp`** — accept an optional second argument and include it in the WS send:
```javascript
window.applyOp = function(opIndex, args) {
    send({ type: 'apply_operator', op_index: opIndex, args: args || null });
};
```
`game_consumer._handle_apply` already reads `content.get('args')` and passes it through
`runner.apply_operator(op_index, args)`, so no server-side change is needed.

### 4.2 HTML state rendering

**Protocol (add to PFF documentation):**
If `state.to_html()` exists, return an HTML string for the game area.
If `state.to_html_for_role(role_num)` exists, return role-specific HTML.
Otherwise fall back to `str(state)` (current behaviour).

**`game_runner._broadcast_state()`** — add:
```python
try:
    state_html = (
        state.to_html_for_role(???)   # role_num not available here — see note
        if hasattr(state, 'to_html_for_role')
        else state.to_html()
        if hasattr(state, 'to_html')
        else None
    )
except Exception:
    state_html = None
payload['state_html'] = state_html
```

> **Design note on role-specific HTML:** `_broadcast_state` broadcasts to the whole group;
> it does not know individual role numbers. Two options:
> (a) Broadcast generic `state.to_html()` and let each consumer call
>     `state.to_html_for_role(self.role_num)` in the `state_update` channel handler
>     — requires the state to be re-instantiated per player, or
> (b) Broadcast `state_html` as the generic form; role-specific rendering is reserved
>     for a future observer/perspective feature.
> Option (b) is simpler. Implement it first.

**`game_consumer.state_update` channel handler** — include `state_html` in the forwarded
message (it is already passed through via `{**event, ...}`).

**`game.html`** — in `onStateUpdate`:
```javascript
const displayEl = document.getElementById('state-display');
if (msg.state_html) {
    displayEl.innerHTML = msg.state_html;   // rendered HTML
} else {
    displayEl.textContent = msg.state_text; // plain text fallback
}
```
Change the `<pre id="state-display">` to a `<div id="state-display">` so injected HTML
renders correctly. Keep the monospace style as a default CSS class that PFF HTML can
override.

### 4.3 Players / roles panel on the game page

**Server side** — add role roster to `state_update`:
In `game_runner._broadcast_state()`, include a `role_roster` field:
```python
rm = self.role_manager
payload['role_roster'] = [
    {'role_num': p.role_num, 'role_name': rm.roles_spec.roles[p.role_num].name,
     'player_name': p.name, 'is_bot': p.is_bot}
    for p in rm.get_assigned_players()
]
```

**Client side** — render a compact panel beneath the operators list (or in the right card):
```
Roles:
  X — owner1        ← current player highlighted
  O — 🤖 Bot-O
```
Highlight the currently active role with a CSS class. Update on every `state_update`.

### 4.4 New play-through within a session

After `goal_reached`, instead of (or alongside) the "New Session with Same Players"
button, offer a "▶ New Play-through" button (owner only). This button sends:
```json
{"type": "request_new_playthrough"}
```

**`game_consumer._handle_new_playthrough(session)`:**
1. Owner-only, session must be `'ended'`.
2. Load a fresh formulation instance.
3. Create a new `playthrough_id`.
4. Create new GDM dirs under the **same** `session_dir`.
5. Create a new `PlayThrough` DB record.
6. Reset runner: `runner.start()` on the fresh formulation.
7. Update `session_store`: `{'status':'in_progress', 'game_runner': runner, ...}`.
8. Write `game_started` event to the new log.
9. Broadcast `{'type': 'new_playthrough_ready'}` to game group.

**Client side** — `onNewPlaythroughReady(msg)`: reset `gameOver = false`, hide goal
banner, re-enable controls. Players stay on the same game page — no redirect.

This reuses the existing session and avoids the full lobby round-trip. The UARD
`GameSession` record stays at `'in_progress'` status until the owner explicitly ends the
session (a future feature), or another play-through reaches a goal and rematch is not
requested.

### 4.5 Operator descriptions (small addition)

Add `'description'` to `get_ops_info()` output (if `op` has a `description` attribute).
In `game.html`, render it as a `title` attribute on the button (tooltip on hover).

### 4.6 Files to modify in Phase 3B

| File | Change |
|------|--------|
| `wsz6_play/engine/game_runner.py` | `get_ops_info`: add description; `_broadcast_state`: add `state_html`, `role_roster` |
| `wsz6_play/consumers/game_consumer.py` | Add `request_new_playthrough` handler |
| `templates/wsz6_play/game.html` | Param input widgets, HTML rendering, role panel, new play-through button |

No new migrations, no new URL routes, no new consumers needed for Phase 3B.

---

## 5. Phase 4 — Observer Mode and Debug Launcher

These items are directly from the original development plan (Section 10, Phase 4).

### 5.1 ObserverConsumer

**URL:** `ws://<host>/ws/observe/<session_key>/`
**File to create:** `wsz6_play/consumers/observer_consumer.py`
The URL is already defined in `routing.py` — the consumer class just needs to be written.

**Behaviour:**
- Connect: require authenticated user; require `is_any_admin` permission (or a special
  observer token issued by the admin panel).
- Join the `game_<session_key>` Channel group (same group as game players).
- Receive all `state_update` broadcasts — **do not filter operators by role** (observers
  see the full operator list and full state).
- Cannot send `apply_operator` or `request_pause` (read-only).
- On connect, immediately send the current game state (same as `GameConsumer.connect()`
  does today, but with no role filtering).

**Perspective switching (optional for first pass):**
A dropdown lets the observer choose a player's perspective (applies `_filter_ops_for_role`
client-side). This is a pure frontend change; the server always sends the unfiltered view.

**Channel handler additions** (same as GameConsumer):
- `state_update(event)` — forward as-is (no role filtering)
- `transition_msg(event)`, `goal_reached(event)`, `game_paused(event)` — forward as-is

**Admin game page changes:**
In `templates/wsz6_admin/dashboard/live_sessions.html` (or the relevant admin template),
add an "Observe" link per live session that navigates to an observer page.

**Observer page:** `templates/wsz6_play/observe.html` — essentially `game.html` but:
- No "Pause" button, no "Undo" button, no operator click handlers.
- A "Perspective" dropdown at the top to choose which role's operator view to display.
- Label: "Observing as [role name]" or "Observing (all roles)".

### 5.2 Debug launcher

**Current state:** `views.debug_launch(request, game_slug)` is a stub that renders a
non-existent `wsz6_play/debug.html`.

**Goal:** Game admin clicks "▶ Start in Debug Mode" on the game detail page and gets
**one browser page with multiple game-view panels**, one per role, all driven by the
same session. This lets the admin see every role's display simultaneously and test
role-specific operator rendering.

**Implementation:**

1. **`views.debug_launch`** — rewrite:
   - Create a new session in `session_store` (key = UUID, owner = admin user, status = lobby).
   - Create a `GameSession` DB record marked with `status='dev'` or tagged debug (add a
     `is_debug` boolean field, or just use a naming convention in the session key).
   - Load the formulation; build a `RoleManager`; assign one simulated player token per
     role.
   - Start the game immediately (skip the lobby): call `runner.start()`.
   - Return all `(role_name, game_page_url)` pairs to the template.

2. **`templates/wsz6_play/debug.html`** — render multiple `<iframe>` elements, one per
   role, each pointing to the corresponding `game_page_url`. Use a CSS grid so all panels
   are visible simultaneously.

3. No new WebSocket consumer needed — each iframe connects to the existing `GameConsumer`
   using its own role token, exactly as a normal player would.

**Cleanup:** Debug sessions should not pollute the sessions list. Options:
- Filter them out of `sessions_log/list.html` based on a flag, or
- Store them under a separate status value (e.g., `'debug'`).
- GDM logs for debug sessions can be written to `GDM_ROOT/<slug>/debug/<session_key>/`
  and excluded from research queries.

### 5.3 Admin live sessions panel (real-time)

**Current state:** `dashboard/views.py` has a `live_sessions` view that renders
a static list from the session store. It is not updated in real time.

**Goal:** The live sessions panel auto-refreshes without page reload; newly started and
just-ended sessions appear/disappear as they happen.

**Implementation options:**

**(a) Simple polling (quickest):** Add a small `<script>` that calls
`setInterval(() => htmx.trigger('#live-list', 'refresh'), 5000)` (or a plain
`fetch` + DOM update). A Django view endpoint returns the current session list as an HTML
fragment. No Channel Layer required. Suitable for the admin-only low-traffic panel.

**(b) WebSocket subscription (richer):** Create an `AdminMonitorConsumer` that subscribes
to a `admin_monitor` Channel group. `lobby_consumer` and `game_consumer` already have
the right places to emit events; add `group_send` calls to `admin_monitor` on session
start, status changes, and session end. The admin dashboard JavaScript listens and updates
the DOM.

Recommendation: start with **(a)** (much simpler) and upgrade to (b) in Phase 7 if needed.

### 5.4 Files to create / modify in Phase 4

| File | Action | Notes |
|------|--------|-------|
| `wsz6_play/consumers/observer_consumer.py` | **CREATE** | `ObserverConsumer` class |
| `templates/wsz6_play/observe.html` | **CREATE** | Observer UI (game.html variant, read-only) |
| `wsz6_play/views.py` | **MODIFY** | Rewrite `debug_launch` stub |
| `templates/wsz6_play/debug.html` | **CREATE** | Multi-iframe debug view |
| `wsz6_admin/dashboard/views.py` | **MODIFY** | Add live-session AJAX/HTMX endpoint |
| `templates/wsz6_admin/dashboard/live_sessions.html` | **MODIFY** | Add Observe link; live refresh |

No new migrations needed. The `ObserverConsumer` URL is already in `routing.py`.

---

## 6. Design decisions to carry forward

1. **Bot moves go through the same code path as human moves.**
   `BotPlayer.maybe_move()` calls `runner.apply_operator()` directly. Logs and broadcasts
   are identical to human moves. The GDM log distinguishes human vs bot only via the
   `role_num` field (the `RoleManager` knows which roles are bots).

2. **`trigger_bots_for_session(session_key)` is the single bot-loop entry point.**
   Call it with `asyncio.ensure_future(...)` whenever the game transitions to a bot's
   turn outside the normal `_handle_apply` flow (game start, resume, undo). Never call
   it directly (it contains `asyncio.sleep`).

3. **Single continuous `PlayThrough` per pause/resume cycle.**
   One `playthrough_id` + one `log.jsonl` per uninterrupted play-through. `game_paused`
   and `game_resumed` events are written to the same log. A new `PlayThrough` record is
   only created when a new play-through literally starts (new `runner.start()`).

4. **`state_stack` is NOT checkpointed.** On resume, `state_stack = [restored_state]`
   (undo history from before the pause is lost). Acceptable for the current phase.

5. **`session_store` is in-process memory (single-worker only).** Suitable for dev and
   small deployments. Phase 7 replaces it with Redis. Any new code that reads/writes
   session state must go through `session_store.get_session()` / `update_session()`.

6. **Deferred imports to avoid circular imports.**
   `game_consumer.py` imports from `lobby_consumer.py` (for `_default_roles_spec`).
   `lobby_consumer.py` imports from `game_consumer.py` (for `trigger_bots_for_session`).
   Both use deferred imports *inside* the calling function to prevent module-level
   circular imports. This pattern is established — follow it for any new cross-consumer
   imports.

7. **Operator role filtering is client-side AND server-side enforced.**
   `_filter_ops_for_role` in `game_consumer` filters which operators are sent.
   `_handle_apply` checks `state.current_role_num == self.role_num` before applying.
   Both guards must remain in place.

8. **Bot-first triggering uses `asyncio.ensure_future` with role check.**
   Only schedule the bot loop at game start if the initial `current_role_num` belongs to
   a bot. Don't schedule it unconditionally — when a human goes first, `_handle_apply`
   is sufficient.

---

## 7. How to reset and run the current dev environment

```bash
# From Claudes-plan-2/ (repo root)
bash run_phase2_tests.sh          # wipes DBs + GDM, migrates both databases, seeds data, starts server

# Or for setup without starting the server:
bash run_phase2_tests.sh --setup-only

# Dev users (all passwords: pass1234)
# admin, gameadm, owner1, owner2, player1, player2
# owner1 and owner2 have SESSION_OWNER type (can start sessions)
# admin and gameadm have game admin rights

# URLs
# http://localhost:8000/            — dashboard
# http://localhost:8000/accounts/login/
# http://localhost:8000/games/      — game catalogue
# http://localhost:8000/sessions/   — session log
```

---

## 8. Suggested Phase 3B → Phase 4 sequencing

The two phases can be worked independently (no blocking dependencies), but this order
minimises rework:

1. **Phase 3B.1 — Parameterized operators** (L1, highest player-facing impact)
2. **Phase 3B.2 — HTML state rendering** (L2)
3. **Phase 3B.3 — Role/players panel** (L3, small but rounds out the game UI)
4. **Phase 4.1 — ObserverConsumer** (straightforward; leverages existing game group)
5. **Phase 3B.4 — New play-through within session** (L4; best done after observer so
   the observer can handle the mid-session state transitions)
6. **Phase 4.2 — Debug launcher** (easiest last; reuses everything above)
7. **Phase 4.3 — Live sessions panel** (optional polish; polling version is trivial)

Phase 3B.5 (operator descriptions) and Phase 3B.6 (disconnect handling / L5) can be
slotted in anywhere and are low-risk.
