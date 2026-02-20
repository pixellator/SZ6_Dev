'''Tic_Tac_Toe.py,

This version for 2025 works with
the new Roles-capable Text_SOLUZION5 client and
the Flash_SOLUZION5 online system.
It can serve as an example to follow by students
implementing new multiplayer games.
  
'''
#<METADATA>
SOLUZION_VERSION = "5.0"
PROBLEM_NAME = "Tic-Tac-Toe"
PROBLEM_VERSION = "1.0"
PROBLEM_AUTHORS = ['S. Tanimoto']
PROBLEM_CREATION_DATE = "15-July-2025"
# The following field is used when explaining
# the game to users, via either the Text_SOLUZION_Client
# or the web-based Flask_SOLUION5 system.
PROBLEM_DESC=\
 '''Tic-Tac-Toe is a traditional game played on a 3x3 board ("grid") by 
 two players: X and O.  They take turns, with X playing first. On
 the first turn, X can place an "X" mark on the grid in any of the 9
 positions. After that, O places and "O" in any of the remaining 8
 positions, etc.  The first player to get three of their marks in
 a line (horizontally, vertically, or diagonally) wins. If the grid
 is filled, but there is no winner, the game is a draw.
'''
#</METADATA>

#<COMMON_DATA>
EMPTY = 2 # Used to represent a black cell in the grid.
X = 0 # Used both for player role numbers and for marks in the grid.
O = 1
NAMES = ["X", "O", " "] # Used to translate an int to a string.
#</COMMON_DATA>

#<COMMON_CODE>
DEBUG=True
from soluzion5 import Basic_State, \
  Basic_Operator as Operator, ROLES_List, add_to_next_transition
import Select_Roles as sr

def int_to_name(i):
  return NAMES[i]


class State(Basic_State):
  def __init__(self, old=None):
    if old == None:
      # Make the initial state
      self.whose_turn = X
      self.current_role_num = X # Although role_num is the same
      # in this game as whose_turn, the SOLUZION software 
      # needs both to be specified, in general.
      self.current_role = int_to_name(self.current_role_num)
      self.board = [[EMPTY, EMPTY, EMPTY],\
                    [EMPTY, EMPTY, EMPTY],\
                    [EMPTY, EMPTY, EMPTY]]
      self.win = "" # String that describes a win, if any.
      self.winner = -1 # Integer giving role number of winner.
      # The initial state is now ready.
    else:
      # Here we handle the case where an old state was passed in;
      # we'll make the new state be a deep copy of the old, and
      # it can then be mutated by the operator that called for
      # this new instance to be created.
      self.whose_turn = old.whose_turn
      self.current_role = old.current_role
      self.current_role_num = old.current_role_num
      self.board = [old.board[i][:] for i in range(3)]
      self.win = old.win
      self.winner = old.winner
      
  def __str__(self):
    # Produces a simple textual description of a state.
    # Doesn't mention any win that might exist.
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
    return self.__str__() == s.__str__()

  def __hash__(self):
    return (self.__str__()).__hash__()
  
  def find_any_win(self):
    for role in [X, O]:
       hwin = self.any_horiz_win(role)
       if hwin: return hwin
       vwin = self.any_vert_win(role)
       if vwin: return vwin
       dwin = self.any_diag_win(role)
       if dwin: return dwin
    return False
  
  def check_for_win(self):
    any = self.find_any_win()
    if any: 
      (self.win, self.winner) = any
      #print("in check_for_win, we found: ", self.win)
    else:
      pass  # self.win = None
    return any
  
  def any_horiz_win(self, role):
    for i in range(3):
      for j in range(3):
        if self.board[i][j] != role: break
        if j==2:
          return(("Win for "+int_to_name(role)+\
                  " in row "+str(i+1), role))
    return False
  
  def any_vert_win(self, role):
    for j in range(3):
      for i in range(3):
        if self.board[i][j] != role: break
        if i==2:
          return(("Win for "+int_to_name(role)+\
                  " in column "+str(j+1), role))
    return False
  
  def any_diag_win(self, role):
    for i in range(3):
        if self.board[i][i] != role: break
        if i==2:
          return(("Win for "+int_to_name(role)+\
                  " on main diagonal", role))
    for i in range(3):
        if self.board[2-i][i] != role: break
        if i==2:
          return(("Win for "+int_to_name(role)+\
                  " on alternate diagonal", role))
    return False
  
  def moves_left(self):
    n_empty = 0
    for i in range(3): 
      for j in range(3):
        if self.board[i][j]==EMPTY:
          n_empty += 1
    if n_empty > 0: return True
    else: return False

  def can_put(self, role, row, column):
    if self.whose_turn != role: return False
    return self.board[row][column]==EMPTY
  
  def put(self, row, column):
    # Perform the current player's move.
    news = State(self)
    add_to_next_transition(int_to_name(self.whose_turn)+\
      " chooses row "+str(row+1)+" and column "+str(column+1)+".", news)
    role = self.whose_turn
    news.board[row][column] = role
    update_turn(news)
    return news
  
  def is_goal(self):
    # This method is used by the SOLUZION system to test if
    # a final state of a game or problem has been reached.
    # In Tic-Tac-Toe, it signals thatt the game is over,
    # no matter whether it's a win or a draw.
    any_win = self.check_for_win()
    if any_win: return True  # Win
    if self.moves_left() == 0: return True  # Draw
    return False # Neither win nor draw.

  def goal_message(self):
    # Needed by SOLUZION.
    if self.win != "":
       return "The winner is "+int_to_name(self.winner)+\
        ". Thanks for playing Tic-Tac-Toe."

  def text_view_for_role(self, role_num):
    # Return a textual rep. of what the player for
    # this role should see in the current state.
    # "View for (role):"
    # Includes information about any win.
    role_name = int_to_name(role_num)
    txt = "Current view for " + role_name + ":\n"
    txt += str(self)
    if self.win == "" and self.moves_left():
      txt += "It's "+int_to_name(self.whose_turn)+"'s turn.\n"
    elif self.winner != -1:
      txt += "Winner is "+int_to_name(self.winner)
    elif not self.moves_left():
      txt += "Game over. It's a draw!\n"
    return txt

