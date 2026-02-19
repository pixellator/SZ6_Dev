'''Tic_Tac_Toe_SZ6.py

Tic-Tac-Toe formulation for SOLUZION6.
Refactored from Tic_Tac_Toe.py (SOLUZION5 version).

Key SZ6 changes from SZ5:
  - Class-based structure; subclasses SZ_Formulation and friends
    from soluzion6_02.py instead of using global variables and
    tagged-section comments.
  - No import of Select_Roles; role selection is handled by the
    game engine (Textual_SOLUZION6.py).
  - Roles are SZ_Role objects in an SZ_Roles_Spec, not dicts in
    a ROLES_List.
  - Operators live in an SZ_Operator_Set instance, not a global
    OPERATORS list.
  - initialize_problem() replaces create_initial_state().
  - is_win() and is_draw() added alongside is_goal().

Status: Initial SZ6 draft, Feb 2026.
'''

SOLUZION_VERSION = 6

import soluzion6_02 as sz

# ---------------------------------------------------------------------------
# GLOBAL CONSTANTS
# ---------------------------------------------------------------------------

EMPTY = 2   # Represents an unoccupied cell.
X     = 0   # Role number and board mark for the X player.
O     = 1   # Role number and board mark for the O player.
NAMES = ["X", "O", " "]   # Map int -> display character.

def int_to_name(i):
    return NAMES[i]

# ---------------------------------------------------------------------------
# METADATA
# ---------------------------------------------------------------------------

class TTT_Metadata(sz.SZ_Metadata):
    def __init__(self):
        self.name             = "Tic-Tac-Toe"
        self.soluzion_version = SOLUZION_VERSION
        self.problem_version  = "1.0"
        self.authors          = ['S. Tanimoto']
        self.creation_date    = "2026-Feb"
        self.brief_desc = (
            "Tic-Tac-Toe is a traditional game played on a 3x3 board by "
            "two players: X and O. They take turns, with X going first. "
            "The first player to get three marks in a line wins. "
            "If the board fills with no winner, the game is a draw."
        )

# ---------------------------------------------------------------------------
# STATE
# ---------------------------------------------------------------------------

class TTT_State(sz.SZ_State):
    '''Represents one board position in a Tic-Tac-Toe game.'''

    def __init__(self, old=None):
        if old is None:
            # Create the initial (empty) board state.
            self.whose_turn      = X
            self.current_role_num = X
            self.board = [[EMPTY, EMPTY, EMPTY],
                          [EMPTY, EMPTY, EMPTY],
                          [EMPTY, EMPTY, EMPTY]]
            self.win    = ""   # Describes any win found; empty if none.
            self.winner = -1   # Role number of the winner; -1 if none.
        else:
            # Deep-copy constructor: copy old state, then mutate as needed.
            self.whose_turn      = old.whose_turn
            self.current_role_num = old.current_role_num
            self.board  = [old.board[i][:] for i in range(3)]
            self.win    = old.win
            self.winner = old.winner

    def __str__(self):
        txt = ''
        for i in range(3):
            for j in range(3):
                txt += int_to_name(self.board[i][j])
                if j < 2:
                    txt += '|'
            if i < 2:
                txt += '\n-----'
            txt += '\n'
        return txt

    def __eq__(self, s):
        return str(self) == str(s)

    def __hash__(self):
        return hash(str(self))

    # -- Win detection --

    def find_any_win(self):
        for role in [X, O]:
            result = (self.any_horiz_win(role) or
                      self.any_vert_win(role)  or
                      self.any_diag_win(role))
            if result:
                return result
        return False

    def check_for_win(self):
        '''Updates self.win and self.winner if a win exists.
        Returns the win tuple or False.'''
        result = self.find_any_win()
        if result:
            (self.win, self.winner) = result
        return result

    def any_horiz_win(self, role):
        for i in range(3):
            for j in range(3):
                if self.board[i][j] != role: break
                if j == 2:
                    return ("Win for " + int_to_name(role) +
                            " in row " + str(i + 1), role)
        return False

    def any_vert_win(self, role):
        for j in range(3):
            for i in range(3):
                if self.board[i][j] != role: break
                if i == 2:
                    return ("Win for " + int_to_name(role) +
                            " in column " + str(j + 1), role)
        return False

    def any_diag_win(self, role):
        for i in range(3):
            if self.board[i][i] != role: break
            if i == 2:
                return ("Win for " + int_to_name(role) +
                        " on main diagonal", role)
        for i in range(3):
            if self.board[2 - i][i] != role: break
            if i == 2:
                return ("Win for " + int_to_name(role) +
                        " on alternate diagonal", role)
        return False

    # -- Board queries --

    def moves_left(self):
        return any(self.board[i][j] == EMPTY
                   for i in range(3) for j in range(3))

    def can_put(self, role, row, col):
        '''Precondition: it must be this role's turn and the cell must be empty.'''
        if self.whose_turn != role:
            return False
        return self.board[row][col] == EMPTY

    # -- Move application --

    def put(self, row, col):
        '''Return the new state resulting from placing the current player's
        mark at (row, col).  Stores a jit_transition message for the engine.'''
        news = TTT_State(old=self)
        news.board[row][col] = self.whose_turn
        news.jit_transition = (int_to_name(self.whose_turn) +
                               " chooses row " + str(row + 1) +
                               " and column " + str(col + 1) + ".")
        _update_turn(news)
        return news

    # -- Goal tests --

    def is_goal(self):
        '''Game ends on a win or a full board.'''
        if self.check_for_win(): return True
        if not self.moves_left(): return True
        return False

    def is_win(self, role_num):
        '''Returns True if the given role has won.'''
        self.check_for_win()
        return self.winner == role_num

    def is_draw(self):
        '''Returns True if the board is full with no winner.'''
        return not self.moves_left() and self.winner == -1

    def goal_message(self):
        self.check_for_win()
        if self.winner != -1:
            return ("The winner is " + int_to_name(self.winner) +
                    ". Thanks for playing Tic-Tac-Toe.")
        return "It's a draw! Thanks for playing Tic-Tac-Toe."

    # -- Display --

    def text_view_for_role(self, role_num):
        '''Returns a textual representation of the board for the given role.'''
        txt = "Current view for " + int_to_name(role_num) + ":\n"
        txt += str(self)
        if self.win == "" and self.moves_left():
            txt += "It's " + int_to_name(self.whose_turn) + "'s turn.\n"
        elif self.winner != -1:
            txt += "Winner is " + int_to_name(self.winner) + "\n"
        else:
            txt += "Game over. It's a draw!\n"
        return txt


