'''OCCLUEdo_SZ6.py

OCCLUEdo: An Occluded Game of Clue — SOLUZION6 formulation.

Adapted from OCCLUEdo_web.py (SOLUZION5 / Flask_SOLUZION5).
A simplified, board-free Clue variant for 2-6 players plus observers.
Players move between rooms, make suggestions about the murder, and try to
identify the murderer, weapon, and crime room before anyone else.

Key SZ6 changes from SZ5:
  - Class-based structure using soluzion6_02.py base classes.
  - No Select_Roles module; active roles tracked as state.active_roles.
  - initialize_problem(config) replaces create_initial_state() + deal().
  - jit_transition replaces add_to_next_transition().
  - Bug fixes:
      * cannot_disprove / can_respond_sorry checked suspect_card twice;
        now correctly checks weapon_card.
      * deal() global declaration now correctly names MURDERER.
      * add_weapon_to_accusation now appends the complete accusation.

Operator index table (must match exactly; used by VIS):
  0-17  go_ops (places 6-23)
  18    op_start_suggestion
  19-24 suspect_ops (6 suspects)
  25-30 weapon_ops (6 weapons)
  31-39 response_ops (card slots 0-8)
  40    op_respond_sorry
  41    op_acknowledge
  42    op_start_accusation
  43-51 add_room_to_accusation (9 rooms)
  52-57 add_player_to_accusation (6 suspects)
  58-63 add_weapon_to_accusation (6 weapons)
  64    op_ask_win
'''

SOLUZION_VERSION = 6

import random
import soluzion6_02 as sz
import OCCLUEdo_WSZ6_VIS as _oc_vis

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

MISS_SCARLET    = 0
MR_GREEN        = 1
COLONEL_MUSTARD = 2
PROFESSOR_PLUM  = 3
MRS_PEACOCK     = 4
MRS_WHITE       = 5
OBSERVER        = 6

NAMES = ['Miss Scarlet', 'Mr. Green', 'Colonel Mustard',
         'Prof. Plum', 'Mrs. Peacock', 'Mrs. White', 'Observer']
WEAPONS = ['Candlestick', 'Knife', 'Lead Pipe', 'Revolver', 'Rope', 'Wrench']
ROOMS   = ['Lounge', 'Dining Room', 'Kitchen', 'Ballroom',
           'Conservatory', 'Billiard Room', 'Library', 'Study', 'Hall']

LOBBIES          = [r + "'s Lobby" for r in ROOMS]
PLAYER_STARTS    = [p + "'s Start" for p in NAMES[:6]]
POSSIBLE_PLAYER_SPOTS = PLAYER_STARTS + LOBBIES + ROOMS
# Indices: 0-5 = starting places, 6-14 = lobbies, 15-23 = rooms

ROLE_COLORS = [
    '#c8102e',   # Miss Scarlet
    '#00843d',   # Mr. Green
    '#d4a017',   # Colonel Mustard
    '#7b2d8b',   # Prof. Plum
    '#1f5fa6',   # Mrs. Peacock
    '#d8d8d8',   # Mrs. White
    '#888888',   # Observer
]


def spot_is_lobby(i):
    return 6 <= i <= 14

def spot_is_room(i):
    return i >= 15


# ---------------------------------------------------------------------------
# MODULE-LEVEL GAME INSTANCE DATA  (set by deal() inside initialize_problem)
# ---------------------------------------------------------------------------
# Single-session limitation: if two OCCLUEdo sessions run in the same process
# they will share these globals.  Noted as a known limitation in the plan.

MURDERER     = None   # int 0-5 — character index
CRIME_ROOM   = None   # int 0-8 — room index
CRIME_WEAPON = None   # int 0-5 — weapon index
PLAYER_HAND  = None   # list[6] of lists of (category, index) tuples


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def card_name(card):
    cat, num = card
    if cat == 'r': return ROOMS[num]
    if cat == 'p': return NAMES[num]
    if cat == 'w': return WEAPONS[num]
    return 'Unknown card'

