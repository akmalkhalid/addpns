"""Depth-first PNS (df-pn) and PN2 baselines on the same Game interface.

Both return the same result dict shape as engine.PNSEngine.solve() so they slot
directly into the benchmark/ablation runner.

- df-pn: Nagai/Kishimoto threshold-controlled depth-first search with a (pn,dn)
  transposition table. Memory ~ TT size; may RE-expand nodes (its known
  time-vs-memory trade-off), which we count honestly in nodes_expanded.
- PN2: two-level best-first PNS. Level-1 leaves are evaluated by a bounded
  level-2 PNS whose tree is then discarded -> small level-1 footprint (low
  peak_nodes), at the cost of extra node generations.
"""
import sys, time
from engine import PNSEngine, Config, INF, _cap
from games import WIN

sys.setrecursionlimit(1_000_000)


class DFPNSolver:
    def __init__(self, game, max_nodes=2_000_000, max_seconds=0.0, start_state=None):
        self.game = game
        self.max_nodes = max_nodes
        self.max_seconds = max_seconds
        self.start_state = start_state
        self._deadline = None
        self.tt = {}                # state -> (pn, dn)
        self.nodes_expanded = 0
        self.aborted = False

    def _is_or(self, state):
        return self.game.player_to_move(state) == 0

    def _eval_terminal(self, state):
        t = self.game.terminal(state)
        if t is None:
            return None
        return (0, INF) if t == WIN else (INF, 0)

    def _lookup(self, state):
        if state in self.tt:
            return self.tt[state]
        term = self._eval_terminal(state)
        return term if term is not None else (1, 1)

    def solve(self):
        t0 = time.perf_counter()
        if self.max_seconds:
            self._deadline = t0 + self.max_seconds
        root = self.start_state if self.start_state is not None else self.game.initial_state()
        self._mid(root, INF, INF)
        pn, dn = self._lookup(root)
        res = "PROVEN" if pn == 0 else "DISPROVEN" if dn == 0 else "UNRESOLVED"
        if self.aborted and res == "UNRESOLVED":
            res = "UNRESOLVED"
        return {"result": res, "nodes_expanded": self.nodes_expanded,
                "nodes_created": self.nodes_expanded, "time_s": time.perf_counter() - t0,
                "peak_nodes": len(self.tt), "tt_hit_rate": 0.0,
                "root_pn": pn, "root_dn": dn}

    def _mid(self, state, pn_t, dn_t):
        if self.nodes_expanded >= self.max_nodes or \
           (self._deadline is not None and time.perf_counter() > self._deadline):
            self.aborted = True
            return
        term = self._eval_terminal(state)
        if term is not None:
            self.tt[state] = term
            return
        is_or = self._is_or(state)
        moves = self.game.legal_moves(state)
        children = [self.game.apply(state, m) for m in moves]
        self.nodes_expanded += 1                 # one (re)generation = one expansion
        while True:
            if self.nodes_expanded >= self.max_nodes or \
               (self._deadline is not None and time.perf_counter() > self._deadline):
                self.aborted = True
                return
            cv = [self._lookup(c) for c in children]   # (pn,dn) per child
            if is_or:
                pn = min(p for p, _ in cv)
                dn = min(INF, sum(d for _, d in cv))
            else:
                pn = min(INF, sum(p for p, _ in cv))
                dn = min(d for _, d in cv)
            if pn >= pn_t or dn >= dn_t:
                self.tt[state] = (pn, dn)
                return
            # choose child to descend + compute its thresholds
            if is_or:
                # pn determined by min child pn; dn is the sum
                idx = min(range(len(cv)), key=lambda i: cv[i][0])
                pns = sorted(p for p, _ in cv)
                pn2 = pns[1] if len(pns) > 1 else INF
                c_pn_t = min(pn_t, pn2 + 1)
                c_dn_t = dn_t - (dn - cv[idx][1])
            else:
                idx = min(range(len(cv)), key=lambda i: cv[i][1])
                dns = sorted(d for _, d in cv)
                dn2 = dns[1] if len(dns) > 1 else INF
                c_dn_t = min(dn_t, dn2 + 1)
                c_pn_t = pn_t - (pn - cv[idx][0])
            self._mid(children[idx], c_pn_t, c_dn_t)


