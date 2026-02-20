# How to Code Interactive Visualizations in WSZ6

**Date:** 2026-02-19
**Milestone:** M3 (Interactive Vis)
**Status:** Tier 1 untested in production; Tier 2 tested with Click-the-Word (SVG scene) and Pixel Probe (raster JPEG, dynamic coordinate capture).

---

## Overview

WSZ6's visualization system lets a game's companion `_WSZ6_VIS.py` file return
arbitrary HTML for each game state.  M3 makes that HTML interactive: players can
click on visual elements to apply operators, hover to see highlights, and
right-click for a context menu.

Two tiers of interaction coexist, because visualizations are not always SVGs:

| Tier | Target | How it works |
|---|---|---|
| **Tier 1** | SVG elements and HTML elements that carry `data-*` attributes | CSS hover + JS event delegation on `#vis-display`. Zero extra JS in the vis file. |
| **Tier 2** | Raster images, canvases, or any scene where regions are *geometric* rather than DOM elements | The vis file embeds a JSON region manifest; `game.html` overlays a transparent `<canvas>` and does point-in-region hit testing. |

Both tiers share the same action handlers (`applyOp`, `showInfoPopup`,
`showCtxMenu`) and produce identical visual feedback (gold highlight, pointer
cursor).

---

## Part 1 — Tier 1: SVG / HTML element interaction

### How it works (no code needed in the vis file)

`game.html` listens for clicks and right-clicks on *all* elements inside
`#vis-display`.  If the clicked element (or any ancestor up to `#vis-display`)
carries one of the magic `data-*` attributes, the corresponding action fires.

### Data-attribute reference

| Attribute | Value type | Effect on left-click |
|---|---|---|
| `data-op-index` | integer | Calls `applyOp(N)` — applies operator N |
| `data-op-args` | JSON array | Passed as `args` with the operator (optional; only used alongside `data-op-index`) |
| `data-info` | string | Shows an info popup near the cursor |
| `data-context` | JSON array | **Right-click only** — shows a context menu; items: `{"label", "op_index"?, "op_args"?, "info"?}` |

Priority rule: `data-op-index` takes precedence over `data-info` on the same element.

### CSS hover behaviour (automatic)

- SVG elements: a gold stroke (`#ffd700`, 3 px) appears on hover.
- Plain HTML elements (non-SVG): a yellow-tint background + gold outline appears.
- The cursor changes to `pointer` over any interactive element.

### Minimal Tier 1 example (SVG Tic-Tac-Toe cell)

```python
def render_state(state):
    ops   = state.available_ops   # list of op indices for empty cells
    cells = []
    for row in range(3):
        for col in range(3):
            idx  = row * 3 + col
            x, y = 10 + col * 60, 10 + row * 60
            op   = ops.get(idx)          # None if cell is taken
            attr = f'data-op-index="{op}"' if op is not None else ''
            hover_info = f'data-info="Cell ({row},{col})"'
            cells.append(
                f'<rect x="{x}" y="{y}" width="58" height="58" '
                f'fill="white" stroke="#333" stroke-width="2" '
                f'{attr} {hover_info}/>'
            )
    return f'<svg width="190" height="190">{"".join(cells)}</svg>'
```

Clicking an empty cell calls `applyOp(op_index)`.  Hovering shows a small info
popup.  No JSON manifest, no canvas — just attributes in the SVG markup.

---

## Part 2 — Tier 2: Canvas region hit-testing

Use Tier 2 when:

- The scene is a raster image (JPEG, PNG) embedded with `<img>`.
- The scene is drawn on a `<canvas>`.
- You want to define hit regions by geometry (polygon, circle, rect) rather than
  by DOM element boundaries — e.g. for complex organic shapes in an SVG where
  you don't want to scatter `data-*` attributes across dozens of `<path>` tags.

### How it works

After every state update, `game.html` calls `setupHitCanvas()`.  That function:

1. Looks for `<script type="application/json" id="wsz6-regions">` inside
   the freshly injected `vis_html`.
2. Parses the JSON manifest.
3. Locates the container element specified by `container_id`.
4. Creates a transparent `<canvas>` overlay (same size as the scene,
   CSS-scaled to fill the container) and appends it to the container.
5. On `mousemove`: iterates regions in array order and highlights the first
   matching one with a gold fill + stroke.
6. On `click` / `contextmenu`: dispatches to the same `applyOp` /
   `showInfoPopup` / `showCtxMenu` handlers as Tier 1.

The canvas is **torn down and rebuilt** on each state update, so stale event
handlers never accumulate.

### Region manifest schema

