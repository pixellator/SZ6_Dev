# Adapting OCCLUEdo for SOLUZION6 (WSZ6-play)

**Date:** 2026-02-20
**Author:** S. Tanimoto (plan by Claude Sonnet 4.6)
**Goal:** Port the existing SOLUZION5 OCCLUEdo game to SOLUZION6, adding an interactive SVG visualization for the WSZ6-play engine.

---

## 1. Overview

OCCLUEdo is a multiplayer deduction game — a simplified online Clue/Cluedo — currently implemented in `SZ5_OCCLUEdo_web_as_ref/OCCLUEdo_web.py` for the Flask-based Web_SOLUZION5 system. This document plans the adaptation to SOLUZION6 class-based structure, with an interactive visualization powered by the WSZ6-play Tier-1 SVG interaction system.

### Files to create

| File | Location | Description |
|---|---|---|
| `OCCLUEdo_SZ6.py` | `Vis-Features-Dev/game_sources/` | Problem formulation (PFF) |
| `OCCLUEdo_WSZ6_VIS.py` | `Vis-Features-Dev/game_sources/` | Interactive visualization module |
| `OCCLUEdo_images/` | `Vis-Features-Dev/game_sources/` | Card and room images (copied from SZ5 ref) |

### Source references

- SZ5 PFF: `SZ5_OCCLUEdo_web_as_ref/OCCLUEdo_web.py`
- SZ5 VIS: `SZ5_OCCLUEdo_web_as_ref/OCCLUEdo_SVG_VIS_FOR_BRIFL.py`
- SZ5 images: `SZ5_OCCLUEdo_web_as_ref/images/` (21 jpg + misc)
- SZ6 base classes: `Textual_SZ6/soluzion6_02.py`
- SZ6 interactive VIS guide: `Vis-Features-Dev/How-to-Code-Interactive-Visualizations-in-WSZ6.md`
- Canonical SZ6 game: `Textual_SZ6/Tic_Tac_Toe_SZ6.py`
- Canonical interactive game: `Vis-Features-Dev/game_sources/Click_Word_SZ6.py`

---

## 2. SZ5 → SZ6 Architecture Mapping

| Concern | SOLUZION5 (SZ5) | SOLUZION6 (SZ6) |
|---|---|---|
| Metadata | Tagged globals `PROBLEM_NAME`, `SOLUZION_VERSION`, etc. | `class OCCLUEdo_Metadata(sz.SZ_Metadata)` |
| State | `class State(Basic_State)` | `class OCCLUEdo_State(sz.SZ_State)` |
| Operators | Global `OPERATORS` list of `Basic_Operator` objects | `class OCCLUEdo_Operator_Set(sz.SZ_Operator_Set)` with `self.operators` list |
| Roles | `ROLES = ROLES_List([...])` + `Select_Roles` module | `class OCCLUEdo_Roles_Spec(sz.SZ_Roles_Spec)` with `self.roles` list of `sz.SZ_Role` |
| Initialization | `create_initial_state()` + `deal()` called at import | `OCCLUEdo_Formulation.initialize_problem(config={})` |
| Transition messages | `add_to_next_transition(msg, new_state)` | `new_state.jit_transition = msg` (single string; concatenate multiple messages with `\n`) |
| Role membership | `Select_Roles.role_being_played(k)` | `k in state.active_roles` (list stored in state) |
| VIS entry point | `render_state(s, roles=None)` — role list injected by Flask server | `render_state(state) -> str` — single shared HTML for all clients (see §9 for secret-card strategy) |
| Module entry point | Discovered by SOLUZION via `OPERATORS`, `ROLES`, etc. | Single formulation instance: `OCCLUEDO = OCCLUEdo_Formulation()` (duck-typed by `pff_loader`) |

---

## 3. Constants and Common Data

These are unchanged from SZ5 and can be copied verbatim at the top of the new PFF:

