"""
Chess Game
==========
A complete two-player chess game with an optional computer opponent.

Full rules are implemented: legal move validation, check, checkmate,
stalemate, castling, en passant, and pawn promotion (auto-queen).

Controls
--------
  Move a piece    :  click a piece, then click a highlighted square
  New game        :  N
  Undo last move  :  U
  Toggle computer :  A   (computer takes over the side NOT to move)
  Difficulty      :  1 = Easy, 2 = Medium, 3 = Hard
  Quit            :  ESC

The computer thinks in a background thread, so the window stays responsive
("Computer is thinking..." is shown while it searches).

Built with pygame.
"""

import sys
import copy
import threading

import pygame

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
SQUARE = 80
BOARD = SQUARE * 8
MARGIN_TOP = 50            # status bar
MARGIN_BOTTOM = 30         # file/rank room
WIDTH = BOARD
HEIGHT = BOARD + MARGIN_TOP + MARGIN_BOTTOM

LIGHT = (240, 217, 181)
DARK = (181, 136, 99)
HILITE = (246, 246, 105)      # selected square
MOVE_DOT = (60, 60, 60)
CHECK_COL = (220, 90, 90)
BG = (40, 42, 48)
TEXT_COL = (235, 235, 240)

# Solid Unicode chess glyphs (used for both colors, tinted per side)
GLYPH = {'K': '♚', 'Q': '♛', 'R': '♜',
         'B': '♝', 'N': '♞', 'P': '♟'}

START = [
    ['bR', 'bN', 'bB', 'bQ', 'bK', 'bB', 'bN', 'bR'],
    ['bP'] * 8,
    [None] * 8,
    [None] * 8,
    [None] * 8,
    [None] * 8,
    ['wP'] * 8,
    ['wR', 'wN', 'wB', 'wQ', 'wK', 'wB', 'wN', 'wR'],
]

VALUE = {'P': 100, 'N': 320, 'B': 330, 'R': 500, 'Q': 900, 'K': 20000}


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------
def new_state():
    return {
        'board': copy.deepcopy(START),
        'turn': 'w',
        'ep': None,                                  # en-passant target square
        'castle': {'wK', 'wQ', 'bK', 'bQ'},          # available castling
    }


def in_bounds(r, c):
    return 0 <= r < 8 and 0 <= c < 8


def enemy(color):
    return 'b' if color == 'w' else 'w'


def find_king(board, color):
    target = color + 'K'
    for r in range(8):
        for c in range(8):
            if board[r][c] == target:
                return r, c
    return None


def is_attacked(board, r, c, by):
    """Is square (r,c) attacked by color `by`?"""
    # Pawn attacks
    pd = 1 if by == 'w' else -1   # white pawns attack toward decreasing row,
    # so a square is attacked by a white pawn sitting one row *below* (r+1).
    for dc in (-1, 1):
        pr, pc = r + pd, c + dc
        if in_bounds(pr, pc) and board[pr][pc] == by + 'P':
            return True
    # Knights
    for dr, dc in ((-2, -1), (-2, 1), (-1, -2), (-1, 2),
                   (1, -2), (1, 2), (2, -1), (2, 1)):
        nr, nc = r + dr, c + dc
        if in_bounds(nr, nc) and board[nr][nc] == by + 'N':
            return True
    # King
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr or dc:
                nr, nc = r + dr, c + dc
                if in_bounds(nr, nc) and board[nr][nc] == by + 'K':
                    return True
    # Sliding: rook/queen (orthogonal), bishop/queen (diagonal)
    for dr, dc, kinds in ((-1, 0, 'RQ'), (1, 0, 'RQ'), (0, -1, 'RQ'), (0, 1, 'RQ'),
                          (-1, -1, 'BQ'), (-1, 1, 'BQ'), (1, -1, 'BQ'), (1, 1, 'BQ')):
        nr, nc = r + dr, c + dc
        while in_bounds(nr, nc):
            p = board[nr][nc]
            if p is not None:
                if p[0] == by and p[1] in kinds:
                    return True
                break
            nr += dr
            nc += dc
    return False