```json
{
  "container_id": "wsz6-scene",
  "scene_width":  600,
  "scene_height": 400,
  "regions": [
    {
      "op_index":    0,
      "shape":       "circle",
      "cx": 215, "cy": 207, "r": 27,
      "hover_label": "apple"
    },
    {
      "op_index":    2,
      "shape":       "rect",
      "x": 148, "y": 215, "w": 284, "h": 65,
      "hover_label": "table"
    },
    {
      "op_index":    3,
      "shape":       "polygon",
      "points":      [[64,180],[154,180],[154,282],[64,282]],
      "hover_label": "chair"
    },
    {
      "info":        "This is just an info region — no operator.",
      "shape":       "rect",
      "x": 10, "y": 10, "w": 80, "h": 30,
      "hover_label": "Help zone"
    },
    {
      "context": [
        {"label": "Pick up", "op_index": 7},
        {"label": "Inspect", "info":     "A worn leather-bound tome."}
      ],
      "shape":       "rect",
      "x": 279, "y": 206, "w": 59, "h": 18,
      "hover_label": "book"
    }
  ]
}
```

#### Shape field reference

| `shape` | Required fields | Description |
|---|---|---|
| `"rect"` | `x, y, w, h` | Axis-aligned rectangle |
| `"circle"` | `cx, cy, r` | Disc |
| `"polygon"` | `points` — array of `[x,y]` pairs | Arbitrary polygon (ray-casting hit test) |

#### Action field reference (one per region)

| Field | Type | Effect |
|---|---|---|
| `op_index` | integer | Left-click → `applyOp(op_index, args?)` |
| `op_args` | any (optional) | Passed as `args` with the operator (static value) |
| `send_click_coords` | boolean (optional) | When `true` alongside `op_index`, forwards `[x, y]` natural-coordinate click position as `args` instead of `op_args`; used when the operator needs the exact pixel clicked |
| `info` | string | Left-click (when no `op_index`) → info popup |
| `context` | array of items | Right-click → context menu |
| `hover_label` | string | Small tooltip near cursor while hovered |

#### Hit-testing priority

Regions are tested **in array order**; the **first** matching region wins.
This means:

- Put **small or specific** regions (objects on a table) **before** the
  larger region that contains them (the table itself).
- Put large background regions last.

---

## Part 3 — Walkthrough: "Cliquez sur l'image"

The Click-the-Word game (`click-the-word` slug) is the canonical M3 Tier-2
demo.  Here we trace every piece from state design to rendered HTML.

### 3.1 The vocabulary list

```python
# Click_Word_SZ6.py
WORDS = [
    ('pomme',   'apple',  0),   # (french, english, region_index)
    ('fenêtre', 'window', 1),
    ('table',   'table',  2),
    ('chaise',  'chair',  3),
    ('tasse',   'cup',    4),
    ('livre',   'book',   5),
]
REGION_NAMES_EN = ['apple', 'window', 'table', 'chair', 'cup', 'book']
```

`region_index` is the **operator index** that clicking that object triggers.
They match 1-to-1, so operator 0 = "click apple", operator 1 = "click window",
etc.

### 3.2 State class

```python
class ClickWord_State(sz.SZ_State):
    def __init__(self, old=None):
        if old is None:
            self.word_idx         = 0   # which word is being asked
            self.attempts         = 0   # total incorrect clicks
            self.current_role_num = 0   # single-player: always role 0
        else:
            # Copy constructor (used by every operator transition)
            self.word_idx         = old.word_idx
            self.attempts         = old.attempts
            self.current_role_num = old.current_role_num

    def is_goal(self):
        return self.word_idx >= len(WORDS)
```

Three points to note:

- `current_role_num` is required by the engine to determine whose turn it is.
- `old` is always `None` only for the very first state; operators receive
  `old` as the current state.
- `is_goal()` controls when the goal banner fires.

### 3.3 Transition helper

Rather than inline the transition logic inside lambdas, we use a named helper:

```python
def _click_region(state, region_idx):
    ns = ClickWord_State(old=state)          # start from a copy
    expected = WORDS[ns.word_idx][2]         # which region is correct

    if region_idx == expected:
        ns.word_idx += 1
        ns.jit_transition = 'Correct! ✓ ...'
    else:
        ns.attempts += 1
        ns.jit_transition = 'Not quite — ... Try again!'
    return ns
```

`jit_transition` is a special attribute recognised by the engine.  When
present on the returned state, its value is broadcast to all clients as a
`transition_msg` WebSocket event.  This is how the "Correct!" / corrective
feedback messages appear in the persistent message bar.

### 3.4 Operators

One operator per region, all with the same structure:

```python
class ClickWord_Operator_Set(sz.SZ_Operator_Set):
    def __init__(self):
        self.operators = [
            sz.SZ_Operator(
                name=f'Click {REGION_NAMES_EN[i]}',
                precond_func=lambda s, i=i: s.word_idx < len(WORDS),
                state_xition_func=lambda s, i=i: _click_region(s, i),
            )
            for i in range(len(WORDS))
        ]
```

The `i=i` default-argument trick captures the loop variable correctly inside
the lambda.

`precond_func` returns `True` while the game is in progress (`word_idx < 6`).
Once the goal is reached, all operators become inapplicable and the panel shows
"No operators available".

### 3.5 Formulation wiring

```python
class ClickWord_Formulation(sz.SZ_Formulation):
    def __init__(self):
        self.metadata    = ClickWord_Metadata()
        self.operators   = ClickWord_Operator_Set()
        self.roles_spec  = ClickWord_Roles_Spec()
        self.common_data = sz.SZ_Common_Data()
        self.vis_module  = _click_vis          # ← links to the VIS module

    def initialize_problem(self, config={}):
        initial = ClickWord_State()
        self.instance_data = sz.SZ_Problem_Instance_Data(
            d={'initial_state': initial}
        )
        return initial

CLICK_WORD = ClickWord_Formulation()           # module-level entry point
```

The `pff_loader` discovers the formulation by scanning the module for an object
with `.metadata`, `.operators`, and `.initialize_problem()`.

### 3.6 The vis module: `render_state`

The entire client-side interaction is driven by what `render_state` returns.
The function produces four pieces of HTML, concatenated:

```
[prompt bar]  ← "Cliquez sur : pomme"
[progress bar]
[#wsz6-scene div containing the SVG]
[<script type="application/json" id="wsz6-regions">]
[hint text]
```

#### The scene container

```python
scene_html = (
    '<div id="wsz6-scene" '
    'style="display:inline-block; line-height:0; overflow:hidden; '
    'border-radius:4px; box-shadow:0 2px 12px rgba(0,0,0,.18);">'
    + _SVG +
    '</div>'
)
```

Two requirements for the container div:

1. **`id="wsz6-scene"`** — must match `container_id` in the JSON manifest.
2. `display:inline-block` (or `position:relative`) — `setupHitCanvas()` sets
   `position:relative` on it automatically so the canvas overlay can anchor
   to its top-left corner.

The inline SVG is pure visual.  No `data-*` attributes on any SVG element.
The canvas overlay (added by `game.html`) sits on top of it and intercepts
all pointer events.

#### The region manifest

```python
_MANIFEST = {
    "container_id":  "wsz6-scene",
    "scene_width":   600,
    "scene_height":  400,
    "regions":       _REGIONS,     # see below
}
regions_html = (
    f'<script type="application/json" id="wsz6-regions">'
    f'{json.dumps(_MANIFEST, separators=(",", ":"))}'
    f'</script>'
)
```

`scene_width` / `scene_height` are the **natural** (unscaled) dimensions.
The overlay canvas is drawn at this resolution and CSS-scaled to fill the
container, so hit coordinates are transformed correctly regardless of zoom.

#### Region array ordering (critical for overlapping regions)

Six objects. Three (apple, cup, book) sit on top of the table.  The table
region, if listed first, would swallow all clicks on those objects.  The
solution is to put the smaller, more-specific regions before the larger one:

```python
_REGIONS = [
    # Specific objects on the table — listed first
    {"op_index": 0, "shape": "circle", "cx": 215, "cy": 207, "r": 27,
     "hover_label": "apple"},
    {"op_index": 4, "shape": "rect", "x": 338, "y": 185, "w": 85, "h": 40,
     "hover_label": "cup"},
    {"op_index": 5, "shape": "rect", "x": 279, "y": 206, "w": 59, "h": 18,
     "hover_label": "book"},
    # Large table surface — listed after the objects that sit on it
    {"op_index": 2, "shape": "rect", "x": 148, "y": 215, "w": 284, "h": 65,
     "hover_label": "table"},
    # Other furniture
    {"op_index": 3, "shape": "rect", "x": 64, "y": 180, "w": 90, "h": 102,
     "hover_label": "chair"},
    {"op_index": 1, "shape": "rect", "x": 420, "y": 25, "w": 160, "h": 133,
     "hover_label": "window"},
]
```

`op_index` does **not** have to equal the position in the array.  The array
order governs hit priority; `op_index` governs which operator fires.

### 3.7 What the client does (step by step)

1. Server sends `state_update` with `vis_html` = the string returned by
   `render_state`.