```python
NAMES = ['Miss Scarlet', 'Mr. Green', 'Colonel Mustard',
         'Prof. Plum', 'Mrs. Peacock', 'Mrs. White', 'Observer']
WEAPONS = ['Candlestick', 'Knife', 'Lead Pipe', 'Revolver', 'Rope', 'Wrench']
ROOMS   = ['Lounge', 'Dining Room', 'Kitchen', 'Ballroom',
           'Conservatory', 'Billiard Room', 'Library', 'Study', 'Hall']
LOBBIES = [r + "'s Lobby" for r in ROOMS]
PLAYER_STARTS = [p + "'s Start" for p in NAMES[:6]]
POSSIBLE_PLAYER_SPOTS = PLAYER_STARTS + LOBBIES + ROOMS
# Indices: 0-5 = starting places, 6-14 = lobbies, 15-23 = rooms

ROLE_COLORS = [
    "#c8102e",  # Miss Scarlet (red)
    "#00843d",  # Mr. Green (green)
    "#d4a017",  # Colonel Mustard (mustard/gold)
    "#7b2d8b",  # Prof. Plum (plum/purple)
    "#1f5fa6",  # Mrs. Peacock (peacock blue)
    "#d8d8d8",  # Mrs. White (white/light grey)
    "#888888",  # Observer (grey)
]
```

Index relationships:
- `spot_is_lobby(i)`: `6 <= i <= 14`
- `spot_is_room(i)`: `15 <= i <= 23`
- Room number from place index: `place_index - 15`
- Room's lobby: `room_no + 6`
- Room from lobby: `lobby_index - 6 + 15`

---

## 4. Game-Instance Data and Card Dealing

### Module-level variables (set by `deal()`)

```python
# Module-level instance data — set in initialize_problem() via deal()
MURDERER    = None   # int 0-5 (character index)
CRIME_ROOM  = None   # int 0-8 (room index)
CRIME_WEAPON = None  # int 0-5 (weapon index)
PLAYER_HAND  = None  # list of 6 lists; PLAYER_HAND[role_num] = [(cat, idx), ...]
```

**Why module-level?** The precondition and transition functions need read access to `PLAYER_HAND`. Passing the formulation object down into every lambda would require significant restructuring. Module-level is the same pattern as SZ5.

**Single-session limitation:** If two OCCLUEdo games run concurrently in the same Django process, they would share these globals. For this initial port, document this as a known limitation; a proper fix would use `SZ_Problem_Instance_Data` and thread-local or session-keyed storage.

### `deal(active_roles)` function

```python
import random

def deal(active_roles):
    """Set up a new game: choose the crime and deal remaining cards to active roles."""
    global MURDERER, CRIME_ROOM, CRIME_WEAPON, PLAYER_HAND

    MURDERER     = random.choice(range(6))    # Any of the 6 characters
    CRIME_ROOM   = random.choice(range(9))
    CRIME_WEAPON = random.choice(range(6))

    # Build the deck minus the three crime cards
    non_murderers = [('p', i) for i in range(6) if i != MURDERER]
    weapons_left  = [('w', i) for i in range(6) if i != CRIME_WEAPON]
    rooms_left    = [('r', i) for i in range(9) if i != CRIME_ROOM]
    deck = _shuffle(non_murderers + weapons_left + rooms_left)

    PLAYER_HAND = [[] for _ in range(6)]
    idx = 0
    n = len(active_roles)
    for i, card in enumerate(deck):
        recipient = active_roles[i % n]
        PLAYER_HAND[recipient] = PLAYER_HAND[recipient] + [card]
```

`_shuffle` is a direct copy of the SZ5 `shuffle()` helper (random.sample equivalent).

---

## 5. State Class

```python
class OCCLUEdo_State(sz.SZ_State):
    def __init__(self, old=None, active_roles=None):
        if old is None:
            # --- Initial state ---
            self.active_roles     = active_roles or [0, 1]  # Roles being played
            self.whose_turn       = self.active_roles[0]    # First active role
            self.current_role_num = self.whose_turn
            self.whose_subturn    = -1       # -1 = no subturn in progress
            self.suggestion       = None     # None or [room_no, suspect_no, weapon_no]
            self.suggestion_phase = 0        # 0-5 (see §5.1)
            self.refutation_card  = None     # Card shown privately
            self.current_accusation = []     # [-1,-1,-1, accuser_role]
            self.accusations      = []       # List of completed accusations
            self.accusation_phase = 0        # 0-4
            self.inactive_players = []       # Roles that made false accusations
            self.recent_arrivals  = []       # Roles just moved into current room
            self.player_places    = list(range(6))  # Each starts at their own index
            self.winner           = None     # Role number of winner, or None
        else:
            # --- Deep copy ---
            self.active_roles       = old.active_roles[:]
            self.whose_turn         = old.whose_turn
            self.current_role_num   = old.current_role_num
            self.whose_subturn      = old.whose_subturn
            self.suggestion         = old.suggestion[:] if old.suggestion else None
            self.suggestion_phase   = old.suggestion_phase
            self.refutation_card    = old.refutation_card
            self.current_accusation = old.current_accusation[:]
            self.accusations        = [a[:] for a in old.accusations]
            self.accusation_phase   = old.accusation_phase
            self.inactive_players   = old.inactive_players[:]
            self.recent_arrivals    = old.recent_arrivals[:]
            self.player_places      = old.player_places[:]
            self.winner             = old.winner
```