SESSION = None

# The function next_player(k, inactive_ok=False) returns
# the number of the player after player k.
def next_player(k):
  if k==X: return O
  else: return X

def update_turn(news):
  # For use after the new state has been created.
  current = news.whose_turn
  updated = next_player(current)
  news.whose_turn = updated
  news.current_role_num = updated
  news.current_role = NAMES[updated]
  # No need to return anything. New state has been mutated.
    
#------------------
#<OPERATORS>
# Here the use of a list comprehension lets us
# create all 9 of X's operators at once.
# The lambda expressions capture the row and
# column values in each operator, but produce
# functions of the state that serve as
# precondition and state-transformation for
# each operator.
XOPS = [Operator("Place an X in row "+str(row+1)+\
                 ", column "+str(column+1),\
  lambda s, r=row, c=column: s.can_put(X, r, c),
  lambda s, r=row, c=column: s.put(r, c))\
      for row in range(3) for column in range(3)]

# Let's do the same for O's operators.
OOPS = [Operator("Place an O in row "+str(row+1)+\
                 ", column "+str(column+1),\
  lambda s, r=row, c=column: s.can_put(O, r, c),
  lambda s, r=row, c=column: s.put(r, c))\
      for row in range(3) for column in range(3)]

OPERATORS = XOPS + OOPS
#</OPERATORS>

# A function to facilitate role-specific visualizations...
def is_user_in_role(role_num):
  username = SESSION['USERNAME']
  rm = SESSION['ROLES_MEMBERSHIP']
  if rm==None: return False
  users_in_role = rm[role_num]
  return username in users_in_role

def get_session():
  return SESSION

#</COMMON_CODE>

#<INITIAL_STATE>
def create_initial_state():
  return State()
#</INITIAL_STATE>

#<ROLES>
ROLES = ROLES_List([ {'name': 'X', 'min': 1, 'max': 1},
          {'name': 'O', 'min': 1, 'max': 1},
          {'name': 'Observer', 'min': 0, 'max': 25}])
ROLES.min_num_of_roles_to_play = 2
ROLES.max_num_of_roles_to_play = 25
#</ROLES>

#<STATE_VIS>
BRIFL_SVG = True
    # The program:
    # Tic_Tac_Toe_SVG_VIS_FOR_BRIFL.py is available
def use_BRIFL_SVG():
  global render_state
  from  Tic_Tac_Toe_SVG_VIS_FOR_BRIFL import render_state
DEBUG_VIS=True # Web_SOLUZION5 should auto-launch browser tabs for all roles, and show initial state with automatic "player" logins.
#</STATE_VIS>