2. `game.html` sets `visDisplay.innerHTML = msg.vis_html`.
3. `setupHitCanvas()` runs:
   - Removes any previous canvas.
   - Finds `<script id="wsz6-regions">` in the new DOM.
   - Parses the JSON.
   - Creates a `<canvas width=600 height=400>` with CSS `width:100%; height:100%;
     position:absolute; top:0; left:0; pointer-events:all`.
   - Appends it to `#wsz6-scene` (which gets `position:relative` if not
     already set).
4. User moves the mouse over the canvas:
   - Viewport coordinates are translated to natural scene coordinates via
     `canvas.getBoundingClientRect()` and the `scene_width/height` ratio.
   - First matching region gets a gold fill + stroke drawn on the canvas.
   - `#vis-region-label` appears near the cursor with `hover_label` text.
5. User left-clicks:
   - Same hit test.
   - `applyOp(region.op_index)` sends `{type: "apply_operator", op_index: N}`
     over WebSocket.
6. Server applies the operator, returns a new `state_update`.
7. `game.html` replaces `visDisplay.innerHTML` and calls `setupHitCanvas()`
   again — old canvas is removed, new canvas built.

---

## Part 4 — Raster image variant (design proven by the Pixel Probe game)

If the scene is a photograph or pre-rendered PNG/JPEG, the SVG is replaced
by an `<img>` tag.  Everything else in the Tier-2 pipeline stays the same.
This is exactly what the **Pixel Probe** game (`pixel-uw-aerial`) does: a
1600 × 1035 aerial JPEG is displayed at 800 px wide, and two half-image
regions forward the click coordinates to the server via `send_click_coords`.
A full step-by-step walkthrough of that game appears in **Part 6**; the
structural pattern is summarised here.

### Vis file structure

```python
_GAME_SLUG  = 'my-raster-game'
_IMG_SUBDIR = 'images'
_ASSET_BASE = f'/play/game-asset/{_GAME_SLUG}/{_IMG_SUBDIR}'

def render_state(state):
    img_url = f'{_ASSET_BASE}/room.jpg'

    scene_html = f'''
<div id="wsz6-scene"
     style="display:inline-block; line-height:0;">
  <img src="{img_url}" width="800" height="600"
       style="display:block; max-width:100%;">
</div>'''

    manifest = {
        "container_id":  "wsz6-scene",
        "scene_width":   800,
        "scene_height":  600,
        "regions": [
            # Regions traced by hand against the image pixel coordinates
            {"op_index": 0, "shape": "polygon",
             "points": [[120,340],[180,340],[180,420],[120,420]],
             "hover_label": "door"},
            {"op_index": 1, "shape": "circle",
             "cx": 410, "cy": 290, "r": 35,
             "hover_label": "lamp"},
        ]
    }
    regions_html = (
        '<script type="application/json" id="wsz6-regions">'
        + json.dumps(manifest, separators=(',',':'))
        + '</script>'
    )
    return scene_html + regions_html
```

### Tracing regions against a raster image

The hardest part of Tier 2 with a raster image is measuring where objects
actually are.  Recommended workflow:

1. Open the image in any tool that shows pixel coordinates (GIMP, Photoshop,
   browser DevTools, or even MS Paint).
2. For rectangles: note the top-left corner (x, y) and the width/height.
3. For circles: note the centre (cx, cy) and radius r.
4. For arbitrary shapes: click around the outline of the object, recording
   each vertex as an `[x, y]` pair.  Six to twelve points are usually enough
   for a natural shape.
5. Write those numbers into the region manifest.  Reload the game and verify
   by hovering — the gold highlight should sit precisely over the object.

### Important: scene_width / scene_height vs. rendered size

Set `scene_width` and `scene_height` to the **natural pixel dimensions** of
the image file (or the `width` / `height` attributes on the `<img>` tag),
not the CSS display size.  The client divides `scene_width / canvas.clientWidth`
to derive the scale factor, so hit coordinates remain accurate even if the
browser window is resized or the image is displayed at a smaller size.

### Images must be served via the game-asset endpoint

Raster images (and SVG files stored as separate files) must live in the game's
installed directory and be served through:

```
/play/game-asset/<slug>/<optional-subdir>/<filename>
```

Install them by adding `images_dir` to the game definition in
`install_test_game.py` (see the `show-mt-rainier` entry for an example).

---

## Part 5 — Step-by-step guide: creating a new interactive vis game

### Step 1 — Design the interaction model

Decide:
- Which objects in the scene correspond to operators?
- Is the scene made of SVG elements you control (→ Tier 1) or a raster/opaque
  image (→ Tier 2)?
- Do you need a context menu (right-click) or just left-click?
- Do operators take arguments, or are they zero-argument?