### 5.1 Suggestion Phase Values

| `suggestion_phase` | Meaning |
|---|---|
| 0 | No suggestion in progress; normal movement/accusation turn |
| 2 | Room is registered (set automatically on entering a room); suspect must be chosen |
| 3 | Suspect chosen; weapon must be chosen |
| 4 | Full suggestion made; awaiting response from each player in turn (subturn rotation) |
| 5 | Refutation done (or no refutation possible); suggesting player acknowledges |

(Phase 1 was unused in SZ5 and is skipped; kept for backward compatibility if needed.)

### 5.2 `next_active_role(k, inactive_ok, state)` (replacing `next_player`)

```python
def next_active_role(k, state, inactive_ok=False):
    """Return the role number of the next active player after role k."""
    roles = state.active_roles
    n = len(roles)
    start_idx = roles.index(k) if k in roles else 0
    for offset in range(1, n + 1):
        candidate = roles[(start_idx + offset) % n]
        if inactive_ok:
            return candidate
        if candidate not in state.inactive_players:
            return candidate
    raise Exception("No active players remain.")
```

### 5.3 Other State Methods

- `__str__`: Keep from SZ5 (used for hashing/debugging) — remove `sr.*` calls; check against `active_roles` instead.
- `is_goal()`: `return self.winner is not None`
- `goal_message()`: `return f"{NAMES[self.winner]} wins! Thanks for playing OCCLUEdo."`
- `format_player_places()`: Iterate `active_roles` instead of `range(6)` + `sr.role_being_played`.

---

## 6. Operator List and Indices

The ordering below is critical because the VIS file uses `data-op-index` attributes that must align with operator positions in `self.operators`.

```
Operator group              | Count | Indices in operators list
-----------------------------|-------|---------------------------
go_ops (places 6-23)        |  18   |  0 – 17
  place 6  → Lounge's Lobby |       |  0
  place 7  → Dining Rm Lobby|       |  1
  place 8  → Kitchen Lobby  |       |  2
  place 9  → Ballroom Lobby |       |  3
  place 10 → Conserv. Lobby |       |  4
  place 11 → Billiard Lobby |       |  5
  place 12 → Library Lobby  |       |  6
  place 13 → Study Lobby    |       |  7
  place 14 → Hall Lobby     |       |  8
  place 15 → Lounge (room)  |       |  9
  place 16 → Dining Room    |       | 10
  place 17 → Kitchen        |       | 11
  place 18 → Ballroom       |       | 12
  place 19 → Conservatory   |       | 13
  place 20 → Billiard Room  |       | 14
  place 21 → Library        |       | 15
  place 22 → Study          |       | 16
  place 23 → Hall           |       | 17
op_start_suggestion          |   1   | 18
suspect_ops (0=Scarlet…5=White)|  6  | 19 – 24
weapon_ops (0=Candle…5=Wrench)|  6  | 25 – 30
response_ops (card slots 0-8)|   9   | 31 – 39
op_respond_sorry             |   1   | 40
op_acknowledge               |   1   | 41
op_start_accusation          |   1   | 42
add_room_to_accusation (0-8) |   9   | 43 – 51
add_player_to_accusation(0-5)|   6   | 52 – 57
add_weapon_to_accusation(0-5)|   6   | 58 – 63
op_ask_win                   |   1   | 64
-----------------------------|-------|---------------------------
TOTAL                        |  65   |
```

### 6.1 Convenience index-calculation formulas (for VIS)

```python
# Given a place index (6-23):
GO_OP_INDEX   = lambda place: place - 6          # 0-17

# Given a suspect number (0-5):
SUSPECT_OP    = lambda s: 19 + s                 # 19-24

# Given a weapon number (0-5):
WEAPON_OP     = lambda w: 25 + w                 # 25-30

# Given a response card slot (0-8):
RESPONSE_OP   = lambda k: 31 + k                 # 31-39

RESPOND_SORRY = 40
ACKNOWLEDGE   = 41
START_ACCUSE  = 42

# Given a room number (0-8):
ACCUSE_ROOM   = lambda r: 43 + r                 # 43-51

# Given a player number (0-5):
ACCUSE_PLAYER = lambda p: 52 + p                 # 52-57

# Given a weapon number (0-5):
ACCUSE_WEAPON = lambda w: 58 + w                 # 58-63

ASK_WIN       = 64
```

