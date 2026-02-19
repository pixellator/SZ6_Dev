# Phase 3 Handoff

**Date:** 2026-02-19
**Status:** Phase 2 complete and manually verified end-to-end.
**Phase 3 goal:** Checkpoints, pause/resume, bot players.
**Milestone:** Owner pauses a running game, resumes it later (possibly with a bot filling a vacated role), and the GDM log is continuous across both sessions.

---

## 1. What is working right now

The full Phase 2 pipeline is verified operational:

| Step | Verified |
|------|---------|
| owner1 starts session → lobby page opens | ✓ |
| player1 joins lobby → appears in "Connected Players" | ✓ |
| owner1 assigns roles X / O, clicks "Start Game" | ✓ |
| both browsers redirect to `/play/game/<key>/<token>/` | ✓ |
| game page connects via WebSocket, state renders | ✓ |
| players apply operators in turn, board updates live | ✓ |
| goal reached → `goal_reached` message sent | ✓ |
| GDM `log.jsonl` written with all events | ✓ |
| `GameSession` updated to "Completed" in UARD | ✓ |

### Bug fixed in this session

**`lobby_consumer.py` — `disconnect()` was wiping the RoleManager.**

When the browser navigates from the lobby page to the game page it closes the lobby WebSocket, triggering `disconnect()`. The old code called `rm.remove_player()` unconditionally, so by the time `GameConsumer.connect()` ran, the role token no longer existed in the `RoleManager` and the connection was rejected (WS close code 4403 → browser shows 1006).

Fix (one line, committed in `a74dd99`): guard `remove_player` with `if session['status'] == 'lobby'` so players are only cleaned up while the game hasn't started.

---

## 2. Repository state entering Phase 3

```
Claudes-plan-2/
  run_phase2_tests.sh        ← reset DB + seed + start server
  start_server.sh            ← start server + open browser + credentials panel
  Phase_3_handoff.md         ← this file
  wsz6_portal/
    wsz6_play/
      engine/
        pff_loader.py        ← loads PFF per play-through (unique module name)
        state_serializer.py  ← serialize_state / deserialize_state  ← READY
        role_manager.py      ← PlayerInfo + RoleManager              ← READY
        game_runner.py       ← state stack, apply, undo, broadcast   ← READY
      persistence/
        gdm_writer.py        ← JSONL log writer, ensures checkpoints/ dir ← READY
        session_sync.py      ← push_session_ended / push_session_status   ← READY
      consumers/
        lobby_consumer.py    ← lobby WS, start_game, bug fixed       ← READY
        game_consumer.py     ← in-game WS, apply/undo/help           ← READY
      session_store.py       ← in-memory dict + Lock                 ← READY
      models.py              ← PlayThrough + Checkpoint DB models     ← READY
```

### What `models.py` already has

Both GDM models exist and are migrated into `db_gdm.sqlite3`:

- **`PlayThrough`** — `playthrough_id`, `session_key`, `game_slug`, `started_at`, `ended_at` (null), `outcome` (blank), `log_path`, `step_count` (0).
  - `ended_at` and `outcome` are **not yet written** anywhere — Phase 3 must fill them.
- **`Checkpoint`** — `checkpoint_id`, `playthrough` (FK → PlayThrough), `created_at`, `label`, `file_path`, `step_number`.
  - The model exists but no code creates `Checkpoint` rows yet.

The `checkpoints/` subdirectory is already created by `ensure_gdm_dirs()` in `gdm_writer.py`, so the file-system side is ready.

---

## 3. Phase 3 scope

### 3.1 Checkpoint save

Create **`wsz6_play/persistence/checkpoint.py`** with two functions:

```python
async def save_checkpoint(session: dict, runner: GameRunner, label: str = '') -> str:
    """Serialize current state to disk and create a Checkpoint DB row.
    Returns the checkpoint_id (UUID hex)."""

async def load_checkpoint(checkpoint_id: str, formulation) -> tuple[state, int]:
    """Load the checkpoint JSON from disk, deserialize state.
    Returns (state, step_number)."""
```

**File layout** (directory already exists):
```
<playthrough_dir>/checkpoints/<checkpoint_id>.json
```

**Checkpoint JSON format:**
```json
{
  "checkpoint_id": "<uuid hex>",
  "playthrough_id": "<uuid hex>",
  "session_key": "<uuid>",
  "step": <int>,
  "label": "<str>",
  "state": { ...serialize_state output... },
  "role_assignments": { ...rm.to_dict() output... }
}
```

