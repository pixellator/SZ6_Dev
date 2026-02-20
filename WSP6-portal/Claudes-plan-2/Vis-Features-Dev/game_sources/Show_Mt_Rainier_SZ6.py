'''Show_Mt_Rainier_SZ6.py

A single-player SOLUZION6 "game" that lets a visitor browse a curated
collection of views from Mt. Rainier National Park and surrounds.

Primary purpose: exercise the M2 image-resource feature.  Each operator
selects one of the available images; the companion vis file
(Show_Mt_Rainier_WSZ6_VIS.py) renders it via the /play/game-asset/ endpoint.

Goal: all images have been viewed at least once.
'''

SOLUZION_VERSION = 6

import soluzion6_02 as sz
import Show_Mt_Rainier_WSZ6_VIS as _rainier_vis

# ---------------------------------------------------------------------------
# IMAGE CATALOGUE
# Each tuple: (filename, title, caption)
# Images live in the game directory (games_repo/show-mt-rainier/).
# ---------------------------------------------------------------------------

IMAGES = [
    (
        'summit_view.svg',
        'Summit View',
        'The iconic snow-capped summit of Mt. Rainier (14,411 ft.) seen from '
        'the south across the Nisqually Glacier moraine. The stratovolcano '
        'rises nearly 13,000 ft. above the surrounding terrain — the greatest '
        'local relief of any mountain in the contiguous United States.',
    ),
    (
        'paradise_meadows.svg',
        'Paradise Meadows',
        'Wildflower meadows at Paradise (5,400 ft.) in mid-July. Over '
        '50 species bloom here each summer, including Indian paintbrush, '
        'glacier lilies, lupine, and bistort. Paradise receives an average '
        'of 53 ft. of snow per year — a world snowfall record at the time '
        'it was measured.',
    ),
    (
        'reflection_lakes.svg',
        'Reflection Lakes',
        'On calm mornings the twin Reflection Lakes mirror the cone of '
        'Mt. Rainier almost perfectly. Located at 4,861 ft. on the '
        'southeast side of the park along the Stevens Canyon Road, they '
        'are one of the most-photographed spots in the national park.',
    ),
    (
        'carbon_glacier.svg',
        'Carbon Glacier',
        'Carbon Glacier descends from the north face and is the longest '
        'glacier in the contiguous United States at about 5.7 miles. Its '
        'thick, debris-covered terminus reaches as low as 3,500 ft. — '
        'the lowest elevation of any glacier in the lower 48 states.',
    ),
    (
        'skyline_trail.svg',
        'Skyline Trail',
        'The Skyline Trail is a 5.5-mile loop departing from Paradise that '
        'climbs to 7,000 ft. at Panorama Point, offering 360° views of '
        'the mountain, the Cascades, and on clear days the Olympic '
        'Mountains. A resident marmot colony entertains hikers near '
        'the upper switchbacks.',
    ),
]


# ---------------------------------------------------------------------------
# METADATA
# ---------------------------------------------------------------------------

class Rainier_Metadata(sz.SZ_Metadata):
    def __init__(self):
        self.name             = 'Mt. Rainier Views'
        self.soluzion_version = SOLUZION_VERSION
        self.problem_version  = '1.0'
        self.authors          = ['S. Tanimoto']
        self.creation_date    = '2026-Feb'
        self.brief_desc = (
            'Browse five scenic views from Mt. Rainier National Park. '
            'Select each image to read its caption. '
            'The goal is reached when all five have been viewed. '
            'Demonstrates the WSZ6 M2 image-resource feature.'
        )


# ---------------------------------------------------------------------------
# STATE
# ---------------------------------------------------------------------------

class Rainier_State(sz.SZ_State):

    def __init__(self, old=None):
        if old is None:
            self.current_idx    = 0              # index into IMAGES; start on first image
            self.viewed_indices = {0}            # set of indices seen so far
            self.current_role_num = 0
        else:
            self.current_idx      = old.current_idx
            self.viewed_indices   = set(old.viewed_indices)
            self.current_role_num = old.current_role_num

    def __str__(self):
        fn, title, caption = IMAGES[self.current_idx]
        seen  = len(self.viewed_indices)
        total = len(IMAGES)
        lines = [
            f'Now viewing ({seen}/{total} seen): {title}',
            '',
            caption,
        ]
        if not self.is_goal():
            unseen = [IMAGES[i][1] for i in range(total) if i not in self.viewed_indices]
            lines += ['', 'Not yet viewed: ' + ', '.join(unseen)]
        return '\n'.join(lines)

    def select_image(self, idx):
        '''Return a new state with image idx selected and marked viewed.'''
        ns = Rainier_State(old=self)
        ns.current_idx = idx
        ns.viewed_indices.add(idx)
        ns.jit_transition = f'Now viewing: {IMAGES[idx][1]}.'
        return ns

    def is_goal(self):
        return len(self.viewed_indices) == len(IMAGES)

    def goal_message(self):
        return (
            'You have viewed all five scenes from Mt. Rainier National Park. '
            'The park was established in 1899 and covers 236,381 acres. '
            'Thanks for exploring!'
        )


# ---------------------------------------------------------------------------
# OPERATORS  (one per image; applicable when that image is not current)
# ---------------------------------------------------------------------------

class Rainier_Operator_Set(sz.SZ_Operator_Set):
    def __init__(self):
        self.operators = [
            sz.SZ_Operator(
                name=f'View: {title}',
                precond_func=lambda s, i=i: s.current_idx != i,
                state_xition_func=lambda s, i=i: s.select_image(i),
            )
            for i, (_, title, _) in enumerate(IMAGES)
        ]


# ---------------------------------------------------------------------------
# ROLES  (single viewer)
# ---------------------------------------------------------------------------

class Rainier_Roles_Spec(sz.SZ_Roles_Spec):
    def __init__(self):
        self.roles = [
            sz.SZ_Role(name='Visitor', description='Browses the gallery.'),
        ]
        self.min_players_to_start = 1
        self.max_players          = 1


# ---------------------------------------------------------------------------
# FORMULATION
# ---------------------------------------------------------------------------

class Rainier_Formulation(sz.SZ_Formulation):
    def __init__(self):
        self.metadata    = Rainier_Metadata()
        self.operators   = Rainier_Operator_Set()
        self.roles_spec  = Rainier_Roles_Spec()
        self.common_data = sz.SZ_Common_Data()
        self.vis_module  = _rainier_vis

    def initialize_problem(self, config={}):
        initial = Rainier_State()
        self.instance_data = sz.SZ_Problem_Instance_Data(
            d={'initial_state': initial}
        )
        return initial


# ---------------------------------------------------------------------------
# MODULE-LEVEL ENTRY POINT
# ---------------------------------------------------------------------------

RAINIER = Rainier_Formulation()