def hand_to_string(hand):
    return '[' + ', '.join(card_name(c) for c in hand) + ']'

def int_to_name(i):
    return NAMES[i]

def _shuffle(lst):
    lc = lst[:]
    result = []
    while lc:
        k = random.randint(0, len(lc) - 1)
        result.append(lc.pop(k))
    return result

def deal(active_roles):
    '''Set up a new game: choose the crime solution and deal remaining cards.'''
    global MURDERER, CRIME_ROOM, CRIME_WEAPON, PLAYER_HAND

    MURDERER     = random.choice(range(6))
    CRIME_ROOM   = random.choice(range(9))
    CRIME_WEAPON = random.choice(range(6))

    non_murderers = [('p', i) for i in range(6) if i != MURDERER]
    weapons_left  = [('w', i) for i in range(6) if i != CRIME_WEAPON]
    rooms_left    = [('r', i) for i in range(9) if i != CRIME_ROOM]
    deck = _shuffle(non_murderers + weapons_left + rooms_left)

    PLAYER_HAND = [[] for _ in range(6)]
    n = len(active_roles)
    for i, card in enumerate(deck):
        recipient = active_roles[i % n]
        PLAYER_HAND[recipient] = PLAYER_HAND[recipient] + [card]


def next_active_role(k, state, inactive_ok=False):
    '''Return the role number of the next active player after role k.'''
    roles = state.active_roles
    if k not in roles:
        start_idx = 0
    else:
        start_idx = roles.index(k)
    n = len(roles)
    for offset in range(1, n + 1):
        candidate = roles[(start_idx + offset) % n]
        if inactive_ok:
            return candidate
        if candidate not in state.inactive_players:
            return candidate
    raise Exception("No active players remain in next_active_role().")


def format_suggestion(sug):
    if not sug:
        return '(no suggestion)'
    room_no, suspect_no, weapon_no = sug
    room    = ROOMS[room_no]
    suspect = NAMES[suspect_no] if suspect_no >= 0 else 'unnamed'
    weapon  = WEAPONS[weapon_no] if weapon_no >= 0 else 'unnamed'
    return f'{suspect} in the {room} with the {weapon}'

def format_one_accusation(acc):
    if not acc:
        return '(no accusation)'
    room_no, suspect_no, weapon_no, accuser = acc
    room    = ROOMS[room_no]    if room_no >= 0 else 'unnamed room'
    suspect = NAMES[suspect_no] if suspect_no >= 0 else 'unnamed'
    weapon  = WEAPONS[weapon_no] if weapon_no >= 0 else 'unnamed'
    return (f'{suspect} in the {room} with the {weapon} '
            f'(accused by {NAMES[accuser]})')


# ---------------------------------------------------------------------------
# STATE
# ---------------------------------------------------------------------------

