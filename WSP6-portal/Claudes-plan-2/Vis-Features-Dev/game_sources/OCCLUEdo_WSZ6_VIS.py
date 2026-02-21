"""
OCCLUEdo_WSZ6_VIS.py

WSZ6 visualization module for OCCLUEdo: An Occluded Game of Clue.
Companion to OCCLUEdo_SZ6.py.

Uses Tier-1 SVG interaction (data-op-index attributes on SVG and HTML elements):
  - Room map SVG: click on rooms and lobbies to trigger go_ops (indices 0-17).
  - Action panel HTML: click on suspect/weapon/room images and buttons for
    suggestion ops (19-30), response ops (31-40, 41), accusation ops (42-64).

Operator index reference (must stay in sync with OCCLUEdo_SZ6.py):
  0-17   go_ops  (places 6-23;  op_idx = place - 6)
  18     op_start_suggestion
  19-24  suspect_ops  (0=Scarlet … 5=White;  19 + suspect_no)
  25-30  weapon_ops   (0=Candle … 5=Wrench;  25 + weapon_no)
  31-39  response_ops (card slots 0-8;        31 + slot)
  40     op_respond_sorry
  41     op_acknowledge
  42     op_start_accusation
  43-51  add_room_to_accusation  (0-8;         43 + room_no)
  52-57  add_player_to_accusation (0-5;        52 + player_no)
  58-63  add_weapon_to_accusation (0-5;        58 + weapon_no)
  64     op_ask_win

Secret passages (diagonal corners of the room grid):
  Kitchen (row=0,col=0) ↔ Study (row=2,col=2)   [main diagonal]
  Conservatory (row=0,col=2) ↔ Lounge (row=2,col=0) [anti-diagonal]
"""

import html as _html_mod

# ---------------------------------------------------------------------------
# Data constants (mirrored from PFF to avoid circular import at load time)
# ---------------------------------------------------------------------------

_NAMES = ['Miss Scarlet', 'Mr. Green', 'Colonel Mustard',
          'Prof. Plum', 'Mrs. Peacock', 'Mrs. White', 'Observer']
_WEAPONS = ['Candlestick', 'Knife', 'Lead Pipe', 'Revolver', 'Rope', 'Wrench']
_ROOMS = ['Lounge', 'Dining Room', 'Kitchen', 'Ballroom',
          'Conservatory', 'Billiard Room', 'Library', 'Study', 'Hall']

_POSSIBLE_PLAYER_SPOTS = (
    [p + "'s Start" for p in _NAMES[:6]]
    + [r + "'s Lobby" for r in _ROOMS]
    + _ROOMS
)

_ROLE_COLORS = [
    '#c8102e', '#00843d', '#d4a017',
    '#7b2d8b', '#1f5fa6', '#d8d8d8', '#888888',
]

_SLUG     = 'occluedo'
_IMG_BASE = f'/play/game-asset/{_SLUG}/OCCLUEdo_images'

_CARD_IMAGES = {
    ('p', 0): 'Miss_Scarlet.jpg',
    ('p', 1): 'Mr_Green.jpg',
    ('p', 2): 'Colonel_Mustard.jpg',
    ('p', 3): 'Prof_Plum.jpg',
    ('p', 4): 'Mrs_Peacock.jpg',
    ('p', 5): 'Mrs_White.jpg',
    ('r', 0): 'Lounge.jpg',
    ('r', 1): 'Dining_Room.jpg',
    ('r', 2): 'Kitchen.jpg',
    ('r', 3): 'Ballroom.jpg',
    ('r', 4): 'Conservatory.jpg',
    ('r', 5): 'Billiard_Room.jpg',
    ('r', 6): 'Library.jpg',
    ('r', 7): 'Study.jpg',
    ('r', 8): 'Hall.jpg',
    ('w', 0): 'Candlestick.jpg',
    ('w', 1): 'Knife.jpg',
    ('w', 2): 'Lead_Pipe.jpg',
    ('w', 3): 'Revolver.jpg',
    ('w', 4): 'Rope.jpg',
    ('w', 5): 'Wrench.jpg',
}

