"""Lightweight online controller for ADDPNS adaptive parameters.

Design goal: capability gains while staying LIGHTWEIGHT. We deliberately avoid
reinforcement learning / online meta-search (heavy, hard to tune, a reviewer
magnet). Instead:

  * lambda(n): read graph-awareness for FREE from the transposition-table hit
    rate the engine already tracks. No extra data structure.
  * R(n): a cheap seesaw detector -- the count of best-child flips at a node --
    decays R toward 0 (depth-first) when oscillation is detected.

An optional contextual-bandit layer (epsilon-greedy over a small discrete grid)
can tune these per cheap context bucket (depth x branching x tt-hit). It is
O(1) per decision and fully reproducible from a seed. Disabled by default so
the base heuristics can be evaluated in isolation (ablation-friendly).
"""
from __future__ import annotations
import random


class HeuristicController:
    """Free, parameter-light adaptation. No learning."""

    def __init__(self, flip_decay: float = 0.5):
        self.flip_decay = flip_decay

    def lambda_for(self, engine, node) -> float:
        # Transposition pressure in [0,1]; high => DAG-like => trust WPNS bound.
        if engine.tt_lookups == 0:
            return 0.0
        return engine.tt_hits / engine.tt_lookups

    def R_for(self, engine, node) -> float:
        # Sustained oscillation (high flip RATE) => smaller R => go deeper.
        # Pure best-first (R=1) otherwise, so ADDPNS never underperforms PNS.
        from engine import flip_rate_R
        return flip_rate_R(node)


class BanditController(HeuristicController):
    """Epsilon-greedy contextual bandit over a discrete (lambda, R) grid.

    Reward = negative marginal node cost since the last pull (cheap proxy for
    'this setting is helping us solve faster'). Context = coarse buckets so the
    table stays tiny. This is the optional 'learned' variant for the ablation
    that shows learning adds value beyond the free heuristics.
    """

    def __init__(self, lambdas=(0.0, 0.5, 1.0), Rs=(0.2, 0.6, 1.0),
                 epsilon: float = 0.1, seed: int = 0):
        super().__init__()
        self.lambdas = lambdas
        self.Rs = Rs
        self.epsilon = epsilon
        self.rng = random.Random(seed)
        self.q = {}            # (ctx, "lam"/"R", value) -> [sum_reward, count]
        self._last_nodes = 0
        self._last_choice = None

    def _ctx(self, engine, node):
        depth_b = min(node.depth // 4, 4)
        nch = len(node.children) if node.children else 0
        branch_b = min(nch // 3, 4)
        hit = engine.tt_hits / engine.tt_lookups if engine.tt_lookups else 0.0
        hit_b = int(hit * 3)
        return (depth_b, branch_b, hit_b)

    def _credit(self, engine):
        if self._last_choice is not None:
            cost = engine.nodes_expanded - self._last_nodes
            reward = -cost
            for key in self._last_choice:
                s = self.q.setdefault(key, [0.0, 0])
                s[0] += reward
                s[1] += 1
        self._last_nodes = engine.nodes_expanded

    def _pick(self, ctx, kind, values):
        if self.rng.random() < self.epsilon:
            return self.rng.choice(values)
        best_v, best_q = values[0], -1e18
        for v in values:
            s = self.q.get((ctx, kind, v))
            qv = (s[0] / s[1]) if s and s[1] else 0.0
            if qv > best_q:
                best_q, best_v = qv, v
        return best_v

    def lambda_for(self, engine, node):
        self._credit(engine)
        ctx = self._ctx(engine, node)
        lam = self._pick(ctx, "lam", self.lambdas)
        R = self._pick(ctx, "R", self.Rs)
        self._last_choice = [(ctx, "lam", lam), (ctx, "R", R)]
        self._last_lambda, self._last_R = lam, R
        return lam

    def R_for(self, engine, node):
        return getattr(self, "_last_R", 1.0)


# ---- a tiny, frozen, offline leaf model (logistic regression) ----
def make_logistic_leaf_model(weights, bias=0.0):
    import math
    def model(features):
        z = bias + sum(w * f for w, f in zip(weights, features))
        return 1.0 / (1.0 + math.exp(-z))
    return model