### 6.2 Key Operator Adaptations

**`go_ops`**: Identical logic to SZ5. Going to a room (place 15-23) sets `suggestion_phase=2` automatically and records the suggestion's room. Going to a lobby (place 6-14) advances the turn via `next_active_role()`.

**`response_ops`**: In SZ5, the operator names were dynamic lambdas. In SZ6, names must be static strings. Use `f"Show card {i+1}"` for the name. The jit_transition message will include the actual card name:
```python
ns.jit_transition = f"{NAMES[state.whose_subturn]} shows: {card_name(hand[card_no])}"
```

**`op_respond_sorry` / `cannot_disprove`**: In SZ5 the precondition had a bug (`if suspect_card in hand: return False` checked twice instead of checking weapon_card). Fix this in SZ6.

**All `add_to_next_transition()` calls**: Replace with assignment to `ns.jit_transition`. Where multiple messages were queued, join them:
```python
ns.jit_transition = msg1 + "\n" + msg2
```
(Only the final assignment before `return ns` matters; the engine broadcasts `jit_transition` once.)

---

## 7. Roles Specification

```python
class OCCLUEdo_Roles_Spec(sz.SZ_Roles_Spec):
    def __init__(self):
        self.roles = [
            sz.SZ_Role(name='Miss Scarlet',     description='Plays as Miss Scarlet.'),
            sz.SZ_Role(name='Mr. Green',        description='Plays as Mr. Green.'),
            sz.SZ_Role(name='Colonel Mustard',  description='Plays as Colonel Mustard.'),
            sz.SZ_Role(name='Prof. Plum',       description='Plays as Prof. Plum.'),
            sz.SZ_Role(name='Mrs. Peacock',     description='Plays as Mrs. Peacock.'),
            sz.SZ_Role(name='Mrs. White',       description='Plays as Mrs. White.'),
            sz.SZ_Role(name='Observer',         description='Watches the game.'),
        ]
        self.min_players_to_start = 2
        self.max_players          = 7
```

---

## 8. Formulation and `initialize_problem`

```python
class OCCLUEdo_Formulation(sz.SZ_Formulation):
    def __init__(self):
        self.metadata    = OCCLUEdo_Metadata()
        self.operators   = OCCLUEdo_Operator_Set()
        self.roles_spec  = OCCLUEdo_Roles_Spec()
        self.common_data = sz.SZ_Common_Data()
        self.vis_module  = _occluedo_vis   # imported at top of PFF

    def initialize_problem(self, config={}):
        # config may carry {'active_roles': [0, 2, 4]} from lobby.
        # Fall back to roles 0 and 1 if not specified (for single-session testing).
        active_roles = config.get('active_roles', [0, 1])
        deal(active_roles)           # Sets module-level MURDERER, CRIME_ROOM, etc.
        initial = OCCLUEdo_State(active_roles=active_roles)
        self.instance_data = sz.SZ_Problem_Instance_Data(
            d={'initial_state': initial, 'active_roles': active_roles}
        )
        return initial


# Module-level entry point (discovered by pff_loader duck typing)
OCCLUEDO = OCCLUEdo_Formulation()
```

### 8.1 Passing active_roles from lobby

The WSZ6 lobby consumer calls `formulation.initialize_problem(config)`. The plan is to pass the list of role numbers that have at least one player in the `config` dict. This requires a small enhancement to `lobby_consumer.py` to populate `config['active_roles']` before calling `initialize_problem`. If that enhancement is not yet made, the fallback `[0, 1]` keeps the game testable.

---

## 9. Interactive Visualization Design (`OCCLUEdo_WSZ6_VIS.py`)

The VIS uses **Tier 1 SVG** (`data-op-index` attributes) throughout — no JSON canvas manifest needed, because all interactive elements are SVG shapes we draw programmatically.

### 9.1 Secret Card Problem

In SZ5, `render_state(s, roles=None)` received the calling player's role list from the Flask server, enabling truly private card displays. The WSZ6 engine currently calls `render_state(state)` with no role argument; all clients receive the same HTML.

