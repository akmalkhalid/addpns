"""Pilot benchmark: compare configurations by nodes_expanded on a set of
seeded mid-game positions. Demonstrates the data the paper's results table
needs (per-config node counts, solve rate). Primary metric is node count
(hardware independent); wall-clock also recorded.
"""
import random, statistics, argparse
from games import ConnectFour
from engine import PNSEngine, Config
from controller import HeuristicController, BanditController, make_logistic_leaf_model

LEAF_MODEL = make_logistic_leaf_model(weights=[0.0, 0.8, 1.2, -0.3], bias=0.0)

def make_configs(budget):
    return {
        "PNS":          (Config(backup="sum", selection="standard", max_nodes=budget), None),
        "WPNS":         (Config(backup="wpns", selection="standard", max_nodes=budget), None),
        "DeepPN(R.4)":  (Config(backup="sum", selection="deeppn", R_value=0.4, max_nodes=budget), None),
        "blend(.5)":    (Config(backup="blend", selection="standard", lambda_value=0.5, max_nodes=budget), None),
        "ADDPNS-heur":  (Config(backup="blend", selection="deeppn", lambda_mode="adaptive",
                                R_mode="adaptive", max_nodes=budget), "heur"),
        "ADDPNS+data":  (Config(backup="blend", selection="deeppn", lambda_mode="adaptive",
                                R_mode="adaptive", leaf_init="data", leaf_model=LEAF_MODEL,
                                max_nodes=budget), "heur"),
    }

def gen_positions(game, n, plies, seed):
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        s = game.initial_state()
        ok = True
        for _ in range(plies):
            mv = game.legal_moves(s)
            if not mv or game.terminal(s) is not None:
                ok = False; break
            s = game.apply(s, rng.choice(mv))
        if ok and game.terminal(s) is None:
            out.append(s)
    return out

def run(cols, rows, n, plies, budget, seed):
    game = ConnectFour(cols=cols, rows=rows, connect=4)
    positions = gen_positions(game, n, plies, seed)
    configs = make_configs(budget)
    stats = {k: {"nodes": [], "time": [], "solved": 0} for k in configs}
    per_pos_solved = []
    for s in positions:
        solved_here = {}
        for name, (cfg, ctrl_kind) in configs.items():
            ctrl = HeuristicController() if ctrl_kind == "heur" else None
            # rebuild game with fixed initial state = s
            g2 = ConnectFour(cols=cols, rows=rows, connect=4)
            g2.initial_state = lambda s=s: s
            out = PNSEngine(g2, cfg, controller=ctrl).solve()
            solved = out["result"] in ("PROVEN", "DISPROVEN")
            solved_here[name] = (solved, out["nodes_expanded"], out["time_s"])
            if solved:
                stats[name]["solved"] += 1
        per_pos_solved.append(solved_here)
    # report on positions solved by ALL configs (fair node comparison)
    common = [i for i, d in enumerate(per_pos_solved) if all(v[0] for v in d.values())]
    print(f"Board {cols}x{rows} | {n} positions @ {plies} plies | budget {budget} | "
          f"{len(common)} solved-by-all")
    print(f"{'config':14s} {'solve%':>7s} {'mean_nodes(all-solved)':>24s} {'mean_time_s':>12s}")
    base = None
    for name in configs:
        nodes = [per_pos_solved[i][name][1] for i in common]
        times = [per_pos_solved[i][name][2] for i in common]
        mn = statistics.mean(nodes) if nodes else float('nan')
        mt = statistics.mean(times) if times else float('nan')
        if name == "PNS": base = mn
        rel = f"({mn/base*100:5.1f}% of PNS)" if base and name != "PNS" else ""
        print(f"{name:14s} {stats[name]['solved']/n*100:6.1f}% {mn:24.1f} {mt:12.4f}  {rel}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--rows", type=int, default=4)
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--plies", type=int, default=6)
    ap.add_argument("--budget", type=int, default=60000)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    run(a.cols, a.rows, a.n, a.plies, a.budget, a.seed)
