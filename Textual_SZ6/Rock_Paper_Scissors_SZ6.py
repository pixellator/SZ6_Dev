'''Rock_Paper_Scissors_SZ6.py

Rock-Paper-Scissors game for SOLUZION6.
Two players, NUM_ROUNDS rounds.  Scores start at 0.

Each round both players simultaneously choose Rock, Paper, or Scissors.
  Rock beats Scissors  (+1 winner, -1 loser)
  Scissors beats Paper (+1 winner, -1 loser)
  Paper beats Rock     (+1 winner, -1 loser)
  Same choice:          draw (0, 0)

The state carries a flag self.parallel = True during the choosing phase.
In a web engine, both players' choices will be collected simultaneously.
In Textual_SOLUZION6.py, they are serialized via player cueing, with the
state's text_view_for_role masking actual choices until both are in.

Status: Initial SZ6 draft, Feb 2026.
'''

SOLUZION_VERSION = 6

import soluzion6_02 as sz

# ---------------------------------------------------------------------------
# GLOBAL CONSTANTS
# ---------------------------------------------------------------------------

ROCK     = 0
PAPER    = 1
SCISSORS = 2
CHOICE_NAMES = ["Rock", "Paper", "Scissors"]

P1         = 0
P2         = 1
NUM_ROUNDS = 3

# ---------------------------------------------------------------------------
# METADATA
# ---------------------------------------------------------------------------

class RPS_Metadata(sz.SZ_Metadata):
    def __init__(self):
        self.name             = "Rock-Paper-Scissors"
        self.soluzion_version = SOLUZION_VERSION
        self.problem_version  = "1.0"
        self.authors          = ['S. Tanimoto']
        self.creation_date    = "2026-Feb"
        self.brief_desc = (
            f"A two-player Rock-Paper-Scissors match over {NUM_ROUNDS} rounds. "
            "Each round both players simultaneously choose Rock, Paper, or Scissors. "
            "Rock beats Scissors, Scissors beats Paper, Paper beats Rock. "
            "Winner of a round gets +1; loser gets -1; ties score 0. "
            "Highest cumulative score after all rounds wins the match."
        )

# ---------------------------------------------------------------------------
# STATE
# ---------------------------------------------------------------------------

class RPS_State(sz.SZ_State):
    '''One moment in a Rock-Paper-Scissors match.

    Phases:
      'choosing'  -- both players are making their choice this round.
                     self.parallel = True.
      'scoring'   -- both choices are in; round result is visible.
                     self.parallel = False.
      'game_over' -- after the final round's scoring.
                     self.parallel = False; is_goal() returns True.
    '''

    def __init__(self, old=None):
        if old is None:
            self.round_num        = 1
            self.scores           = [0, 0]      # [P1_score, P2_score]
            self.phase            = 'choosing'
            self.choices          = [None, None] # None = not yet chosen
            self.parallel         = True
            self.current_role_num = P1
        else:
            self.round_num        = old.round_num
            self.scores           = old.scores[:]
            self.phase            = old.phase
            self.choices          = old.choices[:]
            self.parallel         = old.parallel
            self.current_role_num = old.current_role_num

    def __str__(self):
        return self.text_view_for_role(self.current_role_num)

    def text_view_for_role(self, role_num):
        txt  = f"Round {self.round_num} of {NUM_ROUNDS}\n"
        txt += f"Scores:  P1 = {self.scores[P1]},  P2 = {self.scores[P2]}\n"
        if self.phase == 'choosing':
            # Keep actual choices hidden to preserve simultaneous-choice fairness.
            p1_str = "Made"    if self.choices[P1] is not None else "Pending"
            p2_str = "Made"    if self.choices[P2] is not None else "Pending"
            txt += f"P1 choice this round: {p1_str}\n"
            txt += f"P2 choice this round: {p2_str}\n"
        else:
            # Scoring or game-over: reveal both choices.
            txt += f"P1 chose: {CHOICE_NAMES[self.choices[P1]]}\n"
            txt += f"P2 chose: {CHOICE_NAMES[self.choices[P2]]}\n"
            if self.phase == 'game_over':
                txt += "-- Game Over --\n"
        return txt

    def __eq__(self, s):
        return (self.round_num == s.round_num and
                self.scores    == s.scores    and
                self.phase     == s.phase     and
                self.choices   == s.choices)

    def __hash__(self):
        return hash(str(self))

    # -- Move application --

    def apply_choice(self, player, choice):
        '''Return the new state after `player` submits `choice`.
        If this completes the round (both players have now chosen),
        compute scores and build the jit_transition; otherwise just
        record the choice and hand the turn to the other player.
        '''
        news          = RPS_State(old=self)
        news.choices[player] = choice

        if news.choices[P1] is not None and news.choices[P2] is not None:
            _resolve_round(news)           # mutates news in-place
        else:
            # One player down, one to go.
            news.current_role_num = P2 if player == P1 else P1

        return news

    # -- Goal --

    def is_goal(self):
        return self.phase == 'game_over'

    def goal_message(self):
        s1, s2 = self.scores[P1], self.scores[P2]
        result = ("Player 1 wins the match!" if s1 > s2 else
                  "Player 2 wins the match!" if s2 > s1 else
                  "The match is a draw!")
        return f"{result}  Final scores: P1 = {s1},  P2 = {s2}."


