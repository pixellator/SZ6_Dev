"""
Pixel_Probe_WSZ6_VIS.py

WSZ6 visualization module for the "Pixel Values with Old UW Aerial Image" game.
Companion to Pixel_Probe_SZ6.py.

Demonstrates M3 Tier-2 canvas hit-testing with dynamic coordinate capture:
the two regions carry "send_click_coords": true so the canvas click handler
forwards the natural-coordinate click point as operator args instead of a
static op_args value.

render_state(state) -> str
    Returns an HTML string containing:
      1. A result bar showing the last probe result (or placeholder).
      2. A label for the top half.
      3. A <div id="wsz6-scene"> with the aerial image and a dashed divider.
      4. A label for the bottom half.
      5. A <script type="application/json" id="wsz6-regions"> manifest.
"""

import json

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GAME_SLUG  = 'pixel-uw-aerial'
_IMG_SUBDIR = 'UW_Aerial_images'
_IMG_URL    = f'/play/game-asset/{_GAME_SLUG}/{_IMG_SUBDIR}/Aeroplane-view-of-UW.jpg'

_IMG_W, _IMG_H = 1600, 1035   # natural pixel dimensions
_HALF_Y        = _IMG_H // 2  # = 517
_DISPLAY_W     = 800          # CSS max-width in browser (50 % of natural)

# ---------------------------------------------------------------------------
# Region manifest
# ---------------------------------------------------------------------------

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

_MANIFEST_JSON = json.dumps(_MANIFEST, separators=(',', ':'))

# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def render_state(state) -> str:
    """Return an HTML string for the current game state."""

    last_x      = getattr(state, 'last_x',      None)
    last_y      = getattr(state, 'last_y',      None)
    last_result = getattr(state, 'last_result', None)
    click_count = getattr(state, 'click_count', 0)

    # ── Result bar ───────────────────────────────────────────────────
    if last_x is None:
        result_html = (
            '<div style="text-align:center; padding:.5rem .8rem; '
            'background:#2a2a2a; color:#aaa; border-radius:6px; '
            'font-family:monospace; font-size:.95rem; margin-bottom:.5rem;">'
            'Click the image to probe a pixel.'
            '</div>'
        )
    else:
        result_html = (
            '<div style="text-align:center; padding:.5rem .8rem; '
            'background:#1a3a1a; color:#8fff8f; border-radius:6px; '
            'font-family:monospace; font-size:.95rem; margin-bottom:.5rem;">'
            f'x={last_x}, y={last_y} &nbsp;&rarr;&nbsp; {last_result}'
            f'&nbsp;&nbsp;<span style="color:#5a9;">[{click_count} probe(s)]</span>'
            '</div>'
        )

    # ── Half labels ──────────────────────────────────────────────────
    top_label = (
        '<div style="font-size:.78rem; color:#bbb; margin-bottom:.2rem; '
        'text-align:center;">'
        '\u25b2 TOP HALF \u2014 click for <strong>RGB</strong> values'
        '</div>'
    )
    bottom_label = (
        '<div style="font-size:.78rem; color:#bbb; margin-top:.2rem; '
        'text-align:center;">'
        '\u25bc BOTTOM HALF \u2014 click for <strong>HSV</strong> values'
        '</div>'
    )

    # ── Dashed dividing line (purely visual, pointer-events:none) ────
    divider_html = (
        '<div style="position:absolute; top:0; left:0; '
        'width:100%; height:50%; '
        'border-bottom:2px dashed rgba(255,255,0,0.65); '
        'pointer-events:none; box-sizing:border-box;"></div>'
    )

    # ── Scene container + image ──────────────────────────────────────
    scene_html = (
        '<div id="wsz6-scene" '
        'style="position:relative; display:inline-block; line-height:0; '
        'border-radius:4px; box-shadow:0 2px 12px rgba(0,0,0,.25);">'
        f'<img src="{_IMG_URL}" width="{_IMG_W}" height="{_IMG_H}" '
        f'style="display:block; max-width:{_DISPLAY_W}px; height:auto;">'
        + divider_html
        + '</div>'
    )

    # ── Region manifest (Tier 2 — parsed by game.html setupHitCanvas) ─
    regions_html = (
        '<script type="application/json" id="wsz6-regions">'
        + _MANIFEST_JSON
        + '</script>'
    )

    # ── Hint ─────────────────────────────────────────────────────────
    hint_html = (
        '<div style="font-size:.75rem; color:#888; margin-top:.4rem; '
        'text-align:center;">'
        'Hover to highlight a region; click to read the pixel at that point.'
        '</div>'
    )

    return (
        '<div style="display:flex; flex-direction:column; '
        'align-items:flex-start; gap:0;">'
        + result_html
        + top_label
        + scene_html
        + bottom_label
        + regions_html
        + hint_html
        + '</div>'
    )