# ---------------------------------------------------------------------------
# Operator-index helpers
# ---------------------------------------------------------------------------

def _go_op(place):       return place - 6
def _suspect_op(i):      return 19 + i
def _weapon_op(i):       return 25 + i
def _response_op(k):     return 31 + k
_RESPOND_SORRY = 40
_ACKNOWLEDGE   = 41
_START_ACCUSE  = 42
def _accuse_room(r):     return 43 + r
def _accuse_player(p):   return 52 + p
def _accuse_weapon(w):   return 58 + w
_ASK_WIN       = 64

# ---------------------------------------------------------------------------
# Room grid layout
#   Row 0: Kitchen(2), Ballroom(3), Conservatory(4)
#   Row 1: Billiard Room(5), Dining Room(1), Library(6)
#   Row 2: Lounge(0), Hall(8), Study(7)
# Diagonal secret passages:
#   Kitchen (0,0) ↔ Study (2,2)       [main diagonal]
#   Conservatory (0,2) ↔ Lounge (2,0) [anti-diagonal]
# ---------------------------------------------------------------------------

_ROOM_GRID = [
    [2, 3, 4],
    [5, 1, 6],
    [0, 8, 7],
]

# SVG map dimensions
_SVG_W   = 530
_SVG_H   = 450
_ROOM_W  = 150
_ROOM_H  = 100
_LOBBY_H = 22
_CELL_W  = 160    # ROOM_W + 10 gap
_CELL_H  = 138    # ROOM_H + LOBBY_H + 16 gap
_GX      = 28     # grid left margin
_GY      = 18     # grid top margin

# Secret passage destination map  place → place
_SECRET_PASSAGES = {22: 17, 17: 22, 15: 19, 19: 15}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _esc(text):
    return _html_mod.escape(str(text))

def _card_img_url(card):
    return f'{_IMG_BASE}/{_CARD_IMAGES[card]}'

def _card_name(card):
    cat, num = card
    if cat == 'r': return _ROOMS[num]
    if cat == 'p': return _NAMES[num]
    if cat == 'w': return _WEAPONS[num]
    return 'Unknown'

def _room_xy(row, col):
    """Top-left corner of the room rectangle at (row, col)."""
    return _GX + col * _CELL_W, _GY + row * _CELL_H

def _can_go_to(state, place):
    """Replicate can_go logic without importing the PFF."""
    if getattr(state, 'suggestion_phase', 0) > 0: return False
    if getattr(state, 'accusation_phase', 0)  > 0: return False
    role = getattr(state, 'current_role_num', 0)
    if role is None or role < 0 or role >= 6: return False
    player_places = getattr(state, 'player_places', list(range(6)))
    current = player_places[role]
    if current == place: return False
    if 6 <= place <= 14:   # lobby — must be unoccupied
        return place not in player_places
    if place >= 15:        # room
        if current == place - 9: return True
        if place in _SECRET_PASSAGES and current == _SECRET_PASSAGES[place]:
            return True
    return False


# ---------------------------------------------------------------------------
# Status bar
# ---------------------------------------------------------------------------