def gen_pseudo(state, color):
    """All moves ignoring whether they leave the king in check."""
    board = state['board']
    moves = []
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p is None or p[0] != color:
                continue
            kind = p[1]
            if kind == 'P':
                _pawn_moves(state, r, c, color, moves)
            elif kind == 'N':
                for dr, dc in ((-2, -1), (-2, 1), (-1, -2), (-1, 2),
                               (1, -2), (1, 2), (2, -1), (2, 1)):
                    _try_step(board, r, c, dr, dc, color, moves)
            elif kind == 'K':
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr or dc:
                            _try_step(board, r, c, dr, dc, color, moves)
                _castle_moves(state, r, c, color, moves)
            else:
                dirs = {'R': ((-1, 0), (1, 0), (0, -1), (0, 1)),
                        'B': ((-1, -1), (-1, 1), (1, -1), (1, 1)),
                        'Q': ((-1, 0), (1, 0), (0, -1), (0, 1),
                              (-1, -1), (-1, 1), (1, -1), (1, 1))}[kind]
                for dr, dc in dirs:
                    nr, nc = r + dr, c + dc
                    while in_bounds(nr, nc):
                        q = board[nr][nc]
                        if q is None:
                            moves.append((r, c, nr, nc, None))
                        else:
                            if q[0] != color:
                                moves.append((r, c, nr, nc, None))
                            break
                        nr += dr
                        nc += dc
    return moves


def _try_step(board, r, c, dr, dc, color, moves):
    nr, nc = r + dr, c + dc
    if in_bounds(nr, nc):
        q = board[nr][nc]
        if q is None or q[0] != color:
            moves.append((r, c, nr, nc, None))


def _pawn_moves(state, r, c, color, moves):
    board = state['board']
    d = -1 if color == 'w' else 1          # white advances up the board
    start_row = 6 if color == 'w' else 1
    promo_row = 0 if color == 'w' else 7
    # forward one
    if in_bounds(r + d, c) and board[r + d][c] is None:
        flag = 'promo' if r + d == promo_row else None
        moves.append((r, c, r + d, c, flag))
        # forward two
        if r == start_row and board[r + 2 * d][c] is None:
            moves.append((r, c, r + 2 * d, c, 'double'))
    # captures + en passant
    for dc in (-1, 1):
        nr, nc = r + d, c + dc
        if not in_bounds(nr, nc):
            continue
        q = board[nr][nc]
        if q is not None and q[0] != color:
            flag = 'promo' if nr == promo_row else None
            moves.append((r, c, nr, nc, flag))
        elif state['ep'] == (nr, nc):
            moves.append((r, c, nr, nc, 'ep'))


def _castle_moves(state, r, c, color, moves):
    board = state['board']
    if is_attacked(board, r, c, enemy(color)):
        return
    back = 7 if color == 'w' else 0
    if r != back or c != 4:
        return
    # King-side
    if color + 'K' in state['castle']:
        if board[back][5] is None and board[back][6] is None \
                and board[back][7] == color + 'R' \
                and not is_attacked(board, back, 5, enemy(color)) \
                and not is_attacked(board, back, 6, enemy(color)):
            moves.append((r, c, back, 6, 'castleK'))
    # Queen-side
    if color + 'Q' in state['castle']:
        if board[back][1] is None and board[back][2] is None and board[back][3] is None \
                and board[back][0] == color + 'R' \
                and not is_attacked(board, back, 3, enemy(color)) \
                and not is_attacked(board, back, 2, enemy(color)):
            moves.append((r, c, back, 2, 'castleQ'))