**Strategy for initial SZ6 port:**
- The VIS shows the cards only for `state.current_role_num` (the active player).
- When it is not a player's turn, they see the status and map but not their own hand.
- This is a significant limitation for the secrecy mechanic. It is acceptable for a first working version and for testing with a single operator-player.
- **Future enhancement**: Engine support for per-client role-filtered vis would allow the VIS to show `PLAYER_HAND[viewer_role]` privately to each connected client. This would require passing the viewer's role number as a parameter to `render_state`.

### 9.2 Overall HTML Layout

```
┌─────────────────────────────────────────────────────┐
│  Status bar: whose turn, suggestion/accusation state │
├──────────────────────┬──────────────────────────────┤
│  Location map (SVG)  │  Action panel (SVG or HTML)  │
│  (clickable rooms)   │  (cards, suspects, weapons)  │
├──────────────────────┴──────────────────────────────┤
│  Card hand: current player's face-up cards (images) │
└─────────────────────────────────────────────────────┘
```

### 9.3 Location Map SVG (left panel, 400×400)

Draw the 9 rooms in a 3×3 grid plus small "door" chevrons to their lobbies. Place-to-grid mapping:

```
Grid position  Room index  Room name        Lobby index
(row=0,col=0)    0         Lounge             6
(row=0,col=1)    1         Dining Room        7
(row=0,col=2)    2         Kitchen            8
(row=1,col=0)    3         Ballroom           9
(row=1,col=1)    4         Conservatory      10
(row=1,col=2)    5         Billiard Room     11
(row=2,col=0)    6         Library           12
(row=2,col=1)    7         Study             13
(row=2,col=2)    8         Hall              14
```

Secret passages (diagonal corners): Study(7)↔Kitchen(2) and Lounge(0)↔Conservatory(4).

#### Room cells (Tier 1 interactive)

For each room:
- Draw a 100×100 SVG `<rect>` at grid position.
- If the corresponding go_op is applicable (i.e., the player can enter this room from their current lobby), add `data-op-index="{GO_OP_INDEX(room_place)}"`.
- If the player is already in the room, shade the cell differently (no data-op-index, but show player tokens inside).
- Label with room name and a `data-info` attribute for non-clickable rooms.

#### Lobby "doors"

For each room's lobby:
- Draw a small 30×30 `<rect>` or diamond on the edge of the room cell.
- If `can_go(s, lobby_place)` is True, add `data-op-index="{GO_OP_INDEX(lobby_place)}"`.
- Hovering shows `"Enter {room}'s Lobby"` via CSS tooltip.

#### Player tokens

For each active role, draw a small colored circle at the center of their current cell. Use `ROLE_COLORS[role_num]`. Overlay a text abbreviation of the player's initials. Non-interactive (no data-* attributes).

#### Secret passage markers

Draw a dashed diagonal line across the Study and Kitchen cells (and across Lounge and Conservatory cells) to indicate the secret passage exists. Add `data-info="Secret passage to {other room}"` for informational hover.

### 9.4 Action Panel SVG (right panel, context-sensitive)

The right panel renders differently depending on the game phase.

#### Phase 0 — Normal movement (suggestion_phase == 0 and accusation_phase == 0)

- If the current player is in a room AND in `recent_arrivals`, show `op_start_suggestion` button (index 18).
- Show `op_start_accusation` button (index 42) if applicable.
- (Movement is handled via the room map on the left.)

#### Phase 2 — Choose suspect (suggestion_phase == 2)

Show six suspect portrait images in a 2×3 grid. Each image:
- `<image href="/play/game-asset/occluedo/images/{name_safe}.jpg" ... />`
- `data-op-index="{SUSPECT_OP(i)}"`
- `data-info="{NAMES[i]}"`

Portraits: Miss_Scarlet.jpg, Mr_Green.jpg, Colonel_Mustard.jpg, Prof_Plum.jpg, Mrs_Peacock.jpg, Mrs_White.jpg.

#### Phase 3 — Choose weapon (suggestion_phase == 3)

Show six weapon images in a 2×3 grid with `data-op-index="{WEAPON_OP(i)}"`.

Weapon images: Candlestick.jpg, Knife.jpg, Lead_Pipe.jpg, Revolver.jpg, Rope.jpg, Wrench.jpg.

#### Phase 4 — Refutation round (suggestion_phase == 4)