def _build_status_bar(state):
    winner = getattr(state, 'winner', None)
    if winner is not None:
        color = _ROLE_COLORS[winner] if winner < len(_ROLE_COLORS) else '#fff'
        return (
            f'<div style="background:#1a1a2e; color:#dde; padding:8px 12px; '
            f'border-radius:6px 6px 0 0; font-size:.9rem; margin-bottom:4px;">'
            f'<strong style="color:{_esc(color)};">{_esc(_NAMES[winner])}</strong>'
            f' wins!  Thanks for playing OCCLUEdo.'
            f'</div>'
        )

    whose_turn      = getattr(state, 'whose_turn', 0)
    current_role    = getattr(state, 'current_role_num', 0)
    sug_phase       = getattr(state, 'suggestion_phase', 0)
    acc_phase       = getattr(state, 'accusation_phase', 0)
    suggestion      = getattr(state, 'suggestion', None)
    whose_subturn   = getattr(state, 'whose_subturn', -1)
    ref_card        = getattr(state, 'refutation_card', None)
    player_places   = getattr(state, 'player_places', list(range(6)))
    active_roles    = getattr(state, 'active_roles', [0, 1])
    inactive        = getattr(state, 'inactive_players', [])

    if whose_turn is None:
        return '<div style="background:#1a1a2e;color:#dde;padding:8px 12px;">Game over.</div>'

    turn_color = _ROLE_COLORS[whose_turn] if whose_turn < len(_ROLE_COLORS) else '#fff'

    # Main turn line
    status_parts = [
        f"It's <strong style='color:{_esc(turn_color)};'>"
        f"{_esc(_NAMES[whose_turn])}</strong>'s turn."
    ]

    if sug_phase == 2:
        room_no = suggestion[0] if suggestion else 0
        status_parts.append(f'Suggesting in <em>{_esc(_ROOMS[room_no])}</em>: choose a suspect.')
    elif sug_phase == 3:
        status_parts.append('Suggestion: choose a weapon.')
    elif sug_phase == 4 and suggestion:
        from_color = _ROLE_COLORS[current_role] if current_role < len(_ROLE_COLORS) else '#fff'
        sug_txt    = (f'{_esc(_NAMES[suggestion[1]])} in the {_esc(_ROOMS[suggestion[0]])} '
                      f'with the {_esc(_WEAPONS[suggestion[2]])}')
        status_parts.append(
            f'Suggestion: <em>{sug_txt}</em>.  '
            f'Waiting for <strong style="color:{_esc(from_color)};">'
            f'{_esc(_NAMES[current_role])}</strong> to respond.'
        )
    elif sug_phase == 5:
        if ref_card is not None:
            status_parts.append(
                f'<strong>{_esc(_NAMES[whose_subturn])}</strong> showed a card. '
                f'{_esc(_NAMES[whose_turn])}: click Acknowledge.'
            )
        else:
            status_parts.append(
                f'Nobody could disprove the suggestion. '
                f'{_esc(_NAMES[whose_turn])}: click Acknowledge.'
            )
    elif acc_phase > 0:
        acc_labels = {1: 'choose the room', 2: 'choose the suspect',
                      3: 'choose the weapon', 4: 'submit accusation'}
        status_parts.append(
            f'Accusation in progress ({_esc(acc_labels.get(acc_phase, ""))}).'
        )

    # Player location summary
    loc_parts = []
    for rn in active_roles:
        pp    = player_places[rn]
        place = _POSSIBLE_PLAYER_SPOTS[pp]
        tag   = ' (inactive)' if rn in inactive else ''
        col   = _ROLE_COLORS[rn] if rn < len(_ROLE_COLORS) else '#fff'
        loc_parts.append(
            f'<span style="color:{_esc(col)};">{_esc(_NAMES[rn])}</span>: '
            f'{_esc(place)}{_esc(tag)}'
        )

    return (
        '<div style="background:#1a1a2e; color:#dde; padding:8px 12px; '
        'border-radius:6px 6px 0 0; font-size:.85rem; margin-bottom:4px;">'
        + ' &nbsp;|&nbsp; '.join(status_parts)
        + '<div style="margin-top:4px; font-size:.78rem; color:#aab;">'
        + ' &nbsp;&nbsp; '.join(loc_parts)
        + '</div></div>'
    )


# ---------------------------------------------------------------------------
# Room map SVG
# ---------------------------------------------------------------------------

