"""
Tic_Tac_Toe_WSZ6_VIS.py

WSZ6 visualization module for Tic-Tac-Toe.
Companion to Tic_Tac_Toe_SZ6_with_vis.py.

Convention: the vis file has the same filename prefix as the PFF, with the
suffix _WSZ6_VIS replacing _SZ6 (or appended after the base name).

Public API (called by the game runner):
    render_state(state) -> str
        Return an HTML string containing an SVG board rendering.

The state object is duck-typed; no import from the PFF is needed.
Expected attributes:
    state.board         -- list[list[int]], 3×3; values 0=X, 1=O, 2=EMPTY
    state.winner        -- int, -1=no winner, 0=X, 1=O
    state.whose_turn    -- int, 0=X, 1=O
"""

# ── Board-cell encoding (mirrors Tic_Tac_Toe_SZ6.py; never import from PFF) ──
_X     = 0
_O     = 1
_EMPTY = 2

# ── SVG layout constants ──────────────────────────────────────────────────────
_CELL   = 100    # SVG units per cell
_PAD    = 14     # inner padding for marks (so they don't touch cell edges)
_W      = 300    # board width
_BH     = 300    # board height
_SB     = 30     # status-bar height below board
_H      = _BH + _SB   # total SVG height

# ── Colours ───────────────────────────────────────────────────────────────────
_C_BG_NORMAL  = '#ffffff'
_C_BG_WIN     = '#fffde7'   # light amber for winning cells
_C_GRID_INNER = '#424242'   # dark-grey inner grid lines
_C_CELL_EDGE  = '#e0e0e0'   # thin outer edge of each cell
_C_X          = '#1565C0'   # dark blue for X
_C_O          = '#C62828'   # dark red  for O
_C_STATUS     = '#444444'


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_state(state) -> str:
    """Return an HTML/SVG string visualising *state*."""
    board      = state.board
    winner     = getattr(state, 'winner', -1)
    whose_turn = getattr(state, 'whose_turn', _X)

    moves_remain = any(
        board[r][c] == _EMPTY for r in range(3) for c in range(3)
    )
    win_cells    = _winning_cells(board, winner)
    status_text  = _status_text(winner, whose_turn, moves_remain)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="0 0 {_W} {_H}"'
        f' width="100%"'
        f' style="max-width:360px;display:block;margin:auto;">'
    ]

    # ── Cell backgrounds ──────────────────────────────────────────────────
    for row in range(3):
        for col in range(3):
            x    = col * _CELL
            y    = row * _CELL
            fill = _C_BG_WIN if (row, col) in win_cells else _C_BG_NORMAL
            parts.append(
                f'<rect x="{x}" y="{y}" width="{_CELL}" height="{_CELL}"'
                f' fill="{fill}" stroke="{_C_CELL_EDGE}" stroke-width="1"/>'
            )

    # ── Inner grid lines ──────────────────────────────────────────────────
    for i in range(1, 3):
        p = i * _CELL
        parts.append(
            f'<line x1="{p}" y1="0" x2="{p}" y2="{_BH}"'
            f' stroke="{_C_GRID_INNER}" stroke-width="3"/>'
        )
        parts.append(
            f'<line x1="0" y1="{p}" x2="{_W}" y2="{p}"'
            f' stroke="{_C_GRID_INNER}" stroke-width="3"/>'
        )

    # ── Marks ─────────────────────────────────────────────────────────────
    for row in range(3):
        for col in range(3):
            mark = board[row][col]
            x    = col * _CELL
            y    = row * _CELL

            if mark == _X:
                x1 = x + _PAD;      y1 = y + _PAD
                x2 = x + _CELL - _PAD;  y2 = y + _CELL - _PAD
                parts.append(
                    f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"'
                    f' stroke="{_C_X}" stroke-width="9" stroke-linecap="round"/>'
                )
                parts.append(
                    f'<line x1="{x2}" y1="{y1}" x2="{x1}" y2="{y2}"'
                    f' stroke="{_C_X}" stroke-width="9" stroke-linecap="round"/>'
                )

            elif mark == _O:
                cx = x + _CELL // 2
                cy = y + _CELL // 2
                parts.append(
                    f'<circle cx="{cx}" cy="{cy}" r="36"'
                    f' fill="none" stroke="{_C_O}" stroke-width="9"/>'
                )

    # ── Outer border ──────────────────────────────────────────────────────
    parts.append(
        f'<rect x="0" y="0" width="{_W}" height="{_BH}"'
        f' fill="none" stroke="#9e9e9e" stroke-width="2"/>'
    )

    # ── Status bar ────────────────────────────────────────────────────────
    sy = _BH + _SB // 2 + 5   # vertically centre text in the status band
    parts.append(
        f'<text x="{_W // 2}" y="{sy}" text-anchor="middle"'
        f' font-family="sans-serif" font-size="15" fill="{_C_STATUS}">'
        f'{_esc(status_text)}</text>'
    )

    parts.append('</svg>')
    return '\n'.join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _winning_cells(board, winner):
    """Return the set of (row, col) tuples that form the winning line."""
    if winner not in (_X, _O):
        return set()
    mark = winner
    # Rows
    for r in range(3):
        if all(board[r][c] == mark for c in range(3)):
            return {(r, 0), (r, 1), (r, 2)}
    # Columns
    for c in range(3):
        if all(board[r][c] == mark for r in range(3)):
            return {(0, c), (1, c), (2, c)}
    # Main diagonal
    if all(board[i][i] == mark for i in range(3)):
        return {(0, 0), (1, 1), (2, 2)}
    # Anti-diagonal
    if all(board[2 - i][i] == mark for i in range(3)):
        return {(2, 0), (1, 1), (0, 2)}
    return set()


def _status_text(winner, whose_turn, moves_remain):
    if winner == _X:
        return "X wins!"
    if winner == _O:
        return "O wins!"
    if not moves_remain:
        return "It's a draw!"
    return "X's turn" if whose_turn == _X else "O's turn"


def _esc(text):
    """Minimal XML-safe escaping for SVG text nodes."""
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))