# ---------------------------------------------------------------------------
# ROUND-RESOLUTION HELPER
# ---------------------------------------------------------------------------

def _resolve_round(state):
    '''Mutate state to reflect a completed round.
    Called only when both state.choices are set.
    Updates scores, sets jit_transition, advances phase.
    '''
    c1    = state.choices[P1]
    c2    = state.choices[P2]
    n1    = CHOICE_NAMES[c1]
    n2    = CHOICE_NAMES[c2]
    delta = (c1 - c2) % 3   # 1 → P1 wins, 2 → P2 wins, 0 → tie

    if delta == 1:
        state.scores[P1] += 1
        state.scores[P2] -= 1
        result_line = f"P1 wins this round!   (P1: +1,  P2: -1)"
    elif delta == 2:
        state.scores[P1] -= 1
        state.scores[P2] += 1
        result_line = f"P2 wins this round!   (P1: -1,  P2: +1)"
    else:
        result_line = "Draw — scores unchanged."

    score_line = (f"Scores after round {state.round_num}: "
                  f"P1 = {state.scores[P1]},  P2 = {state.scores[P2]}")

    state.jit_transition = (f"P1 chose {n1}.  P2 chose {n2}.\n"
                             f"{result_line}\n"
                             f"{score_line}")

    state.parallel         = False
    state.current_role_num = P1   # P1 triggers "Start next round" (or sees game-over)

    if state.round_num == NUM_ROUNDS:
        state.phase = 'game_over'
    else:
        state.phase = 'scoring'


# ---------------------------------------------------------------------------
# OPERATORS
# ---------------------------------------------------------------------------

def _start_next_round(s):
    '''Transition function for the "Start next round" operator.'''
    news                  = RPS_State(old=s)
    news.round_num       += 1
    news.phase            = 'choosing'
    news.choices          = [None, None]
    news.parallel         = True
    news.current_role_num = P1
    return news


