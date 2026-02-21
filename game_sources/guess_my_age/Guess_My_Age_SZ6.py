'''Guess_My_Age_SZ6.py

Guess-My-Age formulation for SOLUZION6.
Refactored from Guess_My_Age.py (SOLUZION5 version).

Key SZ6 changes from SZ5:
  - Class-based structure subclassing soluzion6_02.py classes.
  - MY_SECRET_AGE is no longer a global variable; it is stored in
    instance_data so that multiple independent game sessions can
    coexist without interfering with each other.
  - The operator set is created inside initialize_problem(), after
    the secret age is chosen, so each operator closure captures
    that session's secret age.
  - state_xition_func for the parameterized operator takes (s, args),
    consistent with how Textual_SOLUZION6.py will call parameterized
    operators (same convention as Text_SOLUZION5.py).
  - Bug fix from SZ5: copy constructor now correctly copies n_guesses
    from old state (was accidentally hardcoded to 17 in the SZ5 version).

Status: Initial SZ6 draft, Feb 2026.
'''

SOLUZION_VERSION = 6

import soluzion6_02 as sz
import random

# ---------------------------------------------------------------------------
# GLOBAL CONSTANTS
# ---------------------------------------------------------------------------

MIN_AGE = 14
MAX_AGE = 21

# ---------------------------------------------------------------------------
# METADATA
# ---------------------------------------------------------------------------

class GMA_Metadata(sz.SZ_Metadata):
    def __init__(self):
        self.name             = "Guess-My-Age"
        self.soluzion_version = SOLUZION_VERSION
        self.problem_version  = "1.0"
        self.authors          = ['S. Tanimoto']
        self.creation_date    = "2026-Feb"
        self.brief_desc = (
            "A simple single-player game that demonstrates random game "
            "instances and a parameterized operator. The computer picks "
            "a secret age; the player guesses until correct."
        )

# ---------------------------------------------------------------------------
# STATE
# ---------------------------------------------------------------------------

class GMA_State(sz.SZ_State):
    '''Tracks how many guesses have been made and whether the player has won.'''

    def __init__(self, old=None):
        if old is None:
            self.n_guesses        = 0
            self.win              = False
            self.current_role_num = 0
        else:
            # Deep copy. (Bug fix: SZ5 version hardcoded 17 here.)
            self.n_guesses        = old.n_guesses
            self.win              = old.win
            self.current_role_num = old.current_role_num

    def __str__(self):
        return "You've made " + str(self.n_guesses) + " guess(es) so far."

    def text_view_for_role(self, role_num):
        return str(self)

    def __eq__(self, s):
        return self.n_guesses == s.n_guesses and self.win == s.win

    def __hash__(self):
        return hash(str(self))

    def is_goal(self):
        return self.win

    def goal_message(self):
        return "You guessed it!"

    def handle_guess(self, args, secret_age):
        '''Apply the player's guess.  Returns the new state.
        args[0] is the guessed integer.
        secret_age is passed in from the operator closure so this
        state method does not depend on any global or module-level variable.
        '''
        news = GMA_State(old=self)
        news.n_guesses = self.n_guesses + 1
        guess = args[0]

        if guess == secret_age:
            news.win = True
            news.jit_transition = (str(guess) + " is a nice guess. " +
                                   "You got it!  The secret age was " +
                                   str(secret_age) + ".")
        else:
            hint = "Too low. " if guess < secret_age else "Too high. "
            news.win = False
            news.jit_transition = str(guess) + " is a nice guess. Nice try. " + hint

        return news

# ---------------------------------------------------------------------------
# OPERATOR SET
# (Created inside initialize_problem so the secret age can be captured.)
# ---------------------------------------------------------------------------

def _make_operator_set(secret_age):
    '''Build and return a GMA_Operator_Set whose single operator closes
    over secret_age.  Called once per game session from initialize_problem().
    '''

    class GMA_Operator_Set(sz.SZ_Operator_Set):
        def __init__(self):
            guess_op = sz.SZ_Operator(
                name="Guess my age",
                precond_func=lambda s: True,
                state_xition_func=lambda s, args, sa=secret_age: s.handle_guess(args, sa),
                params=[{'name': 'age', 'type': 'int',
                         'min': MIN_AGE, 'max': MAX_AGE}]
            )
            self.operators = [guess_op]

    return GMA_Operator_Set()

# ---------------------------------------------------------------------------
# ROLES
# ---------------------------------------------------------------------------

class GMA_Roles_Spec(sz.SZ_Roles_Spec):
    def __init__(self):
        self.roles = [
            sz.SZ_Role(name='Age Guesser',
                       description='Tries to guess the computer-chosen secret age.'),
        ]
        self.min_players_to_start = 1
        self.max_players          = 1

# ---------------------------------------------------------------------------
# FORMULATION
# ---------------------------------------------------------------------------

class GMA_Formulation(sz.SZ_Formulation):
    '''Top-level formulation for Guess-My-Age.
    initialize_problem() picks the secret age, builds the operator set
    with that age captured in a closure, and creates the initial state.
    '''

    def __init__(self):
        self.metadata    = GMA_Metadata()
        self.roles_spec  = GMA_Roles_Spec()
        self.common_data = sz.SZ_Common_Data()
        # operators are set in initialize_problem(), not here, because they
        # must close over the session-specific secret age.
        self.operators   = None

    def initialize_problem(self, config={}):
        '''Choose a secret age, wire up operators, create initial state.'''
        secret_age = random.randint(MIN_AGE, MAX_AGE)
        self.operators = _make_operator_set(secret_age)
        initial_state  = GMA_State()
        self.instance_data = sz.SZ_Problem_Instance_Data(
            d={'secret_age':     secret_age,
               'initial_state':  initial_state}
        )
        return initial_state

# ---------------------------------------------------------------------------
# MODULE-LEVEL ENTRY POINT
# ---------------------------------------------------------------------------

GMA = GMA_Formulation()

# ---------------------------------------------------------------------------
# SELF-TEST  (run with: python3 Guess_My_Age_SZ6.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Guess-My-Age SZ6 self-test ===")
    s = GMA.initialize_problem()
    secret = GMA.instance_data.data['secret_age']
    print(f"Secret age (revealed for testing): {secret}")
    print(s)

    op = GMA.operators.operators[0]
    print(f"Operator: '{op.name}'")
    print(f"Params:   {op.params}")

    # Simulate a wrong guess, then the correct one.
    wrong_guess = MIN_AGE if secret != MIN_AGE else MAX_AGE
    print(f"\nGuessing {wrong_guess} (wrong):")
    s = op.state_xition_func(s, [wrong_guess])
    print(s)
    if hasattr(s, 'jit_transition'):
        print("Transition:", s.jit_transition)

    print(f"\nGuessing {secret} (correct):")
    s = op.state_xition_func(s, [secret])
    print(s)
    if hasattr(s, 'jit_transition'):
        print("Transition:", s.jit_transition)
    print("is_goal:", s.is_goal())
    print(s.goal_message())