### Step 2 — Write the PFF (`_SZ6.py`)

1. Define your `WORDS` / object list (or equivalent data structure).
2. Write a `State` subclass:
   - Include `current_role_num = 0` (for single-player) or manage it properly
     for multi-player.
   - Implement `is_goal()` and `goal_message()`.
3. Write a transition helper function that takes `(state, click_data)` and
   returns a new state with `jit_transition` set.
4. Create one `SZ_Operator` per interactive region, using the lambda-with-
   default-argument pattern:
   ```python
   sz.SZ_Operator(
       name='Click foo',
       precond_func=lambda s, i=i: not s.is_goal(),
       state_xition_func=lambda s, i=i: _handle_click(s, i),
   )
   ```
5. Wire the formulation:
   ```python
   self.vis_module = _my_vis   # import at the top of the PFF
   ```
6. Add a module-level entry point: `MY_GAME = MyFormulation()`.

### Step 3 — Write the vis module (`_WSZ6_VIS.py`)

1. Import `json`.
2. Build (or load) the scene HTML.  For Tier 2, the scene lives in a container
   div with a stable `id`:
   ```python
   scene_html = '<div id="wsz6-scene" style="display:inline-block; line-height:0;">' + scene + '</div>'
   ```
3. Define the region manifest as a Python dict.  **Remember the ordering rule:
   specific/small regions before large containing regions.**
4. Embed the manifest as:
   ```python
   regions_html = (
       '<script type="application/json" id="wsz6-regions">'
       + json.dumps(manifest, separators=(',', ':'))
       + '</script>'
   )
   ```
5. Return `scene_html + regions_html` (plus any prompt/score HTML you want).

For Tier 1 (SVG with `data-*` attributes), skip steps 3–4 and just put
`data-op-index="N"` on the relevant SVG elements.

### Step 4 — Register the game

In `install_test_game.py`, add an entry to `GAME_DEFS`:

```python
{
    'slug':        'my-game',
    'name':        'My Interactive Game',
    'pff_file':    'My_Game_SZ6.py',
    'vis_file':    'My_Game_WSZ6_VIS.py',
    'source_dir':  'Vis-Features-Dev/game_sources',   # if not in Textual_SZ6
    'brief_desc':  '...',
    'min_players': 1,
    'max_players': 1,
},
```

Then run:

```bash
python manage.py install_test_game
```

### Step 5 — Test

Start the dev server and open the game in a browser.  Work through the
test checklist:

- [ ] Hovering over each interactive region produces a gold highlight.
- [ ] `hover_label` text appears near the cursor (Tier 2).
- [ ] Left-click on the correct target fires the right operator (check the
      transition message and the updated state).
- [ ] Left-click on a wrong target produces the expected corrective message.
- [ ] Info popup appears and closes on click-outside and Esc.
- [ ] Right-click context menu items work (if implemented).
- [ ] Works in full-screen mode (enter full-screen, verify canvas still scales).
- [ ] After goal is reached, no interactive regions respond.

---

## Quick-reference: minimum vis module (Tier 2)

```python
"""my_game_WSZ6_VIS.py — skeleton"""
import json

_MANIFEST = {
    "container_id": "wsz6-scene",
    "scene_width":  600,
    "scene_height": 400,
    "regions": [
        {"op_index": 0, "shape": "rect", "x": 50, "y": 50, "w": 100, "h": 100,
         "hover_label": "target A"},
        {"op_index": 1, "shape": "circle", "cx": 400, "cy": 200, "r": 60,
         "hover_label": "target B"},
    ],
}
_MANIFEST_JSON = json.dumps(_MANIFEST, separators=(',', ':'))

def render_state(state) -> str:
    # Build your scene SVG or image tag here
    scene_svg = '<svg width="600" height="400"><!-- ... --></svg>'

    return (
        '<div id="wsz6-scene" style="display:inline-block; line-height:0;">'
        + scene_svg
        + '</div>'
        + '<script type="application/json" id="wsz6-regions">'
        + _MANIFEST_JSON
        + '</script>'
    )
```

---

## Quick-reference: minimum vis module (Tier 1, SVG only)

```python
"""my_game_WSZ6_VIS.py — Tier 1 skeleton"""

def render_state(state) -> str:
    ops = state.applicable_op_indices   # however your state exposes these
    cells = ''.join(
        f'<rect x="{x}" y="{y}" width="80" height="80" fill="white"'
        f' data-op-index="{op}"'
        f' data-info="Click to apply operator {op}"/>'
        for op, (x, y) in zip(ops, [(10,10),(100,10),(190,10)])
    )
    return f'<svg width="280" height="100">{cells}</svg>'
```

