# Report on Adapting OCCLUEdo for SOLUZION6

**Date:** 2026-02-20
**Author:** S. Tanimoto (work done with Claude Sonnet 4.6)

---

## Overview

This report documents the adaptation of OCCLUEdo from its SOLUZION5 / Flask-based
implementation (`SZ5_OCCLUEdo_web_as_ref/OCCLUEdo_web.py`) to a new SOLUZION6
implementation compatible with the WSZ6-play Django/ASGI game engine.

The new version includes an interactive SVG visualization using the WSZ6 Tier-1
interaction system (`data-op-index` attributes on SVG and HTML elements), allowing
players to move between rooms, choose suspects and weapons, and respond to
suggestions by clicking on card images rather than selecting from a text list.

---

## Files Created

| File | Location | Lines | Purpose |
|---|---|---|---|
| `Adapting-OCCLUEdo-for-SZ6.md` | `Vis-Features-Dev/` | — | Detailed design plan |
| `OCCLUEdo_SZ6.py` | `Vis-Features-Dev/game_sources/` | 368 | SZ6 problem formulation (PFF) |
| `OCCLUEdo_WSZ6_VIS.py` | `Vis-Features-Dev/game_sources/` | 430 | Interactive visualization module |
| `OCCLUEdo_images/` | `Vis-Features-Dev/game_sources/` | 26 images | Card and room image assets |

`install_test_game.py` was also updated to include an OCCLUEdo entry (slug `occluedo`,
min 2 / max 7 players). The game was installed successfully into `games_repo/occluedo/`.

---

## Key Design Decisions

### SZ5 → SZ6 Architecture Mapping

| Concern | SOLUZION5 | SOLUZION6 |
|---|---|---|
| Metadata | Tagged globals (`PROBLEM_NAME`, etc.) | `OCCLUEdo_Metadata(sz.SZ_Metadata)` |
| State | `class State(Basic_State)` | `class OCCLUEdo_State(sz.SZ_State)` |
| Operators | Global `OPERATORS` list | `class OCCLUEdo_Operator_Set(sz.SZ_Operator_Set)` |
| Roles | `ROLES_List` + `Select_Roles` module | `class OCCLUEdo_Roles_Spec(sz.SZ_Roles_Spec)` |
| Initialization | `create_initial_state()` + `deal()` at import | `initialize_problem(config={})` method |
| Transition messages | `add_to_next_transition(msg, state)` | `new_state.jit_transition = msg` |
| Role membership | `Select_Roles.role_being_played(k)` | `k in state.active_roles` |
| Module entry point | `OPERATORS`, `ROLES` globals | `OCCLUEDO = OCCLUEdo_Formulation()` |

### Role Management Without Select_Roles

The `next_active_role(k, state, inactive_ok)` function replaces `next_player()`.
Active roles are passed in via `config['active_roles']` in `initialize_problem()`,
stored in `state.active_roles`, and consulted by all precondition and transition
functions. The default `[0, 1]` (Miss Scarlet, Mr. Green) makes single-session
testing easy.

### Operator Ordering (65 total)

The operator ordering is critical because the VIS uses `data-op-index` attributes
that must align with positions in the operator list.

```
Indices  0–17  go_ops (places 6–23; op_idx = place − 6)
Index    18    op_start_suggestion
Indices 19–24  suspect_ops (19 + suspect_no)
Indices 25–30  weapon_ops  (25 + weapon_no)
Indices 31–39  response_ops (31 + card_slot)
Index    40    op_respond_sorry
Index    41    op_acknowledge
Index    42    op_start_accusation
Indices 43–51  add_room_to_accusation (43 + room_no)
Indices 52–57  add_player_to_accusation (52 + player_no)
Indices 58–63  add_weapon_to_accusation (58 + weapon_no)
Index    64    op_ask_win
```

### Bug Fixes from SZ5

Three bugs in the original SZ5 code were corrected in the SZ6 version:

1. **`can_respond_sorry` / `cannot_disprove`**: The SZ5 version checked
   `suspect_card in hand` twice instead of checking `weapon_card` on the
   last line. Fixed to correctly check `weapon_card`.

2. **`deal()` global declaration**: SZ5 declared `global MURDER` (typo) while
   assigning to `MURDERER`, making `MURDERER` a local variable that never
   escaped the function. Fixed to `global MURDERER, CRIME_ROOM, CRIME_WEAPON,
   PLAYER_HAND`.

3. **`add_weapon_to_accusation` history**: SZ5 appended `s.current_accusation`
   (before the weapon was added) to `accusations`. Fixed to append the complete
   four-element accusation record `[room, suspect, weapon, accuser]`.

---

## Interactive Visualization Design

The visualization uses **Tier-1 SVG interaction** (`data-op-index` on SVG
elements and HTML `<div>` elements). No JSON region manifest or canvas overlay
is needed. The `game.html` CSS and JS handle all hover highlighting and
click dispatch automatically.

### Layout

