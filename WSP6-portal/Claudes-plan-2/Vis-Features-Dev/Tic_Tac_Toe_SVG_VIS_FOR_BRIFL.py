# Author:  S. Tanimoto
# Purpose: Provide the player's "visualizations" of the game
# of Tic-Tac-Toe in the web browser.
# Created: July 8, 2025 for Flash_SOLUZION5.

import svgwrite
import Tic_Tac_Toe as prob

DEBUG = False
GRAPHIC_W = 800 # Width of State display rectangular area.
GRAPHIC_H = 600
HALF_GW = GRAPHIC_W / 2
BOARD_W = 300 # Width of Tic-Tac-Toe board 
HALF_BW = BOARD_W/2
SQW = BOARD_W/3
HALF_SQW = SQW/2
BOARD_H = BOARD_W
ROLE_COLORS = [
    "rgb(64, 0, 128)",    # X is violet
    "rgb(200, 150, 0)",   # O is gold
    "rgb(200, 200, 200)"] # EMPTY is light gray
GRID_LINE_COLOR = "dark gray" # charcoal
FONT_COLOR = "peacock", # peacock
LARGE_FS = "36"  # Font size for X and O marks.
MEDIUM_FS = "18" # Font size for whose turn.

session = None # Will be assigned during a call to render_state.
def render_state(s, roles=None):
    global session
    if DEBUG: print("In Tic_Tac_Toe_VIS_FOR_BRIFL.py, roles = "+str(roles))

    # Define some alt_text to help with accessibility of the state display.
    alt_text = "This is a Tic-Tac-Toe state display.\n"

    session = prob.SESSION # Need HOST and PORT info for accessing images.
    # Note that SESSION is not part of the formulation but a variable written 
    # by ZZ005_02 into the PROBLEM name space.
    #if DEBUG: print("In render_state, session is ", session)
    dwg = svgwrite.Drawing(filename = "test-svgwrite.svg",
                           id = "state_svg",  # Must match the id in the html template.
                           size = (str(GRAPHIC_W)+"px", str(GRAPHIC_H)+"px"),
                           debug=True)

    dwg.add(dwg.rect(insert = (0,0),
                     size = (str(GRAPHIC_W)+"px", str(GRAPHIC_H)+"px"),
                     stroke_width = "1",
                     stroke = "pink",
                     fill = "green"))

    if roles==None or roles==[]:
      label = "This player doesn't have any role in the game."
      alt_text += label + "\n"
      x = 0; y = 50
      dwg.add(dwg.text(label, insert = (x+HALF_GW, y),
                     text_anchor="middle",
                     font_size=MEDIUM_FS,
                     fill = "red"))
    else:
      yc = 100
      # Instead of rendering all this player's roles, render just
      # the vis for the role that is currently up or if none of
      # this player's roles are up, an arbitrary role belonging
      # this this player.
      # This info should be in the state.
      if s.current_role_num in roles:
          role = s.current_role_num
      else: role = roles[0]  # This player's first role.
      x = (GRAPHIC_W - BOARD_W)/2
      y = 100
      dwg.add(dwg.rect(insert = (x,y),
                     size = (str(BOARD_W)+"px", str(BOARD_H)+"px"),
                     stroke_width = "1",
                     stroke = "black",
                     fill = "gray"))
      dwg.add(dwg.line((x, y+SQW), (x+BOARD_W, y+SQW), stroke='black', stroke_width=3))
      dwg.add(dwg.line((x, y+2*SQW), (x+BOARD_W, y+2*SQW), stroke='black', stroke_width=3))
      dwg.add(dwg.line((x+SQW, y), (x+SQW, y+BOARD_H), stroke='black', stroke_width=3))
      dwg.add(dwg.line((x+2*SQW, y), (x+2*SQW, y+BOARD_H), stroke='black', stroke_width=3))
      if DEBUG: print("Rendering for role "+prob.int_to_name(role))

      label = "This view is for the role of "+prob.ROLES[role]["name"]  # Include possibility of "Observer" role.
      alt_text = label + ".\n"
      x = HALF_GW; y = 50 
      dwg.add(dwg.text(label, insert = (x, y),
                     text_anchor="middle",
                     font_size=MEDIUM_FS,
                     stroke = "black",
                     fill = "blue"))
      x = (GRAPHIC_W - BOARD_W)/2
      y = 100 + 9 # Adjustment to get character centered vertically in grid cell.
      board = s.board
      for i in range(3):
          for j in range(3):
             mark = board[i][j]
             label = prob.int_to_name(mark)
             xc = x + HALF_SQW + j*SQW
             yc = y + HALF_SQW + i*SQW
             dwg.add(dwg.text(label, insert = (xc, yc),
                     text_anchor="middle",
                     font_size=LARGE_FS,
                     stroke = "black",
                     fill = "black"))
             if mark != prob.EMPTY:
               alt_text += label + " in row "+str(i+1)+", column "+str(j+1)+"; \n"
      who = prob.int_to_name(s.current_role_num)
      if s.moves_left():
         label = "It is "+who+"'s turn."
      else:
         label = "No more moves. The game is a draw."
      xc = HALF_GW; 
      yc = 500
      dwg.add(
         dwg.text(label, insert = (xc, yc),
                  text_anchor="middle",
                  font_size=MEDIUM_FS,
                  stroke = "black",
                  fill = "blue"))
      alt_text += label
    dwg.add(svgwrite.base.Title(alt_text)) # Register alt_text as SVG title.
    svg_string = dwg.tostring()
    return svg_string



