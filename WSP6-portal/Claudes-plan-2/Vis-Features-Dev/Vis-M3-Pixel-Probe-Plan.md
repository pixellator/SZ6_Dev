# Pixel Probe Game — Implementation Plan

**Date:** 2026-02-19
**Game name:** "Pixel Values with Old UW Aerial Image"
**Slug:** `pixel-uw-aerial`
**Feature focus:** M3 Tier-2 canvas hit-testing on a raster JPEG; dynamic
coordinate capture at click time; server-side image pixel access with Pillow.

---

## 1. Game Concept

A single aerial photograph of the University of Washington campus
(`Aeroplane-view-of-UW.jpg`, 1600 × 1035 px) is displayed.
The image is split into two horizontal halves by a visual dividing line.

| Region | Action |
|---|---|
| **Top half** | Click → transition message reports `x=NNN, y=NNN → RGB = (r, g, b)` |
| **Bottom half** | Click → transition message reports `x=NNN, y=NNN → HSV = (h°, s%, v%)` |

Clicking anywhere invokes the appropriate operator *without* the player
first pressing a button.  No form appears; the click coordinates are sent
as `args` automatically.  The operator reads the pixel from the server's
copy of the image (using Pillow) and emits the result as a
`jit_transition` message.

The game is open-ended (no goal state); the player explores the image
until they stop the session.

---

## 2. What Is New vs. What Already Exists

### Already works (reuse unchanged)
- Tier-2 canvas overlay machinery (`setupHitCanvas`, `_hitTest`, `_drawRegion`)
- Gold hover highlight and `hover_label` tooltip
- `applyOp(opIndex, clientArgs)` dispatches `args` straight to the server
  when `clientArgs !== undefined`
- `game_runner.py` calls `state_xition_func(state, args)` when the operator
  has a non-empty `params` list (lines 120-125 of `game_runner.py` — already
  implemented)
- `install_test_game.py` `images_dir` mechanism copies a subfolder of assets
  into the game's repo directory

### New: `send_click_coords` manifest field (one change to `game.html`)
The current canvas `click` handler sends `reg.op_args` (a static value
baked into the manifest at render time).  For coordinate capture we need
the *runtime* click position.  A new boolean field `"send_click_coords": true`
on a region tells the handler to substitute the actual natural-coordinate
click point instead:

```javascript
// Inside setupHitCanvas(), replace the existing canvas 'click' handler:
canvas.addEventListener('click', function(e) {
    closeInfoPopup(); closeCtxMenu();
    const [px, py] = scalePoint(e.clientX, e.clientY);
    const reg = findRegion(px, py);
    if (!reg) return;
    if (reg.op_index !== undefined) {
        let args;
        if (reg.send_click_coords) {
            args = [Math.round(px), Math.round(py)];  // ← live coords
        } else {
            args = reg.op_args || undefined;           // ← static (existing)
        }
        applyOp(reg.op_index, args);
    } else if (reg.info) {
        showInfoPopup(e.clientX, e.clientY, reg.info);
    }
});
```

This is the **only change to `game.html`** needed for this game.

### New: Pillow pixel access in the PFF
The operator's `state_xition_func` uses Pillow to open the installed copy
of the image and read the pixel at `(args[0], args[1])`.  Pillow is already
in the venv (verify with `pip show Pillow`; install with `pip install Pillow`
if absent).

---

## 3. Image Details

| Property | Value |
|---|---|
| File | `Aeroplane-view-of-UW.jpg` |
| Current location | `Vis-Features-Dev/Aeroplane-view-of-UW.jpg` |
| Dimensions | 1600 × 1035 pixels |
| Mode | RGB |
| Display size (in browser) | 800 px wide (50 % of native), height auto |
| Half-split y boundary | y = 517 (natural coords) |

For installation, move the image into a named subdirectory so the
existing `images_dir` mechanism can copy it:

```
Vis-Features-Dev/game_sources/
  UW_Aerial_images/
    Aeroplane-view-of-UW.jpg
  Pixel_Probe_SZ6.py
  Pixel_Probe_WSZ6_VIS.py
```

---

## 4. PFF: `Pixel_Probe_SZ6.py`

### 4.1 Image access helper

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

def _read_rgb(x, y):
    img = _get_image()
    x = max(0, min(x, img.width  - 1))
    y = max(0, min(y, img.height - 1))
    return img.getpixel((x, y))    # returns (r, g, b)