# -- Turn-taking helpers (module-level, not part of the public API) --

def _next_player(k):
    return O if k == X else X

def _update_turn(s):
    '''Mutate s to reflect the next player's turn.'''
    s.whose_turn       = _next_player(s.whose_turn)
    s.current_role_num = s.whose_turn


# ---------------------------------------------------------------------------
# OPERATORS
# ---------------------------------------------------------------------------

class TTT_Operator_Set(sz.SZ_Operator_Set):
    '''18 operators: 9 for X (one per cell) and 9 for O.
    Each operator has a precondition (cell empty AND it's this role's turn)
    and a state transition (put the mark, advance the turn).'''

    def __init__(self):
        xops = [
            sz.SZ_Operator(
                name="Place an X in row " + str(row + 1) + ", column " + str(col + 1),
                precond_func=lambda s, r=row, c=col: s.can_put(X, r, c),
                state_xition_func=lambda s, r=row, c=col: s.put(r, c)
            )
            for row in range(3) for col in range(3)
        ]
        oops = [
            sz.SZ_Operator(
                name="Place an O in row " + str(row + 1) + ", column " + str(col + 1),
                precond_func=lambda s, r=row, c=col: s.can_put(O, r, c),
                state_xition_func=lambda s, r=row, c=col: s.put(r, c)
            )
            for row in range(3) for col in range(3)
        ]
        self.operators = xops + oops


# ---------------------------------------------------------------------------
# ROLES
# ---------------------------------------------------------------------------

class TTT_Roles_Spec(sz.SZ_Roles_Spec):
    def __init__(self):
        self.roles = [
            sz.SZ_Role(name='X',        description='Places X marks. Goes first.'),
            sz.SZ_Role(name='O',        description='Places O marks. Goes second.'),
            sz.SZ_Role(name='Observer', description='Watches the game without playing.'),
        ]
        self.min_players_to_start = 2   # Need at least one X and one O.
        self.max_players          = 27  # 1 X + 1 O + up to 25 observers.


# ---------------------------------------------------------------------------
# FORMULATION
# ---------------------------------------------------------------------------

class TTT_Formulation(sz.SZ_Formulation):
    '''Top-level formulation object for Tic-Tac-Toe.
    The game engine instantiates this class and then calls
    initialize_problem() to create the initial state.'''

    def __init__(self):
        self.metadata    = TTT_Metadata()
        self.operators   = TTT_Operator_Set()
        self.roles_spec  = TTT_Roles_Spec()
        self.common_data = sz.SZ_Common_Data()

    def initialize_problem(self, config={}):
        '''Create and store the initial game state.
        Returns the initial state for convenience.'''
        initial_state = TTT_State()
        self.instance_data = sz.SZ_Problem_Instance_Data(
            d={'initial_state': initial_state}
        )
        return initial_state


# ---------------------------------------------------------------------------
# MODULE-LEVEL ENTRY POINT
# Game engines should import this module and use TTT (the formulation
# instance) rather than instantiating TTT_Formulation themselves.
# ---------------------------------------------------------------------------

TTT = TTT_Formulation()

# ---------------------------------------------------------------------------
# SELF-TEST  (run with: python Tic_Tac_Toe_SZ6.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Tic-Tac-Toe SZ6 self-test ===")
    s = TTT.initialize_problem()
    print("Initial state:")
    print(s)
    ops = TTT.operators.operators
    print(f"Number of operators: {len(ops)}")

    # Apply a sequence: X center, O top-left, X top-right,
    #                   O bottom-left, X bottom-right (X wins diagonal? No.)
    # Let's try a quick win: X plays (0,0), (0,1), (0,2) -> row win.
    moves = [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2)]  # X wins row 1
    for (row, col) in moves:
        role = s.whose_turn
        # Find the applicable operator for (role, row, col)
        op = None
        for o in ops:
            if o.precond_func(s):
                # Match by name
                target = ("Place an X" if role == X else "Place an O") + \
                         f" in row {row+1}, column {col+1}"
                if o.name == target:
                    op = o
                    break
        if op is None:
            print(f"No applicable operator found for role={role}, ({row},{col})")
            break
        s = op.state_xition_func(s)
        print(f"After move ({row+1},{col+1}):")
        print(s)
        if s.is_goal():
            print(s.goal_message())
            break
