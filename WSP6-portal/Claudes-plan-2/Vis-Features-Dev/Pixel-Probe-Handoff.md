# Pixel Probe Game — Session Handoff

**For:** Claude Code (next session)
**Task:** Implement the "Pixel Values with Old UW Aerial Image" game per the plan
in `Vis-Features-Dev/Vis-M3-Pixel-Probe-Plan.md`.

---

## Context

M3 interactive visualization is complete and committed (commit `c69e53e`).
The Tier-2 canvas hit-testing system works (tested with Click-the-Word game).
This session adds one small extension to that system and implements a new game
on top of it.

---

## What to implement (8 steps)

**Step 1 — Move the image**
```bash
mkdir -p Vis-Features-Dev/game_sources/UW_Aerial_images
mv Vis-Features-Dev/Aeroplane-view-of-UW.jpg \
   Vis-Features-Dev/game_sources/UW_Aerial_images/
```
Image is 1600 × 1035 px, RGB JPEG.

**Step 2 — Extend `game.html` canvas click handler**
In `setupHitCanvas()`, find the `canvas.addEventListener('click', ...)` block
and add one branch for `send_click_coords`:

```javascript
// Replace the existing applyOp call inside the click handler:
if (reg.op_index !== undefined) {
    let args;
    if (reg.send_click_coords) {
        args = [Math.round(px), Math.round(py)];   // ← NEW
    } else {
        args = reg.op_args || undefined;
    }
    applyOp(reg.op_index, args);
}
```

File: `wsz6_portal/templates/wsz6_play/game.html`

**Step 3 — Create `Pixel_Probe_SZ6.py`**
Location: `Vis-Features-Dev/game_sources/Pixel_Probe_SZ6.py`

Key facts:
- Slug: `pixel-uw-aerial`
- Image read via Pillow from `os.path.dirname(__file__)/UW_Aerial_images/Aeroplane-view-of-UW.jpg`
- Two operators, both with `params=[{'name':'x','type':'int'},{'name':'y','type':'int'}]`
  (non-empty params is required so game_runner calls `state_xition_func(state, args)`)
- Op 0 (`_probe_rgb`): reads PIL pixel → `jit_transition = f"x={x}, y={y}  →  RGB = ({r}, {g}, {b})"`
- Op 1 (`_probe_hsv`): reads PIL pixel, converts via `colorsys.rgb_to_hsv` →
  `jit_transition = f"x={x}, y={y}  →  HSV = ({h}°, {s}%, {v}%)"`
- State fields: `last_x`, `last_y`, `last_result`, `click_count`, `current_role_num=0`
- `is_goal()` returns `False` (open-ended exploration game)
- Module-level entry point: `PIXEL_PROBE = PixelProbe_Formulation()`

**Step 4 — Create `Pixel_Probe_WSZ6_VIS.py`**
Location: `Vis-Features-Dev/game_sources/Pixel_Probe_WSZ6_VIS.py`

Key facts:
- Image URL: `/play/game-asset/pixel-uw-aerial/UW_Aerial_images/Aeroplane-view-of-UW.jpg`
- Display width: 800 px (`max-width:800px; height:auto`) — natural coords 1600×1035
- `scene_width=1600, scene_height=1035` in the manifest
- Two regions: top half `rect(0,0,1600,517)` → `op_index:0`, bottom half `rect(0,517,1600,518)` → `op_index:1`
- Both regions: `"send_click_coords": true`
- `hover_label`: "Click to probe RGB" / "Click to probe HSV"
- Dashed dividing line: `position:absolute; pointer-events:none; border-bottom:2px dashed rgba(255,255,0,0.65)` div covering the top 50% of `#wsz6-scene`
- `#wsz6-scene` container: `position:relative; display:inline-block; line-height:0`
- Show last probe result above the image; hint text below

**Step 5 — Update `install_test_game.py`**
Add to `GAME_DEFS`:
```python
{
    'slug':        'pixel-uw-aerial',
    'name':        'Pixel Values with Old UW Aerial Image',
    'pff_file':    'Pixel_Probe_SZ6.py',
    'vis_file':    'Pixel_Probe_WSZ6_VIS.py',
    'images_dir':  'UW_Aerial_images',
    'source_dir':  'Vis-Features-Dev/game_sources',
    'brief_desc':  '...',
    'min_players': 1,
    'max_players': 1,
},
```

**Step 6 — Add quick link to `start_server.sh`**
Add `Pixel Probe` line alongside the other quick links.

**Step 7 — Install and verify**
```bash
cd wsz6_portal
source .venv/bin/activate
DJANGO_SETTINGS_MODULE=wsz6_portal.settings.development python manage.py install_test_game
```
Check Pillow is available: `python -c "from PIL import Image; print('ok')"`.
If absent: `pip install Pillow`.

**Step 8 — Commit**
Stage and commit the 5 changed/new files. Push to `origin/master`.

---

## Key engine mechanic (don't forget)

`game_runner.py` line 120-125: operators call `state_xition_func(state, args)`
**only if** `bool(op.params)` is True. Empty or absent `params` → args silently
dropped. Both operators must have non-empty `params`.

---

## Files to read before starting (if you need context)

| File | Why |
|---|---|
| `Vis-Features-Dev/Vis-M3-Pixel-Probe-Plan.md` | Full plan with all code sketches |
| `Vis-Features-Dev/game_sources/Click_Word_SZ6.py` | Reference PFF pattern |
| `Vis-Features-Dev/game_sources/Click_Word_WSZ6_VIS.py` | Reference vis pattern |
| `wsz6_portal/templates/wsz6_play/game.html` | The canvas click handler to modify |
| `wsz6_play/engine/game_runner.py` lines 88–130 | The args-passing mechanic |