class OCCLUEdo_State(sz.SZ_State):

    def __init__(self, old=None, active_roles=None):
        if old is None:
            self.active_roles       = active_roles or [0, 1]
            self.whose_turn         = self.active_roles[0]
            self.current_role_num   = self.whose_turn
            self.whose_subturn      = -1
            self.suggestion         = None
            self.suggestion_phase   = 0
            self.refutation_card    = None
            self.current_accusation = []
            self.accusations        = []
            self.accusation_phase   = 0
            self.inactive_players   = []
            self.recent_arrivals    = []
            self.player_places      = list(range(6))
            self.winner             = None
        else:
            self.active_roles       = old.active_roles[:]
            self.whose_turn         = old.whose_turn
            self.current_role_num   = old.current_role_num
            self.whose_subturn      = old.whose_subturn
            self.suggestion         = old.suggestion[:] if old.suggestion else None
            self.suggestion_phase   = old.suggestion_phase
            self.refutation_card    = old.refutation_card
            self.current_accusation = old.current_accusation[:]
            self.accusations        = [a[:] for a in old.accusations]
            self.accusation_phase   = old.accusation_phase
            self.inactive_players   = old.inactive_players[:]
            self.recent_arrivals    = old.recent_arrivals[:]
            self.player_places      = old.player_places[:]
            self.winner             = old.winner

    def __str__(self):
        if self.winner is not None:
            return f'The game is over. {NAMES[self.winner]} won.\n'
        txt  = self._format_player_places()
        txt += f"It's {NAMES[self.whose_turn]}'s turn.\n"
        if self.suggestion is not None:
            txt += f'Suggestion: {format_suggestion(self.suggestion)}.\n'
        if self.whose_subturn >= 0 and self.suggestion_phase == 4:
            txt += f'Waiting for {NAMES[self.whose_subturn]} to respond.\n'
        elif self.suggestion_phase == 5:
            if self.refutation_card is not None:
                txt += (f'Refutation: {card_name(self.refutation_card)} '
                        f'shown by {NAMES[self.whose_subturn]}.\n')
            else:
                txt += 'Nobody could disprove the suggestion.\n'
        if self.current_accusation:
            txt += (f'Current accusation: '
                    f'{format_one_accusation(self.current_accusation)}.\n')
        if self.inactive_players:
            txt += (f'Inactive: '
                    f'{", ".join(NAMES[r] for r in self.inactive_players)}.\n')
        return txt

    def __eq__(self, s):
        return str(self) == str(s)

    def __hash__(self):
        return hash(str(self))

    def _format_player_places(self):
        txt = ''
        for rn in self.active_roles:
            place_no = self.player_places[rn]
            place    = POSSIBLE_PLAYER_SPOTS[place_no]
            prefix   = 'the ' if place_no > 5 else ''
            txt += f'{NAMES[rn]} is in {prefix}{place}; '
        return txt + '\n'

    def is_goal(self):
        return self.winner is not None

    def goal_message(self):
        return f'{NAMES[self.winner]} wins!  Thanks for playing OCCLUEdo.'


# ---------------------------------------------------------------------------
# PRECONDITION AND TRANSITION FUNCTIONS
# ---------------------------------------------------------------------------

def can_go(state, place):
    if state.suggestion_phase > 0: return False
    if state.accusation_phase  > 0: return False
    role_num      = state.current_role_num
    if role_num >= 6: return False          # Observer cannot move
    current_place = state.player_places[role_num]
    if current_place == place: return False

    if spot_is_lobby(place):
        # Any player already there? (includes starting places check)
        return place not in state.player_places

    if spot_is_room(place):
        # Must approach from the adjacent lobby
        if current_place == place - 9:
            return True
        # Secret passages
        if current_place == 22 and place == 17: return True  # Study → Kitchen
        if current_place == 17 and place == 22: return True  # Kitchen → Study
        if current_place == 15 and place == 19: return True  # Lounge → Conservatory
        if current_place == 19 and place == 15: return True  # Conservatory → Lounge

    return False


def go(state, place):
    ns  = OCCLUEdo_State(old=state)
    who = state.whose_turn
    ns.player_places[who] = place
    ns.jit_transition = (
        f'{NAMES[who]} moves to {POSSIBLE_PLAYER_SPOTS[place]}.'
    )
    if who in ns.recent_arrivals:
        ns.recent_arrivals.remove(who)
    if spot_is_room(place):
        # Entering a room automatically starts a suggestion
        ns.suggestion_phase = 2
        ns.suggestion       = [place - 15, -1, -1]
    else:
        # Moving to a lobby ends the turn
        ns.whose_turn       = next_active_role(ns.whose_turn, state,
                                               inactive_ok=False)
        ns.current_role_num = ns.whose_turn
    return ns


def can_start_suggestion(state):
    '''Available when the player was summoned to a room and it is now their turn.'''
    if state.suggestion_phase > 0: return False
    if state.accusation_phase  > 0: return False
    role_num = state.current_role_num
    if role_num not in state.recent_arrivals: return False
    if not spot_is_room(state.player_places[role_num]): return False
    return True