class RPS_Operator_Set(sz.SZ_Operator_Set):
    '''
    Six choice operators (three per player) plus one "Start next round".

    Each choice operator carries op.role = P1 or P2 so that
    Textual_SOLUZION6's get_applicability_vector can show each player
    only their own operators during the serialized choosing phase,
    even though both sets are simultaneously applicable in the state.

    The web engine, which handles the parallel phase natively, will
    use op.role to route each operator to the correct player's browser.
    '''

    def __init__(self):
        p1_ops = [
            sz.SZ_Operator(
                name=f"P1 chooses {CHOICE_NAMES[c]}",
                precond_func=lambda s, ch=c: (s.phase == 'choosing' and
                                              s.choices[P1] is None),
                state_xition_func=lambda s, ch=c: s.apply_choice(P1, ch),
                role=P1
            )
            for c in [ROCK, PAPER, SCISSORS]
        ]
        p2_ops = [
            sz.SZ_Operator(
                name=f"P2 chooses {CHOICE_NAMES[c]}",
                precond_func=lambda s, ch=c: (s.phase == 'choosing' and
                                              s.choices[P2] is None),
                state_xition_func=lambda s, ch=c: s.apply_choice(P2, ch),
                role=P2
            )
            for c in [ROCK, PAPER, SCISSORS]
        ]
        next_round_op = sz.SZ_Operator(
            name="Start next round",
            precond_func=lambda s: (s.phase == 'scoring' and
                                    s.round_num < NUM_ROUNDS),
            state_xition_func=_start_next_round,
            role=None   # Either player (or the engine) can trigger this.
        )
        self.operators = p1_ops + p2_ops + [next_round_op]


# ---------------------------------------------------------------------------
# ROLES
# ---------------------------------------------------------------------------

class RPS_Roles_Spec(sz.SZ_Roles_Spec):
    def __init__(self):
        self.roles = [
            sz.SZ_Role(name='P1',
                       description='Player 1 — goes first in the serial engine.'),
            sz.SZ_Role(name='P2',
                       description='Player 2.'),
        ]
        self.min_players_to_start = 2
        self.max_players          = 2

# ---------------------------------------------------------------------------
# FORMULATION
# ---------------------------------------------------------------------------

class RPS_Formulation(sz.SZ_Formulation):
    def __init__(self):
        self.metadata    = RPS_Metadata()
        self.operators   = RPS_Operator_Set()
        self.roles_spec  = RPS_Roles_Spec()
        self.common_data = sz.SZ_Common_Data()

    def initialize_problem(self, config={}):
        initial_state = RPS_State()
        self.instance_data = sz.SZ_Problem_Instance_Data(
            d={'initial_state': initial_state}
        )
        return initial_state

# ---------------------------------------------------------------------------
# MODULE-LEVEL ENTRY POINT
# ---------------------------------------------------------------------------

RPS = RPS_Formulation()

# ---------------------------------------------------------------------------
# SELF-TEST  (run with: python3 Rock_Paper_Scissors_SZ6.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Rock-Paper-Scissors SZ6 self-test ===\n")

    s = RPS.initialize_problem()
    ops = RPS.operators.operators
    # ops[0..2] = P1 ops (Rock, Paper, Scissors)
    # ops[3..5] = P2 ops (Rock, Paper, Scissors)
    # ops[6]    = Start next round

    print(f"Initial state (P1 view):\n{s.text_view_for_role(P1)}")

    # --- Round 1: P1 chooses Rock, P2 chooses Scissors → P1 wins ---
    s = ops[0].state_xition_func(s)          # P1: Rock
    print(f"After P1 chooses Rock (P2 view):\n{s.text_view_for_role(P2)}")

    s = ops[5].state_xition_func(s)          # P2: Scissors
    print(f"Transition: {s.jit_transition}\n")
    print(f"Scoring state:\n{s}")

    # --- Round 2: P1 chooses Scissors, P2 chooses Paper → P1 wins ---
    s = ops[6].state_xition_func(s)          # Start next round
    s = ops[1].state_xition_func(s)          # P1: Paper  (index 1)
    s = ops[4].state_xition_func(s)          # P2: Rock   (index 3)  — Paper beats Rock
    print(f"Round 2 transition: {s.jit_transition}\n")

    # --- Round 3: tie (both choose Rock) ---
    s = ops[6].state_xition_func(s)
    s = ops[0].state_xition_func(s)          # P1: Rock
    s = ops[3].state_xition_func(s)          # P2: Rock
    print(f"Round 3 transition: {s.jit_transition}\n")
    print(f"Final state:\n{s}")
    print(f"is_goal: {s.is_goal()}")
    print(f"goal_message: {s.goal_message()}")