```
┌──────────────────────────────────────────────────────┐
│  Status bar: active player name + location summary   │
├──────────────────────────────────────────────────────┤
│           Room map SVG (530 × 450)                   │
│   3×3 grid arranged to match classic Clue layout:   │
│   Kitchen  | Ballroom  | Conservatory                │
│   Billiard | DiningRm  | Library                    │
│   Lounge   | Hall      | Study                      │
│   (diagonal secret passages marked in gold dashes)   │
├──────────────────────────────────────────────────────┤
│  Action panel (context-sensitive HTML + SVG):        │
│    Phase 0:  movement hint + Start Accusation button │
│    Phase 2:  6 clickable suspect portrait images     │
│    Phase 3:  6 clickable weapon images               │
│    Phase 4:  current player's hand (green = matches  │
│              suggestion, grey = no match) + Sorry btn│
│    Phase 5:  refutation card + Acknowledge button    │
│    Acc 1-3:  room / suspect / weapon image grids     │
│    Acc 4:    accusation summary + Submit button      │
├──────────────────────────────────────────────────────┤
│  Card hand strip: current player's cards as images   │
└──────────────────────────────────────────────────────┘
```

### Room Map

- Each room is an SVG `<rect>` that turns **green** when the current player
  can enter it, adding `data-op-index` for the corresponding `go_op`.
- Each room has a **lobby strip** below it, also clickable when accessible.
- **Player tokens** are colored circles (using `ROLE_COLORS`) inside the
  cell corresponding to their current location.
- **Secret passages** are shown as gold dashed diagonal lines across the
  grid, with a small `↗ RoomName` label that becomes clickable when the
  player is in the passage's source room.

### Action Panel

- **Phase 2 (choose suspect)**: Displays all 6 suspect card images as
  clickable `<div>` elements, each with `data-op-index` pointing to the
  corresponding `suspect_op` (indices 19–24).
- **Phase 3 (choose weapon)**: Same pattern with 6 weapon images
  (indices 25–30).
- **Phase 4 (refutation)**: Shows the subturn player's hand. Cards that
  match the suggestion are highlighted with a green border and are
  clickable (response_ops 31–39); non-matching cards are greyed out
  (opacity 0.35, no data-op-index). A "Cannot disprove" button triggers
  op 40.
- **Phase 5 (acknowledge)**: Shows the refutation card (if any) and an
  Acknowledge button (op 41).
- **Accusation phases**: Room → suspect → weapon image grids
  (ops 43–63), then a Submit button (op 64).

### Image Assets

Card images are served via the game-asset endpoint:
```
/play/game-asset/occluedo/images/<filename>
```
The 26 images from `SZ5_OCCLUEdo_web_as_ref/images/` cover all 6 suspects,
9 rooms, and 6 weapons.

---

## Known Limitations

### Secret Card Display

In SZ5 the Flask server passed a `roles` list to `render_state(s, roles=None)`,
enabling truly role-private card displays. The WSZ6 engine currently calls
`render_state(state)` with no role argument; all connected clients receive the
same HTML.

The current implementation shows the cards only for `state.current_role_num`
(the active player). Players who are watching but not currently active do not
see their own hand until it is their turn. A future engine enhancement would
send per-client role-filtered vis_html to enable genuine secrecy.

### Single-Session Module-Level Globals

`PLAYER_HAND`, `MURDERER`, `CRIME_ROOM`, and `CRIME_WEAPON` are module-level
variables. If two OCCLUEdo sessions run concurrently in the same Django process
they will overwrite each other's data. For the initial port this is acceptable
(development use only). A proper fix would store these in
`SZ_Problem_Instance_Data` keyed by session ID.

### active_roles Initialization

`initialize_problem(config)` defaults to `active_roles=[0, 1]` if the lobby
does not pass `config['active_roles']`. A small enhancement to
`lobby_consumer.py` to populate `config['active_roles']` from role assignments
before calling `initialize_problem()` is needed for full multiplayer support.

---

## Test Results

All automated smoke tests passed:

- **Syntax check**: Both `OCCLUEdo_SZ6.py` and `OCCLUEdo_WSZ6_VIS.py` parse
  cleanly with `ast.parse`.
- **Operator count and names**: 65 operators at correct indices (verified by
  printing `ops[0]`, `ops[18]`, `ops[19]`, `ops[25]`, `ops[40]`, `ops[41]`,
  `ops[42]`, `ops[64]`).
- **State machine flow**: Movement → lobby → room (suggestion_phase=2) →
  suspect selection (phase 3) → weapon selection (phase 4) all transition
  correctly.
- **`can_respond_sorry` bug fix**: With Miss Scarlet holding the Lounge card
  and the suggestion being "Miss Scarlet in the Lounge with the Candlestick",
  `can_respond_sorry` correctly returns `False` (she can refute).
- **VIS rendering**: `render_state` returns non-empty HTML for the initial
  state (8 199 chars), phase-2 suspect panel (10 993 chars), phase-3 weapon
  panel (10 926 chars), and phase-4 refutation panel (13 017 chars). All
  contain the expected `data-op-index` attributes and panel headings.
- **Installation**: `python manage.py install_test_game` reports
  `OK 'OCCLUEdo: An Occluded Game of Clue' created (slug='occluedo',
  status='published')`.

---

## Next Steps

1. **Live browser test**: Start the dev server, log in as two players, assign
   Miss Scarlet and Mr. Green roles, and walk through a complete game.
2. **Lobby `active_roles` wiring**: Enhance `lobby_consumer.py` to pass
   `config['active_roles']` from role assignments into `initialize_problem()`.
3. **Per-player VIS secrecy**: Investigate engine support for role-filtered
   `vis_html` so each player sees only their own hand.
4. **Deduction notepad**: Consider adding an SVG Clue-sheet overlay where
   players can mark off eliminated suspects/weapons/rooms.