No JSON manifest needed.  The CSS and JS in `game.html` handle everything
from the `data-*` attributes.

---

## Part 6 — Walkthrough: "Pixel Values with Old UW Aerial Image"

The Pixel Probe game (`pixel-uw-aerial` slug) extends the Tier-2 canvas
system with a new capability: **dynamic coordinate capture**.  Unlike
Click-the-Word, where the operator to invoke is determined entirely by
*which* region the player clicks, Pixel Probe needs to know *where exactly*
within the region the click landed.  The click coordinates are forwarded as
operator arguments and used server-side to read a pixel from a JPEG via
Pillow.

### 6.1 The new `send_click_coords` manifest field

Without `send_click_coords`, a region can only dispatch a fixed `op_args`
value baked into the manifest at render time.  For coordinate capture we
need the *runtime* click position.

Adding `"send_click_coords": true` to a region tells `game.html`'s canvas
click handler to substitute the actual natural-coordinate click point for
`op_args`:

```javascript
// Inside setupHitCanvas() canvas 'click' listener (game.html):
if (reg.op_index !== undefined) {
    let args;
    if (reg.send_click_coords) {
        args = [Math.round(px), Math.round(py)];  // live click position
    } else {
        args = reg.op_args || undefined;           // static value (existing)
    }
    applyOp(reg.op_index, args);
}
```

`px` and `py` are already in natural scene coordinates — `scalePoint()`
divides the viewport click by `canvas.getBoundingClientRect().width` and
multiplies by `scene_width`.  So `args` arriving at the server are always
in the same pixel space as the PIL `getpixel()` call, regardless of window
size.

### 6.2 Server-side image access with Pillow

The transition functions read the installed JPEG using Pillow.  The image
is decoded once per process and cached in a module-level variable:

```python
import os
from PIL import Image
import colorsys

_GAME_DIR  = os.path.dirname(os.path.abspath(__file__))
_IMAGE_REL = os.path.join('UW_Aerial_images', 'Aeroplane-view-of-UW.jpg')
_IMG_CACHE = None

def _get_image():
    global _IMG_CACHE
    if _IMG_CACHE is None:
        path = os.path.join(_GAME_DIR, _IMAGE_REL)
        _IMG_CACHE = Image.open(path).convert('RGB')
    return _IMG_CACHE
```

`__file__` in the installed copy resolves to
`games_repo/pixel-uw-aerial/Pixel_Probe_SZ6.py`, so `_GAME_DIR` is the
installed directory.  The `images_dir` field in `install_test_game.py`
copies `UW_Aerial_images/` alongside the PFF, so the relative path always
resolves correctly.

Coordinate clamping guards against any edge-case out-of-bounds click:

```python
def _read_rgb(x, y):
    img = _get_image()
    x = max(0, min(x, img.width  - 1))
    y = max(0, min(y, img.height - 1))
    return img.getpixel((x, y))    # (r, g, b)
```

Python's `colorsys` module works in `[0.0, 1.0]`; we scale to degrees /
percent for readability:

```python
def _rgb_to_hsv(r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return round(h * 360), round(s * 100), round(v * 100)
```

### 6.3 State class

The state holds only the most recent probe result plus a running count.
`is_goal()` permanently returns `False` — this is an open-ended exploration
game that the player ends voluntarily.

```python
class PixelProbe_State(sz.SZ_State):
    def __init__(self, old=None):
        if old is None:
            self.last_x           = None   # most recently probed x
            self.last_y           = None   # most recently probed y
            self.last_result      = None   # e.g. "RGB = (120, 85, 45)"
            self.click_count      = 0
            self.current_role_num = 0
        else:
            self.last_x           = old.last_x
            self.last_y           = old.last_y
            self.last_result      = old.last_result
            self.click_count      = old.click_count
            self.current_role_num = old.current_role_num

    def is_goal(self):
        return False
```

### 6.4 Transition helpers

Both operators copy state, read the pixel, set `jit_transition`, and return
the new state.  Notice the function signature is `(state, args)` — two
positional parameters — because `game_runner` passes `args` when
`bool(op.params)` is `True` (see §6.5).

```python
def _probe_rgb(state, args):
    x, y = int(args[0]), int(args[1])
    r, g, b = _read_rgb(x, y)
    ns = PixelProbe_State(old=state)
    ns.last_x      = x
    ns.last_y      = y
    ns.last_result = f'RGB = ({r}, {g}, {b})'
    ns.click_count = state.click_count + 1
    ns.jit_transition = f'x={x}, y={y}  →  RGB = ({r}, {g}, {b})'
    return ns

def _probe_hsv(state, args):
    x, y = int(args[0]), int(args[1])
    r, g, b = _read_rgb(x, y)
    h, s, v = _rgb_to_hsv(r, g, b)
    ns = PixelProbe_State(old=state)
    ns.last_x      = x
    ns.last_y      = y
    ns.last_result = f'HSV = ({h}°, {s}%, {v}%)'
    ns.click_count = state.click_count + 1
    ns.jit_transition = f'x={x}, y={y}  →  HSV = ({h}°, {s}%, {v}%)'
    return ns
```

