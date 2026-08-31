"""Configurable Proof-Number Search engine for the ADDPNS study.

One engine, many algorithms via a Config object:
  - leaf_init:  "uniform" (classic 1/1) | "data" (1 + beta * model)
  - backup:     "sum" (classic PNS) | "wpns" | "blend" (lambda mix)
  - selection:  "standard" (min pn/dn) | "deeppn" (depth-aware E-score)
  - lambda_mode / R_mode: "fixed" or "adaptive" (controller-driven)

Effort numbers affect SEARCH ORDER ONLY; the proven/disproven value returned is
independent of them, so every configuration is sound (the unit-test invariant).
Primary metric: nodes_expanded (hardware independent).
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import time

from games import Game, WIN, LOSS, DRAW

INF = 1_000_000_000


def _cap(x):
    return INF if x >= INF else x


def flip_rate_R(n, tau=0.30, rmin=0.2, alpha=2.0, warmup=8):
    """R recovery rule: pure best-first (R=1) until SUSTAINED oscillation.

    flip_rate = best-child changes / visits. Below tau (or during warmup) R=1,
    so ADDPNS reduces exactly to best-first PNS selection on easy positions.
    Above tau, R decays toward rmin to force depth-first penetration.
    """
    if n.visits < warmup:
        return 1.0
    rate = n.flips / n.visits
    if rate <= tau:
        return 1.0
    return max(rmin, 1.0 - alpha * (rate - tau))


@dataclass
class Config:
    leaf_init: str = "uniform"
    backup: str = "sum"
    selection: str = "standard"
    lambda_mode: str = "fixed"
    lambda_value: float = 0.0
    R_mode: str = "fixed"
    R_value: float = 1.0
    beta: float = 4.0
    leaf_model: object = None
    # Freeze the adaptive lambda at its value after this many table look-ups
    # (0 = never freeze). Provided so that readers who prefer strictly monotone
    # effort estimates can have them; see the Monotonicity discussion in the
    # paper. Soundness is unaffected either way.
    lambda_freeze_after: int = 0
    max_nodes: int = 2_000_000
    max_seconds: float = 0.0


class Node:
    __slots__ = ("state", "is_or", "depth", "children", "expanded",
                 "pn", "dn", "deep", "parent", "flips", "best_child", "visits")

    def __init__(self, state, is_or, depth, parent):
        self.state = state
        self.is_or = is_or
        self.depth = depth
        self.parent = parent
        self.children = None
        self.expanded = False
        self.pn = 1
        self.dn = 1
        self.deep = 1.0 / (depth + 1)
        self.flips = 0
        self.visits = 0
        self.best_child = None


class PNSEngine:
    def __init__(self, game, config, controller=None, start_state=None):
        self.game = game
        self.start_state = start_state
        self.cfg = config
        self.controller = controller
        self.nodes_created = 0
        self.nodes_expanded = 0
        self.tt_lookups = 0
        self.tt_hits = 0
        self._tt = {}
        self.peak_nodes = 0
        self._lambda_frozen = None

    def solve(self):
        g, cfg = self.game, self.cfg
        root_state = self.start_state if self.start_state is not None else g.initial_state()
        root = self._make_node(root_state, g.player_to_move(root_state) == 0, 0, None)
        self._evaluate_leaf(root)
        t0 = time.perf_counter()
        deadline = t0 + cfg.max_seconds if cfg.max_seconds else None
        i = 0
        while root.pn != 0 and root.dn != 0 and self.nodes_expanded < cfg.max_nodes:
            mpn = self._select_most_proving(root)
            self._expand(mpn)
            self._backup(mpn)
            if deadline is not None:
                i += 1
                if (i & 255) == 0 and time.perf_counter() > deadline:
                    break
        elapsed = time.perf_counter() - t0
        result = "PROVEN" if root.pn == 0 else "DISPROVEN" if root.dn == 0 else "UNRESOLVED"
        return {
            "result": result,
            "nodes_expanded": self.nodes_expanded,
            "nodes_created": self.nodes_created,
            "time_s": elapsed,
            "peak_nodes": self.peak_nodes,
            "tt_hit_rate": (self.tt_hits / self.tt_lookups) if self.tt_lookups else 0.0,
            "root_pn": root.pn,
            "root_dn": root.dn,
        }

    def _make_node(self, state, is_or, depth, parent):
        n = Node(state, is_or, depth, parent)
        self.nodes_created += 1
        self.tt_lookups += 1
        cnt = self._tt.get(state, 0)
        if cnt > 0:
            self.tt_hits += 1
        self._tt[state] = cnt + 1
        return n

    def _evaluate_leaf(self, n):
        term = self.game.terminal(n.state)
        if term is not None:
            if term == WIN:
                n.pn, n.dn = 0, INF
            else:
                n.pn, n.dn = INF, 0
            return
        if self.cfg.leaf_init == "data" and self.cfg.leaf_model is not None:
            p = self.cfg.leaf_model(self.game.features(n.state))
            p = min(max(p, 1e-3), 1 - 1e-3)
            n.pn = max(1, math.ceil(1 + self.cfg.beta * (1 - p)))
            n.dn = max(1, math.ceil(1 + self.cfg.beta * p))
        else:
            n.pn, n.dn = 1, 1

    def _expand(self, n):
        self.nodes_expanded += 1
        moves = self.game.legal_moves(n.state)
        n.children = []
        for m in moves:
            cs = self.game.apply(n.state, m)
            cp = self.game.player_to_move(cs)
            child = self._make_node(cs, (cp == 0), n.depth + 1, n)
            self._evaluate_leaf(child)
            n.children.append(child)
        n.expanded = True
        live = len(self._tt)
        if live > self.peak_nodes:
            self.peak_nodes = live

    def _select_most_proving(self, root):
        n = root
        while n.expanded and n.children:
            n = self._pick_child(n)
        return n

    def _pick_child(self, n):
        cfg = self.cfg
        n.visits += 1
        if cfg.selection == "standard":
            if n.is_or:
                best = min(n.children, key=lambda c: (c.pn, c.depth))
            else:
                best = min(n.children, key=lambda c: (c.dn, c.depth))
        else:
            R = self._R_for(n)
            best = min(n.children, key=lambda c: self._escore(c, n, R))
        if n.best_child is not None and n.best_child is not best:
            n.flips += 1
        n.best_child = best
        return best

    def _escore(self, c, parent, R):
        phi = c.pn if parent.is_or else c.dn
        if phi <= 0:
            return 0.0  # solved on the relevant side: most attractive
        phi = min(phi, INF)
        base = max(0.0, 1 - 1.0 / phi)
        return base ** R + c.deep * (1 - R)

    def _backup(self, n):
        cur = n
        while cur is not None:
            self._recompute(cur)
            cur = cur.parent

    def _recompute(self, n):
        if not n.expanded or not n.children:
            return
        lam = self._lambda_for(n)
        ch = n.children
        if n.is_or:
            n.pn = _cap(min(c.pn for c in ch))
            n.dn = self._sum_side([c.dn for c in ch], lam)
        else:
            n.dn = _cap(min(c.dn for c in ch))
            n.pn = self._sum_side([c.pn for c in ch], lam)
        n.deep = min(c.deep for c in ch)

    def _sum_side(self, vals, lam):
        if any(v >= INF for v in vals):
            return INF
        live = [v for v in vals if v > 0]
        if not live:
            return 0
        S = _cap(sum(vals))
        if self.cfg.backup == "sum":
            return S
        W = _cap(max(live) + (len(live) - 1))
        if self.cfg.backup == "wpns":
            return W
        return _cap(math.ceil((1 - lam) * S + lam * W))

    def _lambda_for(self, n):
        if self.cfg.lambda_mode == "fixed":
            return self.cfg.lambda_value
        freeze = self.cfg.lambda_freeze_after
        if freeze:
            if self._lambda_frozen is not None:
                return self._lambda_frozen
            if self.tt_lookups >= freeze:
                self._lambda_frozen = (self.tt_hits / self.tt_lookups
                                       if self.tt_lookups else 0.0)
                return self._lambda_frozen
        if self.controller is not None:
            return self.controller.lambda_for(self, n)
        return self.tt_hits / self.tt_lookups if self.tt_lookups else 0.0

    def _R_for(self, n):
        if self.cfg.R_mode == "fixed":
            return self.cfg.R_value
        if self.controller is not None:
            return self.controller.R_for(self, n)
        return flip_rate_R(n)
