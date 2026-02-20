'''Tic_Tac_Toe_SZ6_with_vis.py

Tic-Tac-Toe formulation for SOLUZION6, with SVG visualization.

This is Tic_Tac_Toe_SZ6.py extended by two lines:
  1. Import of the companion visualization module (Tic_Tac_Toe_WSZ6_VIS).
  2. self.vis_module set on the formulation, so the WSZ6 game runner
     knows to call vis_module.render_state(state) after each move.

The original Tic_Tac_Toe_SZ6.py is unchanged and continues to work
as a text-only version (slug: tic-tac-toe).
This file installs under slug: tic-tac-toe-vis.
'''

SOLUZION_VERSION = 6

import soluzion6_02 as sz
import Tic_Tac_Toe_WSZ6_VIS as _ttt_vis   # ← vis module import (M1 addition)

# ---------------------------------------------------------------------------
# GLOBAL CONSTANTS
# ---------------------------------------------------------------------------

EMPTY = 2
X     = 0
O     = 1
NAMES = ["X", "O", " "]

def int_to_name(i):
    return NAMES[i]

# ---------------------------------------------------------------------------
# METADATA
# ---------------------------------------------------------------------------

class TTT_Metadata(sz.SZ_Metadata):
    def __init__(self):
        self.name             = "Tic-Tac-Toe (Visual)"
        self.soluzion_version = SOLUZION_VERSION
        self.problem_version  = "1.0"
        self.authors          = ['S. Tanimoto']
        self.creation_date    = "2026-Feb"
        self.brief_desc = (
            "Tic-Tac-Toe with SVG board visualization. "
            "Identical rules to the standard version, but the board is "
            "rendered as a graphic instead of ASCII text. "
            "Demonstrates the WSZ6 M1 visualization feature."
        )

# ---------------------------------------------------------------------------
# STATE
# ---------------------------------------------------------------------------

class TTT_State(sz.SZ_State):
    '''Represents one board position in a Tic-Tac-Toe game.'''

    def __init__(self, old=None):
        if old is None:
            self.whose_turn      = X
            self.current_role_num = X
            self.board = [[EMPTY, EMPTY, EMPTY],
                          [EMPTY, EMPTY, EMPTY],
                          [EMPTY, EMPTY, EMPTY]]
            self.win    = ""
            self.winner = -1
        else:
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

    def find_any_win(self):
        for role in [X, O]:
            result = (self.any_horiz_win(role) or
                      self.any_vert_win(role)  or
                      self.any_diag_win(role))
            if result:
                return result
        return False

    def check_for_win(self):
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

    def moves_left(self):
        return any(self.board[i][j] == EMPTY
                   for i in range(3) for j in range(3))

    def can_put(self, role, row, col):
        if self.whose_turn != role:
            return False
        return self.board[row][col] == EMPTY

    def put(self, row, col):
        news = TTT_State(old=self)
        news.board[row][col] = self.whose_turn
        news.jit_transition = (int_to_name(self.whose_turn) +
                               " chooses row " + str(row + 1) +
                               " and column " + str(col + 1) + ".")
        _update_turn(news)
        return news

    def is_goal(self):
        if self.check_for_win(): return True
        if not self.moves_left(): return True
        return False

    def is_win(self, role_num):
        self.check_for_win()
        return self.winner == role_num

    def is_draw(self):
        return not self.moves_left() and self.winner == -1

    def goal_message(self):
        self.check_for_win()
        if self.winner != -1:
            return ("The winner is " + int_to_name(self.winner) +
                    ". Thanks for playing Tic-Tac-Toe.")
        return "It's a draw! Thanks for playing Tic-Tac-Toe."

    def text_view_for_role(self, role_num):
        txt = "Current view for " + int_to_name(role_num) + ":\n"
        txt += str(self)
        if self.win == "" and self.moves_left():
            txt += "It's " + int_to_name(self.whose_turn) + "'s turn.\n"
        elif self.winner != -1:
            txt += "Winner is " + int_to_name(self.winner) + "\n"
        else:
            txt += "Game over. It's a draw!\n"
        return txt


def _next_player(k):
    return O if k == X else X

def _update_turn(s):
    s.whose_turn       = _next_player(s.whose_turn)
    s.current_role_num = s.whose_turn


# ---------------------------------------------------------------------------
# OPERATORS
# ---------------------------------------------------------------------------

class TTT_Operator_Set(sz.SZ_Operator_Set):
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
        self.min_players_to_start = 2
        self.max_players          = 27


# ---------------------------------------------------------------------------
# FORMULATION
# ---------------------------------------------------------------------------

class TTT_Formulation(sz.SZ_Formulation):
    def __init__(self):
        self.metadata    = TTT_Metadata()
        self.operators   = TTT_Operator_Set()
        self.roles_spec  = TTT_Roles_Spec()
        self.common_data = sz.SZ_Common_Data()
        self.vis_module  = _ttt_vis          # ← vis module reference (M1 addition)

    def initialize_problem(self, config={}):
        initial_state = TTT_State()
        self.instance_data = sz.SZ_Problem_Instance_Data(
            d={'initial_state': initial_state}
        )
        return initial_state


# ---------------------------------------------------------------------------
# MODULE-LEVEL ENTRY POINT
# ---------------------------------------------------------------------------

TTT = TTT_Formulation()