def apply_move(state, move):
    """Return a new state with `move` applied (does not mutate input)."""
    s = {'board': [row[:] for row in state['board']],
         'turn': enemy(state['turn']),
         'ep': None,
         'castle': set(state['castle'])}
    b = s['board']
    fr, fc, tr, tc, flag = move
    piece = b[fr][fc]
    color = piece[0]
    b[fr][fc] = None
    b[tr][tc] = piece

    if flag == 'double':
        s['ep'] = ((fr + tr) // 2, fc)
    elif flag == 'ep':
        b[fr][tc] = None                       # captured pawn is beside us
    elif flag == 'promo':
        b[tr][tc] = color + 'Q'
    elif flag == 'castleK':
        back = tr
        b[back][7] = None
        b[back][5] = color + 'R'
    elif flag == 'castleQ':
        back = tr
        b[back][0] = None
        b[back][3] = color + 'R'

    # Update castling rights
    if piece[1] == 'K':
        s['castle'].discard(color + 'K')
        s['castle'].discard(color + 'Q')
    if piece[1] == 'R':
        back = 7 if color == 'w' else 0
        if fr == back and fc == 0:
            s['castle'].discard(color + 'Q')
        elif fr == back and fc == 7:
            s['castle'].discard(color + 'K')
    # Rook captured -> lose that right
    for col in ('w', 'b'):
        back = 7 if col == 'w' else 0
        if b[back][0] != col + 'R':
            s['castle'].discard(col + 'Q')
        if b[back][7] != col + 'R':
            s['castle'].discard(col + 'K')
    return s


def legal_moves(state, color=None):
    if color is None:
        color = state['turn']
    out = []
    for mv in gen_pseudo(state, color):
        ns = apply_move(state, mv)
        kr, kc = find_king(ns['board'], color)
        if not is_attacked(ns['board'], kr, kc, enemy(color)):
            out.append(mv)
    return out


def in_check(state, color):
    kr, kc = find_king(state['board'], color)
    return is_attacked(state['board'], kr, kc, enemy(color))


def game_status(state):
    """Return 'play', 'checkmate', or 'stalemate' for the side to move."""
    if legal_moves(state):
        return 'play'
    return 'checkmate' if in_check(state, state['turn']) else 'stalemate'


# ---------------------------------------------------------------------------
# Simple AI (negamax + alpha-beta, material evaluation)
# ---------------------------------------------------------------------------
def evaluate(state, color):
    score = 0
    for row in state['board']:
        for p in row:
            if p:
                v = VALUE[p[1]]
                score += v if p[0] == color else -v
    return score


def _order(state, moves):
    # Search captures first for better pruning.
    b = state['board']
    return sorted(moves, key=lambda m: 0 if b[m[2]][m[3]] is None else 1, reverse=True)


def negamax(state, depth, alpha, beta, color):
    moves = legal_moves(state, color)
    if not moves:
        if in_check(state, color):
            return -100000 - depth, None      # checkmated: worse if sooner
        return 0, None                         # stalemate
    if depth == 0:
        return evaluate(state, color), None
    best_move = None
    best = -10 ** 9
    for mv in _order(state, moves):
        ns = apply_move(state, mv)
        val, _ = negamax(ns, depth - 1, -beta, -alpha, enemy(color))
        val = -val
        if val > best:
            best, best_move = val, mv
        alpha = max(alpha, val)
        if alpha >= beta:
            break
    return best, best_move


def ai_move(state, depth=3):
    _, mv = negamax(state, depth, -10 ** 9, 10 ** 9, state['turn'])
    return mv


# ---------------------------------------------------------------------------
# Rendering / main loop
# ---------------------------------------------------------------------------
def draw_piece(screen, font, piece, x, y):
    glyph = GLYPH[piece[1]]
    fill = (250, 250, 250) if piece[0] == 'w' else (25, 25, 25)
    outline = (25, 25, 25) if piece[0] == 'w' else (210, 210, 210)
    cx, cy = x + SQUARE // 2, y + SQUARE // 2
    base = font.render(glyph, True, outline)
    rect = base.get_rect(center=(cx, cy))
    for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
        screen.blit(base, rect.move(ox, oy))
    top = font.render(glyph, True, fill)
    screen.blit(top, top.get_rect(center=(cx, cy)))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Chess  -  N=new  U=undo  A=computer  1/2/3=difficulty  ESC=quit")
    piece_font = pygame.font.SysFont("segoeuisymbol", 64)
    status_font = pygame.font.SysFont("segoeui", 22, bold=True)
    label_font = pygame.font.SysFont("segoeui", 14)
    clock = pygame.time.Clock()
    print(__doc__)

    state = new_state()
    history = []
    selected = None           # (r, c)
    sel_moves = []            # legal moves from selected square
    vs_ai = False
    ai_color = 'b'
    status = 'play'

    # Difficulty -> search depth
    difficulty = {1: ('Easy', 2), 2: ('Medium', 3), 3: ('Hard', 4)}
    diff_level = 2
    ai_thread = None
    ai_holder = [None]

    def refresh_status():
        nonlocal status
        status = game_status(state)

    def cancel_ai():
        """Stop tracking any in-flight search (its result will be discarded)."""
        nonlocal ai_thread
        ai_thread = None

    while True:
        thinking = vs_ai and state['turn'] == ai_color and status == 'play'

        # Drive the computer's move in a background thread so the UI stays live.
        if thinking:
            if ai_thread is None:
                ai_holder = [None]
                snapshot = copy.deepcopy(state)
                depth = difficulty[diff_level][1]

                def _search(holder=ai_holder, st=snapshot, d=depth):
                    holder[0] = ai_move(st, d)

                ai_thread = threading.Thread(target=_search, daemon=True)
                ai_thread.start()
            elif not ai_thread.is_alive():
                mv = ai_holder[0]
                ai_thread = None
                # Only apply if still legal (guards against undo/new-game races).
                if mv and mv in legal_moves(state):
                    history.append(copy.deepcopy(state))
                    state = apply_move(state, mv)
                    selected, sel_moves = None, []
                    refresh_status()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                elif event.key == pygame.K_n:
                    cancel_ai()
                    state = new_state(); history = []
                    selected, sel_moves, status = None, [], 'play'
                elif event.key == pygame.K_u and history:
                    cancel_ai()
                    state = history.pop()
                    # When playing the computer, undo the pair of plies.
                    if vs_ai and state['turn'] == ai_color and history:
                        state = history.pop()
                    selected, sel_moves = None, []
                    refresh_status()
                elif event.key == pygame.K_a:
                    cancel_ai()
                    vs_ai = not vs_ai
                    ai_color = enemy(state['turn']) if vs_ai else 'b'
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    cancel_ai()
                    diff_level = {pygame.K_1: 1, pygame.K_2: 2, pygame.K_3: 3}[event.key]
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 \
                    and status == 'play':
                if vs_ai and state['turn'] == ai_color:
                    continue
                mx, my = event.pos
                c = mx // SQUARE
                r = (my - MARGIN_TOP) // SQUARE
                if not in_bounds(r, c):
                    continue
                # Click a destination?
                chosen = [m for m in sel_moves if m[2] == r and m[3] == c]
                if chosen:
                    history.append(copy.deepcopy(state))
                    state = apply_move(state, chosen[0])
                    selected, sel_moves = None, []
                    refresh_status()
                else:
                    p = state['board'][r][c]
                    if p and p[0] == state['turn']:
                        selected = (r, c)
                        sel_moves = [m for m in legal_moves(state)
                                     if m[0] == r and m[1] == c]
                    else:
                        selected, sel_moves = None, []

        # ---- draw ----
        screen.fill(BG)
        check_sq = None
        if in_check(state, state['turn']):
            check_sq = find_king(state['board'], state['turn'])

        for r in range(8):
            for c in range(8):
                x, y = c * SQUARE, r * SQUARE + MARGIN_TOP
                color = LIGHT if (r + c) % 2 == 0 else DARK
                if check_sq == (r, c):
                    color = CHECK_COL
                pygame.draw.rect(screen, color, (x, y, SQUARE, SQUARE))
                if selected == (r, c):
                    s = pygame.Surface((SQUARE, SQUARE), pygame.SRCALPHA)
                    s.fill((*HILITE, 140))
                    screen.blit(s, (x, y))
                p = state['board'][r][c]
                if p:
                    draw_piece(screen, piece_font, p, x, y)

        # legal-move markers
        for m in sel_moves:
            x = m[3] * SQUARE + SQUARE // 2
            y = m[2] * SQUARE + MARGIN_TOP + SQUARE // 2
            capture = state['board'][m[2]][m[3]] is not None or m[4] == 'ep'
            if capture:
                pygame.draw.circle(screen, MOVE_DOT, (x, y), SQUARE // 2 - 4, 4)
            else:
                dot = pygame.Surface((SQUARE, SQUARE), pygame.SRCALPHA)
                pygame.draw.circle(dot, (*MOVE_DOT, 120), (SQUARE // 2, SQUARE // 2), 12)
                screen.blit(dot, (m[3] * SQUARE, m[2] * SQUARE + MARGIN_TOP))

        # file / rank labels
        for i in range(8):
            f = label_font.render("abcdefgh"[i], True, TEXT_COL)
            screen.blit(f, (i * SQUARE + SQUARE - 14, HEIGHT - 18))
            rk = label_font.render(str(8 - i), True, TEXT_COL)
            screen.blit(rk, (2, i * SQUARE + MARGIN_TOP + 2))

        # status bar
        turn_name = "White" if state['turn'] == 'w' else "Black"
        if status == 'checkmate':
            winner = "Black" if state['turn'] == 'w' else "White"
            msg = f"Checkmate - {winner} wins!   (N = new game)"
        elif status == 'stalemate':
            msg = "Stalemate - draw   (N = new game)"
        elif thinking:
            msg = f"Computer is thinking...  ({difficulty[diff_level][0]})"
        else:
            chk = "  (check!)" if check_sq else ""
            mode = f"  vs Computer [{difficulty[diff_level][0]}]" if vs_ai else "  (2 players)"
            msg = f"{turn_name} to move{chk}{mode}"
        screen.blit(status_font.render(msg, True, TEXT_COL), (10, 12))

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