def _build_room_map(state):
    player_places = getattr(state, 'player_places', list(range(6)))
    active_roles  = getattr(state, 'active_roles', [0, 1])
    current_role  = getattr(state, 'current_role_num', 0)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg"'
        f' width="{_SVG_W}" height="{_SVG_H}"'
        f' style="display:block;">'
    ]

    # Dark background
    parts.append(
        f'<rect x="0" y="0" width="{_SVG_W}" height="{_SVG_H}"'
        f' fill="#0d1117" rx="6"/>'
    )

    # Secret passage diagonal lines
    # Kitchen (row=0,col=0) ↔ Study (row=2,col=2)
    kx, ky = _room_xy(0, 0)
    sx, sy = _room_xy(2, 2)
    parts.append(
        f'<line x1="{kx + _ROOM_W}" y1="{ky + _ROOM_H}"'
        f' x2="{sx}" y2="{sy}"'
        f' stroke="#ffd700" stroke-width="1.5" stroke-dasharray="5,4" opacity="0.45"/>'
    )
    # Conservatory (row=0,col=2) ↔ Lounge (row=2,col=0)
    cx, cy = _room_xy(0, 2)
    lx, ly = _room_xy(2, 0)
    parts.append(
        f'<line x1="{cx}" y1="{cy + _ROOM_H}"'
        f' x2="{lx + _ROOM_W}" y2="{ly}"'
        f' stroke="#ffd700" stroke-width="1.5" stroke-dasharray="5,4" opacity="0.45"/>'
    )

    for row in range(3):
        for col in range(3):
            room_idx    = _ROOM_GRID[row][col]
            room_place  = room_idx + 15    # place index for the room
            lobby_place = room_idx + 6     # place index for the lobby
            rx, ry      = _room_xy(row, col)

            can_enter    = _can_go_to(state, room_place)
            room_fill    = '#1e5f3a' if can_enter else '#1c2a3a'
            room_stroke  = '#2dbd6e' if can_enter else '#3a5070'
            room_attr    = f' data-op-index="{_go_op(room_place)}"' if can_enter else ''

            # Room rectangle
            parts.append(
                f'<rect x="{rx}" y="{ry}" width="{_ROOM_W}" height="{_ROOM_H}"'
                f' fill="{room_fill}" stroke="{room_stroke}" stroke-width="1.5"'
                f' rx="4"{room_attr}/>'
            )

            # Room name
            label_col = '#7fdc8f' if can_enter else '#6a90bb'
            parts.append(
                f'<text x="{rx + _ROOM_W // 2}" y="{ry + 20}"'
                f' text-anchor="middle" font-family="sans-serif"'
                f' font-size="11" fill="{label_col}"'
                f'{room_attr}>{_esc(_ROOMS[room_idx])}</text>'
            )

            # Secret passage label (corner rooms only)
            if room_place in _SECRET_PASSAGES:
                dest_place = _SECRET_PASSAGES[room_place]
                dest_room  = dest_place - 15
                can_use    = _can_go_to(state, dest_place)
                if can_use:
                    parts.append(
                        f'<text x="{rx + _ROOM_W // 2}" y="{ry + _ROOM_H - 8}"'
                        f' text-anchor="middle" font-family="sans-serif"'
                        f' font-size="9" fill="#ffd700"'
                        f' data-op-index="{_go_op(dest_place)}">'
                        f'↗ {_esc(_ROOMS[dest_room])}</text>'
                    )
                else:
                    dest_name = _ROOMS[dest_room]
                    parts.append(
                        f'<text x="{rx + _ROOM_W // 2}" y="{ry + _ROOM_H - 8}"'
                        f' text-anchor="middle" font-family="sans-serif"'
                        f' font-size="9" fill="#777"'
                        f' data-info="Secret passage to {_esc(dest_name)}">'
                        f'≋ {_esc(dest_name)}</text>'
                    )

            # Lobby strip
            lbx = rx + 25
            lby = ry + _ROOM_H + 4
            lbw = _ROOM_W - 50
            can_lobby   = _can_go_to(state, lobby_place)
            lob_fill    = '#2d3f1c' if can_lobby else '#141c12'
            lob_stroke  = '#6aad3a' if can_lobby else '#334'
            lob_attr    = (f' data-op-index="{_go_op(lobby_place)}"' if can_lobby
                           else f' data-info="{_esc(_ROOMS[room_idx])}\'s Lobby"')
            parts.append(
                f'<rect x="{lbx}" y="{lby}" width="{lbw}" height="{_LOBBY_H}"'
                f' fill="{lob_fill}" stroke="{lob_stroke}" stroke-width="1"'
                f' rx="3"{lob_attr}/>'
            )
            lob_txt_col = '#9bd65a' if can_lobby else '#556'
            parts.append(
                f'<text x="{lbx + lbw // 2}" y="{lby + 15}"'
                f' text-anchor="middle" font-family="sans-serif"'
                f' font-size="9" fill="{lob_txt_col}"{lob_attr}>'
                f'Lobby</text>'
            )

            # Player tokens inside this room
            occupants = [r for r in active_roles
                         if r < 6 and player_places[r] == room_place]
            tx = rx + 15
            ty = ry + 55
            for rn in occupants:
                col_str  = _ROLE_COLORS[rn]
                initials = ''.join(w[0] for w in _NAMES[rn].split()[:2])
                txt_col  = '#000' if rn != 5 else '#111'  # White role needs dark text
                parts.append(
                    f'<circle cx="{tx + 11}" cy="{ty}" r="11"'
                    f' fill="{col_str}" stroke="white" stroke-width="1"'
                    f' data-info="{_esc(_NAMES[rn])}"/>'
                )
                parts.append(
                    f'<text x="{tx + 11}" y="{ty + 4}"'
                    f' text-anchor="middle" font-family="sans-serif"'
                    f' font-size="9" font-weight="bold" fill="{txt_col}"'
                    f' data-info="{_esc(_NAMES[rn])}">{_esc(initials)}</text>'
                )
                tx += 26

            # Player tokens inside this lobby
            lob_occ = [r for r in active_roles
                       if r < 6 and player_places[r] == lobby_place]
            for rn in lob_occ:
                col_str  = _ROLE_COLORS[rn]
                initials = ''.join(w[0] for w in _NAMES[rn].split()[:2])
                parts.append(
                    f'<circle cx="{lbx + lbw // 2}" cy="{lby + 11}" r="9"'
                    f' fill="{col_str}" stroke="white" stroke-width="1"'
                    f' data-info="{_esc(_NAMES[rn])} (lobby)"/>'
                )
                parts.append(
                    f'<text x="{lbx + lbw // 2}" y="{lby + 15}"'
                    f' text-anchor="middle" font-family="sans-serif"'
                    f' font-size="8" fill="#000"'
                    f' data-info="{_esc(_NAMES[rn])} (lobby)">{_esc(initials)}</text>'
                )

    # Players at starting places — shown as a row along the bottom
    at_start = [r for r in active_roles if r < 6 and player_places[r] < 6]
    if at_start:
        bx = _GX
        by = _SVG_H - 26
        parts.append(
            f'<text x="{bx}" y="{by - 4}" font-family="sans-serif"'
            f' font-size="9" fill="#556">At starting place:</text>'
        )
        for rn in at_start:
            col_str  = _ROLE_COLORS[rn]
            initials = ''.join(w[0] for w in _NAMES[rn].split()[:2])
            parts.append(
                f'<circle cx="{bx + 50 + at_start.index(rn)*26}" cy="{by + 8}"'
                f' r="10" fill="{col_str}" stroke="white" stroke-width="1"'
                f' data-info="{_esc(_NAMES[rn])} (starting place)"/>'
            )
            parts.append(
                f'<text x="{bx + 50 + at_start.index(rn)*26}" y="{by + 12}"'
                f' text-anchor="middle" font-family="sans-serif"'
                f' font-size="8" fill="#000">{_esc(initials)}</text>'
            )

    parts.append('</svg>')
    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# Action panel (context-sensitive)
