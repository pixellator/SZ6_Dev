# Experience Porting OCCLUEdo from SOLUZION5 to SOLUZION6

**Date:** 2026-02-20
**Session files:** `Vis-Features-Dev/`

---

## 1. Background

OCCLUEdo ("An Occluded Game of Clue") is a multi-player deduction game based on
the board game Clue.  The original implementation (`OCCLUEdo_web.py`) ran on
SOLUZION5 with a Flask web server.  This report documents the experience of
adapting it to the WSZ6-portal (SOLUZION6 + Django Channels), focusing on the
issues encountered with role-specific visualization.

The source files involved are:
- `game_sources/OCCLUEdo_SZ6.py` — the SZ6 problem formulation (PFF)
- `game_sources/OCCLUEdo_WSZ6_VIS.py` — the visualization module
- `wsz6_play/engine/game_runner.py` — the async game engine
- `wsz6_play/consumers/game_consumer.py` — the per-player WebSocket consumer

A reference web implementation (`SZ5_OCCLUEdo_web_as_ref/`) was available for
comparison.

---

## 2. The Role-Specific Visualization Problem

### 2.1 Why OCCLUEdo needs role-specific rendering

In standard SZ6 games (Tic-Tac-Toe, Missionaries, etc.) all players see
identical visualizations: the game state is fully public.  OCCLUEdo is different:

- Each player holds a private hand of cards that only they should see.
- During the refutation phase, only the responding player should see their own
  hand and the "Sorry" button.
- Only the suggester (not bystanders) should see which card was revealed to them.
- Observers should see no private hands at all.

### 2.2 The original (broken) architecture

Before porting, the engine's `_broadcast_state()` called
`vis_module.render_state(state)` once and broadcast the identical `vis_html` to
all connected players.  There was no mechanism to produce different HTML for
different viewers.

### 2.3 The fix: per-consumer rendering

The fix follows the same pattern already used for operator filtering.

**`game_runner.py`:**
- `_broadcast_state()` now sends a *base payload* with no `vis_html`.
- A new async method `render_vis_for_role(state, role_num=None)` uses
  `inspect.signature` to call `vis_module.render_state(state, **kwargs)`,
  passing only the keyword arguments the VIS module's signature declares.
  This preserves full backward compatibility with existing VIS modules.

**`game_consumer.py`:**
- `connect()` caches `self.runner` and calls
  `build_state_payload(role_num=self.role_num)` so the initial render is
  role-aware from the first connection.
- `state_update()` calls `self.runner.render_vis_for_role(...)` with the
  consumer's `role_num` and attaches the result to the outgoing payload,
  stripping any `vis_html` from the broadcast if rendering fails.

**`OCCLUEdo_WSZ6_VIS.py`:**
- `render_state(state, role_num=None, instance_data=None)` — new signature.
- `_build_hand_display` shows only the *viewing player's* hand.
- `_build_action_panel` during refutation (phase 4) shows the hand and "Sorry"
  button only to the responding player; others see "Waiting for [Name]...".
- During phase 5 (acknowledge), only the suggester sees which card was shown;
  others see "[Name] showed a card to [Suggester].  Waiting...".

---

## 3. The Module Isolation Bug

### 3.1 What went wrong

The first attempt at role-specific card display used *late imports* inside the
VIS helper functions:

```python
import OCCLUEdo_SZ6 as _pff
player_hand = _pff.PLAYER_HAND
```

This produced silent failures: cards never appeared.  The root cause was in
`pff_loader.py`.

### 3.2 How `pff_loader` works

`pff_loader.load_formulation()` loads the PFF using
`importlib.util.spec_from_file_location()` under a **unique module name**:

```python
unique_name = f"_pff_{game_slug.replace('-', '_')}_{uuid.uuid4().hex}"
sys.modules[unique_name] = module
```

The PFF module is therefore registered in `sys.modules` as
`_pff_occluedo_<uuid>`, *not* as `'OCCLUEdo_SZ6'`.  This is intentional: it
ensures that two concurrent sessions of the same game never share module-level
state (a known SZ5 bug).

When `initialize_problem()` runs, it calls `deal()`, which sets the module-level
globals `PLAYER_HAND`, `MURDERER`, `CRIME_ROOM`, and `CRIME_WEAPON` *on the
unique-named module instance*.  These are the correct, initialized values.

When VIS code later executed `import OCCLUEdo_SZ6 as _pff`, Python found no
`'OCCLUEdo_SZ6'` key in `sys.modules` and loaded a **fresh, uninitialized**
copy of the file from `sys.path`.  On that fresh copy, `PLAYER_HAND = None`
(the module-level default), so the `if not player_hand: return ''` guard
silently suppressed all card rendering.

The same issue affected `MURDERER`, `CRIME_ROOM`, and `CRIME_WEAPON` in the
game-over panel, and would have produced `'(solution unavailable)'` at game end.