def dfpn_solve(game, max_nodes=2_000_000, max_seconds=0.0, start_state=None):
    return DFPNSolver(game, max_nodes, max_seconds, start_state).solve()


def pn2_solve(game, max_nodes=2_000_000, level2_cap=20000, max_seconds=0.0, start_state=None):
    """Two-level PNS. Level-1 is best-first PNS; each level-1 leaf is evaluated
    by a bounded level-2 PNS (tree discarded). We реuse PNSEngine for level-2 by
    rooting it at the leaf state. nodes_expanded sums both levels; peak_nodes is
    the level-1 footprint (PN2's selling point)."""
    from engine import PNSEngine
    # Level-1 engine with a hooked leaf evaluator
    eng = PNSEngine(game, Config(backup="sum", selection="standard", max_nodes=max_nodes,
                                max_seconds=max_seconds), start_state=start_state)
    l2_nodes = [0]
    orig_eval = eng._evaluate_leaf

    def eval_leaf(n):
        term = game.terminal(n.state)
        if term is not None:
            orig_eval(n); return
        # bounded level-2 search rooted at this leaf
        g2 = type(game).__new__(type(game)); g2.__dict__.update(game.__dict__)
        g2.initial_state = lambda s=n.state: s
        budget = min(level2_cap, max(50, eng.nodes_expanded))
        sub = PNSEngine(g2, Config(backup="sum", selection="standard", max_nodes=budget,
                                   max_seconds=(max_seconds * 0.1 if max_seconds else 0.0)))
        out = sub.solve()
        l2_nodes[0] += out["nodes_expanded"]
        if out["result"] == "PROVEN":
            n.pn, n.dn = 0, INF
        elif out["result"] == "DISPROVEN":
            n.pn, n.dn = INF, 0
        else:
            n.pn, n.dn = max(1, out["root_pn"]), max(1, out["root_dn"])
    eng._evaluate_leaf = eval_leaf
    out = eng.solve()
    out["nodes_expanded"] += l2_nodes[0]
    return out


# =========================================================================== #
# ADD-df-pn: data-driven, graph-aware df-pn (the proposed method on the strong
# substrate). Adds (1) data-driven leaf initialization and (2) lambda-blend
# graph-aware backup on top of df-pn's transposition table.
#
# Soundness: proven/disproven (0/INF) propagation is exact (0 iff all children 0,
# INF if any child INF), so the game value is unchanged. The blend and the data
# init only affect effort estimates / search order. Child thresholds are CLAMPED
# to (child_value+1 .. parent_threshold) to guarantee strict progress, so the
# search still terminates regardless of the blend. Verified by test_correctness
# and test_reroot.
# =========================================================================== #
import math as _math


