# VIS_DEV_PLAN.md — Visualization & Rich Play Features for WSZ6-play

**Date:** 2026-02-19
**Context:** Building out the visualization, interactivity, and player-experience features
described in `Vis-Features-Prompt.txt`, building on the completed Phase 2 WSZ6-play MVP.

---

## 1. Recommended Mix of Activities

Activities a–e from the prompt are not equally weighted. Here is the proposed balance:

| Activity | Weight | Rationale |
|---|---|---|
| **a. Read existing WSZ6-play code** | Low ongoing | Already done in this session; small follow-up reads as needed before each feature |
| **b. Read SOLUZION5 vis files** | Low–Medium | Useful for inspiration and porting, but SOLUZION6 diverges enough that we mostly design fresh |
| **c. Construct new vis test files** | Medium | A well-crafted Tic-Tac-Toe vis file drives development of every milestone; we add a second game (Missionaries or Fox & Hounds) for Milestone 3+ testing |
| **d. Implement features** | High | This is the primary work across all milestones |
| **e. Test new features** | Medium | Each milestone ends with a defined test checklist; no separate "test phase" at the end |

**Key principle:** Build a vis file and implement the server/client feature that renders it together, in
the same milestone. This keeps the feedback loop tight and avoids building infrastructure that
nobody has tested with real art.

---

## 2. Milestones

| # | Name | Description |
|---|---|---|
| **M0** | **Transition History (Quick Win)** | Fix disappearing transition messages; add persistent history panel |
| **M1** | **Basic Vis Rendering** | `_WSZ6_VIS.py` file convention; server loading; HTML div rendering; Tic-Tac-Toe SVG board |
| **M2** | **Image Resources** | Serve game-folder images as static assets; client-side caching |
| **M3** | **Interactive Vis** | Click graphic to activate operator; coordinate capture for parameterized ops |
| **M4** | **Full-Screen Mode** | Full-screen view; operator buttons auto-hide/reveal; Esc to exit |
| **M5** | **Previous-State Toggle** | Toggle between current-state and previous-state vis; available in both normal and full-screen |
| **M6** | **Visual Transitions** | Cross-fade and configurable CSS/SVG animation between state vis updates |
| **M7** | **Audio Support** | Play audio files on state/transition; optional TTS of transition messages |
| **M8** | **Vis-Debug Mode** | Debug flag in PFF; auto-open browser tabs; live-reload of vis file |

---

## 3. Detailed Plan

---

### M0 — Transition History (Quick Win)

**Goal:** Eliminate the layout-jump problem caused by auto-dismissing transition messages,
and provide a persistent, reviewable transition history.

**Why first:** It is a regression relative to SOLUZION5, it is annoying to players right now,
and it sets up the "message history" data structure that later milestones (M7 TTS, M8 debug)
will also use.

#### Changes

**`wsz6_portal/wsz6_play/templates/wsz6_play/game.html`**

1. Remove the `setTimeout` that hides the transition message.
2. Keep the current-message element permanently visible. Style it with a game-controllable CSS
   class (e.g. `transition-msg`) so formulations can later customize it (M1+).
3. Add a collapsible `<details id="transition-history">` panel below the state display (or in a
   dedicated sidebar area). Each `transition_msg` event prepends a `<li>` to the history list.
4. History items are plain text by default. When a history item is clicked/selected, show it
   re-rendered with the original styling (store the raw HTML alongside each item).
5. The history header shows a count: "Transition History (12 moves)".

**No server-side changes needed for M0.**

#### Test Checklist
- [ ] Transition message never disappears automatically.
- [ ] Page layout does not jump when a message arrives.
- [ ] History accumulates across the full game.
- [ ] Clicking a history item re-displays it with original styling.
- [ ] Collapsing/expanding the history panel works.

---

### M1 — Basic Vis Rendering

**Goal:** Define the vis file convention, plumb it through the server, and render the first
real SVG visualization for Tic-Tac-Toe.