`jit_transition` is broadcast to all clients as a `transition_msg`
WebSocket event — the same mechanism used by Click-the-Word for its
"Correct!" feedback.

### 6.5 Operators and the `params` mechanic

`game_runner.py` decides how to call `state_xition_func` based on whether
the operator has a non-empty `params` list:

```python
# game_runner.py (lines ~120–125):
if bool(getattr(op, 'params', None)):
    new_state = op.state_xition_func(state, args)   # args forwarded
else:
    new_state = op.state_xition_func(state)          # args dropped silently
```

For Pixel Probe the operators genuinely take (x, y) parameters, so
`_COORD_PARAMS` is semantically correct — not a workaround:

```python
_COORD_PARAMS = [
    {'name': 'x', 'type': 'int', 'min': 0, 'max': 1599},
    {'name': 'y', 'type': 'int', 'min': 0, 'max': 1034},
]

class PixelProbe_Operator_Set(sz.SZ_Operator_Set):
    def __init__(self):
        self.operators = [
            sz.SZ_Operator(
                name='Probe pixel — RGB (top half)',
                precond_func=lambda s: True,
                state_xition_func=_probe_rgb,
                params=_COORD_PARAMS,
            ),
            sz.SZ_Operator(
                name='Probe pixel — HSV (bottom half)',
                precond_func=lambda s: True,
                state_xition_func=_probe_hsv,
                params=_COORD_PARAMS,
            ),
        ]
```

A player who clicks an operator *button* (rather than the image) will see a
two-field x/y form — a useful fallback for accessibility or debugging.

**Rule:** any operator whose region carries `send_click_coords: true` must
have a non-empty `params` list.  If `params` is empty or absent, `game_runner`
silently drops `args` and the transition function receives only `state`.

### 6.6 Formulation wiring

Identical pattern to Click-the-Word:

```python
class PixelProbe_Formulation(sz.SZ_Formulation):
    def __init__(self):
        self.metadata    = PixelProbe_Metadata()
        self.operators   = PixelProbe_Operator_Set()
        self.roles_spec  = PixelProbe_Roles_Spec()   # single "Visitor" role
        self.common_data = sz.SZ_Common_Data()
        self.vis_module  = _pixel_vis                 # import at top

    def initialize_problem(self, config={}):
        initial = PixelProbe_State()
        self.instance_data = sz.SZ_Problem_Instance_Data(
            d={'initial_state': initial}
        )
        return initial

PIXEL_PROBE = PixelProbe_Formulation()    # module-level entry point
```

### 6.7 The vis module: `render_state`

`render_state` returns five pieces of HTML, concatenated:

```
[result bar]        ← monospace probe result, or placeholder on first render
[top-half label]    ← "▲ TOP HALF — click for RGB values"
[#wsz6-scene div]   ← <img> tag + purely-visual dashed divider overlay
[bottom-half label] ← "▼ BOTTOM HALF — click for HSV values"
[<script wsz6-regions>]
[hint text]
```

#### The scene container (raster JPEG)

```python
_IMG_URL   = '/play/game-asset/pixel-uw-aerial/UW_Aerial_images/Aeroplane-view-of-UW.jpg'
_IMG_W     = 1600
_IMG_H     = 1035
_DISPLAY_W = 800    # CSS max-width — the image is shown at 50 % of natural size

divider_html = (
    '<div style="position:absolute; top:0; left:0; '
    'width:100%; height:50%; '
    'border-bottom:2px dashed rgba(255,255,0,0.65); '
    'pointer-events:none; box-sizing:border-box;"></div>'
)

scene_html = (
    '<div id="wsz6-scene" '
    'style="position:relative; display:inline-block; line-height:0;">'
    f'<img src="{_IMG_URL}" width="{_IMG_W}" height="{_IMG_H}" '
    f'style="display:block; max-width:{_DISPLAY_W}px; height:auto;">'
    + divider_html
    + '</div>'
)
```

Two differences from the SVG-scene container in Part 3:

1. **`position:relative`** is set explicitly — needed because the dashed
   divider uses `position:absolute`.  (`setupHitCanvas()` also sets this
   automatically for the canvas overlay.)