class CDFPN:
    def __init__(self, game, max_nodes=2_000_000, max_seconds=0.0, start_state=None,
                 leaf_model=None, beta=4.0, backup="sum",
                 lambda_mode="adaptive", lambda_value=0.0):
        self.game = game
        self.max_nodes = max_nodes
        self.max_seconds = max_seconds
        self.start_state = start_state
        self.leaf_model = leaf_model
        self.beta = beta
        self.backup = backup                 # "sum" | "blend"
        self.lambda_mode = lambda_mode       # "adaptive" | "fixed"
        self.lambda_value = lambda_value
        self.tt = {}
        self.tt_lookups = 0
        self.tt_hits = 0
        self.nodes_expanded = 0
        self.aborted = False
        self._deadline = None

    def _is_or(self, state):
        return self.game.player_to_move(state) == 0

    def _eval_terminal(self, state):
        t = self.game.terminal(state)
        if t is None:
            return None
        return (0, INF) if t == WIN else (INF, 0)

    def _leaf_init(self, state):
        if self.leaf_model is None:
            return (1, 1)
        p = self.leaf_model(self.game.features(state))
        p = min(max(p, 1e-3), 1 - 1e-3)
        return (max(1, _math.ceil(1 + self.beta * (1 - p))),
                max(1, _math.ceil(1 + self.beta * p)))

    def _lookup(self, state):
        self.tt_lookups += 1
        if state in self.tt:
            self.tt_hits += 1
            return self.tt[state]
        term = self._eval_terminal(state)
        return term if term is not None else self._leaf_init(state)

    def _lam(self):
        if self.lambda_mode == "fixed":
            return self.lambda_value
        return self.tt_hits / self.tt_lookups if self.tt_lookups else 0.0

    def _blend(self, vals):
        """Summation side (dn at OR, pn at AND) with graph-aware bound.
        Exact on solved children: INF if any INF, 0 iff all zero."""
        if any(v >= INF for v in vals):
            return INF
        live = [v for v in vals if v > 0]
        if not live:
            return 0
        S = _cap(sum(vals))
        if self.backup == "sum":
            return S
        W = _cap(max(live) + (len(live) - 1))
        lam = self._lam()
        return _cap(_math.ceil((1 - lam) * S + lam * W))

    def solve(self):
        import time as _time
        t0 = _time.perf_counter()
        if self.max_seconds:
            self._deadline = t0 + self.max_seconds
        root = self.start_state if self.start_state is not None else self.game.initial_state()
        self._mid(root, INF, INF)
        pn, dn = self._lookup(root)
        res = "PROVEN" if pn == 0 else "DISPROVEN" if dn == 0 else "UNRESOLVED"
        return {"result": res, "nodes_expanded": self.nodes_expanded,
                "nodes_created": self.nodes_expanded, "time_s": _time.perf_counter() - t0,
                "peak_nodes": len(self.tt),
                "tt_hit_rate": (self.tt_hits / self.tt_lookups) if self.tt_lookups else 0.0,
                "root_pn": pn, "root_dn": dn}

    def _over(self):
        import time as _time
        return (self.nodes_expanded >= self.max_nodes or
                (self._deadline is not None and _time.perf_counter() > self._deadline))

    def _mid(self, state, pn_t, dn_t):
        if self._over():
            self.aborted = True; return
        term = self._eval_terminal(state)
        if term is not None:
            self.tt[state] = term; return
        is_or = self._is_or(state)
        moves = self.game.legal_moves(state)
        children = [self.game.apply(state, m) for m in moves]
        self.nodes_expanded += 1
        while True:
            if self._over():
                self.aborted = True; return
            cv = [self._lookup(c) for c in children]
            if is_or:
                pn = min(p for p, _ in cv)
                dn = self._blend([d for _, d in cv])
            else:
                dn = min(d for _, d in cv)
                pn = self._blend([p for p, _ in cv])
            if pn >= pn_t or dn >= dn_t:
                self.tt[state] = (pn, dn); return
            if is_or:
                idx = min(range(len(cv)), key=lambda i: cv[i][0])
                pns = sorted(p for p, _ in cv)
                pn2 = pns[1] if len(pns) > 1 else INF
                c_pn_t = min(pn_t, pn2 + 1)
                c_dn_t = dn_t - (dn - cv[idx][1])
                c_dn_t = max(cv[idx][1] + 1, min(dn_t, c_dn_t))   # clamp -> strict progress
            else:
                idx = min(range(len(cv)), key=lambda i: cv[i][1])
                dns = sorted(d for _, d in cv)
                dn2 = dns[1] if len(dns) > 1 else INF
                c_dn_t = min(dn_t, dn2 + 1)
                c_pn_t = pn_t - (pn - cv[idx][0])
                c_pn_t = max(cv[idx][0] + 1, min(pn_t, c_pn_t))
            self._mid(children[idx], c_pn_t, c_dn_t)


def adfpn_solve(game, max_nodes=2_000_000, max_seconds=0.0, start_state=None,
                leaf_model=None, beta=4.0, backup="blend",
                lambda_mode="adaptive", lambda_value=0.0):
    return CDFPN(game, max_nodes, max_seconds, start_state, leaf_model, beta,
                 backup, lambda_mode, lambda_value).solve()
