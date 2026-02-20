"""
Click_Word_WSZ6_VIS.py

WSZ6 visualization module for the "Cliquez sur l'image" vocabulary game.
Companion to Click_Word_SZ6.py.

Demonstrates M3 Tier-2 canvas hit-testing: the scene is a pure SVG image
(no data-op-index attributes on any element); interactivity is driven by
a JSON region manifest embedded in a <script type="application/json"
id="wsz6-regions"> block.  The game.html client overlays a transparent
<canvas>, does point-in-region testing, and dispatches operator calls.

render_state(state) -> str
    Returns an HTML string containing:
      1. A prompt bar showing the French word to find.
      2. A progress / score line.
      3. A <div id="wsz6-scene"> with a 600×400 inline SVG room scene.
      4. A <script type="application/json" id="wsz6-regions"> block with
         the Tier-2 region manifest (6 regions, one per object).

Region ordering in the manifest (important for hit-test priority —
first match wins, so smaller/more-specific regions come before larger ones):
  index 0 in array → apple  (op_index 0)   — small circle, on table
  index 1 in array → cup    (op_index 4)   — small rect, on table
  index 2 in array → book   (op_index 5)   — small rect, on table
  index 3 in array → table  (op_index 2)   — large rect, catches table surface
  index 4 in array → chair  (op_index 3)   — rect, left of table
  index 5 in array → window (op_index 1)   — large rect, top-right wall

Note: array order ≠ op_index.  Each region carries an explicit op_index field.
"""

import json

# ---------------------------------------------------------------------------
# WORD LIST (mirrors Click_Word_SZ6.WORDS — imported via state module attr
# to avoid circular import; we duplicate the minimal data we need here).
# ---------------------------------------------------------------------------

_WORDS = [
    ('pomme',   'apple',  0),
    ('fenêtre', 'window', 1),
    ('table',   'table',  2),
    ('chaise',  'chair',  3),
    ('tasse',   'cup',    4),
    ('livre',   'book',   5),
]

# ---------------------------------------------------------------------------
# SVG SCENE  (600 × 400)
# ---------------------------------------------------------------------------
#
#  Layout (y increases downward):
#    Wall (beige):       full background, y 0–400
#    Floor (wood):       y 265–400
#    Baseboard:          y 260–268
#    Window (fenêtre):   x 420–580, y 25–150   (top-right wall)
#    Table (table):      x 148–432, y 220–238   top; legs to y 276
#    Chair (chaise):     x 70–154, y 185–282    (left of table)
#    Apple (pomme):      ellipse cx=215, cy=207, rx=20, ry=18   (on table)
#    Cup (tasse):        trapezoid x≈345–392, y 192–220       (on table right)
#    Book (livre):       rect x=281–335, y 209–222            (on table centre)
# ---------------------------------------------------------------------------