### 3.3 First fix (temporary kludge)

The first fix stored `player_hand` and `crime_solution` directly on the
`OCCLUEdo_State` object and copied them through every state transition.  This
made cards visible but was architecturally wrong: these values are not part of
game state (they never change during a game) and should not bloat every state
object.

### 3.4 Proper fix: `instance_data`

The correct home for per-game-instance constants is the formulation's
`instance_data` object, which is created by `initialize_problem()` and lives
on the formulation for the lifetime of the game.

**`OCCLUEdo_SZ6.py` — `initialize_problem()`:**
```python
self.instance_data = sz.SZ_Problem_Instance_Data(
    d={'initial_state': initial, 'active_roles': active_roles}
)
self.instance_data.player_hand    = PLAYER_HAND
self.instance_data.crime_solution = (MURDERER, CRIME_ROOM, CRIME_WEAPON)
```

**`game_runner.py` — `render_vis_for_role()`:**
Extended to pass `instance_data` as a keyword argument when the VIS module's
`render_state` signature declares it:
```python
if 'instance_data' in params:
    kwargs['instance_data'] = getattr(self.formulation, 'instance_data', None)
```

**`OCCLUEdo_WSZ6_VIS.py`:**
`render_state(state, role_num=None, instance_data=None)` extracts `player_hand`
and `crime_solution` from `instance_data` at the top and passes them as explicit
parameters to `_build_hand_display` and `_build_action_panel`.  No late imports
of the PFF remain in the VIS file.

**`OCCLUEdo_State`:**
`player_hand` and `crime_solution` were removed entirely from the state class.
State objects are back to being pure per-turn value objects.

### 3.5 Rematch correctness

On rematch, `lobby_consumer` loads a fresh formulation (new unique module name)
and calls `runner.start()` → `initialize_problem()`.  `deal()` re-runs,
generating a new random `PLAYER_HAND`, `MURDERER`, etc., which are stored on the
fresh `instance_data`.  The previous game's `instance_data` is discarded with the
old formulation.  No special handling was needed in the WSZ6-play system.

---

## 4. Backward Compatibility

The `inspect.signature` dispatch in `render_vis_for_role()` means existing VIS
modules require no changes:

| VIS module | `render_state` signature | Engine behaviour |
|---|---|---|
| Tic-Tac-Toe, Mt. Rainier, etc. | `def render_state(state)` | Called with no kwargs |
| OCCLUEdo | `def render_state(state, role_num=None, instance_data=None)` | Called with both kwargs |
| Future games | Either pattern | Works automatically |

---

## 5. Current Status

### 5.1 Visualization: working

- Each player sees only their own card hand in the bottom strip.
- During refutation (phase 4), only the responding player sees their cards and
  the "Sorry" button; others see a waiting message.
- During phase 5, only the suggester sees which card was shown; others see a
  neutral message.
- Observers (role 6) see no private hand (guarded by `viewing_role >= 6`).
- Reconnecting players receive the correct role-specific vis from `connect()`.
- Tic-Tac-Toe and all other existing games are unaffected (regression confirmed).

### 5.2 Game logic: suspected issue

During testing (Owner1 as Miss Scarlet, Player1 as Mr. Green), the game hung
after the "Sorry — I cannot disprove the suggestion" button was clicked.  No
operators responded to clicks afterwards.  The sequence before the hang was:

1. Miss Scarlet moves to Kitchen's Lobby.
2. Mr. Green moves to Study's Lobby.
3. Miss Scarlet moves to Kitchen (entering a room auto-starts suggestion phase 2).
4. Miss Scarlet suggests Miss Scarlet (suspect).
5. Miss Scarlet suggests Candlestick (weapon) → transitions to phase 4 (refutation).
6. Mr. Green clicks "Sorry" → game hangs.

This suggests a bug in the `respond_sorry` or `can_respond_sorry` logic, or in
the transition that follows (advancing `current_role_num` after the refutation
round), not in the VIS or engine routing.  This has not yet been debugged.

---

## 6. Technical Debt

- The `can_respond_sorry` / refutation-loop logic should be traced and tested.
- Module-level globals (`MURDERER`, `CRIME_ROOM`, `CRIME_WEAPON`, `PLAYER_HAND`)
  still exist in `OCCLUEdo_SZ6.py` for use by operator preconditions and
  transitions (e.g. `can_respond`).  These work correctly within the unique
  module instance but represent the "single-session limitation" noted in the
  PFF's own comments.  If the portal ever runs two concurrent OCCLUEdo sessions
  in the same process, those sessions will share these globals.  A full fix
  would pass the relevant data through the state object or through operator
  closures; this is deferred as known technical debt.
- The `instance_data` approach is the right architectural direction for VIS
  access to per-game constants and should be adopted by any future multi-player
  game with private information.