# ---------------------------------------------------------------------------

_CARD_DIV_STYLE = (
    'display:inline-flex; flex-direction:column; align-items:center; '
    'border:2px solid #334; border-radius:6px; padding:4px; '
    'background:#14202e; cursor:pointer; width:82px; '
)
_CARD_NAME_STYLE = (
    'font-size:9px; color:#99b; margin-top:3px; text-align:center; '
    'max-width:78px; word-break:break-word;'
)


def _card_div(card, op_idx, extra_style=''):
    """Return HTML for a clickable card image div."""
    url  = _card_img_url(card)
    name = _card_name(card)
    return (
        f'<div data-op-index="{op_idx}" style="{_CARD_DIV_STYLE}{extra_style}">'
        f'<img src="{url}" width="70" height="90" '
        f'style="object-fit:cover; border-radius:4px;">'
        f'<div style="{_CARD_NAME_STYLE}">{_esc(name)}</div>'
        f'</div>'
    )


def _grey_card_div(card):
    """Return a non-clickable, greyed-out card image div."""
    url  = _card_img_url(card)
    name = _card_name(card)
    return (
        f'<div style="{_CARD_DIV_STYLE}opacity:0.35; cursor:default;">'
        f'<img src="{url}" width="70" height="90" '
        f'style="object-fit:cover; border-radius:4px;">'
        f'<div style="{_CARD_NAME_STYLE}">{_esc(name)}</div>'
        f'</div>'
    )


