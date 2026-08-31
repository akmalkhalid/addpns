"""General multi-domain benchmark for the ADDPNS study.

Generates seeded positions, runs each configuration, and reports solve rate +
mean nodes_expanded on positions solved by all configs (fair comparison), with
a paired Wilcoxon test vs PNS. Scale up via --n / --budget for paper-grade runs.

Examples:
  python3 benchmark.py --domain hex --size 4 --n 30 --plies 1 --budget 2000000
  python3 benchmark.py --domain connect4 --cols 6 --rows 5 --n 40 --plies 8
  python3 benchmark.py --domain othello --size 6 --n 30 --plies 24 --budget 500000
"""
import random, statistics, argparse
from games import ConnectFour, Hex, Othello
from engine import PNSEngine, Config
from controller import HeuristicController, make_logistic_leaf_model

LEAF = make_logistic_leaf_model(weights=[0.0, 0.8, 1.2, -0.3], bias=0.0)

def configs(budget):
    return {
        "PNS":         Config(backup="sum",  selection="standard", max_nodes=budget),
        "WPNS":        Config(backup="wpns", selection="standard", max_nodes=budget),
        "DeepPN(R.4)": Config(backup="sum",  selection="deeppn", R_value=0.4, max_nodes=budget),
        "ADDPNS":      Config(backup="blend", selection="deeppn", lambda_mode="adaptive",
                              R_mode="adaptive", max_nodes=budget),
        "ADDPNS+data": Config(backup="blend", selection="deeppn", lambda_mode="adaptive",
                              R_mode="adaptive", leaf_init="data", leaf_model=LEAF,
                              max_nodes=budget),
    }

def make_game(a):
    if a.domain == "hex": return Hex(a.size)
    if a.domain == "othello": return Othello(a.size)
    return ConnectFour(a.cols, a.rows, 4)

def gen(game, n, plies, seed):
    rng = random.Random(seed); out = []
    tries = 0
    while len(out) < n and tries < n * 50:
        tries += 1
        s = game.initial_state(); ok = True
        for _ in range(plies):
            if game.terminal(s) is not None: ok = False; break
            s = game.apply(s, rng.choice(game.legal_moves(s)))
        if ok and game.terminal(s) is None: out.append(s)
    return out

def clone_with_state(game, s):
    g2 = type(game).__new__(type(game)); g2.__dict__.update(game.__dict__)
    g2.initial_state = lambda s=s: s
    return g2

def wilcoxon(a, b):
    """Wilcoxon signed-rank test (normal approximation with tie & continuity
    correction). Returns approximate two-sided p-value. Dependency-free.
    For final paper numbers, scipy.stats.wilcoxon is recommended if available.
    """
    import math
    diffs = [x - y for x, y in zip(a, b) if x - y != 0]
    n = len(diffs)
    if n == 0:
        return 1.0
    order = sorted(range(n), key=lambda i: abs(diffs[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(diffs[order[j+1]]) == abs(diffs[order[i]]):
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    wp = sum(r for d, r in zip(diffs, ranks) if d > 0)
    wn = sum(r for d, r in zip(diffs, ranks) if d < 0)
    W = min(wp, wn)
    mean = n * (n + 1) / 4
    var = n * (n + 1) * (2 * n + 1) / 24
    if var == 0:
        return 1.0
    z = (W - mean + 0.5) / math.sqrt(var)
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return max(0.0, min(1.0, p))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=["hex","connect4","othello"], default="hex")
    ap.add_argument("--size", type=int, default=3)
    ap.add_argument("--cols", type=int, default=5); ap.add_argument("--rows", type=int, default=4)
    ap.add_argument("--n", type=int, default=12); ap.add_argument("--plies", type=int, default=1)
    ap.add_argument("--budget", type=int, default=200000); ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    game = make_game(a); cfgs = configs(a.budget)
    pos = gen(game, a.n, a.plies, a.seed)
    rows = {k: {"solved":0, "per":{}} for k in cfgs}
    for idx, s in enumerate(pos):
        for k, cfg in cfgs.items():
            ctrl = HeuristicController() if k.startswith("ADDPNS") else None
            o = PNSEngine(clone_with_state(game, s), cfg, controller=ctrl).solve()
            if o["result"] in ("PROVEN","DISPROVEN"):
                rows[k]["solved"] += 1; rows[k]["per"][idx] = o["nodes_expanded"]
    common = set(range(len(pos)))
    for k in cfgs: common &= set(rows[k]["per"].keys())
    common = sorted(common)
    print(f"Domain {game.name} | {len(pos)} positions @ {a.plies} plies | budget {a.budget} "
          f"| {len(common)} solved-by-all")
    base = [rows["PNS"]["per"][i] for i in common]
    bmean = statistics.mean(base) if base else float("nan")
    print(f"{'config':13s} {'solve%':>7s} {'mean_nodes':>11s} {'vs PNS':>8s} {'p(vs PNS)':>10s}")
    for k in cfgs:
        ns = [rows[k]["per"][i] for i in common]
        m = statistics.mean(ns) if ns else float("nan")
        rel = "" if (k=="PNS" or not bmean or m!=m) else f"{m/bmean*100:5.0f}%"
        w = "" if k=="PNS" else f"{wilcoxon(ns, base):.3f}"
        print(f"{k:13s} {rows[k]['solved']/len(pos)*100:6.1f}% {m:11.0f} {rel:>8s} {w:>10s}")

if __name__ == "__main__":
    main()