This panel appears only for the player whose subturn it is (`state.whose_subturn`). Since the VIS is shared, render this panel showing the **current subturn player's hand** (`PLAYER_HAND[state.whose_subturn]`):

- For each card in the hand, draw the card image.
  - If the card can refute the suggestion (matches suggestion room, suspect, or weapon), add `data-op-index="{RESPONSE_OP(card_slot_index)}"`.
  - Otherwise, grey it out (no data-op-index).
- If no cards can refute, show `op_respond_sorry` button (index 40) prominently.

**Note on secrecy**: In a real game, players should not see each other's cards. The initial SZ6 implementation shows the current subturn player's hand to all viewers. Future engine improvements can address this.

#### Phase 5 — Acknowledge refutation (suggestion_phase == 5)

Show:
- If `state.refutation_card` is not None: the refutation card image (visible only in this phase).
- Message: who showed it (or "Nobody could disprove the suggestion.").
- `op_acknowledge` button (index 41) for the main turn player.

#### Accusation — Phase 1, 2, 3, 4

Similar grid approach for room/suspect/weapon selection during an accusation. Reuse the same image grids as for suggestion, but use ACCUSE_ROOM / ACCUSE_PLAYER / ACCUSE_WEAPON operator index formulas. Phase 4 shows `op_ask_win` button (index 64).

### 9.5 Card Hand Display (bottom strip)

Below the two SVG panels, render an HTML strip showing the **current player's** known cards as `<img>` tags (not SVG images, so they display in natural aspect ratio):

```html
<div style="display:flex; gap:8px; margin-top:8px;">
  <img src="/play/game-asset/occluedo/images/Miss_Scarlet.jpg" height="90">
  <img src="/play/game-asset/occluedo/images/Ballroom.jpg" height="90">
  ...
</div>
```

These are informational only (no data-op-index). They are only rendered when `state.current_role_num < 6` and `PLAYER_HAND[state.current_role_num]` is not empty.

### 9.6 Status Bar

A narrow HTML header above the SVG panels:

```html
<div style="background:#1a1a2e; color:#fff; padding:6px 12px; font-size:.9rem;">
  It's <strong style="color:{ROLE_COLORS[whose_turn]}">Miss Scarlet</strong>'s turn.
  | Suggestion: Col. Mustard in the Library with the Rope
  | Waiting for Mr. Green to respond.
</div>
```

Color-code the active player's name using `ROLE_COLORS[state.whose_turn]`.

### 9.7 Image URL Pattern

```python
_SLUG     = 'occluedo'
_IMG_BASE = f'/play/game-asset/{_SLUG}/images'

CARD_IMAGES = {
    ('p', 0): 'Miss_Scarlet.jpg',
    ('p', 1): 'Mr_Green.jpg',
    ('p', 2): 'Colonel_Mustard.jpg',
    ('p', 3): 'Prof_Plum.jpg',
    ('p', 4): 'Mrs_Peacock.jpg',
    ('p', 5): 'Mrs_White.jpg',
    ('r', 0): 'Lounge.jpg',
    ('r', 1): 'Dining_Room.jpg',
    ('r', 2): 'Kitchen.jpg',
    ('r', 3): 'Ballroom.jpg',
    ('r', 4): 'Conservatory.jpg',
    ('r', 5): 'Billiard_Room.jpg',
    ('r', 6): 'Library.jpg',
    ('r', 7): 'Study.jpg',
    ('r', 8): 'Hall.jpg',
    ('w', 0): 'Candlestick.jpg',
    ('w', 1): 'Knife.jpg',
    ('w', 2): 'Lead_Pipe.jpg',
    ('w', 3): 'Revolver.jpg',
    ('w', 4): 'Rope.jpg',
    ('w', 5): 'Wrench.jpg',
}

def card_img_url(card):
    return f'{_IMG_BASE}/{CARD_IMAGES[card]}'
```

---

## 10. Image Assets

Copy all `.jpg` files from `SZ5_OCCLUEdo_web_as_ref/images/` into `game_sources/OCCLUEdo_images/`. The relevant images are:

