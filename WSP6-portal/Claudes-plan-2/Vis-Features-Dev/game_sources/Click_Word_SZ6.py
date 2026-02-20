'''Click_Word_SZ6.py

Single-player French vocabulary game ("Cliquez sur l'image").

A stylised room scene is displayed alongside a French word.  The player
clicks on the object in the scene that matches the word.

Primary purpose: exercise the WSZ6 M3 Tier-2 canvas hit-testing feature.
Each scene region is defined in a JSON manifest embedded by the companion
vis module (Click_Word_WSZ6_VIS.py); the client overlays a transparent
canvas and does point-in-region testing without any SVG data-* attributes.

State:
  word_idx  – index of the word currently being asked (0 – len(WORDS))
  attempts  – cumulative incorrect clicks
  current_role_num = 0 (single-player)

Operators (one per scene region, indices 0–5):
  Always applicable while word_idx < len(WORDS).
  Clicking the correct region advances word_idx; clicking any other
  region increments attempts and keeps the same word.

Goal:  word_idx == len(WORDS)  (all words correctly identified)
'''

SOLUZION_VERSION = 6

import soluzion6_02 as sz
import Click_Word_WSZ6_VIS as _click_vis

# ---------------------------------------------------------------------------
# VOCABULARY LIST
# Each tuple: (french_word, english_name, region_index)
# region_index must match the op_index carried by the corresponding region
# in the JSON manifest produced by the vis module.
# ---------------------------------------------------------------------------

WORDS = [
    ('pomme',    'apple',  0),
    ('fenêtre',  'window', 1),
    ('table',    'table',  2),
    ('chaise',   'chair',  3),
    ('tasse',    'cup',    4),
    ('livre',    'book',   5),
]

# Human-readable English name for each region (used in corrective feedback).
REGION_NAMES_EN = ['apple', 'window', 'table', 'chair', 'cup', 'book']


# ---------------------------------------------------------------------------
# METADATA
# ---------------------------------------------------------------------------

class ClickWord_Metadata(sz.SZ_Metadata):
    def __init__(self):
        self.name             = "Cliquez sur l'image"
        self.soluzion_version = SOLUZION_VERSION
        self.problem_version  = '1.0'
        self.authors          = ['S. Tanimoto']
        self.creation_date    = '2026-Feb'
        self.brief_desc = (
            'A French vocabulary game. A room scene is displayed; '
            'click on the object that matches the French word shown. '
            'Demonstrates the WSZ6 M3 Tier-2 canvas hit-testing feature.'
        )


# ---------------------------------------------------------------------------
# STATE
# ---------------------------------------------------------------------------

class ClickWord_State(sz.SZ_State):

    def __init__(self, old=None):
        if old is None:
            self.word_idx         = 0   # which word is being asked
            self.attempts         = 0   # total incorrect clicks
            self.current_role_num = 0
        else:
            self.word_idx         = old.word_idx
            self.attempts         = old.attempts
            self.current_role_num = old.current_role_num

    def __str__(self):
        if self.word_idx >= len(WORDS):
            return (
                'Félicitations! You identified all the words.\n'
                f'Total incorrect clicks: {self.attempts}'
            )
        french, english, _ = WORDS[self.word_idx]
        remaining = len(WORDS) - self.word_idx
        return (
            f'Word {self.word_idx + 1} of {len(WORDS)}: '
            f'"{french}" means {english}\n'
            f'Incorrect clicks so far: {self.attempts}  |  '
            f'{remaining} word(s) remaining'
        )

    def is_goal(self):
        return self.word_idx >= len(WORDS)

    def goal_message(self):
        return (
            f'Félicitations! You identified all {len(WORDS)} French words. '
            f'Incorrect clicks: {self.attempts}. '
            'Use ↩ Undo to review any step, or start a new session to play again.'
        )


# ---------------------------------------------------------------------------
# HELPER: create a new state for clicking region `region_idx`
# ---------------------------------------------------------------------------

def _click_region(state, region_idx):
    '''Return a new state reflecting a click on the given region.'''
    ns = ClickWord_State(old=state)
    if ns.word_idx >= len(WORDS):
        return ns   # game already over; no-op

    expected_region = WORDS[ns.word_idx][2]
    french          = WORDS[ns.word_idx][0]
    english         = WORDS[ns.word_idx][1]

    if region_idx == expected_region:
        # Correct!
        ns.word_idx += 1
        if ns.word_idx < len(WORDS):
            next_fr = WORDS[ns.word_idx][0]
            ns.jit_transition = f'Correct! ✓   Now find: {next_fr}'
        else:
            ns.jit_transition = 'Correct! ✓   Félicitations — you found them all!'
    else:
        # Incorrect click.
        ns.attempts += 1
        wrong_en = REGION_NAMES_EN[region_idx]
        ns.jit_transition = (
            f'Not quite — "{french}" means {english}. '
            f'You clicked the {wrong_en}. Try again!'
        )
    return ns


# ---------------------------------------------------------------------------
# OPERATORS  (one per scene region / object)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# ROLES  (single learner)
# ---------------------------------------------------------------------------

class ClickWord_Roles_Spec(sz.SZ_Roles_Spec):
    def __init__(self):
        self.roles = [
            sz.SZ_Role(
                name='Learner',
                description='Identifies French vocabulary words by clicking the scene.',
            ),
        ]
        self.min_players_to_start = 1
        self.max_players          = 1


# ---------------------------------------------------------------------------
# FORMULATION
# ---------------------------------------------------------------------------

class ClickWord_Formulation(sz.SZ_Formulation):
    def __init__(self):
        self.metadata    = ClickWord_Metadata()
        self.operators   = ClickWord_Operator_Set()
        self.roles_spec  = ClickWord_Roles_Spec()
        self.common_data = sz.SZ_Common_Data()
        self.vis_module  = _click_vis

    def initialize_problem(self, config={}):
        initial = ClickWord_State()
        self.instance_data = sz.SZ_Problem_Instance_Data(
            d={'initial_state': initial}
        )
        return initial


# ---------------------------------------------------------------------------
# MODULE-LEVEL ENTRY POINT (required by pff_loader duck-typing)
# ---------------------------------------------------------------------------

CLICK_WORD = ClickWord_Formulation()
