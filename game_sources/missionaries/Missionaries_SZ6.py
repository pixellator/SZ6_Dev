'''Missionaries_SZ6.py
("Missionaries and Cannibals" problem)

SOLUZION6 formulation.
Refactored from Missionaries.py (SOLUZION5 version).

Key SZ6 changes from SZ5:
  - Class-based structure subclassing soluzion6_02.py classes.
  - No import of soluzion5; uses soluzion6_02 instead.
  - Roles spec added explicitly (single Solver role); in SZ5 this
    defaulted silently inside Text_SOLUZION5.py.
  - text_view_for_role() made explicit; in SZ5 it defaulted to str(self).
  - initialize_problem() replaces implicit State() construction in the engine.
  - Local Operator subclass (which was just a pass-through in SZ5) removed;
    sz.SZ_Operator used directly.

Status: Initial SZ6 draft, Feb 2026.
'''

SOLUZION_VERSION = 6

import soluzion6_02 as sz

# ---------------------------------------------------------------------------
# GLOBAL CONSTANTS
# ---------------------------------------------------------------------------

M     = 0   # Index for missionaries in the people array.
C     = 1   # Index for cannibals.
LEFT  = 0   # Index for the left bank.
RIGHT = 1   # Index for the right bank.

# The five legal boat-load combinations (missionaries, cannibals).
# At least one missionary must steer; boat holds at most 3.
MC_COMBINATIONS = [(1,0),(2,0),(3,0),(1,1),(2,1)]

# ---------------------------------------------------------------------------
# METADATA
# ---------------------------------------------------------------------------

class MC_Metadata(sz.SZ_Metadata):
    def __init__(self):
        self.name             = "Missionaries and Cannibals"
        self.soluzion_version = SOLUZION_VERSION
        self.problem_version  = "3.0"
        self.authors          = ['S. Tanimoto']
        self.creation_date    = "2026-Feb"
        self.brief_desc = (
            'The "Missionaries and Cannibals" problem is a traditional puzzle '
            "in which the player starts off with three missionaries and three "
            "cannibals on the left bank of a river. The object is to execute a "
            "sequence of legal moves that transfers them all to the right bank. "
            "In this version, the boat carries at most three people, one of whom "
            "must be a missionary to steer. Missionaries must never be outnumbered "
            "by cannibals on either bank or in the boat."
        )

# ---------------------------------------------------------------------------
# STATE
# ---------------------------------------------------------------------------

class MC_State(sz.SZ_State):
    '''Represents one configuration of people and the boat.

    self.d is a dict with two keys:
      'people': a 2x2 list where people[type][side] gives the count of
                that type (M=0 or C=1) on that side (LEFT=0 or RIGHT=1).
      'boat':   LEFT or RIGHT — which bank the boat is currently on.
    '''

    def __init__(self, old=None):
        if old is None:
            # Initial state: all people on the left, boat on the left.
            self.d = {
                'people': [[3, 0],   # missionaries: [left, right]
                           [3, 0]],  # cannibals:    [left, right]
                'boat':   LEFT
            }
            self.current_role_num = 0
        else:
            # Deep copy.
            self.d = {
                'people': [old.d['people'][kind][:] for kind in [M, C]],
                'boat':   old.d['boat']
            }
            self.current_role_num = old.current_role_num

    def __str__(self):
        p    = self.d['people']
        side = 'left' if self.d['boat'] == LEFT else 'right'
        txt  = "\n M on left:"  + str(p[M][LEFT])  + "\n"
        txt +=  " C on left:"  + str(p[C][LEFT])  + "\n"
        txt +=  "   M on right:" + str(p[M][RIGHT]) + "\n"
        txt +=  "   C on right:" + str(p[C][RIGHT]) + "\n"
        txt +=  " boat is on the " + side + ".\n"
        return txt

    def text_view_for_role(self, role_num):
        return str(self)

    def __eq__(self, s2):
        if s2 is None:
            return False
        return (self.d['people'] == s2.d['people'] and
                self.d['boat']   == s2.d['boat'])

    def __hash__(self):
        return hash(str(self))

    # -- Move legality --

    def can_move(self, m, c):
        '''Return True if it is legal to cross the river taking
        m missionaries and c cannibals.'''
        side = self.d['boat']
        p    = self.d['people']
        if m < 1:
            return False  # Need at least one missionary to steer.
        if p[M][side] < m:
            return False  # Not enough missionaries available.
        if p[C][side] < c:
            return False  # Not enough cannibals available.
        m_remaining  = p[M][side]   - m
        c_remaining  = p[C][side]   - c
        m_at_arrival = p[M][1-side] + m
        c_at_arrival = p[C][1-side] + c
        # Missionaries must not be outnumbered on either bank.
        if m_remaining  > 0 and m_remaining  < c_remaining:  return False
        if m_at_arrival > 0 and m_at_arrival < c_at_arrival: return False
        return True

    # -- Move application --

    def move(self, m, c):
        '''Return the new state resulting from crossing with m missionaries
        and c cannibals.  Assumes can_move(m, c) is True.'''
        news = MC_State(old=self)
        side = self.d['boat']
        p    = news.d['people']
        p[M][side]   -= m
        p[C][side]   -= c
        p[M][1-side] += m
        p[C][1-side] += c
        news.d['boat'] = 1 - side
        return news

    # -- Goal --

    def is_goal(self):
        '''All missionaries and cannibals have reached the right bank.'''
        p = self.d['people']
        return p[M][RIGHT] == 3 and p[C][RIGHT] == 3

    def goal_message(self):
        return ("Congratulations on successfully guiding the missionaries "
                "and cannibals across the river!")