def _action_button(label, op_idx, color='#2a5fa5'):
    return (
        f'<div data-op-index="{op_idx}" style="'
        f'background:{color}; color:#fff; padding:7px 14px; '
        f'border-radius:5px; cursor:pointer; font-size:.85rem; '
        f'display:inline-block; margin:4px;">{_esc(label)}</div>'
    )


def _section(title, content):
    return (
        f'<div style="margin:6px 0;">'
        f'<div style="font-size:.78rem; color:#778; margin-bottom:4px;">'
        f'{_esc(title)}</div>'
        f'<div style="display:flex; flex-wrap:wrap; gap:6px;">{content}</div>'
        f'</div>'
    )


def _build_action_panel(state, viewing_role, player_hand, crime_solution):
    sug_phase = getattr(state, 'suggestion_phase', 0)
    acc_phase = getattr(state, 'accusation_phase', 0)
    winner    = getattr(state, 'winner', None)
    ref_card  = getattr(state, 'refutation_card', None)
    suggestion = getattr(state, 'suggestion', None)
    whose_subturn = getattr(state, 'whose_subturn', -1)
    current_role  = getattr(state, 'current_role_num', 0)
    whose_turn    = getattr(state, 'whose_turn', 0)

    panel = '<div style="margin-top:6px; font-family:sans-serif; color:#dde;">'

    # ── Game over ──────────────────────────────────────────────────────────────
    if winner is not None:
        panel += (
            f'<div style="color:#ffd700; font-size:1rem; padding:8px;">'
            f'{_esc(_NAMES[winner])} wins! The crime was: '
        )
        if crime_solution:
            murderer, crime_room, crime_weapon = crime_solution
            panel += (
                f'{_esc(_NAMES[murderer])} in the '
                f'{_esc(_ROOMS[crime_room])} '
                f'with the {_esc(_WEAPONS[crime_weapon])}.'
            )
        else:
            panel += '(solution unavailable)'
        panel += '</div>'
        panel += '</div>'
        return panel

    # ── Phase 5: Acknowledge ───────────────────────────────────────────────────
    if sug_phase == 5:
        if ref_card is not None:
            if viewing_role == whose_turn:
                # Only the suggester sees which card was shown.
                panel += (
                    f'<div style="margin-bottom:6px; font-size:.85rem;">'
                    f'<strong>{_esc(_NAMES[whose_subturn])}</strong> showed you a card:'
                    f'</div>'
                )
                panel += '<div style="display:flex; flex-wrap:wrap; gap:6px; margin-bottom:8px;">'
                panel += _grey_card_div(ref_card)   # display only, non-clickable
                panel += '</div>'
                panel += _action_button('Acknowledge', _ACKNOWLEDGE, color='#1a6a3a')
            else:
                # Other players only learn that a card was shown, not which one.
                whose_turn_color = _ROLE_COLORS[whose_turn] if whose_turn < len(_ROLE_COLORS) else '#fff'
                panel += (
                    f'<div style="font-size:.85rem; color:#778;">'
                    f'<strong>{_esc(_NAMES[whose_subturn])}</strong> showed a card to '
                    f'<strong style="color:{_esc(whose_turn_color)};">'
                    f'{_esc(_NAMES[whose_turn])}</strong>. '
                    f'Waiting for them to acknowledge…'
                    f'</div>'
                )
        else:
            panel += (
                '<div style="color:#f0a; margin-bottom:6px; font-size:.85rem;">'
                'Nobody could disprove the suggestion!</div>'
            )
            if viewing_role == whose_turn:
                panel += _action_button('Acknowledge', _ACKNOWLEDGE, color='#1a6a3a')
            else:
                whose_turn_color = _ROLE_COLORS[whose_turn] if whose_turn < len(_ROLE_COLORS) else '#fff'
                panel += (
                    f'<div style="font-size:.85rem; color:#778;">'
                    f'Waiting for <strong style="color:{_esc(whose_turn_color)};">'
                    f'{_esc(_NAMES[whose_turn])}</strong> to acknowledge…'
                    f'</div>'
                )
        panel += '</div>'
        return panel

    # ── Phase 4: Refutation round ──────────────────────────────────────────────
    if sug_phase == 4:
        if suggestion:
            sug_txt = (
                f'{_NAMES[suggestion[1]]} in the {_ROOMS[suggestion[0]]} '
                f'with the {_WEAPONS[suggestion[2]]}'
            )
            panel += (
                f'<div style="font-size:.8rem; color:#aac; margin-bottom:5px;">'
                f'Suggestion: <em>{_esc(sug_txt)}</em></div>'
            )

        if viewing_role != current_role:
            # Non-refuting player: show a neutral waiting message, no hand.
            current_role_color = _ROLE_COLORS[current_role] if current_role < len(_ROLE_COLORS) else '#fff'
            panel += (
                f'<div style="font-size:.85rem; color:#778;">'
                f'Waiting for <strong style="color:{_esc(current_role_color)};">'
                f'{_esc(_NAMES[current_role])}</strong> to respond…'
                f'</div>'
            )
            panel += '</div>'
            return panel

        # Only the refuting player sees their own hand and the Sorry button.
        hand = (player_hand[current_role]
                if player_hand and current_role is not None and current_role < 6
                else [])

        if hand:
            panel += (
                f'<div style="font-size:.8rem; color:#aac; margin-bottom:4px;">'
                f'Show a card that disproves the suggestion, or pass.</div>'
            )
            card_html = ''
            for slot, card in enumerate(hand):
                matches = False
                if suggestion:
                    matches = (
                        (card[0] == 'r' and card[1] == suggestion[0]) or
                        (card[0] == 'p' and card[1] == suggestion[1]) or
                        (card[0] == 'w' and card[1] == suggestion[2])
                    )
                if matches:
                    card_html += _card_div(card, _response_op(slot),
                                           extra_style='border-color:#2dbd6e;')
                else:
                    card_html += _grey_card_div(card)
            panel += _section('Your hand (green = can refute):', card_html)
        else:
            panel += (
                f'<div style="font-size:.8rem; color:#aac; margin-bottom:4px;">'
                f'You have no cards in hand.</div>'
            )

        panel += _action_button(
            "Sorry — I cannot disprove the suggestion.", _RESPOND_SORRY,
            color='#6a2a2a'
        )
        panel += '</div>'
        return panel

    # ── Suggestion phase 3: choose weapon ─────────────────────────────────────
    if sug_phase == 3:
        w_html = ''.join(
            _card_div(('w', i), _weapon_op(i)) for i in range(6)
        )
        panel += _section('Choose the weapon:', w_html)
        panel += '</div>'
        return panel

    # ── Suggestion phase 2: choose suspect ────────────────────────────────────
    if sug_phase == 2:
        s_html = ''.join(
            _card_div(('p', i), _suspect_op(i)) for i in range(6)
        )
        panel += _section('Choose the suspect:', s_html)
        panel += '</div>'
        return panel

    # ── Accusation in progress ─────────────────────────────────────────────────
    if acc_phase == 1:
        r_html = ''.join(
            _card_div(('r', r), _accuse_room(r)) for r in range(9)
        )
        panel += _section('Accusation — choose the room:', r_html)
        panel += '</div>'
        return panel

    if acc_phase == 2:
        p_html = ''.join(
            _card_div(('p', p), _accuse_player(p)) for p in range(6)
        )
        panel += _section('Accusation — choose the murderer:', p_html)
        panel += '</div>'
        return panel

    if acc_phase == 3:
        w_html = ''.join(
            _card_div(('w', w), _accuse_weapon(w)) for w in range(6)
        )
        panel += _section('Accusation — choose the weapon:', w_html)
        panel += '</div>'
        return panel

    if acc_phase == 4:
        ca = getattr(state, 'current_accusation', [])
        summary = '(incomplete)'
        if len(ca) >= 4:
            summary = (
                f'{_NAMES[ca[1]]} in the {_ROOMS[ca[0]]} '
                f'with the {_WEAPONS[ca[2]]}'
            )
        panel += (
            f'<div style="font-size:.85rem; color:#ffd700; margin-bottom:8px;">'
            f'Your accusation: <em>{_esc(summary)}</em></div>'
        )
        panel += _action_button('Submit accusation — Did I win?', _ASK_WIN,
                                color='#7a1a1a')
        panel += '</div>'
        return panel

    # ── Phase 0: normal turn ───────────────────────────────────────────────────
    # Show contextual buttons for start_suggestion (if available) and make_accusation
    recent_arrivals = getattr(state, 'recent_arrivals', [])
    player_places   = getattr(state, 'player_places', list(range(6)))

    buttons = ''
    if (whose_turn is not None and whose_turn < 6 and
            whose_turn in recent_arrivals and
            player_places[whose_turn] >= 15):
        buttons += _action_button('Start a suggestion (you just arrived here)',
                                  18, color='#1a4a6a')
    buttons += _action_button('Make an accusation', _START_ACCUSE,
                              color='#5a1a1a')

    panel += (
        '<div style="font-size:.78rem; color:#778; margin-bottom:6px;">'
        'Move by clicking a room or lobby on the map above, or:'
        '</div>'
    )
    panel += buttons
    panel += '</div>'
    return panel