- **Suspects** (6): Miss_Scarlet.jpg, Mr_Green.jpg, Colonel_Mustard.jpg, Prof_Plum.jpg, Mrs_Peacock.jpg, Mrs_White.jpg
- **Rooms** (9): Ballroom.jpg, Billiard_Room.jpg, Conservatory.jpg, Dining_Room.jpg, Hall.jpg, Kitchen.jpg, Library.jpg, Lounge.jpg, Study.jpg
- **Weapons** (6): Candlestick.jpg, Knife.jpg, Lead_Pipe.jpg, Revolver.jpg, Rope.jpg, Wrench.jpg
- **Other** (optional for now): Box_cover.jpg, Clue_card_back.jpg, Clue_sheet.jpg, board-for-OCLUEdo.jpg

The board image `board-for-OCLUEdo.jpg` could be used as a decorative background for the room map SVG in a future enhancement. For the initial version, the SVG room grid is drawn programmatically.

---

## 11. Installation

Add to `install_test_game.py` GAME_DEFS:

```python
{
    'slug':        'occluedo',
    'name':        'OCCLUEdo: An Occluded Game of Clue',
    'pff_file':    'OCCLUEdo_SZ6.py',
    'vis_file':    'OCCLUEdo_WSZ6_VIS.py',
    'images_dir':  'OCCLUEdo_images',
    'source_dir':  'Vis-Features-Dev/game_sources',
    'brief_desc':  (
        'A simplified online Clue/Cluedo for 2-6 players + observers. '
        'Players move between rooms, make suggestions about the murder, '
        'and try to identify the murderer, weapon, and room before anyone else.'
    ),
    'min_players': 2,
    'max_players': 7,
},
```

Then run:
```bash
source .venv/bin/activate && \
  DJANGO_SETTINGS_MODULE=wsz6_portal.settings.development \
  python manage.py install_test_game
```

Verify the images are served:
```
http://localhost:8000/play/game-asset/occluedo/images/Miss_Scarlet.jpg
```

---

## 12. Key Implementation Notes and Gotchas

### 12.1 Bug fix in `cannot_disprove` / `can_respond_sorry`

In the SZ5 code, `cannot_disprove` has a copy-paste bug:
```python
weapon_card = ('w', s.suggestion[2])
if suspect_card in hand: return False  # BUG: checks suspect_card again
```
The last line should be `if weapon_card in hand: return False`. Fix this in SZ6.

### 12.2 `go()` sets `suggestion_phase` directly

When a player moves into a room via `go()`, the function sets `news.suggestion_phase = 2` and `news.suggestion = [room_no, -1, -1]` — there is no separate "enter room" step. The turn does NOT advance (the same player must now choose a suspect). Only moving to a lobby advances the turn via `next_active_role()`.

The VIS must be careful: when `suggestion_phase == 2` AND `state.whose_turn == state.current_role_num`, it means the active player just moved into a room and must now pick a suspect. Show the suspect grid.

### 12.3 `op_start_suggestion` vs. automatic suggestion on `go()`