#### Vis File Convention

A vis file is an optional Python module located in the game's directory:

```
<game_dir>/<game_slug>_WSZ6_VIS.py
```

It must expose a single callable:

```python
def render_state(state) -> str:
    """Return an HTML string (may include SVG, CSS, or plain HTML)
    representing the given state. Called after every operator application."""
    ...
```

It may also optionally expose:

```python
def render_previous_state(current_state, previous_state) -> tuple[str, str]:
    """Return (current_html, previous_html) when the previous-state toggle
    is active. Falls back to calling render_state twice if not defined."""
    ...

VIS_METADATA = {
    "transition_effect": "crossfade",   # M6: "none" | "crossfade" | "slide"
    "transition_duration_ms": 400,      # M6
    "audio_on_transition": None,        # M7: path relative to game_dir, or None
    "tts_enabled": False,               # M7
}
```

#### Server Changes

**`wsz6_play/engine/pff_loader.py`**

Add `load_vis_module(game_dir, slug)` helper:

```python
def load_vis_module(game_dir: str, slug: str):
    """Try to load <game_dir>/<slug>_WSZ6_VIS.py.
    Returns the module or None if not found."""
```

- Uses `importlib.util.spec_from_file_location` with a unique module name (same pattern as PFF
  loading).
- Called once at session start (in lobby consumer, right after PFF is loaded).
- The module handle is stored on the `GameRunner` instance as `runner.vis_module`.

**`wsz6_play/engine/game_runner.py`**

- After each operator application, if `vis_module` is set, call
  `vis_module.render_state(new_state)` in a thread and include the result in the
  `state_update` broadcast as the `vis_html` key.
- Also compute `prev_vis_html` (render of the previous state) and include it in the broadcast.
  This supports M5 without extra round-trips.
- If `render_state` raises, log the exception and fall back to the existing `str(state)` display.

#### Client Changes

**`game.html`**

- Replace the `<pre id="state-display">` with:
  ```html
  <div id="vis-display" class="vis-container">
      <!-- filled by JS from vis_html; falls back to <pre> if vis_html is absent -->
  </div>
  ```
- In the `state_update` handler:
  - If `vis_html` is present, set `vis_display.innerHTML = msg.vis_html`.
  - Otherwise, render a `<pre>` with `str_state` as before (backward-compatible).
- Add a small CSS block for `.vis-container` (overflow: auto, sensible max dimensions).

#### New Test Vis File

**`/mnt/c/users/sltan/desktop/SZ6_Dev/games_repo/tic_tac_toe/tic_tac_toe_WSZ6_VIS.py`**

Render the 3×3 board as an SVG grid:
- 3×3 grid of rectangles; X drawn as two crossing lines, O as a circle.
- Winning cells highlighted (e.g. gold background).
- Recent move highlighted with a subtle pulse animation.
- Board is sized relative to the container (`viewBox` + `width="100%"`).

#### Test Checklist
- [ ] When a game without a vis file is played, the `<pre>` fallback still works.
- [ ] When a game with `_WSZ6_VIS.py` is played, the SVG renders in `#vis-display`.
- [ ] Each operator application updates the SVG.
- [ ] Vis rendering exceptions do not break the game; fallback activates automatically.
- [ ] Tic-Tac-Toe board is visually correct for all states (empty, mid-game, win, draw).

---

### M2 — Image Resources

**Goal:** Allow vis files to reference images stored in the game folder (e.g. piece sprites,
background textures). Serve them efficiently with client-side caching.

#### Server Changes

**New URL route** (in `wsz6_play/urls.py`):

```
/play/game-asset/<slug>/<path:filename>
```

**New view** (`wsz6_play/views.py`):

```python
def game_asset(request, slug, filename):
    """Serve a file from the game's directory as a static asset.
    Validates that the file is inside the game dir (no path traversal).
    Sets long Cache-Control headers for browser caching."""
```

