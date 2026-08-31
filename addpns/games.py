"""Game domains for the ADDPNS experimental harness.

Each game exposes a minimal interface the PNS engine needs. States are
immutable, hashable keys so the transposition table can detect repeats
(needed to measure transposition density for the lambda controller).

A "position" is evaluated from the perspective of the player to move at the
ROOT. The PNS root is an OR node: it tries to PROVE that the root player can
force a WIN. Draws count as failure-to-prove (disproof) in this binary setup.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Hashable, List, Optional, Tuple

# Terminal results from the perspective of the player who JUST moved is awkward;
# we report results from the perspective of the ROOT player consistently.
WIN = "WIN"        # root player has won
LOSS = "LOSS"      # root player has lost
DRAW = "DRAW"      # drawn / cannot win
ONGOING = None


class Game(ABC):
    """Abstract two-player, zero-sum, perfect-information game."""

    name: str = "game"

    @abstractmethod
    def initial_state(self) -> Hashable: ...

    @abstractmethod
    def player_to_move(self, state) -> int:
        """0 = root player (OR / attacker), 1 = opponent (AND / defender)."""

    @abstractmethod
    def legal_moves(self, state) -> List: ...

    @abstractmethod
    def apply(self, state, move) -> Hashable: ...

    @abstractmethod
    def terminal(self, state) -> Optional[str]:
        """Return WIN/LOSS/DRAW from the ROOT player's perspective, or None."""

    def features(self, state) -> List[float]:
        """Cheap feature vector for the data-driven leaf model. Override."""
        return [0.0]


# --------------------------------------------------------------------------- #
# Synthetic AND/OR tree: ground-truth control for correctness unit tests.
# --------------------------------------------------------------------------- #
class SyntheticTree(Game):
    """A hand-built AND/OR tree with a known game-theoretic value.

    Spec: dict mapping node_id -> either a terminal string (WIN/LOSS/DRAW)
    or a list of child node_ids. Root is node 0. Layers alternate OR/AND
    starting with OR at the root (depth 0 even => OR/root player to move).
    """

    name = "synthetic"

    def __init__(self, spec: dict, root: int = 0):
        self.spec = spec
        self.root = root

    def initial_state(self):
        return (self.root, 0)  # (node_id, depth)

    def player_to_move(self, state) -> int:
        _, depth = state
        return depth % 2  # 0 => OR/root, 1 => AND/opponent

    def legal_moves(self, state):
        nid, _ = state
        node = self.spec[nid]
        return list(range(len(node))) if isinstance(node, list) else []

    def apply(self, state, move):
        nid, depth = state
        child = self.spec[nid][move]
        return (child, depth + 1)

    def terminal(self, state):
        nid, _ = state
        node = self.spec[nid]
        return node if isinstance(node, str) else None


# --------------------------------------------------------------------------- #
# Connect Four (variable board size). Rich in transpositions => good test for
# the graph-aware (lambda) component.
# --------------------------------------------------------------------------- #
class ConnectFour(Game):
    """Connect Four on a cols x rows board. Goal: root player forces a win.

    State = (tuple of column-stacks, player_to_move). Each column-stack is a
    tuple of pieces from bottom up; piece is 0 (root) or 1 (opponent).
    """

    def __init__(self, cols: int = 5, rows: int = 4, connect: int = 4):
        self.cols = cols
        self.rows = rows
        self.connect = connect
        self.name = f"connect{connect}_{cols}x{rows}"

    def initial_state(self):
        return (tuple(() for _ in range(self.cols)), 0)

    def player_to_move(self, state) -> int:
        return state[1]

    def legal_moves(self, state):
        board, _ = state
        return [c for c in range(self.cols) if len(board[c]) < self.rows]

    def apply(self, state, move):
        board, p = state
        col = board[move] + (p,)
        new_board = board[:move] + (col,) + board[move + 1:]
        return (new_board, 1 - p)

    def _last_player(self, state):
        # The player who just moved is the opponent of player_to_move.
        return 1 - state[1]

    def terminal(self, state):
        board, p = state
        mover = 1 - p  # who just moved and could have completed a line
        if self._has_line(board, mover):
            return WIN if mover == 0 else LOSS
        if all(len(board[c]) == self.rows for c in range(self.cols)):
            return DRAW
        return ONGOING

    def _has_line(self, board, player) -> bool:
        cols, rows, k = self.cols, self.rows, self.connect
        def cell(c, r):
            return board[c][r] if r < len(board[c]) else None
        for c in range(cols):
            for r in range(rows):
                if cell(c, r) != player:
                    continue
                for dc, dr in ((1, 0), (0, 1), (1, 1), (1, -1)):
                    cnt = 1
                    cc, rr = c + dc, r + dr
                    while 0 <= cc < cols and 0 <= rr < rows and cell(cc, rr) == player:
                        cnt += 1
                        if cnt >= k:
                            return True
                        cc += dc
                        rr += dr
        return False

    def features(self, state):
        """Cheap features for the leaf model: mobility + center control."""
        board, p = state
        mobility = len(self.legal_moves(state))
        center = self.cols // 2
        center_root = sum(1 for piece in board[center] if piece == 0)
        center_opp = sum(1 for piece in board[center] if piece == 1)
        filled = sum(len(col) for col in board)
        return [1.0, mobility / self.cols, (center_root - center_opp) / self.rows,
                filled / (self.cols * self.rows)]


