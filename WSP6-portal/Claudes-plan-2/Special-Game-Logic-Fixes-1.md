# Special Game Logic Fixes — Session 1

## Overview

This document summarizes multi-game support work and game-logic bug fixes
discovered by testing five new SZ6 games against the WSZ6-play web engine.

---

## Extended the Game Installer

`install_test_game.py` was rewritten from a single Tic-Tac-Toe installer into
a general-purpose command that installs all six SZ6 games in one shot.  Each
game gets its own directory under `games_repo/` with its PFF and
`soluzion6_02.py`.

```
python manage.py install_test_game
```

Games installed: Tic-Tac-Toe, Guess My Age, Missionaries and Cannibals,
Rock-Paper-Scissors, Remote LLM Test Game, Trivial Writing Game.

---

## Bug Fix 1 — Parameterized Operators (Guess My Age, Remote LLM Test Game)

**Symptom:** Clicking a parameterized operator produced the error:
> `Operator execution failed: <lambda>() missing 1 required positional argument: 'args'`

**Root cause:** `game_runner.apply_operator` decided the calling convention
(`state_xition_func(state)` vs `state_xition_func(state, args)`) by checking
whether `args` were actually supplied by the client — but the frontend never
collected them, so `args` was always `None`.

**Fix — backend (`game_runner.py`):** Mirror `Textual_SOLUZION6.py`'s own
rule: check `op.params` to decide the calling convention, not whether `args`
were provided.

```python
has_params = bool(getattr(op, 'params', None))
new_state = (
    op.state_xition_func(state, args) if has_params
    else op.state_xition_func(state)
)
```

**Fix — frontend (`game.html`):** Added an inline param-input form that
appears when the player clicks a parameterized operator.  Supports:
- `int` — number input with optional min/max range hint
- `float` — number input with optional min/max range hint
- `str` — plain text input

Parameterized operators are marked with a subtle `▸` indicator in the
operator list.

---

## Bug Fix 2 — Blocking I/O & Silent Startup Failures (Remote LLM Test Game)

### 2a. Blocking event loop

**Symptom:** The LLM HTTP call (inside `state_xition_func`) ran synchronously
in Django Channels' async event loop, blocking all other WebSocket connections
for the duration of the API round-trip.

**Fix (`game_runner.py`):** Run both `initialize_problem()` and
`state_xition_func` via `asyncio.to_thread` so they execute in a thread-pool
worker and never block the event loop.

```python
# start()
initial_state = await asyncio.to_thread(self.formulation.initialize_problem)

# apply_operator()
new_state = await asyncio.to_thread(op.state_xition_func, state, args)
```

### 2b. Session stuck in broken state on startup failure

**Symptom:** If `initialize_problem()` raised (e.g. missing `google-genai`
package or `GEMINI_API_KEY` not set), the lobby WebSocket closed with code
1011.  The session was already marked `in_progress` with no valid game state,
leaving it permanently broken — the owner could not retry.

**Root cause:** `session_store.update_session(status='in_progress')` was
called *before* `runner.start()`, so a startup failure left the session in
an invalid state with no recovery path.

**Fix (`lobby_consumer.py`):** Wrap `runner.start()` in try/except.  On
failure, revert the session to `'lobby'` status and send a user-visible error
message so the owner can correct the problem (e.g. set the API key) and try
again.

```python
try:
    await runner.start()
except Exception as exc:
    session_store.update_session(self.session_key, {
        'status': 'lobby', 'game_runner': None, 'bots': [],
    })
    await push_session_status(self.session_key, 'open')
    await self.send_json({'type': 'error', 'message': f'Failed to start game: {exc}'})
    return
```

**Environment note:** The Remote LLM Test Game requires:
1. `pip install google-genai` in the project venv
2. `export GEMINI_API_KEY="your-key-here"` (add to `~/.bashrc` for persistence
   across WSL sessions)

---

## Bug Fix 3 — File-Edit Operator (Trivial Writing Game)

**Symptom:** The `file_edit` param type is designed to open a local terminal
editor (`nano` / `$EDITOR`).  In the browser context this is meaningless —
no editor opens, the operator cannot be applied.

**Fix — frontend only (`game.html`):** Detect `file_edit` params and route
them to a purpose-built full-viewport modal text editor instead of the inline
param form.

### Modal features
- Full-screen overlay with a dark backdrop (clicking outside cancels)
- Large `<textarea>` in a serif writing font (Georgia), pre-filled with the
  operator's `initial_text`
- Live word count updating as the player types
- **Ctrl+Enter** keyboard shortcut to save
- **Save & Apply** and **Cancel** buttons
- Smooth slide-in animation

### How it works
The textarea content is collected and sent to the server as `args[0]`, which
is exactly what `state_xition_func(state, args)` expects — the same value
the terminal engine would have read back from the edited file.  No server-side
changes were required.

File-edit operators are marked with a `✎` pencil icon in the operator list
to distinguish them from other parameterized operators (`▸`).

---

## Commits (this session)

| Hash | Description |
|------|-------------|
| `e6939b0` | Extend install_test_game to install all 6 SZ6 test games |
| `5c6cbe2` | Fix parameterized operators: collect args in UI before sending |
| `b90ab25` | Fix blocking I/O and silent start failures in game_runner/lobby |
| `62f5e94` | Add in-browser modal text editor for file_edit operator params |