def start_suggestion(state):
    ns  = OCCLUEdo_State(old=state)
    who = ns.whose_turn
    if who in ns.recent_arrivals:
        ns.recent_arrivals.remove(who)
    location  = ns.player_places[who]
    sugg_room = location - 15
    ns.suggestion_phase = 2
    ns.suggestion       = [sugg_room, -1, -1]
    ns.jit_transition   = f'A suggestion is starting in the {ROOMS[sugg_room]}.'
    return ns


def can_suggest_suspect(state, suspect):
    return state.suggestion_phase == 2

def suggest_suspect(state, suspect):
    ns  = OCCLUEdo_State(old=state)
    ns.suggestion[1]    = suspect
    ns.suggestion_phase = 3
    # Summon the suspect to the suggested room
    room      = ns.suggestion[0]
    old_place = ns.player_places[suspect]
    new_place = room + 15
    if old_place != new_place:
        ns.recent_arrivals.append(suspect)
        ns.player_places[suspect] = new_place
    ns.jit_transition = (
        f'{NAMES[state.current_role_num]} suggests the murderer '
        f'is {NAMES[suspect]}.'
    )
    return ns


def can_suggest_weapon(state, weapon):
    return state.suggestion_phase == 3

def suggest_weapon(state, weapon):
    ns                  = OCCLUEdo_State(old=state)
    ns.suggestion[2]    = weapon
    ns.suggestion_phase = 4
    # Start the refutation rotation at the player after the suggester
    ns.whose_subturn    = next_active_role(ns.whose_turn, ns, inactive_ok=True)
    ns.current_role_num = ns.whose_subturn
    ns.jit_transition   = (
        f'{NAMES[state.current_role_num]} suggests the weapon '
        f'is the {WEAPONS[weapon]}.'
    )
    return ns


def can_respond(state, card_no):
    '''Can the current subturn player show their card_no-th hand card to refute?'''
    if state.suggestion_phase != 4: return False
    role_num = state.current_role_num
    hand     = (PLAYER_HAND[role_num] if PLAYER_HAND and role_num < 6 else [])
    if card_no >= len(hand): return False
    card = hand[card_no]
    sug  = state.suggestion
    if card[0] == 'r' and card[1] == sug[0]: return True
    if card[0] == 'p' and card[1] == sug[1]: return True
    if card[0] == 'w' and card[1] == sug[2]: return True
    return False

def respond(state, card_no):
    ns   = OCCLUEdo_State(old=state)
    hand = (PLAYER_HAND[state.whose_subturn]
            if PLAYER_HAND and state.whose_subturn < 6 else [])
    evidence            = hand[card_no]
    ns.refutation_card  = evidence
    ns.suggestion_phase = 5
    ns.current_role_num = ns.whose_turn   # suggester acknowledges next
    ns.jit_transition   = (
        f'The suggestion by {NAMES[state.whose_turn]} has been disproved '
        f'by {NAMES[state.whose_subturn]}.'
    )
    return ns


def can_respond_sorry(state):
    '''True if it is the subturn player's turn and NONE of their cards refute.'''
    if state.suggestion_phase != 4: return False
    role_num = state.current_role_num
    hand     = (PLAYER_HAND[role_num] if PLAYER_HAND and role_num < 6 else [])
    sug      = state.suggestion
    for card in hand:
        if card[0] == 'r' and card[1] == sug[0]: return False
        if card[0] == 'p' and card[1] == sug[1]: return False
        if card[0] == 'w' and card[1] == sug[2]: return False   # bug-fixed from SZ5
    return True