`op_start_suggestion` is only applicable when:
- It is the player's turn
- The player is currently in a room (not starting place or lobby)
- `suggestion_phase == 0` and `accusation_phase == 0`
- The player is in `state.recent_arrivals` (they were summoned there by another player's suggestion)

This covers the case where a player who was summoned to a room by someone else's suggestion now wants to make their own suggestion on their own turn. Normally, entering a room via `go()` bypasses this operator.

The VIS should show the `op_start_suggestion` button (index 18) only during phase 0 when the player is in a room and in recent_arrivals.

### 12.4 Response operator names (dynamic in SZ5)

In SZ5, `response_ops` used lambda for names: `lambda s, card_no=i: card_prompt(s, card_no)`. This cannot be done with `sz.SZ_Operator` which requires a static name string. Instead:

- Name the operators `"Show hand card 1"`, `"Show hand card 2"`, etc.
- The actual card name is conveyed via `jit_transition` in the transition function.
- In the VIS, these operators are triggered by clicking card images rather than named buttons, so the button label is less important.

### 12.5 `active_roles` initialization in `initialize_problem`

For testing, default to `[0, 1]` (Miss Scarlet and Mr. Green). The lobby consumer should eventually pass `config['active_roles']` listing the integer role indices that have at least one player. Until that lobby enhancement is made, the game is testable with `[0, 1]`.

### 12.6 Turn advancement in `go()` vs. `next_active_role()`

The `go()` function in SZ5 uses `next_player(news.whose_turn, state=s)` (with `state` passed), which skips inactive players. Replicate this by calling `next_active_role(news.whose_turn, s, inactive_ok=False)`. Note: `state=s` (the OLD state) is used so that `inactive_players` is checked before the new move is applied, consistent with SZ5 behavior.

### 12.7 Observer role

The Observer role (index 6) should never be in `active_roles` for game-play purposes. If a player takes the Observer role, they watch but do not appear in `player_places` or `inactive_players`. The VIS should gracefully handle `current_role_num == 6` by showing only the public game state without a hand panel.

---

## 13. Implementation Order

1. **Create `OCCLUEdo_images/`** directory and copy image files.
2. **Write `OCCLUEdo_SZ6.py`**:
   - Constants and helpers (`card_name`, `hand_to_string`, `next_active_role`, `deal`, `_shuffle`)
   - `OCCLUEdo_State`
   - All precondition and transition functions (adapted from SZ5)
   - `OCCLUEdo_Operator_Set` (verify operator order matches §6 index table)
   - `OCCLUEdo_Roles_Spec`
   - `OCCLUEdo_Formulation` (import vis module at top)
   - Module entry point `OCCLUEDO = OCCLUEdo_Formulation()`
3. **Write `OCCLUEdo_WSZ6_VIS.py`**:
   - Image URL helpers
   - `_render_status_bar(state)`
   - `_render_room_map(state)` → SVG with clickable rooms/lobbies
   - `_render_action_panel(state)` → context-sensitive right panel
   - `_render_hand(state)` → card image strip
   - `render_state(state)` → concatenate all four
4. **Update `install_test_game.py`** with the OCCLUEdo entry.
5. **Run installation** and test.

---

## 14. Testing Checklist

### Functional (no-VIS)

- [ ] `OCCLUEDO.initialize_problem({'active_roles': [0,1]})` runs without error; returns initial state
- [ ] `PLAYER_HAND` is set; each active role has at least one card
- [ ] `MURDERER`, `CRIME_ROOM`, `CRIME_WEAPON` are set and not in any hand
- [ ] Miss Scarlet (role 0) can move to Lounge's Lobby (op 0) from starting place
- [ ] Miss Scarlet can then move to the Lounge (op 9) from the lobby
- [ ] After entering the Lounge, `suggestion_phase == 2` and `suggestion[0] == 0` (Lounge)
- [ ] Suspect selection (op 19-24) advances `suggestion_phase` to 3
- [ ] Weapon selection (op 25-30) advances `suggestion_phase` to 4; subturn begins
- [ ] Mr. Green (role 1) can respond with a card (op 31-39) or sorry (op 40)
- [ ] After refutation, `suggestion_phase == 5`; Miss Scarlet acknowledges (op 41)
- [ ] After acknowledge, `suggestion_phase == 0`; it is Mr. Green's turn
- [ ] Accusation sequence works end-to-end (ops 42-64)
- [ ] Correct accusation sets `state.winner`; `is_goal()` returns True
- [ ] False accusation adds role to `inactive_players`; game continues with remaining players

### Visualization

- [ ] Status bar shows correct active player name and role color
- [ ] Room map SVG renders; all 9 rooms and 9 lobbies appear in 3×3 grid
- [ ] Hovering over accessible room/lobby shows gold highlight and hover tooltip
- [ ] Clicking accessible room applies the correct `go_op` (check jit_transition message)
- [ ] After entering a room, suspect grid appears with 6 portrait images
- [ ] Hovering over suspect portrait shows gold highlight
- [ ] Clicking suspect applies correct `suspect_op`; weapon grid appears next
- [ ] After suggestion is complete, action panel shows refutation instructions
- [ ] Current hand cards display correctly in the bottom strip
- [ ] Accusation mode shows room/suspect/weapon grids in sequence
- [ ] Game-over state renders without errors (no interactive elements should appear)

---

## 15. Future Enhancements (out of scope for initial port)

- **Per-player role-filtered VIS**: The engine sends different `vis_html` to each connected client based on their role. This enables truly private card displays.
- **Notepad / deduction sheet overlay**: Show `Clue_sheet.jpg` or an SVG deduction grid where players can mark off eliminated possibilities.
- **Board image background**: Use `board-for-OCLUEdo.jpg` (Tier 2 canvas overlay) for more faithful visual presentation of the room layout.
- **Multi-session card isolation**: Move `PLAYER_HAND` and crime solution into `SZ_Problem_Instance_Data` keyed by session ID.
- **Lobby `active_roles` passing**: Enhance `lobby_consumer.py` to populate `config['active_roles']` from role assignments before calling `initialize_problem()`.