- Looks up `slug` → game directory via `GamesCatalog` model.
- Validates the resolved path is under the game directory.
- Serves with `FileResponse` and `Cache-Control: max-age=86400`.
- Only image types (png, jpg, gif, svg, webp) are served; others return 404.

#### Vis File API

In vis files, authors use a helper injected by the loader:

```python
# At the top of the vis file — this import is auto-injected or available via a helper:
from wsz6_vis_helpers import game_asset_url

def render_state(state):
    img_url = game_asset_url("pieces/pawn.png")  # resolved at runtime
    return f'<img src="{img_url}" .../>'
```

Alternative (simpler, no import needed): the loader calls `set_game_asset_base_url(base_url)`
on the vis module before first render, and the module stores it in a module-level variable.

#### Client Changes

No special JS changes beyond standard browser image caching (driven by `Cache-Control` headers).

For games that use many images, the vis file can pre-declare them so the client fetches them
eagerly:

```python
PRELOAD_ASSETS = ["pieces/pawn.png", "pieces/knight.png", ...]
```

On game start, the server sends a `preload_assets` message with URLs; the client inserts
`<link rel="preload">` tags.

#### Test Checklist
- [ ] Images served from game dir appear in vis correctly.
- [ ] Path traversal attacks (e.g. `../../settings.py`) are blocked (404).
- [ ] Non-image file types are blocked.
- [ ] Browser caches images across moves (verify with DevTools Network tab).
- [ ] Preload hints eliminate first-move image flicker.

---

### M3 — Interactive Visualization

**Goal:** Let players interact with the state visualization directly — clicking to activate
operators or obtain contextual information — instead of always using the operator button list.

#### Design

The vis file's `render_state` function embeds `data-*` attributes on clickable elements:

```python
# Activate an operator by clicking (no-param or fully-specified param):
f'<rect data-op-index="3" data-op-args="[1,2]" .../>'

# Activate a parameterized operator by supplying mouse coordinates:
# (coords are relative to the bounding box of the element with this attribute)
f'<rect id="board" data-op-index="3" data-op-coord-target="true" .../>'

# Show info on click (does not activate an operator):
f'<circle data-info="This is the knight at e4." .../>'
```

#### Client Changes

**`game.html`** — event delegation on `#vis-display`:

```javascript
visDisplay.addEventListener('click', (e) => {
    const el = e.target.closest('[data-op-index]');
    if (!el) return;
    const opIndex = parseInt(el.dataset.opIndex);
    if (el.dataset.opCoordTarget === 'true') {
        const rect = el.getBoundingClientRect();
        const x = (e.clientX - rect.left) / rect.width;   // 0.0–1.0
        const y = (e.clientY - rect.top) / rect.height;
        sendMessage({ type: 'apply_operator', op_index: opIndex,
                      args: { x: x.toFixed(4), y: y.toFixed(4) } });
    } else if (el.dataset.opArgs) {
        sendMessage({ type: 'apply_operator', op_index: opIndex,
                      args: JSON.parse(el.dataset.opArgs) });
    } else {
        sendMessage({ type: 'apply_operator', op_index: opIndex });
    }
});

visDisplay.addEventListener('click', (e) => {
    const el = e.target.closest('[data-info]');
    if (el) showInfoTooltip(e.clientX, e.clientY, el.dataset.info);
});
```

Operator buttons remain visible alongside the graphic; clicking the graphic is an additional
path, not a replacement.

#### Updated Tic-Tac-Toe Vis File

Each empty cell gets `data-op-index` pointing to the appropriate `PlaceX` or `PlaceO` operator.
The grid becomes fully clickable — no need to type row/col in the parameter form.

#### Server Changes

None required beyond what M1 already delivers. Coordinate args arrive via the normal
`apply_operator` message.