_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 400"
     width="600" height="400" style="display:block;">

  <!-- ── Background ── -->
  <rect x="0" y="0" width="600" height="400" fill="#f2e8d0"/>

  <!-- ── Floor ── -->
  <rect x="0" y="265" width="600" height="135" fill="#c4934e"/>
  <!-- Floorboards -->
  <line x1="0" y1="295" x2="600" y2="295" stroke="#b07e3a" stroke-width="1.5"/>
  <line x1="0" y1="325" x2="600" y2="325" stroke="#b07e3a" stroke-width="1.5"/>
  <line x1="0" y1="355" x2="600" y2="355" stroke="#b07e3a" stroke-width="1.5"/>
  <line x1="0" y1="385" x2="600" y2="385" stroke="#b07e3a" stroke-width="1.5"/>
  <line x1="100" y1="265" x2="100" y2="400" stroke="#b07e3a" stroke-width="1"/>
  <line x1="230" y1="265" x2="230" y2="400" stroke="#b07e3a" stroke-width="1"/>
  <line x1="370" y1="265" x2="370" y2="400" stroke="#b07e3a" stroke-width="1"/>
  <line x1="500" y1="265" x2="500" y2="400" stroke="#b07e3a" stroke-width="1"/>

  <!-- ── Baseboard ── -->
  <rect x="0" y="258" width="600" height="9" fill="#9a7040"/>
  <line x1="0" y1="258" x2="600" y2="258" stroke="#7a5020" stroke-width="1"/>

  <!-- ── Window (fenêtre) ── -->
  <!-- Outer frame -->
  <rect x="420" y="25" width="160" height="125" rx="3"
        fill="#e0cfa0" stroke="#5d4e37" stroke-width="4"/>
  <!-- Glass panes -->
  <rect x="428" y="33" width="144" height="109" fill="#b4dcf5"/>
  <!-- Horizontal glazing bar -->
  <rect x="428" y="85" width="144" height="5" fill="#5d4e37"/>
  <!-- Vertical glazing bar -->
  <rect x="498" y="33" width="5" height="109" fill="#5d4e37"/>
  <!-- Sky glint in top-left pane -->
  <ellipse cx="448" cy="55" rx="18" ry="12"
           fill="rgba(255,255,240,0.45)"/>
  <!-- Sill -->
  <rect x="416" y="148" width="168" height="8" rx="2"
        fill="#c8a870" stroke="#5d4e37" stroke-width="1.5"/>

  <!-- ── Chair (chaise) ── -->
  <!-- Back post -->
  <rect x="70" y="185" width="14" height="60" fill="#8b5e3c" rx="2"/>
  <!-- Top rail -->
  <rect x="70" y="185" width="76" height="13" fill="#a06840" rx="3"/>
  <!-- Seat -->
  <rect x="70" y="232" width="76" height="14" fill="#8b5e3c" rx="2"/>
  <!-- Front-left leg -->
  <rect x="76" y="246" width="10" height="30" fill="#7a5030" rx="1"/>
  <!-- Front-right leg -->
  <rect x="127" y="246" width="10" height="30" fill="#7a5030" rx="1"/>

  <!-- ── Table (table) ── -->
  <!-- Table top -->
  <rect x="148" y="220" width="284" height="18"
        fill="#8b5e3c" stroke="#5a3a20" stroke-width="1.5" rx="2"/>
  <!-- Table edge highlight -->
  <rect x="150" y="220" width="280" height="4" fill="#9a6e48" rx="1"/>
  <!-- Left leg -->
  <rect x="163" y="238" width="15" height="38" fill="#7a5030"/>
  <!-- Right leg -->
  <rect x="396" y="238" width="15" height="38" fill="#7a5030"/>
  <!-- Shadow under table -->
  <ellipse cx="290" cy="278" rx="128" ry="8"
           fill="rgba(0,0,0,0.10)"/>

  <!-- ── Apple (pomme) — on table ── -->
  <!-- Body -->
  <ellipse cx="215" cy="207" rx="20" ry="18" fill="#d82020"/>
  <!-- Highlight -->
  <ellipse cx="208" cy="199" rx="5" ry="4"
           fill="rgba(255,255,255,0.42)"/>
  <!-- Stem -->
  <line x1="215" y1="189" x2="217" y2="177"
        stroke="#4a2a0a" stroke-width="2.5" stroke-linecap="round"/>
  <!-- Leaf -->
  <ellipse cx="224" cy="178" rx="9" ry="5" fill="#2d7a20"
           transform="rotate(-35,224,178)"/>

  <!-- ── Cup (tasse) — on table ── -->
  <!-- Body (trapezoid) -->
  <polygon points="345,220 352,192 386,192 393,220"
           fill="#9eb8c0" stroke="#7e9898" stroke-width="1.5"/>
  <!-- Rim -->
  <ellipse cx="369" cy="192" rx="17.5" ry="5" fill="#7e9898"/>
  <!-- Handle -->
  <path d="M393,203 Q415,203 415,212 Q415,221 393,221"
        fill="none" stroke="#9eb8c0" stroke-width="7"
        stroke-linecap="round"/>
  <!-- Liquid surface -->
  <ellipse cx="369" cy="192" rx="15" ry="3.5"
           fill="rgba(210,175,120,0.55)"/>

  <!-- ── Book (livre) — flat on table ── -->
  <!-- Cover -->
  <rect x="281" y="208" width="55" height="14"
        fill="#2050c0" stroke="#1a3a90" stroke-width="1.5" rx="1"/>
  <!-- Spine -->
  <rect x="281" y="208" width="7" height="14" fill="#1a3a80"/>
  <!-- Page lines -->
  <line x1="292" y1="210.5" x2="333" y2="210.5"
        stroke="rgba(255,255,255,0.38)" stroke-width="1"/>
  <line x1="292" y1="214" x2="333" y2="214"
        stroke="rgba(255,255,255,0.38)" stroke-width="1"/>
  <line x1="292" y1="217.5" x2="333" y2="217.5"
        stroke="rgba(255,255,255,0.38)" stroke-width="1"/>