# --------------------------------------------------------------------------- #
# Hex: connection game, NO draws, classic seesaw domain (exercises R).
# Player 0 (root) connects top<->bottom; player 1 connects left<->right.
# --------------------------------------------------------------------------- #
class Hex(Game):
    _NB = ((-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0))

    def __init__(self, size: int = 4):
        self.size = size
        self.name = f"hex{size}"

    def initial_state(self):
        return (tuple([None] * (self.size * self.size)), 0)

    def player_to_move(self, state) -> int:
        return state[1]

    def legal_moves(self, state):
        board, _ = state
        return [i for i, v in enumerate(board) if v is None]

    def apply(self, state, move):
        board, p = state
        nb = board[:move] + (p,) + board[move + 1:]
        return (nb, 1 - p)

    def _connected(self, board, player) -> bool:
        n = self.size
        # BFS from one side to the other through `player` stones.
        from collections import deque
        seen = set()
        dq = deque()
        for k in range(n):
            idx = (0 * n + k) if player == 0 else (k * n + 0)
            if board[idx] == player:
                seen.add(idx); dq.append(idx)
        while dq:
            cur = dq.popleft()
            r, c = divmod(cur, n)
            at_goal = (r == n - 1) if player == 0 else (c == n - 1)
            if at_goal:
                return True
            for dr, dc in self._NB:
                nr, nc = r + dr, c + dc
                if 0 <= nr < n and 0 <= nc < n:
                    ni = nr * n + nc
                    if ni not in seen and board[ni] == player:
                        seen.add(ni); dq.append(ni)
        return False

    def terminal(self, state):
        board, _ = state
        if self._connected(board, 0):
            return WIN
        if self._connected(board, 1):
            return LOSS
        return ONGOING  # Hex cannot draw

    def features(self, state):
        board, p = state
        empty = sum(1 for v in board if v is None)
        return [1.0, empty / (self.size * self.size)]


# --------------------------------------------------------------------------- #
# Othello (compact): DAG + draws possible (exercises lambda and draw handling).
# Best set up as ENDGAME positions (few empties) for tractable solving.
# --------------------------------------------------------------------------- #
class Othello(Game):
    _DIRS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))

    def __init__(self, size: int = 6):
        self.size = size
        self.name = f"othello{size}"

    def initial_state(self):
        n = self.size
        b = [None] * (n * n)
        m = n // 2
        b[(m - 1) * n + (m - 1)] = 1
        b[(m - 1) * n + m] = 0
        b[m * n + (m - 1)] = 0
        b[m * n + m] = 1
        return (tuple(b), 0, False)  # (board, player_to_move, last_passed)

    def player_to_move(self, state) -> int:
        return state[1]

    def _flips(self, board, idx, p):
        n = self.size
        r, c = divmod(idx, n)
        gained = []
        for dr, dc in self._DIRS:
            line = []
            nr, nc = r + dr, c + dc
            while 0 <= nr < n and 0 <= nc < n and board[nr * n + nc] == (1 - p):
                line.append(nr * n + nc); nr += dr; nc += dc
            if line and 0 <= nr < n and 0 <= nc < n and board[nr * n + nc] == p:
                gained.extend(line)
        return gained

    def _legal(self, board, p):
        return [i for i, v in enumerate(board) if v is None and self._flips(board, i, p)]

    def legal_moves(self, state):
        board, p, _ = state
        mv = self._legal(board, p)
        return mv if mv else ["PASS"]

    def apply(self, state, move):
        board, p, last_passed = state
        if move == "PASS":
            return (board, 1 - p, True)
        gained = self._flips(board, move, p)
        b = list(board)
        b[move] = p
        for g in gained:
            b[g] = p
        return (tuple(b), 1 - p, False)

    def terminal(self, state):
        board, p, last_passed = state
        full = all(v is not None for v in board)
        no_moves = not self._legal(board, p)
        ended = full or (no_moves and last_passed)
        if not ended:
            return ONGOING
        s0 = sum(1 for v in board if v == 0)
        s1 = sum(1 for v in board if v == 1)
        if s0 > s1:
            return WIN
        if s0 < s1:
            return LOSS
        return DRAW

    def features(self, state):
        board, p, _ = state
        s0 = sum(1 for v in board if v == 0)
        s1 = sum(1 for v in board if v == 1)
        tot = s0 + s1 or 1
        return [1.0, (s0 - s1) / tot]