def respond_sorry(state):
    ns           = OCCLUEdo_State(old=state)
    prev_subturn = state.whose_subturn
    next_resp    = next_active_role(prev_subturn, ns, inactive_ok=True)
    base_msg     = f'{NAMES[prev_subturn]} cannot disprove the suggestion.'
    if next_resp == state.whose_turn:
        # Rotation complete — nobody could refute
        ns.current_role_num = ns.whose_turn
        ns.suggestion_phase = 5
        ns.suggestion       = None
        ns.jit_transition   = base_msg + '\nNobody could disprove the suggestion!'
    else:
        ns.whose_subturn    = next_resp
        ns.current_role_num = next_resp
        ns.jit_transition   = base_msg
    return ns


def can_acknowledge(state):
    return state.suggestion_phase == 5

def acknowledge(state):
    ns                  = OCCLUEdo_State(old=state)
    ns.jit_transition   = (
        f'{NAMES[state.current_role_num]} acknowledges the result.'
    )
    ns.whose_turn       = next_active_role(ns.whose_turn, state,
                                           inactive_ok=False)
    ns.current_role_num = ns.whose_turn
    ns.suggestion       = None
    ns.refutation_card  = None
    ns.suggestion_phase = 0
    return ns


def can_start_accusation(state):
    if state.suggestion_phase > 0: return False
    if state.accusation_phase  > 0: return False
    return True

def start_accusation(state):
    ns                    = OCCLUEdo_State(old=state)
    ns.accusation_phase   = 1
    ns.current_accusation = [-1, -1, -1, state.whose_turn]
    ns.jit_transition     = f'{NAMES[state.whose_turn]} is making an accusation!'
    return ns


def can_add_room_to_accusation(state, room):
    return state.accusation_phase == 1

def add_room_to_accusation(state, room):
    ns                       = OCCLUEdo_State(old=state)
    ns.accusation_phase      = 2
    ns.current_accusation[0] = room
    ns.jit_transition        = (
        f'{NAMES[state.whose_turn]} names the room: {ROOMS[room]}.'
    )
    return ns


def can_add_player_to_accusation(state, player):
    return state.accusation_phase == 2

def add_player_to_accusation(state, player):
    ns                       = OCCLUEdo_State(old=state)
    ns.accusation_phase      = 3
    ns.current_accusation[1] = player
    ns.jit_transition        = (
        f'{NAMES[state.whose_turn]} accuses {NAMES[player]}.'
    )
    return ns


def can_add_weapon_to_accusation(state, weapon):
    return state.accusation_phase == 3

def add_weapon_to_accusation(state, weapon):
    ns                       = OCCLUEdo_State(old=state)
    ns.accusation_phase      = 4
    ns.current_accusation[2] = weapon
    # Record the complete accusation (bug-fixed from SZ5 which appended before weapon)
    ns.accusations.append([
        state.current_accusation[0],
        state.current_accusation[1],
        weapon,
        state.whose_turn,
    ])
    ns.jit_transition = (
        f'{NAMES[state.whose_turn]} names the weapon: {WEAPONS[weapon]}.'
    )
    return ns


def can_ask_win(state):
    return state.accusation_phase == 4

def ask_win(state):
    ns  = OCCLUEdo_State(old=state)
    acc = state.current_accusation
    win = (acc[0] == CRIME_ROOM and acc[1] == MURDERER and acc[2] == CRIME_WEAPON)
    if win:
        ns.winner           = state.whose_turn
        ns.whose_turn       = None
        ns.current_role_num = -1
        ns.jit_transition   = f'{NAMES[state.whose_turn]} wins the game!'
    else:
        ns.inactive_players.append(state.whose_turn)
        ns.accusation_phase   = 0
        ns.current_accusation = []
        ns.jit_transition = (
            f'{NAMES[state.whose_turn]} made a false accusation '
            f'and is now inactive.'
        )
        active_left = [r for r in ns.active_roles
                       if r not in ns.inactive_players]
        if len(active_left) == 1:
            ns.winner           = active_left[0]
            ns.whose_turn       = None
            ns.current_role_num = -1
            ns.jit_transition += (
                f'\n{NAMES[active_left[0]]} wins as the last active player!'
            )
        else:
            ns.whose_turn       = next_active_role(state.whose_turn, ns,
                                                   inactive_ok=False)
            ns.current_role_num = ns.whose_turn
    return ns