`save_checkpoint` must:
1. Call `serialize_state(runner.current_state)`.
2. Write the JSON file to `<playthrough_dir>/checkpoints/<id>.json`.
3. Create a `Checkpoint` DB row (`asyncio.to_thread`).
4. Write a `checkpoint_saved` event to the GDM log.
5. Return the `checkpoint_id`.

### 3.2 Pause/resume flow

**Pause (in `game_consumer.py`):**

Add a `request_pause` handler alongside `apply_operator` and `request_undo`:

```python
elif msg_type == 'request_pause': await self._handle_pause(session)
```

`_handle_pause` must:
1. Call `save_checkpoint(session, runner, label='pause')`.
2. Call `push_session_status(session_key, 'paused')`.
3. Update `session_store`: `{'status': 'paused', 'latest_checkpoint_id': checkpoint_id}`.
4. Write `game_paused` event to GDM log.
5. Broadcast `{'type': 'game_paused', 'checkpoint_id': ..., 'step': ...}` to the game group.

**PlayThrough closure** (also in `game_consumer.py`):

When a game ends (goal reached), update the `PlayThrough` record:
- `ended_at = now()`
- `outcome = 'completed'`
- `step_count = runner.step`

When a game is paused, leave `PlayThrough.ended_at` null (it hasn't ended); do update `step_count`.

**Resume (in `lobby_consumer.py` + `views.py`):**

`join_session` HTTP view already redirects to the game page if the session is `in_progress`. It needs a second branch: if `status == 'paused'`, render a **"Resume Session"** lobby page instead.

In `_handle_start_game`, add a resume path: if `session['status'] == 'paused'` and a `latest_checkpoint_id` exists:
1. Load the checkpoint.
2. Restore the `GameRunner` state stack from the checkpoint state.
3. Set `runner.step` from the checkpoint.
4. Write a `game_resumed` event to the GDM log (same `log.jsonl` — it is append-only and continuous).
5. Set session status back to `'in_progress'`.
6. Broadcast `game_starting_event` as normal.

> **Key design decision:** a resumed play-through is a continuation of the same `PlayThrough` row (same `playthrough_id`, same `log.jsonl`). Only if an entirely new play-through is started after a goal is reached does a new `PlayThrough` row get created. This keeps the GDM log continuous and replay-complete.

### 3.3 Bot player

Create **`wsz6_play/engine/bot_player.py`**:

```python
class BotPlayer:
    """Async task that applies operators on behalf of a bot role."""
    def __init__(self, role_num: int, strategy: str = 'random', delay: float = 1.2):
        ...
    async def maybe_move(self, runner: GameRunner, current_role_num: int) -> bool:
        """If it is this bot's turn, pick and apply an operator. Returns True if moved."""
        ...
```

Two strategies:
- `'random'` — pick a random applicable operator.
- `'first'` — pick the first applicable operator.

The bot is triggered from `game_consumer.py` after every state broadcast: call `bot_player.maybe_move(runner, state.current_role_num)` for each bot assigned in the `RoleManager`. Bot moves must go through the same `runner.apply_operator()` path (so they are logged and broadcast identically to human moves).

### 3.4 Bot assignment in the lobby UI

In `lobby_consumer.py`, add a new message type:

```python
elif msg_type == 'assign_bot': await self._handle_assign_bot(content, session)
```

`_handle_assign_bot(content, session)`:
1. Owner-only.
2. Accepts `{'type': 'assign_bot', 'role_num': <int>, 'strategy': 'random'|'first'}`.
3. Creates a `PlayerInfo` with `is_bot=True`, assigns it to `role_num`.
4. Stores `strategy` on the `PlayerInfo` (add `strategy` field to `PlayerInfo.__slots__`).
5. Broadcasts updated `lobby_state`.

In `join.html`, add an "Assign Bot" button next to each unoccupied role slot (visible to owner only).

When `_handle_start_game` runs, collect bot assignments from the `RoleManager` and instantiate `BotPlayer` objects. Store them in the session store under `'bots'`. After `GameConsumer` connects, it checks for bots and calls `maybe_move` after each state update.

---

## 4. Files to create / modify

| File | Action | Notes |
|------|--------|-------|
| `wsz6_play/persistence/checkpoint.py` | **CREATE** | `save_checkpoint`, `load_checkpoint` |
| `wsz6_play/engine/bot_player.py` | **CREATE** | `BotPlayer` class, random and first strategies |
| `wsz6_play/consumers/game_consumer.py` | **MODIFY** | Add `request_pause` handler; trigger bot moves; update `PlayThrough` on end |
| `wsz6_play/consumers/lobby_consumer.py` | **MODIFY** | Add `assign_bot` handler; resume path in `_handle_start_game` |
| `wsz6_play/views.py` | **MODIFY** | `join_session` — add `paused` → "Resume" page branch |
| `wsz6_play/persistence/session_sync.py` | **MODIFY** | Add `push_session_paused(session_key)` |
| `wsz6_play/persistence/gdm_writer.py` | **MODIFY** | Add `checkpoint_saved`, `game_paused`, `game_resumed` event constants (just doc; `write_event` is already generic) |
| `wsz6_play/models.py` | **MODIFY** | No model changes needed; `Checkpoint` row is written by `checkpoint.py` |
| `templates/wsz6_play/join.html` | **MODIFY** | "Assign Bot" buttons per role; "Resume" mode display |
| `templates/wsz6_play/game.html` | **MODIFY** | "Pause" button for session owner |

No new Django app, no new migrations (both `PlayThrough` and `Checkpoint` models already exist and are migrated).

---

## 5. Key design decisions to carry forward

1. **Single continuous `PlayThrough` per resume.** Don't create a new `PlayThrough` row on resume — append to the same `log.jsonl`. The log format is replay-complete: `game_paused` + `game_resumed` events are sufficient to reconstruct the full session.

2. **`state_stack` is not checkpointed** — only the current state is saved. On resume, the stack starts as `[restored_state]` (no undo history from before the pause). This is acceptable for Phase 3; full undo-history checkpointing can be a Phase 7 refinement.

3. **Bot moves via the same code path as humans.** `BotPlayer.maybe_move` calls `runner.apply_operator()` directly, which logs and broadcasts identically. The GDM log does not distinguish human vs bot moves except through the `role_num` field (the `RoleManager` knows which role_nums are bots).

4. **`BotPlayer` lives in the session store.** Store under `session['bots']` as a list of `BotPlayer` instances. `GameConsumer` reads this on each state update and calls `maybe_move` for every bot. No separate task or thread needed.

5. **Pause is owner-only.** Like `start_game`, only the session owner's `GameConsumer` should accept `request_pause`. Check `request.user.id == session['owner_id']` using the WS scope.

---

## 6. Session store additions for Phase 3

Add these fields to the session dict (populated by `_handle_start_game` / `_handle_pause`):

```
latest_checkpoint_id   str | None   UUID hex of most recent checkpoint
bots                   list         List of BotPlayer instances (empty if no bots)
```

---

## 7. How to test Phase 3

Use `bash run_phase2_tests.sh --setup-only && bash start_server.sh`.

### Checkpoint + Pause test
1. Start a game (owner1 + player1 as before).
2. Apply 2–3 moves.
3. Click "Pause" — verify:
   - Both browsers get `game_paused` message.
   - File exists: `SZ6_Dev/gdm/tic-tac-toe/sessions/<key>/playthroughs/<id>/checkpoints/<id>.json`
   - `log.jsonl` contains `game_paused` event.
   - Admin sessions page shows status "Paused".

### Resume test
4. Refresh both browser pages (simulates a reconnect).
5. Navigate to lobby URL — "Resume Session" button visible.
6. Click Resume → game page reappears at the step count where it was paused.
7. Continue playing to goal — verify `log.jsonl` has the full sequence: `game_started → op→op→… → game_paused → game_resumed → op→… → game_ended`.

### Bot test
1. Start a new session; assign player1 to role X, assign a Bot to role O (strategy: random).
2. Player1 makes a move — bot should respond automatically within ~1–2 seconds.
3. Play to completion — verify `log.jsonl` shows alternating human/bot moves.

---

## 8. What comes after Phase 3

**Phase 4 – Observer Mode & Debug Launcher**
- `ObserverConsumer` (read-only, full-state broadcast).
- Debug launcher: single-user session with all roles run by one account.
- `launch_debug` internal API endpoint implementation.

**Phase 5 – Parameterized Operators**
- UI for collecting operator parameters before applying.
- Parameter spec parsing from `op.params`.

**Phase 6 – Research / GDM Analytics**
- Admin "Research" tab: browse GDM logs, session timeline, aggregate stats.
- Download session data as ZIP.

**Phase 7 – Production Hardening**
- Replace `InMemoryChannelLayer` + in-process `session_store` with Redis.
- HTTPS/WSS, nginx, rate limiting, automated tests.