#### Test Checklist
- [ ] Clicking an empty Tic-Tac-Toe cell applies the correct operator.
- [ ] Clicking an already-occupied cell does nothing (precondition fails on server; error shown).
- [ ] Clicking an info-annotated element shows a tooltip.
- [ ] Coordinate-capture ops (if tested with a custom game) receive correct normalized x/y.
- [ ] Operator buttons still work alongside graphic clicks.
- [ ] Turn guard still applies: clicking on the graphic during the opponent's turn is ignored.

---

### M4 — Full-Screen Mode

**Goal:** Replicate and improve on the Web_SOLUZION5 full-screen visualization experience.

#### Behavior

- A "⛶ Full Screen" button appears beneath the state vis area.
- Clicking it enters full-screen mode:
  - The `#vis-display` element expands to cover the entire browser viewport (CSS `position:fixed`,
    full width/height, dark backdrop).
  - The SVG `viewBox` is preserved so it scales to fill available space correctly.
  - The operator button panel is hidden.
  - A semi-transparent operator tray slides in from the bottom when the mouse cursor moves to the
    bottom 10% of the screen (CSS hover + JS pointer-tracking fallback).
  - The Esc key exits full-screen mode.
  - A small "✕" button is always visible in the top-right corner of the full-screen overlay.
- State updates continue to flow normally; the vis rerenders in-place.
- The previous-state toggle (M5) is also available in full-screen mode.

#### Implementation

**`game.html`**

- Add a `<div id="fs-overlay" class="fs-overlay hidden">` wrapping `#vis-display` clone (or move
  the original element into the overlay on enter and restore it on exit).
- CSS: `.fs-overlay { position: fixed; inset: 0; z-index: 9999; background: #111; display: flex;
  flex-direction: column; align-items: center; justify-content: center; }`
- JS: `enterFullscreen()` / `exitFullscreen()` functions toggle `.hidden` and bind/unbind Esc key.
- The operator tray in full-screen is a `<div class="fs-op-tray">` positioned at the bottom,
  shown/hidden with CSS transitions triggered by a pointer-proximity check.
- The transition history panel (M0) is also accessible in full-screen via a floating icon button.

#### Test Checklist
- [ ] Full-screen button appears for games with a vis file.
- [ ] Entering full-screen hides all normal page chrome.
- [ ] Vis fills screen while preserving aspect ratio.
- [ ] Moving pointer to bottom reveals operator tray; moving away hides it.
- [ ] Esc and ✕ button both exit full-screen.
- [ ] State updates (opponent moves, bot moves) still render correctly in full-screen.
- [ ] Full-screen works on both wide and narrow viewport aspect ratios.

---

### M5 — Previous-State Toggle

**Goal:** Let players compare the current state vis to the previous state vis, in both normal
and full-screen modes.

#### Behavior

- A "↔ Show Previous" toggle button appears beneath the vis area (and in the full-screen tray).
- When toggled on, the display switches to `prev_vis_html` (which the server already sends in
  `state_update` messages as of M1).
- The button label changes to "↔ Show Current".
- An "PREVIOUS STATE" watermark or banner overlays the vis to avoid confusion.
- At step 0 (initial state), there is no previous state; the button is disabled.

#### Implementation

**`game.html`**

- Maintain `currentVisHtml` and `prevVisHtml` variables in JS.
- Toggle button flips a boolean `showingPrev` and re-renders accordingly.
- On each new `state_update`, if `showingPrev` is true, revert to "show current" automatically
  (a new move implies the player wants to see the new state).

#### Test Checklist
- [ ] Toggle is disabled at step 0.
- [ ] Toggling shows the previous state vis with watermark.
- [ ] A new move automatically reverts the toggle to "show current".
- [ ] Works in full-screen mode.

---

### M6 — Visual Transitions

**Goal:** Smooth visual transitions between state visualizations, configurable per-game.

#### Options