def _rgb_to_hsv(r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return round(h * 360), round(s * 100), round(v * 100)
```

`_IMG_CACHE` is module-level so the image is decoded only once per process.

### 4.2 State

```python
class PixelProbe_State(sz.SZ_State):
    def __init__(self, old=None):
        if old is None:
            self.last_x      = None   # most recently probed x (natural coords)
            self.last_y      = None   # most recently probed y
            self.last_result = None   # string, e.g. "RGB = (120, 85, 45)"
            self.click_count = 0      # total probes made
            self.current_role_num = 0
        else:
            self.last_x      = old.last_x
            self.last_y      = old.last_y
            self.last_result = old.last_result
            self.click_count = old.click_count
            self.current_role_num = old.current_role_num

    def is_goal(self):
        return False    # open-ended exploration game

    def __str__(self):
        if self.last_x is None:
            return 'Click anywhere on the image to probe a pixel.\nTop half → RGB  |  Bottom half → HSV'
        return (
            f'Last click: x={self.last_x}, y={self.last_y}\n'
            f'Result:     {self.last_result}\n'
            f'Total probes: {self.click_count}'
        )
```

### 4.3 Transition helpers

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

### 4.4 Operators

The `params` list must be **non-empty** so that `game_runner` uses the
`state_xition_func(state, args)` calling convention (see `game_runner.py`
lines 120–125).  We define two `int` params (x, y) — these also document
the expected input if a player clicks the button instead of the image.

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

Note: a player who clicks the operator *button* (rather than the image)
will see a two-field coordinate form.  This is acceptable behaviour and
actually a useful fallback.

### 4.5 Formulation wiring

Same pattern as all other games:

```python
class PixelProbe_Formulation(sz.SZ_Formulation):
    def __init__(self):
        self.metadata    = PixelProbe_Metadata()
        self.operators   = PixelProbe_Operator_Set()
        self.roles_spec  = PixelProbe_Roles_Spec()   # single Visitor role
        self.common_data = sz.SZ_Common_Data()
        self.vis_module  = _pixel_vis               # import at top

    def initialize_problem(self, config={}):
        initial = PixelProbe_State()
        self.instance_data = sz.SZ_Problem_Instance_Data(
            d={'initial_state': initial}
        )
        return initial

PIXEL_PROBE = PixelProbe_Formulation()
```

---

## 5. Vis Module: `Pixel_Probe_WSZ6_VIS.py`

### 5.1 Asset URL

```python
_GAME_SLUG  = 'pixel-uw-aerial'
_IMG_SUBDIR = 'UW_Aerial_images'
_IMG_URL    = f'/play/game-asset/{_GAME_SLUG}/{_IMG_SUBDIR}/Aeroplane-view-of-UW.jpg'

_IMG_W, _IMG_H     = 1600, 1035   # natural pixel dimensions
_HALF_Y            = _IMG_H // 2  # = 517
_DISPLAY_W         = 800          # CSS width for browser display (50 % scale)
```

### 5.2 Region manifest

```python
_MANIFEST = {
    "container_id": "wsz6-scene",
    "scene_width":  _IMG_W,
    "scene_height": _IMG_H,
    "regions": [
        {
            "op_index":         0,
            "shape":            "rect",
            "x": 0, "y": 0, "w": _IMG_W, "h": _HALF_Y,
            "send_click_coords": True,
            "hover_label":      "Click to probe RGB",
        },
        {
            "op_index":         1,
            "shape":            "rect",
            "x": 0, "y": _HALF_Y, "w": _IMG_W, "h": _IMG_H - _HALF_Y,
            "send_click_coords": True,
            "hover_label":      "Click to probe HSV",
        },
    ],
}
```

### 5.3 `render_state` structure

```python
def render_state(state) -> str:
    last_x = getattr(state, 'last_x', None)
    ...

    # ── Result bar (empty placeholder on first render) ──────────────
    if last_x is None:
        result_html = '<div style="...">Click the image to probe a pixel.</div>'
    else:
        result_html = f'<div>x={last_x}, y={last_y} → {state.last_result}</div>'

    # ── Labels for the two halves (rendered as HTML above and below) ─
    top_label    = '<div style="...">▲ TOP HALF — click for RGB values</div>'
    bottom_label = '<div style="...">▼ BOTTOM HALF — click for HSV values</div>'

    # ── Scene container + image ──────────────────────────────────────
    # The dividing line is a 2 px CSS border-bottom on a positioned div
    # that covers the top half of the container.
    divider_html = (
        '<div style="position:absolute; top:0; left:0; '
        f'width:100%; height:50%; '
        'border-bottom: 2px dashed rgba(255,255,0,0.65); '
        'pointer-events:none; box-sizing:border-box;"></div>'
    )

    scene_html = (
        f'<div id="wsz6-scene" '
        f'style="position:relative; display:inline-block; '
        f'line-height:0; border-radius:4px; '
        f'box-shadow:0 2px 12px rgba(0,0,0,.25);">'
        f'<img src="{_IMG_URL}" width="{_IMG_W}" height="{_IMG_H}" '
        f'style="display:block; max-width:{_DISPLAY_W}px; height:auto;">'
        + divider_html
        + '</div>'
    )

    regions_html = (
        '<script type="application/json" id="wsz6-regions">'
        + json.dumps(_MANIFEST, separators=(',',':'))
        + '</script>'
    )

    return (
        result_html
        + top_label
        + scene_html
        + bottom_label
        + regions_html
    )
```

The yellow dashed `divider_html` div sits inside `#wsz6-scene` with
`position:absolute` and `pointer-events:none`, so it is purely visual
and does not interfere with the canvas overlay.

---

## 6. Installation

### 6.1 File layout after move

```
Vis-Features-Dev/game_sources/
  UW_Aerial_images/
    Aeroplane-view-of-UW.jpg      ← moved from Vis-Features-Dev/
  Pixel_Probe_SZ6.py
  Pixel_Probe_WSZ6_VIS.py
```

### 6.2 `install_test_game.py` entry

```python
{
    'slug':        'pixel-uw-aerial',
    'name':        'Pixel Values with Old UW Aerial Image',
    'pff_file':    'Pixel_Probe_SZ6.py',
    'vis_file':    'Pixel_Probe_WSZ6_VIS.py',
    'images_dir':  'UW_Aerial_images',
    'source_dir':  'Vis-Features-Dev/game_sources',
    'brief_desc':  (
        'Click on an aerial photograph of the University of Washington '
        'to read the pixel values at the clicked point. '
        'The top half of the image reports RGB values; the bottom half '
        'reports HSV values. '
        'Demonstrates Tier-2 canvas regions on a raster JPEG with '
        'dynamic coordinate capture and server-side Pillow image access.'
    ),
    'min_players': 1,
    'max_players': 1,
},
```

After adding this entry, run:
```bash
python manage.py install_test_game
```

The installer will copy `Pixel_Probe_SZ6.py`, `Pixel_Probe_WSZ6_VIS.py`,
`soluzion6_02.py`, and `UW_Aerial_images/Aeroplane-view-of-UW.jpg` into
`games_repo/pixel-uw-aerial/`.

---

## 7. Pre-flight Check: Pillow

Verify Pillow is available in the venv:
```bash
source wsz6_portal/.venv/bin/activate
python -c "from PIL import Image; print(Image.__version__)"
```

If absent:
```bash
pip install Pillow
```

---

## 8. Implementation Steps (in order)

| # | Step | File(s) touched |
|---|---|---|
| 1 | Move image into `game_sources/UW_Aerial_images/` | (filesystem) |
| 2 | Add `send_click_coords` branch in canvas `click` handler | `game.html` |
| 3 | Write `Pixel_Probe_SZ6.py` | new file |
| 4 | Write `Pixel_Probe_WSZ6_VIS.py` | new file |
| 5 | Add entry to `GAME_DEFS` in `install_test_game.py` | existing file |
| 6 | Add quick link to `start_server.sh` | existing file |
| 7 | `python manage.py install_test_game` | (command) |
| 8 | Smoke-test in browser | — |

---

## 9. Test Checklist

- [ ] Image loads and is visible at ~800 px wide.
- [ ] Dashed yellow line divides the image horizontally at the midpoint.
- [ ] Hovering over the top half: gold highlight covers top half, label "Click to probe RGB".
- [ ] Hovering over the bottom half: gold highlight covers bottom half, label "Click to probe HSV".
- [ ] Clicking the top half: transition message appears with `x=NNN, y=NNN → RGB = (r, g, b)`.
- [ ] Clicking the bottom half: transition message appears with `x=NNN, y=NNN → HSV = (h°, s%, v%)`.
- [ ] Values are correct (spot-check a few pixels with an image editor).
- [ ] RGB → HSV conversion is correct (e.g. a pure red pixel: RGB=(255,0,0) → HSV=(0°,100%,100%)).
- [ ] Clicking the "Probe pixel — RGB" *button* opens a two-field x/y form; submitting it works.
- [ ] `click_count` increments correctly; `last_x / last_y / last_result` shown in text display.
- [ ] Undo reverts to previous probe result (or initial state).
- [ ] Works in full-screen mode (canvas scales, hover highlight still correct).
- [ ] Out-of-bounds coordinates clamped gracefully (click near edge).

---

## 10. Design Notes

### Why `params` must be non-empty

`game_runner.py` uses `bool(getattr(op, 'params', None))` to decide whether
to call `state_xition_func(state, args)` or just `state_xition_func(state)`.
If `params=[]` or `params` is absent, args are silently dropped.  For this
game the operator genuinely has parameters (x and y), so the non-empty
params list is semantically correct, not a hack.

### Why the canvas sends natural coordinates

`scene_width` and `scene_height` in the manifest are the **natural image
dimensions** (1600 × 1035), not the CSS display size (800 × ~517).
`setupHitCanvas()` creates the canvas at 1600 × 1035 and CSS-scales it
to fill the container.  `scalePoint()` divides by the canvas's
`getBoundingClientRect().width` to convert viewport clicks back to
natural coordinates.  This means `args[0]` and `args[1]` are always in
the same coordinate space as the PIL `getpixel()` call — even if the
window is resized.

### Extending to arbitrary operator args via `send_click_coords`

The `send_click_coords` flag is general.  Any Tier-2 region can use it
to pass runtime `[x, y]` coordinates to any parameterised operator.
A future extension could support `"send_click_rel": true` (normalised
0.0–1.0 coordinates) or `"send_click_label": true` (sends a string
like `"x=532, y=232"` if the operator expects a single `str` param).
