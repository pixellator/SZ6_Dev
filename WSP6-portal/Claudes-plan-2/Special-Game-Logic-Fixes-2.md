# Special-Game-Logic-Fixes-2.md

**Date:** 2026-02-19
**Session focus:** True parallel input and parallel-phase undo guard

---

## Problems fixed

### 1. Parallel input was being serialized

`game_consumer._handle_apply` blocked any player whose `role_num ≠ state.current_role_num`,
even when `state.parallel == True`.  Both players were effectively taking turns to submit
their "simultaneous" choices, which is wrong for games like Rock-Paper-Scissors.

A secondary race condition also existed: two concurrent `apply_operator` calls could both
read the same pre-choice state, causing the second player's choice to overwrite the first.

### 2. Undo was permitted after parallel-phase moves

Players could click Undo after committing a choice, which in a hidden-information game
allows a bad-faith player to learn what the other player submitted (or what the state
reveals) before changing their own choice.

---

## Changes made

### `wsz6_play/engine/game_runner.py`
- Added `self._lock = asyncio.Lock()` — serialises concurrent `apply_operator` calls so
  each player's transition is computed from the correct post-previous-player state.
- Added `self.op_history` list — tracks which `op_index` was used at each step (parallel
  to `state_stack`), so the undo guard can check whether the last operator allows undo.
- `apply_operator` now runs entirely inside `async with self._lock`; `op_history` is
  updated alongside `state_stack`.
- `undo` now runs inside `async with self._lock` and checks: if `state_stack[-2].parallel
  is True`, undo is blocked unless the operator that produced the current state has
  `allow_undo = True` (default: blocked).  `op_history` is popped in sync with the stack.
- `_broadcast_state` now includes `is_parallel` in every `state_update` payload.

### `wsz6_play/consumers/game_consumer.py`
- `_handle_apply`: turn-check is bypassed when `state.parallel == True`; both players can
  submit without waiting.  Correctness is guaranteed by the lock + operator preconditions.
- `connect`: initial on-connect `state_update` now includes `is_parallel`.

### `templates/wsz6_play/game.html`
- `onStateUpdate` uses `is_parallel` to compute `isMyTurn` (based on `hasApplicableOps`
  in parallel mode rather than `current_role_num`).
- Turn banner shows **"Make your choice!"** / **"Choice submitted — waiting for other
  player…"** during parallel phases.
- Undo button is disabled client-side whenever `is_parallel` (server also blocks it).

---

## Design notes

- `Rock_Paper_Scissors_SZ6.py` required **no changes**.  The PFF already uses
  `state.parallel`, role-scoped operators, and hidden-choice `text_view_for_role`.
- The `allow_undo = True` override on an operator is the hook for future games that
  legitimately need to permit undo during a parallel phase.
- The asyncio.Lock holds across `await asyncio.to_thread(...)`, so two simultaneous
  applies queue safely; the second one reads the state the first one produced.