2. **`max-width / height:auto`** on the `<img>` — the image is *displayed*
   at 800 px but *described* to `setupHitCanvas()` at 1600 × 1035.  The
   canvas is drawn at full natural resolution and CSS-scaled to fill the
   container, so click coordinates from `scalePoint()` are already in
   natural image space.

#### The dashed divider

The divider is a `position:absolute` `<div>` covering the top 50 % of the
container with a yellow dashed `border-bottom`.  `pointer-events:none`
ensures it does not block the transparent canvas overlay above it.  Because
it is purely decorative CSS, it appears immediately on page load — before
any JS runs — and does not interfere with the hit-test geometry.

#### The region manifest with `send_click_coords`

```python
_HALF_Y = _IMG_H // 2   # = 517

_MANIFEST = {
    "container_id": "wsz6-scene",
    "scene_width":  _IMG_W,    # 1600 — natural coords, NOT display width
    "scene_height": _IMG_H,    # 1035
    "regions": [
        {
            "op_index":          0,
            "shape":             "rect",
            "x": 0, "y": 0, "w": _IMG_W, "h": _HALF_Y,
            "send_click_coords": True,
            "hover_label":       "Click to probe RGB",
        },
        {
            "op_index":          1,
            "shape":             "rect",
            "x": 0, "y": _HALF_Y, "w": _IMG_W, "h": _IMG_H - _HALF_Y,
            "send_click_coords": True,
            "hover_label":       "Click to probe HSV",
        },
    ],
}
```

The two regions tile the whole image with no overlap, so array ordering
does not matter for hit priority.  What matters is that **both carry
`send_click_coords: true`**, which causes the client to forward `[x, y]`
(in natural image pixels) instead of a static `op_args`.

`scene_width` and `scene_height` are set to the **natural image dimensions**
(1600 × 1035), not the CSS display size (800 × ~517).  This ensures that
the coordinate space the canvas uses for hit testing matches the coordinate
space that PIL's `getpixel()` expects.

### 6.8 What the client does — step by step

1. Server sends `state_update` with `vis_html` from `render_state`.
2. `game.html` injects `vis_html` and calls `setupHitCanvas()`.
3. A `<canvas width="1600" height="1035">` overlay is created and
   CSS-scaled to fill the 800 px container (`width:100%; height:100%;
   position:absolute; top:0; left:0`).
4. User moves the mouse over the canvas:
   - `scalePoint(e.clientX, e.clientY)` converts viewport position to
     natural image coordinates.
   - First matching region is highlighted with a translucent gold fill.
   - Tooltip shows "Click to probe RGB" or "Click to probe HSV".
5. User clicks (say at viewport position that maps to `[432, 280]`):
   - Hit test identifies the top-half region (`y=280 < 517`).
   - `send_click_coords` is `true`, so `args = [432, 280]`.
   - `applyOp(0, [432, 280])` sends
     `{type: "apply_operator", op_index: 0, args: [432, 280]}`
     over WebSocket.
6. Server receives `apply_operator`.  `op.params` is non-empty, so
   `game_runner` calls `_probe_rgb(state, [432, 280])`.
7. `_probe_rgb` reads `img.getpixel((432, 280))` → e.g. `(142, 128, 98)`.
8. New state returned with
   `jit_transition = "x=432, y=280  →  RGB = (142, 128, 98)"`.
9. Engine broadcasts the transition message; then sends a new `state_update`
   with updated `vis_html` showing the result bar updated to
   `x=432, y=280 → RGB = (142, 128, 98)`.
10. `game.html` injects the new `vis_html` and rebuilds the canvas overlay.

### 6.9 Installation notes

The JPEG must be served by the game-asset endpoint.  In `install_test_game.py`:

```python
{
    'slug':        'pixel-uw-aerial',
    'name':        'Pixel Values with Old UW Aerial Image',
    'pff_file':    'Pixel_Probe_SZ6.py',
    'vis_file':    'Pixel_Probe_WSZ6_VIS.py',
    'images_dir':  'UW_Aerial_images',          # ← copies the image folder
    'source_dir':  'Vis-Features-Dev/game_sources',
    'brief_desc':  '...',
    'min_players': 1,
    'max_players': 1,
},
```

The installer copies `UW_Aerial_images/Aeroplane-view-of-UW.jpg` into
`games_repo/pixel-uw-aerial/UW_Aerial_images/`, which is exactly where
`_GAME_DIR + _IMAGE_REL` resolves at runtime.

Verify Pillow is available before running:

```bash
python -c "from PIL import Image; print(Image.__version__)"
# → 12.1.1  (or similar)
```

If absent: `pip install Pillow`.