# ---------------------------------------------------------------------------
# OPERATOR SET
# (Ordering must exactly match the index table at the top of this file.)
# ---------------------------------------------------------------------------

class OCCLUEdo_Operator_Set(sz.SZ_Operator_Set):

    def __init__(self):
        # go_ops: places 6-23 → op indices 0-17
        go_ops = [
            sz.SZ_Operator(
                name=f'Go to {POSSIBLE_PLAYER_SPOTS[place]}',
                precond_func=lambda s, p=place: can_go(s, p),
                state_xition_func=lambda s, p=place: go(s, p),
            )
            for place in range(6, 24)
        ]

        # index 18
        op_start_suggestion = sz.SZ_Operator(
            name='Start a suggestion.',
            precond_func=lambda s: can_start_suggestion(s),
            state_xition_func=lambda s: start_suggestion(s),
        )

        # indices 19-24
        suspect_ops = [
            sz.SZ_Operator(
                name=f'Suggest suspect {NAMES[i]}',
                precond_func=lambda s, i=i: can_suggest_suspect(s, i),
                state_xition_func=lambda s, i=i: suggest_suspect(s, i),
            )
            for i in range(6)
        ]

        # indices 25-30
        weapon_ops = [
            sz.SZ_Operator(
                name=f'Suggest the weapon was the {WEAPONS[i]}',
                precond_func=lambda s, i=i: can_suggest_weapon(s, i),
                state_xition_func=lambda s, i=i: suggest_weapon(s, i),
            )
            for i in range(6)
        ]

        # indices 31-39  (static names; actual card shown in jit_transition)
        response_ops = [
            sz.SZ_Operator(
                name=f'Show hand card {i + 1}',
                precond_func=lambda s, i=i: can_respond(s, i),
                state_xition_func=lambda s, i=i: respond(s, i),
            )
            for i in range(9)
        ]

        # index 40
        op_respond_sorry = sz.SZ_Operator(
            name="Respond: sorry, I cannot disprove your suggestion.",
            precond_func=lambda s: can_respond_sorry(s),
            state_xition_func=lambda s: respond_sorry(s),
        )

        # index 41
        op_acknowledge = sz.SZ_Operator(
            name='Acknowledge end of suggestion round.',
            precond_func=lambda s: can_acknowledge(s),
            state_xition_func=lambda s: acknowledge(s),
        )

        # index 42
        op_start_accusation = sz.SZ_Operator(
            name='Make an accusation.',
            precond_func=lambda s: can_start_accusation(s),
            state_xition_func=lambda s: start_accusation(s),
        )

        # indices 43-51
        add_room_ops = [
            sz.SZ_Operator(
                name=f'Accuse: room is the {ROOMS[r]}',
                precond_func=lambda s, r=r: can_add_room_to_accusation(s, r),
                state_xition_func=lambda s, r=r: add_room_to_accusation(s, r),
            )
            for r in range(9)
        ]

        # indices 52-57
        add_player_ops = [
            sz.SZ_Operator(
                name=f'Accuse: murderer is {NAMES[p]}',
                precond_func=lambda s, p=p: can_add_player_to_accusation(s, p),
                state_xition_func=lambda s, p=p: add_player_to_accusation(s, p),
            )
            for p in range(6)
        ]

        # indices 58-63
        add_weapon_ops = [
            sz.SZ_Operator(
                name=f'Accuse: weapon is the {WEAPONS[w]}',
                precond_func=lambda s, w=w: can_add_weapon_to_accusation(s, w),
                state_xition_func=lambda s, w=w: add_weapon_to_accusation(s, w),
            )
            for w in range(6)
        ]

        # index 64
        op_ask_win = sz.SZ_Operator(
            name='Submit accusation — did I win?',
            precond_func=lambda s: can_ask_win(s),
            state_xition_func=lambda s: ask_win(s),
        )

        self.operators = (
            go_ops
            + [op_start_suggestion]
            + suspect_ops
            + weapon_ops
            + response_ops
            + [op_respond_sorry, op_acknowledge]
            + [op_start_accusation]
            + add_room_ops
            + add_player_ops
            + add_weapon_ops
            + [op_ask_win]
        )


