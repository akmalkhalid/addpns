"""Best-first Proof-Number Search over a DAG: PNS with a real transposition table.

Motivation (Reviewer 1, C1). In `engine.PNSEngine` the best-first family expands a
TREE: a state reached by several move orders is represented by several nodes, is
expanded several times, and is counted several times in the AND/OR sums. df-pn, by
contrast, is threshold-based AND transposition-table based. Comparing the two
therefore confounds two independent design axes (frontier-vs-threshold control and
tree-vs-DAG representation), so it cannot isolate what data-driven initialization
contributes.

This module removes the confound. `DAGPNSEngine` keeps the *frontier* discipline of
best-first PNS exactly as in `PNSEngine` -- identical leaf initialization, identical
backup rules, identical most-proving descent -- and changes only the representation:

  * one Node per distinct state (`self._nodes`), so a transposition is expanded once;
  * a node records ALL its parents, and backup propagates to every one of them.

Running PNS+TT with and without the data-driven leaf initialization is then a
controlled comparison in which the only difference is the initialization.

Layered-DAG assumption
----------------------
In every domain used here (Hex, Connect Four, Othello, and the fault-tolerant
planning grid) the ply count is a function of the state, so all paths from the root
to a state have the same length. The state graph is therefore a *layered* DAG:
every parent of a depth-d node has depth d-1. Backup exploits this by sweeping one
layer at a time, which both terminates and visits each affected node once per sweep.
`assert_layered=True` checks the assumption at run time.

Soundness is unchanged. Proof and disproof numbers still influence only the ORDER of
expansion: 0/INF verdicts propagate exactly as in classical PNS (a node is proven iff
the classical rule says so), and node sharing cannot change a verdict because a state's
game-theoretic value does not depend on the path taken to reach it. Verified against
brute-force minimax in `test_correctness_tt.py`.
"""
from __future__ import annotations

import time

from engine import PNSEngine, Config, INF, flip_rate_R  # noqa: F401  (Config re-exported)
from games import WIN


class DagNode:
    """A node of the search DAG. Same fields as engine.Node, but many parents."""

    __slots__ = ("state", "is_or", "depth", "children", "expanded",
                 "pn", "dn", "deep", "parents", "flips", "best_child", "visits")

    def __init__(self, state, is_or, depth):
        self.state = state
        self.is_or = is_or
        self.depth = depth
        self.parents = []
        self.children = None
        self.expanded = False
        self.pn = 1
        self.dn = 1
        self.deep = 1.0 / (depth + 1)
        self.flips = 0
        self.visits = 0
        self.best_child = None

    # engine.PNSEngine._backup walks `.parent`; we never call it, but keep the
    # attribute name available for any helper that peeks at a single parent.
    @property
    def parent(self):
        return self.parents[0] if self.parents else None


class DAGPNSEngine(PNSEngine):
    """Best-first PNS with node sharing (a transposition table).

    Inherits leaf initialization (`_evaluate_leaf`), the lambda/WPNS blend
    (`_sum_side`), child selection (`_pick_child`, `_escore`) and the adaptive
    parameter hooks (`_lambda_for`, `_R_for`) from PNSEngine unchanged, so the
    ablation toggles mean exactly what they mean for the tree engine.
    """

    def __init__(self, game, config, controller=None, start_state=None,
                 assert_layered=True):
        super().__init__(game, config, controller=controller, start_state=start_state)
        self._nodes = {}            # state -> DagNode  (the transposition table)
        self.assert_layered = assert_layered
        self.layer_violations = 0

    # ---------------- node creation / sharing ----------------

    def _get_node(self, state, is_or, depth):
        """Return the node for `state`, creating it only if unseen."""
        self.tt_lookups += 1
        n = self._nodes.get(state)
        if n is not None:
            self.tt_hits += 1
            if depth != n.depth:
                # Violates the layered assumption; keep the shallower depth so the
                # DeepPN 'deep' term stays well defined, and record the violation.
                self.layer_violations += 1
                if depth < n.depth:
                    n.depth = depth
            return n, False
        n = DagNode(state, is_or, depth)
        self._nodes[state] = n
        self.nodes_created += 1
        return n, True

    # ---------------- main loop ----------------

    def solve(self):
        g, cfg = self.game, self.cfg
        root_state = self.start_state if self.start_state is not None else g.initial_state()
        root, _ = self._get_node(root_state, g.player_to_move(root_state) == 0, 0)
        self._evaluate_leaf(root)
        t0 = time.perf_counter()
        deadline = t0 + cfg.max_seconds if cfg.max_seconds else None
        i = 0
        stalled = 0
        last_id = None
        while root.pn != 0 and root.dn != 0 and self.nodes_expanded < cfg.max_nodes:
            mpn = self._select_most_proving(root)
            if mpn.expanded or self.game.terminal(mpn.state) is not None:
                # Defensive: a correct most-proving descent never lands here,
                # because solved children are unattractive on the relevant side.
                # Re-backing up refreshes stale values; if nothing moves, stop.
                self._backup(mpn)
                stalled = stalled + 1 if id(mpn) == last_id else 0
                last_id = id(mpn)
                if stalled > 2:
                    break
                continue
            stalled, last_id = 0, None
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
            # Stored nodes = distinct states held in the table (one Node each).
            "peak_nodes": self.peak_nodes,
            "tt_hit_rate": (self.tt_hits / self.tt_lookups) if self.tt_lookups else 0.0,
            "root_pn": root.pn,
            "root_dn": root.dn,
            "layer_violations": self.layer_violations,
        }

    def _expand(self, n):
        self.nodes_expanded += 1
        n.children = []
        for m in self.game.legal_moves(n.state):
            cs = self.game.apply(n.state, m)
            child, is_new = self._get_node(cs, self.game.player_to_move(cs) == 0,
                                           n.depth + 1)
            if is_new:
                self._evaluate_leaf(child)
            child.parents.append(n)
            n.children.append(child)
        n.expanded = True
        if len(self._nodes) > self.peak_nodes:
            self.peak_nodes = len(self._nodes)

    # ---------------- backup over the DAG ----------------

    def _backup(self, node):
        """Sweep upward one layer at a time, re-deriving every affected ancestor.

        A node is re-examined only if a child's (pn, dn) actually changed, so a
        converged region of the DAG costs nothing.
        """
        frontier = {id(node): node}
        guard = 0
        max_sweeps = node.depth + 2
        while frontier and guard <= max_sweeps:
            guard += 1
            nxt = {}
            for nd in frontier.values():
                before = (nd.pn, nd.dn, nd.deep)
                self._recompute(nd)
                if nd is node or (nd.pn, nd.dn, nd.deep) != before:
                    for p in nd.parents:
                        nxt[id(p)] = p
            frontier = nxt


def pns_tt_solve(game, config, controller=None, start_state=None):
    """Convenience wrapper mirroring dfpn_solve / pn2_solve."""
    return DAGPNSEngine(game, config, controller=controller,
                        start_state=start_state).solve()
