'''Pixel_Probe_SZ6.py

Single-player pixel-value exploration game.

An aerial photograph of the University of Washington campus is displayed.
The image is split horizontally into two halves:
  Top half    — click to read the RGB values at the clicked point.
  Bottom half — click to read the HSV values at the clicked point.

The click coordinates are captured at runtime by the Tier-2 canvas
hit-testing system (send_click_coords: true) and forwarded as operator
args.  Pillow reads the pixel from the server-side copy of the image.

The game is open-ended (no goal state); the player explores until done.
'''

SOLUZION_VERSION = 6

import os
import colorsys

from PIL import Image

import soluzion6_02 as sz
import Pixel_Probe_WSZ6_VIS as _pixel_vis

# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

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
    return img.getpixel((x, y))    # (r, g, b)


def _rgb_to_hsv(r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return round(h * 360), round(s * 100), round(v * 100)


# ---------------------------------------------------------------------------
# METADATA
# ---------------------------------------------------------------------------

class PixelProbe_Metadata(sz.SZ_Metadata):
    def __init__(self):
        self.name             = 'Pixel Values with Old UW Aerial Image'
        self.soluzion_version = SOLUZION_VERSION
        self.problem_version  = '1.0'
        self.authors          = ['S. Tanimoto']
        self.creation_date    = '2026-Feb'
        self.brief_desc = (
            'Click on an aerial photograph of the University of Washington '
            'to read the pixel values at the clicked point. '
            'Top half reports RGB; bottom half reports HSV. '
            'Demonstrates Tier-2 canvas regions with dynamic coordinate capture.'
        )


# ---------------------------------------------------------------------------
# STATE
# ---------------------------------------------------------------------------

class PixelProbe_State(sz.SZ_State):

    def __init__(self, old=None):
        if old is None:
            self.last_x           = None
            self.last_y           = None
            self.last_result      = None
            self.click_count      = 0
            self.current_role_num = 0
        else:
            self.last_x           = old.last_x
            self.last_y           = old.last_y
            self.last_result      = old.last_result
            self.click_count      = old.click_count
            self.current_role_num = old.current_role_num

    def is_goal(self):
        return False    # open-ended exploration game

    def __str__(self):
        if self.last_x is None:
            return (
                'Click anywhere on the image to probe a pixel.\n'
                'Top half \u2192 RGB  |  Bottom half \u2192 HSV'
            )
        return (
            f'Last click: x={self.last_x}, y={self.last_y}\n'
            f'Result:     {self.last_result}\n'
            f'Total probes: {self.click_count}'
        )


# ---------------------------------------------------------------------------
# TRANSITION HELPERS
# ---------------------------------------------------------------------------

def _probe_rgb(state, args):
    x, y = int(args[0]), int(args[1])
    r, g, b = _read_rgb(x, y)
    ns = PixelProbe_State(old=state)
    ns.last_x      = x
    ns.last_y      = y
    ns.last_result = f'RGB = ({r}, {g}, {b})'
    ns.click_count = state.click_count + 1
    ns.jit_transition = f'x={x}, y={y}  \u2192  RGB = ({r}, {g}, {b})'
    return ns


def _probe_hsv(state, args):
    x, y = int(args[0]), int(args[1])
    r, g, b = _read_rgb(x, y)
    h, s, v = _rgb_to_hsv(r, g, b)
    ns = PixelProbe_State(old=state)
    ns.last_x      = x
    ns.last_y      = y
    ns.last_result = f'HSV = ({h}\u00b0, {s}%, {v}%)'
    ns.click_count = state.click_count + 1
    ns.jit_transition = f'x={x}, y={y}  \u2192  HSV = ({h}\u00b0, {s}%, {v}%)'
    return ns


# ---------------------------------------------------------------------------
# OPERATORS
# ---------------------------------------------------------------------------

_COORD_PARAMS = [
    {'name': 'x', 'type': 'int', 'min': 0, 'max': 1599},
    {'name': 'y', 'type': 'int', 'min': 0, 'max': 1034},
]


class PixelProbe_Operator_Set(sz.SZ_Operator_Set):
    def __init__(self):
        self.operators = [
            sz.SZ_Operator(
                name='Probe pixel \u2014 RGB (top half)',
                precond_func=lambda s: True,
                state_xition_func=_probe_rgb,
                params=_COORD_PARAMS,
            ),
            sz.SZ_Operator(
                name='Probe pixel \u2014 HSV (bottom half)',
                precond_func=lambda s: True,
                state_xition_func=_probe_hsv,
                params=_COORD_PARAMS,
            ),
        ]


# ---------------------------------------------------------------------------
# ROLES  (single Visitor)
# ---------------------------------------------------------------------------

class PixelProbe_Roles_Spec(sz.SZ_Roles_Spec):
    def __init__(self):
        self.roles = [
            sz.SZ_Role(
                name='Visitor',
                description='Explores the aerial image by clicking to probe pixel values.',
            ),
        ]
        self.min_players_to_start = 1
        self.max_players          = 1


# ---------------------------------------------------------------------------
# FORMULATION
# ---------------------------------------------------------------------------

class PixelProbe_Formulation(sz.SZ_Formulation):
    def __init__(self):
        self.metadata    = PixelProbe_Metadata()
        self.operators   = PixelProbe_Operator_Set()
        self.roles_spec  = PixelProbe_Roles_Spec()
        self.common_data = sz.SZ_Common_Data()
        self.vis_module  = _pixel_vis

    def initialize_problem(self, config={}):
        initial = PixelProbe_State()
        self.instance_data = sz.SZ_Problem_Instance_Data(
            d={'initial_state': initial}
        )
        return initial


# ---------------------------------------------------------------------------
# MODULE-LEVEL ENTRY POINT (required by pff_loader duck-typing)
# ---------------------------------------------------------------------------

PIXEL_PROBE = PixelProbe_Formulation()
