# Vis_M1_Done.md — Session Summary for M1 (Basic Vis Rendering)

**Date:** 2026-02-19
**Session context:** Vis-Features-Dev branch of WSZ6-portal / Claudes-plan-2

---

## What Was Accomplished

Milestone M1 introduces the `_WSZ6_VIS.py` file convention and wires it end-to-end:
a game formulation can now declare a visualization module, and the WSZ6-play server
will call `render_state(state)` after every operator application (and on initial
connection), sending the resulting HTML/SVG to all clients as `vis_html` inside the
`state_update` message.  Clients that receive `vis_html` display the graphic instead
of the ASCII text fallback; clients playing games without a vis module continue to
work exactly as before.

M0 (persistent transition history) was also completed in this session — see M0
work in the commit history and game.html.

---

## Files Created

### `SZ6_Dev/Textual_SZ6/Tic_Tac_Toe_WSZ6_VIS.py`
The first WSZ6 visualization module.  Public API: `render_state(state) -> str`.

- Completely standalone — no imports from the PFF; uses duck-typing on the
  state object (`state.board`, `state.winner`, `state.whose_turn`).
- Returns an inline SVG (no external dependencies, no JavaScript).
- SVG layout: 300 × 330 px logical units, `width="100%"` with `max-width:360px`
  so it scales responsively inside the left column.
- X marks: two bold diagonal lines, dark blue (`#1565C0`), rounded caps.
- O marks: bold circle, dark red (`#C62828`), no fill.
- Winning cells highlighted with light amber background (`#fffde7`).
  Winning line detected by re-checking all rows, columns, and diagonals
  against `state.winner` — robust even when `check_for_win()` was called
  before render.
- Status bar below the grid: "X's turn", "O's turn", "X wins!", "O wins!",
  or "It's a draw!" — updated on every render.
- XML-safe helper `_esc()` prevents injection through state text.

### `SZ6_Dev/Textual_SZ6/Tic_Tac_Toe_SZ6_with_vis.py`
A new problem formulation file, mechanically derived from `Tic_Tac_Toe_SZ6.py`
with two additions:

1. `import Tic_Tac_Toe_WSZ6_VIS as _ttt_vis` at the top.
2. `self.vis_module = _ttt_vis` in `TTT_Formulation.__init__`.

The metadata `name` is changed to `"Tic-Tac-Toe (Visual)"` to distinguish it
in the games catalog.  The original `Tic_Tac_Toe_SZ6.py` is untouched.

The import works because `pff_loader` adds the game directory to `sys.path`
before executing the PFF module, so `Tic_Tac_Toe_WSZ6_VIS.py` (which lives in
the same directory) is found automatically.

---

## Files Modified

### `wsz6_play/engine/game_runner.py`
**New method: `async def build_state_payload(self) -> dict`**

Extracted from `_broadcast_state`, this method builds the complete
`state_update` payload for the current state:
- Calls `get_ops_info`, checks `is_goal`.
- If `formulation.vis_module` exists and has a callable `render_state`,
  calls it via `asyncio.to_thread` (thread-safe; future vis files may do I/O).
- On any exception from `render_state`, logs it and leaves `vis_html = None`
  (graceful fallback to text display).
- Includes `vis_html` in the payload only when it is not `None` (so text-only
  games send no extra key).

`_broadcast_state` is now a one-liner that calls `build_state_payload` and
broadcasts the result.

**Why the extraction matters:** the consumer's `connect()` handler used to
hand-build its own payload dict, bypassing the vis rendering path entirely.
This caused the bug where the initial board was shown as ASCII and the SVG
only appeared after the first move.

### `wsz6_play/consumers/game_consumer.py`
`connect()` now calls `await runner.build_state_payload()` and appends the
per-player fields (`operators` role-filtered, `your_role_num`, `is_owner`)
before sending.  The SVG is therefore present in the very first message the
client receives, matching every subsequent move update.

### `wsz6_portal/templates/wsz6_play/game.html`
- Added CSS rule `#vis-display { padding:.8rem; overflow:auto; }`.
- Added `<div id="vis-display" style="display:none;"></div>` inside the same
  card as `<pre id="state-display">`, above it in the DOM.
- `onStateUpdate` now switches between the two elements:
  - `msg.vis_html` present → set `vis-display.innerHTML`, show it, hide the pre.
  - `msg.vis_html` absent → set `state-display.textContent`, show it, hide the div.
  Both elements start hidden/visible correctly on the very first message.

### `wsz6_admin/games_catalog/management/commands/install_test_game.py`
- Added new entry `'tic-tac-toe-vis'` to `GAME_DEFS`, pointing to
  `Tic_Tac_Toe_SZ6_with_vis.py` with `'vis_file': 'Tic_Tac_Toe_WSZ6_VIS.py'`.
- `_install_game` now reads `gdef.get('vis_file')` and copies the vis file
  alongside the PFF into the game's `games_repo` directory, with a warning if
  the source file is missing.

### `start_server.sh`
- Added quick link `TTT (Visual)` → `/games/tic-tac-toe-vis/` to the
  credentials panel.
- Added an M1 test-flow note alongside the existing Phase-2 test flow.

---

## Game Directory After Install

Running `python manage.py install_test_game` creates:

```
SZ6_Dev/games_repo/tic-tac-toe-vis/
    Tic_Tac_Toe_SZ6_with_vis.py   ← PFF (formulation entry point)
    Tic_Tac_Toe_WSZ6_VIS.py       ← vis module
    soluzion6_02.py               ← SOLUZION6 base library
```

The database record `Game(slug='tic-tac-toe-vis', name='Tic-Tac-Toe (Visual)')`
was created successfully during this session.

---

## Architecture Pattern Established

The vis module connection is explicit and PFF-driven:

```
PFF (__init__)
  └─ self.vis_module = <imported vis module>
        └─ render_state(state) -> str   (called by game_runner)
```

This is intentionally different from the naming-convention-based server-side
loading described in the VIS_DEV_PLAN (where `pff_loader` would scan for
`<slug>_WSZ6_VIS.py`).  The PFF-import approach was chosen because it makes
the vis association explicit and verifiable without any file-scanning magic.
The two approaches are not mutually exclusive; the naming convention can be
added in a later pass for games that do not import their vis file directly.

---

## M1 Test Checklist Status

- [x] Games without a vis file continue to display ASCII text (no regression).
- [x] `Tic-Tac-Toe (Visual)` renders the SVG board from the very first frame
      (initial connect, not just after first move).
- [x] Each operator application updates the SVG correctly.
- [x] Vis rendering exceptions do not crash the game; fallback to text activates.
- [x] Winning cells are highlighted on the SVG (amber background).
- [x] Status text below the grid reflects game state correctly.
- [ ] Formal multi-browser test with owner1 / player1 (to be done by user).

---

## Known Gaps / Next Steps

- **M3 (Interactive Vis):** Tic-Tac-Toe cells should become clickable to apply
  operators directly, eliminating the need to select from the operator list.
  This requires embedding `data-op-index` attributes in the SVG cells and
  adding a click-event listener in `game.html`.
- **Previous-state vis (M5):** `build_state_payload` could also compute
  `prev_vis_html` (render of `state_stack[-2]`) and include it, so the
  previous-state toggle (M5) works without an extra server round-trip.
- **Naming-convention loader (optional):** A `load_vis_module()` helper in
  `pff_loader.py` could auto-discover `<slug>_WSZ6_VIS.py` for games that
  do not explicitly set `self.vis_module`.
