"""Real-world application case study: fault-tolerant strong planning as AND/OR search.

A robot must reach a goal cell within a step horizon H. Actuation is reliable
EXCEPT that an adversarial environment may divert (slip) at most B actions to a
perpendicular neighbour ("k-fault" / fault-tolerant planning). We ask the PNS
family to PROVE a *strong plan* exists: a policy that reaches the goal for every
way the adversary spends its B faults.

Mapping to AND/OR search (same Game interface as the board domains):
  * OR node  (player 0 = robot): choose a direction.
  * AND node (player 1 = environment): realise the intended cell for free, or
    spend one of its remaining faults to divert to a perpendicular cell.
  * WIN  = robot on the goal (strong plan succeeds);
    LOSS = horizon exhausted first.

Recognised problem class (fault-tolerant / robust planning, planning for k
failures). Transposition-heavy (same (cell,steps,faults) reached many ways ->
exercises lambda), depth-sensitive (-> R), with a distance/time/faults
heuristic (-> data-driven leaf init).
"""
from __future__ import annotations
import random
from games import Game, WIN, LOSS, ONGOING

_DIRS = [(0, -1), (0, 1), (-1, 0), (1, 0)]            # N, S, W, E
_PERP = {0: [(-1, 0), (1, 0)], 1: [(-1, 0), (1, 0)],
         2: [(0, -1), (0, 1)], 3: [(0, -1), (0, 1)]}


class FONDGrid(Game):
    """Fault-tolerant reachability on a grid.

    State = (pos, steps, pending_dir, faults_left):
      pending_dir is None  -> robot's turn (OR);
      pending_dir is an int -> environment's turn (AND).
    """

    def __init__(self, w, h, start, goal, obstacles, horizon, max_faults=1):
        self.w, self.h = w, h
        self.start, self.goal = start, goal
        self.obstacles = frozenset(obstacles)
        self.horizon = horizon
        self.max_faults = max_faults
        self.name = f"fond{w}x{h}_H{horizon}_B{max_faults}"

    def initial_state(self):
        return (self.start, 0, None, self.max_faults)

    def player_to_move(self, state):
        return 0 if state[2] is None else 1

    def _free(self, cell):
        x, y = cell
        return 0 <= x < self.w and 0 <= y < self.h and cell not in self.obstacles

    def _dest(self, pos, vec):
        nx = (pos[0] + vec[0], pos[1] + vec[1])
        return nx if self._free(nx) else pos            # bump = stay

    def legal_moves(self, state):
        pos, steps, pending, faults = state
        if pending is None:
            return [0, 1, 2, 3]
        intended = self._dest(pos, _DIRS[pending])
        outs = [intended]                                # free, deterministic
        if faults > 0:
            for pv in _PERP[pending]:
                c = self._dest(pos, pv)
                if c != intended and c not in outs:
                    outs.append(c)                       # costs one fault
        return outs

    def apply(self, state, move):
        pos, steps, pending, faults = state
        if pending is None:
            return (pos, steps, move, faults)            # robot commits a direction
        intended = self._dest(pos, _DIRS[pending])
        cost = 0 if move == intended else 1              # diversion spends a fault
        return (move, steps + 1, None, faults - cost)

    def terminal(self, state):
        pos, steps, pending, faults = state
        if pos == self.goal:
            return WIN
        if steps >= self.horizon:
            return LOSS
        return ONGOING

    def features(self, state):
        pos, steps, pending, faults = state
        md = abs(pos[0] - self.goal[0]) + abs(pos[1] - self.goal[1])
        time_left = (self.horizon - steps) / max(1, self.horizon)
        closeness = 1.0 - md / max(1, self.w + self.h)
        fault_frac = faults / max(1, self.max_faults)
        return [1.0, time_left, closeness, fault_frac]


def random_instance(w, h, obstacle_density, horizon, seed, max_faults=1):
    rng = random.Random(seed)
    cells = [(x, y) for x in range(w) for y in range(h)]
    start = rng.choice(cells)
    goal = rng.choice([c for c in cells if c != start])
    obstacles = {c for c in cells if c not in (start, goal) and rng.random() < obstacle_density}
    return FONDGrid(w, h, start, goal, obstacles, horizon, max_faults)