# ---------------------------------------------------------------------------
# Hand display
# ---------------------------------------------------------------------------

def _build_hand_display(state, viewing_role, player_hand):
    winner = getattr(state, 'winner', None)
    if winner is not None or viewing_role is None or viewing_role < 0 or viewing_role >= 6:
        return ''
    if not player_hand:
        return ''

    hand = player_hand[viewing_role]
    if not hand:
        return ''

    name  = _NAMES[viewing_role]
    color = _ROLE_COLORS[viewing_role]
    cards_html = ''.join(
        f'<img src="{_card_img_url(c)}" height="80" '
        f'style="border-radius:4px; margin-right:4px;" '
        f'title="{_esc(_card_name(c))}">'
        for c in hand
    )

    return (
        f'<div style="margin-top:8px; padding:6px 8px; '
        f'background:#101820; border-radius:0 0 6px 6px; '
        f'font-family:sans-serif;">'
        f'<div style="font-size:.75rem; color:{_esc(color)}; margin-bottom:4px;">'
        f'Your cards ({_esc(name)}):</div>'
        f'<div style="display:flex; flex-wrap:wrap; gap:4px;">{cards_html}</div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_state(state, role_num=None, instance_data=None) -> str:
    """Return an HTML string for the current OCCLUEdo game state.

    ``role_num`` is the viewing player's role; the engine passes the
    consumer's role so each player sees only their own private hand.

    ``instance_data`` is the formulation's instance_data object, set by
    ``initialize_problem()`` and re-created fresh for every new game /
    rematch.  It carries per-game constants (dealt hands, crime solution)
    that never belong on the state object itself.
    """
    viewing_role   = role_num if role_num is not None else getattr(state, 'current_role_num', 0)
    player_hand    = getattr(instance_data, 'player_hand',    None)
    crime_solution = getattr(instance_data, 'crime_solution', None)

    status_html = _build_status_bar(state)
    map_html    = _build_room_map(state)
    action_html = _build_action_panel(state, viewing_role, player_hand, crime_solution)
    hand_html   = _build_hand_display(state, viewing_role, player_hand)

    return (
        '<div style="font-family:sans-serif; background:#0d0d1a; '
        'padding:0; border-radius:6px; max-width:560px;">'
        + status_html
        + map_html
        + action_html
        + hand_html
        + '</div>'
    )