| Effect | Description | Implementation |
|---|---|---|
| `none` | Immediate swap (current default behavior) | — |
| `crossfade` | Old vis fades out while new fades in | CSS `opacity` transition on two overlaid divs |
| `slide_left` | New state slides in from the right | CSS `transform: translateX` transition |
| `custom_css` | Game provides CSS animation class names | Applied to the vis container div |
| `svg_animate` | Game's SVG uses `<animate>` / `<animateTransform>` | No extra plumbing needed — SVG handles it |

#### Implementation

**`game_runner.py`** — include `VIS_METADATA["transition_effect"]` and
`VIS_METADATA["transition_duration_ms"]` in the initial `game_info` message.

**`game.html`**

- The vis container holds two child divs: `#vis-a` and `#vis-b` (double-buffering).
- On `state_update`, write new HTML to the off-screen div, then trigger the CSS transition that
  swaps opacity/transform, then make the new div the "active" one.
- Transition class applied to the container: `vis-transition-crossfade`, etc.
- CSS for each effect is included in the template; duration is set via a CSS custom property
  (`--vis-transition-duration`).

#### Test Checklist
- [ ] Games with `transition_effect: "none"` still work (immediate swap).
- [ ] Crossfade is smooth at the configured duration.
- [ ] Transition does not cause layout shifts outside the vis container.
- [ ] Rapidly applied operators (e.g. bot moves) queue transitions or skip to the latest state
  without visual glitching.

---

### M7 — Audio Support

**Goal:** Allow game formulations to play audio as part of state updates or transition messages.

#### Vis File API

```python
VIS_METADATA = {
    "audio_on_transition": None,   # str: path relative to game_dir, played on every transition
    "tts_enabled": False,          # bool: read transition messages aloud
    "tts_voice": "default",        # str: Web Speech API voice name hint
}

def get_audio_for_transition(prev_state, new_state, op_name: str) -> str | None:
    """Return a path (relative to game_dir) to play, or None for silence.
    Called after each operator application. Takes precedence over audio_on_transition."""
    ...
```

#### Client Changes

**`game.html`**

- On `state_update`, if `audio_url` is present in the message, play it:
  ```javascript
  new Audio(audioUrl).play();
  ```
- For TTS: on `transition_msg`, if TTS is enabled for the game, use the Web Speech API:
  ```javascript
  const utt = new SpeechSynthesisUtterance(msg.text);
  window.speechSynthesis.speak(utt);
  ```
- Add a global mute button (🔇) in the game page header; stores preference in `localStorage`.
- Audio respects browser autoplay policies; a one-time click anywhere on the page unlocks audio
  (standard technique).

#### Server Changes

**`game_runner.py`** — if vis module defines `get_audio_for_transition`, call it after each op,
include the resolved asset URL in the `state_update` message as `audio_url`.

#### Test Checklist
- [ ] Audio file plays after an operator application.
- [ ] TTS reads the transition message aloud.
- [ ] Mute button silences both audio and TTS; preference persists across page reload.
- [ ] No audio plays if no audio is configured (no regressions).
- [ ] Browser autoplay prompt handled gracefully.

---

### M8 — Vis-Debug Mode

**Goal:** Support rapid iteration on vis files by game designers without needing to manually
set up multi-player test sessions.

#### PFF Flag

In the game's PFF (or `VIS_METADATA`), add:

```python
VIS_DEBUG = {
    "enabled": True,
    "num_players": 2,           # number of browser tabs to open
    "auto_moves": 3,            # apply this many random moves before pausing
    "live_reload": True,        # watch vis file for changes and reload
}
```

#### Behavior

When a game is started with `VIS_DEBUG.enabled = True`:

1. **Server:** After `initialize_problem()`, if `auto_moves > 0`, apply that many randomly chosen
   valid operators (one per player, in turn order).
