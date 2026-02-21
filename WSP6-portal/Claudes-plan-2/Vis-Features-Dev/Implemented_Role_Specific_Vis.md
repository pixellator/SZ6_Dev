# Implemented: Role-Specific Visualizations in WSZ6-play

**Date:** 2026-02-20
**Branch:** master
**Session plan file:** `Plan-for-Role-Specific-Vis.md`

---

## Problem solved

Games like OCCLUEdo require each player to see a different visualization of
the same game state — e.g., only their own card hand, not opponents'.
Previously, `GameRunner._broadcast_state()` called `vis_module.render_state(state)`
once and broadcast the identical `vis_html` to all connected players.

---

## Architecture

The same pattern already used for operator filtering was extended to
visualization:

- `_broadcast_state()` sends a **base payload** with no `vis_html`.
- Each `GameConsumer` calls `runner.render_vis_for_role(state, role_num)`
  independently and adds its own role-specific `vis_html` before forwarding
  to the browser.
- VIS modules that do not declare a `role_num` parameter continue to work
  unchanged (backward compatible via `inspect.signature`).

---

## Files changed

### `wsz6_play/engine/game_runner.py`

| Addition | Description |
|---|---|
| `import inspect` | Needed for signature introspection |
| `_build_base_payload()` | Synchronous helper — builds `state_update` dict without `vis_html` |
| `render_vis_for_role(state, role_num=None)` | Async — calls `render_state(state, role_num)` if VIS module supports it, else `render_state(state)` |
| `build_state_payload(role_num=None)` | Async — `_build_base_payload()` + `render_vis_for_role()`; used by `connect()` |
| `_broadcast_state()` | Now calls `_build_base_payload()` only — no vis in the broadcast |

### `wsz6_play/consumers/game_consumer.py`

| Location | Change |
|---|---|
| `connect()` | Added `self.runner = runner` (cache for `state_update`) |
| `connect()` | Changed `build_state_payload()` → `build_state_payload(role_num=self.role_num)` |
| `state_update()` | After filtering operators, calls `render_vis_for_role(runner.current_state, self.role_num)` and sets/strips `vis_html` in the outgoing payload |

### `Vis-Features-Dev/game_sources/OCCLUEdo_WSZ6_VIS.py`

| Location | Change |
|---|---|
| `render_state(state)` | New signature: `render_state(state, role_num=None)` |
| Inside `render_state` | Computes `viewing_role = role_num if role_num is not None else state.current_role_num` |
| `_build_hand_display(state)` | New signature: `_build_hand_display(state, viewing_role)` — uses `viewing_role` to select which player's hand to show; label updated to "Your cards (Name):" |

The room map, action panel, and status bar remain based on `state` attributes
and are the same for all players (shared game view).

---

## Backward compatibility

| VIS module | `render_state` signature | Engine behaviour |
|---|---|---|
| Existing (TTT, Mt. Rainier, Click-Word, Pixel-Probe) | `def render_state(state)` | `inspect.signature` finds no `role_num` → called as before |
| OCCLUEdo (updated) | `def render_state(state, role_num=None)` | Called with viewer's `role_num`; defaults to `state.current_role_num` when omitted |
| Future games | `def render_state(state, role_num=None)` | Full role-aware rendering |

---

## Verification checklist

1. **Regression — Tic-Tac-Toe**: Start a TTT session; confirm vis renders
   normally for both players (VIS has no `role_num` param → unchanged code path).
2. **Role-specific — OCCLUEdo**:
   - Log in as two users in separate browser windows.
   - Assign Miss Scarlet (role 0) to player 1, Mr. Green (role 1) to player 2.
   - Start game. Verify player 1's card strip shows Miss Scarlet's cards;
     player 2's strip shows Mr. Green's cards.
   - Make a move; verify both browsers update and still show the correct
     private hands.
3. **Observer**: Join as observer (role 6); verify no private hand is shown
   (the `viewing_role >= 6` guard in `_build_hand_display` returns `''`).
4. **Reconnect**: Close and reopen one browser tab; verify the reconnected
   player receives the correct role-specific vis from the `connect()` handler.