</svg>"""


# ---------------------------------------------------------------------------
# REGION MANIFEST
# ---------------------------------------------------------------------------
#
# Array ordering (most specific first to resolve overlaps correctly):
#   [0] apple  (op_index 0)  – on table; must come before table
#   [1] cup    (op_index 4)  – on table; must come before table
#   [2] book   (op_index 5)  – on table; must come before table
#   [3] table  (op_index 2)  – large rect; catches table surface clicks
#   [4] chair  (op_index 3)
#   [5] window (op_index 1)
# ---------------------------------------------------------------------------

_REGIONS = [
    {
        "op_index":   0,
        "shape":      "circle",
        "cx":         215,  "cy": 207, "r": 27,
        "hover_label": "apple",
    },
    {
        "op_index":   4,
        "shape":      "rect",
        "x": 338, "y": 185, "w": 85, "h": 40,
        "hover_label": "cup",
    },
    {
        "op_index":   5,
        "shape":      "rect",
        "x": 279, "y": 206, "w": 59, "h": 18,
        "hover_label": "book",
    },
    {
        "op_index":   2,
        "shape":      "rect",
        "x": 148, "y": 215, "w": 284, "h": 65,
        "hover_label": "table",
    },
    {
        "op_index":   3,
        "shape":      "rect",
        "x": 64, "y": 180, "w": 90, "h": 102,
        "hover_label": "chair",
    },
    {
        "op_index":   1,
        "shape":      "rect",
        "x": 420, "y": 25, "w": 160, "h": 133,
        "hover_label": "window",
    },
]

_MANIFEST = {
    "container_id":  "wsz6-scene",
    "scene_width":   600,
    "scene_height":  400,
    "regions":       _REGIONS,
}

_MANIFEST_JSON = json.dumps(_MANIFEST, separators=(',', ':'))


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def render_state(state) -> str:
    """Return an HTML string for the current game state."""

    words       = _WORDS          # avoid circular import; duplicated above
    word_idx    = getattr(state, 'word_idx',  0)
    attempts    = getattr(state, 'attempts',  0)
    at_goal     = word_idx >= len(words)

    # ── Prompt bar ──────────────────────────────────────────────────
    if at_goal:
        prompt_html = (
            '<div style="text-align:center; padding:.6rem .8rem; '
            'background:#d4edda; color:#155724; border-radius:6px; '
            'font-size:1.1rem; font-weight:700; margin-bottom:.6rem;">'
            '&#10003; Félicitations! You identified all the words!'
            '</div>'
        )
    else:
        french = words[word_idx][0]
        prompt_html = (
            '<div style="text-align:center; padding:.5rem .8rem; '
            'background:#1a3a6c; color:#fff; border-radius:6px; '
            'font-size:1.1rem; margin-bottom:.6rem;">'
            'Cliquez sur&nbsp;: '
            f'<strong style="font-size:1.25rem; letter-spacing:.05em;">'
            f'{french}</strong>'
            '</div>'
        )

    # ── Progress / score ────────────────────────────────────────────
    progress = word_idx
    total    = len(words)
    pct      = int(progress / total * 100)
    score_html = (
        '<div style="display:flex; align-items:center; gap:.6rem; '
        'margin-bottom:.5rem; font-size:.85rem; color:#555;">'
        f'<span>{progress}/{total} found</span>'
        '<div style="flex:1; height:8px; background:#ddd; border-radius:4px;">'
        f'<div style="width:{pct}%; height:100%; background:#2d6a4f; '
        'border-radius:4px; transition:width .3s;"></div>'
        '</div>'
        f'<span style="color:#c00;">{attempts} wrong</span>'
        '</div>'
    )

    # ── Scene container + SVG ────────────────────────────────────────
    scene_html = (
        '<div id="wsz6-scene" '
        'style="display:inline-block; line-height:0; overflow:hidden; '
        'border-radius:4px; box-shadow:0 2px 12px rgba(0,0,0,.18);">'
        + _SVG +
        '</div>'
    )

    # ── Region manifest (Tier 2 — parsed by game.html setupHitCanvas) ──
    regions_html = (
        f'<script type="application/json" id="wsz6-regions">'
        f'{_MANIFEST_JSON}'
        f'</script>'
    )

    # ── Hint line (after scene) ─────────────────────────────────────
    hint_html = (
        '<div style="font-size:.78rem; color:#888; margin-top:.35rem; '
        'text-align:center;">'
        'Hover over objects to identify them; click to select.'
        '</div>'
    )

    return (
        '<div style="display:flex; flex-direction:column; '
        'align-items:flex-start; gap:0;">'
        + prompt_html
        + score_html
        + scene_html
        + regions_html
        + hint_html
        + '</div>'
    )