2. **Auto browser tabs:** A management command or dev-server hook opens browser tabs for each
   player role automatically (using Python's `webbrowser` module).
3. **Live reload:** A background thread watches the vis file with `watchdog` (or falls back to
   polling). When the file changes, re-import it and broadcast a `vis_reload` message. The client
   re-requests the current state rendering (send a `request_state_refresh` WS message).

#### Implementation Notes

- `VIS_DEBUG` is only honored when `DEBUG=True` in Django settings (never in production).
- The management command `python manage.py vis_debug <game_slug>` creates a temporary session,
  opens tabs, and streams debug output to the terminal.
- Live-reload uses `importlib.reload()` on the vis module; thread-safe via the existing
  GameRunner lock.

#### Test Checklist
- [ ] `vis_debug` management command creates a session and opens browser tabs.
- [ ] Auto-moves leave the board in an interesting mid-game state.
- [ ] Editing and saving the vis file causes the browser to refresh the visualization within 2s.
- [ ] `VIS_DEBUG` is completely ignored when `DEBUG=False`.

---

## 4. Implementation Order and Dependencies

```
M0 (Transition History)
  └─ No dependencies; do first.

M1 (Basic Vis Rendering)
  └─ Blocks M2, M3, M4, M5, M6, M7, M8 (all require vis rendering).

M2 (Image Resources)
  └─ Independent of M3–M8 (can be done in parallel with M3).

M3 (Interactive Vis)
  └─ Requires M1; enhances Tic-Tac-Toe vis file.

M4 (Full-Screen)
  └─ Requires M1; enhanced by M5 (toggle available in full-screen).

M5 (Previous-State Toggle)
  └─ Requires M1; can be done before or after M4.

M6 (Visual Transitions)
  └─ Requires M1; independent of M3–M5.

M7 (Audio)
  └─ Requires M1; independent of M3–M6.

M8 (Vis-Debug)
  └─ Requires M1; benefits from M3 (interactive) for testing interaction ops.
```

Recommended implementation sequence:
**M0 → M1 → M3 → M5 → M4 → M2 → M6 → M7 → M8**

Rationale: M3 (interactive vis) is the highest-value feature for players and provides the most
interesting test cases; M4 (full-screen) and M5 (toggle) are companion display features; M2, M6,
M7, M8 are important but less fundamental.

---

## 5. New Test Vis Files to Create

| File | Game | Primary Features Exercised |
|---|---|---|
| `tic_tac_toe_WSZ6_VIS.py` | Tic-Tac-Toe | SVG board, click-to-place (M3), win highlight, crossfade (M6) |
| `missionaries_WSZ6_VIS.py` | Missionaries & Cannibals | SVG river scene, animated crossing (M6), coordinate capture |
| `rock_paper_scissors_WSZ6_VIS.py` | Rock-Paper-Scissors | Simple icon display, audio on reveal (M7), previous-state toggle (M5) |

The Tic-Tac-Toe vis is the primary driver for M1 through M6. Rock-Paper-Scissors is ideal for
M7 because the state change is minimal but the audio feedback (e.g. a "scissors snip" sound) is
immediately satisfying to test.

---

## 6. Files That Will Change

### Modified
- `wsz6_play/engine/pff_loader.py` — add `load_vis_module()`
- `wsz6_play/engine/game_runner.py` — vis rendering per state update; audio_url; debug mode
- `wsz6_play/consumers/lobby_consumer.py` — call `load_vis_module()` at session start
- `wsz6_play/templates/wsz6_play/game.html` — all client-side changes (all milestones)
- `wsz6_play/urls.py` — add game-asset route
- `wsz6_play/views.py` — add `game_asset` view

### New
- `wsz6_play/vis_loader.py` — module wrapping vis file loading and live-reload (extracted from
  `pff_loader.py` for cleanliness)
- `wsz6_play/management/commands/vis_debug.py` — dev management command (M8)
- `games_repo/tic_tac_toe/tic_tac_toe_WSZ6_VIS.py` — primary test vis
- `games_repo/rock_paper_scissors/rock_paper_scissors_WSZ6_VIS.py` — audio test vis (M7)
- `games_repo/missionaries/missionaries_WSZ6_VIS.py` — coordinate-capture test (M3)

---

*End of VIS_DEV_PLAN.md*