# ---------------------------------------------------------------------------
# METADATA
# ---------------------------------------------------------------------------

class OCCLUEdo_Metadata(sz.SZ_Metadata):
    def __init__(self):
        self.name             = 'OCCLUEdo: An Occluded Game of Clue'
        self.soluzion_version = SOLUZION_VERSION
        self.problem_version  = '2.1'
        self.authors          = ['S. Tanimoto']
        self.creation_date    = '2026-Feb'
        self.brief_desc = (
            'A simplified online Clue/Cluedo for 2-6 players plus observers. '
            'Players move between rooms, make suggestions about the murder, '
            'and try to identify the murderer, weapon, and room before anyone else. '
            'Secret cards are dealt at the start; players show cards to disprove '
            "each other's suggestions."
        )


# ---------------------------------------------------------------------------
# ROLES SPEC
# ---------------------------------------------------------------------------

class OCCLUEdo_Roles_Spec(sz.SZ_Roles_Spec):
    def __init__(self):
        self.roles = [
            sz.SZ_Role(name='Miss Scarlet',
                       description='Plays as Miss Scarlet. Goes first.'),
            sz.SZ_Role(name='Mr. Green',
                       description='Plays as Mr. Green.'),
            sz.SZ_Role(name='Colonel Mustard',
                       description='Plays as Colonel Mustard.'),
            sz.SZ_Role(name='Prof. Plum',
                       description='Plays as Prof. Plum.'),
            sz.SZ_Role(name='Mrs. Peacock',
                       description='Plays as Mrs. Peacock.'),
            sz.SZ_Role(name='Mrs. White',
                       description='Plays as Mrs. White.'),
            sz.SZ_Role(name='Observer',
                       description='Watches the game without playing.'),
        ]
        self.min_players_to_start = 2
        self.max_players          = 7


# ---------------------------------------------------------------------------
# FORMULATION
# ---------------------------------------------------------------------------

class OCCLUEdo_Formulation(sz.SZ_Formulation):

    def __init__(self):
        self.metadata    = OCCLUEdo_Metadata()
        self.operators   = OCCLUEdo_Operator_Set()
        self.roles_spec  = OCCLUEdo_Roles_Spec()
        self.common_data = sz.SZ_Common_Data()
        self.vis_module  = _oc_vis

    def initialize_problem(self, config={}):
        # config may include {'active_roles': [0, 2, 4]} from the lobby.
        # Falls back to [0, 1] (Miss Scarlet + Mr. Green) for easy testing.
        active_roles = config.get('active_roles', [0, 1])
        deal(active_roles)
        initial = OCCLUEdo_State(active_roles=active_roles)
        self.instance_data = sz.SZ_Problem_Instance_Data(
            d={'initial_state': initial, 'active_roles': active_roles}
        )
        # Per-game-instance constants: dealt hands and crime solution.
        # Stored on instance_data (not on state) because they never change
        # during a game but are re-computed fresh on each new game / rematch.
        # The engine passes instance_data to render_state() via render_vis_for_role().
        self.instance_data.player_hand    = PLAYER_HAND
        self.instance_data.crime_solution = (MURDERER, CRIME_ROOM, CRIME_WEAPON)
        return initial


# ---------------------------------------------------------------------------
# MODULE-LEVEL ENTRY POINT  (discovered by pff_loader duck typing)
# ---------------------------------------------------------------------------

OCCLUEDO = OCCLUEdo_Formulation()