# ---------------------------------------------------------------------------
# OPERATORS
# ---------------------------------------------------------------------------

class MC_Operator_Set(sz.SZ_Operator_Set):
    '''One operator per legal (missionaries, cannibals) boat-load combination.'''

    def __init__(self):
        self.operators = [
            sz.SZ_Operator(
                name=("Cross the river with " + str(m) +
                      " missionaries and " + str(c) + " cannibals"),
                precond_func=lambda s, m1=m, c1=c: s.can_move(m1, c1),
                state_xition_func=lambda s, m1=m, c1=c: s.move(m1, c1)
            )
            for (m, c) in MC_COMBINATIONS
        ]

# ---------------------------------------------------------------------------
# ROLES
# (Single-player puzzle; one Solver role.)
# ---------------------------------------------------------------------------

class MC_Roles_Spec(sz.SZ_Roles_Spec):
    def __init__(self):
        self.roles = [
            sz.SZ_Role(name='Solver',
                       description='Guides missionaries and cannibals across the river.'),
        ]
        self.min_players_to_start = 1
        self.max_players          = 1

# ---------------------------------------------------------------------------
# FORMULATION
# ---------------------------------------------------------------------------

class MC_Formulation(sz.SZ_Formulation):
    def __init__(self):
        self.metadata    = MC_Metadata()
        self.operators   = MC_Operator_Set()
        self.roles_spec  = MC_Roles_Spec()
        self.common_data = sz.SZ_Common_Data()

    def initialize_problem(self, config={}):
        initial_state = MC_State()
        self.instance_data = sz.SZ_Problem_Instance_Data(
            d={'initial_state': initial_state}
        )
        return initial_state

# ---------------------------------------------------------------------------
# MODULE-LEVEL ENTRY POINT
# ---------------------------------------------------------------------------

MC = MC_Formulation()

# ---------------------------------------------------------------------------
# SELF-TEST  (run with: python3 Missionaries_SZ6.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Missionaries and Cannibals SZ6 self-test ===")
    s = MC.initialize_problem()
    print("Initial state:", s)

    ops = MC.operators.operators
    print(f"Number of operators: {len(ops)}")
    for op in ops:
        print(f"  '{op.name}'  applicable: {op.precond_func(s)}")

    # Apply the known optimal first move: 1 missionary, 1 cannibal cross.
    op_1m1c = ops[3]  # (1,1) is index 3 in MC_COMBINATIONS
    print(f"\nApplying: '{op_1m1c.name}'")
    s2 = op_1m1c.state_xition_func(s)
    print(s2)

    # Apply return trip: 1 missionary comes back.
    op_1m0c = ops[0]  # (1,0) is index 0
    print(f"Applying: '{op_1m0c.name}'")
    s3 = op_1m0c.state_xition_func(s2)
    print(s3)

    print("is_goal (should be False):", s3.is_goal())
