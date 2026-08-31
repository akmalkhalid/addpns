"""Soundness of the transposition-table (DAG) best-first engine.

Node sharing must not change any verdict: a state's game-theoretic value does not
depend on the path taken to reach it. We check DAGPNSEngine against brute-force
minimax on synthetic AND/OR trees, on small board positions, and on re-rooted
positions with either player to move, exactly as test_correctness.py does for the
tree engine -- and we additionally check that PNS+TT agrees with plain PNS
position by position.
"""
import random

from games import SyntheticTree, ConnectFour, Hex, Othello, WIN, LOSS, DRAW
from engine import PNSEngine, Config
from engine_tt import DAGPNSEngine
from controller import HeuristicController, make_logistic_leaf_model
from planning import FONDGrid, random_instance
from test_correctness import minimax

LEAF = make_logistic_leaf_model(weights=[0.0, 0.8, 1.2, -0.3], bias=0.0)

CONFIGS = {
    "PNS+TT":        Config(backup="sum", selection="standard"),
    "PNS+TT+data":   Config(backup="sum", selection="standard",
                            leaf_init="data", leaf_model=LEAF),
    "PNS+TT+lambda": Config(backup="blend", selection="standard", lambda_mode="adaptive"),
    "ADDPNS+TT":     Config(backup="blend", selection="deeppn",
                            lambda_mode="adaptive", R_mode="adaptive"),
    "ADDPNS+TT+data": Config(backup="blend", selection="deeppn",
                             lambda_mode="adaptive", R_mode="adaptive",
                             leaf_init="data", leaf_model=LEAF),
}


def _midgame(game, plies, seed):
    rng = random.Random(seed)
    s = game.initial_state()
    for _ in range(plies):
        if game.terminal(s) is not None:
            break
        s = game.apply(s, rng.choice(game.legal_moves(s)))
    return s


def run(label, game, start_state=None, budget=300_000, seconds=30.0):
    ss = start_state if start_state is not None else game.initial_state()
    truth = minimax(game, ss)
    expected = "PROVEN" if truth else "DISPROVEN"
    print(f"[{label}] expect {expected}")
    ok = True
    for name, base in CONFIGS.items():
        cfg = Config(**{**base.__dict__})
        cfg.max_nodes, cfg.max_seconds = budget, seconds
        out = DAGPNSEngine(game, cfg, controller=HeuristicController(),
                           start_state=ss).solve()
        r = out["result"]
        if r == expected:
            tag = "OK"
        elif r == "UNRESOLVED":
            tag = "unsolved (budget) - not a correctness failure"
        else:
            tag = f"WRONG (expected {expected})"
            ok = False
        lv = out.get("layer_violations", 0)
        extra = f" layer_violations={lv}" if lv else ""
        print(f"  {name:16s} -> {r:10s} nodes={out['nodes_expanded']:8d} "
              f"stored={out['peak_nodes']:8d} tt_hit={out['tt_hit_rate']:.2f}  {tag}{extra}")
    return ok


def main():
    all_ok = True

    t1 = SyntheticTree({0: [1, 2], 1: [3, 4], 2: WIN, 3: WIN, 4: WIN})
    t2 = SyntheticTree({0: [1, 2], 1: [3, 4], 2: [5, 6],
                        3: WIN, 4: LOSS, 5: DRAW, 6: WIN})
    all_ok &= run("Synthetic tree 1", t1)
    all_ok &= run("Synthetic tree 2", t2)

    g44 = ConnectFour(4, 4, 4)
    all_ok &= run("Connect Four 4x4 from empty", g44)

    g54 = ConnectFour(5, 4, 4)
    for seed in (1, 2, 3):
        all_ok &= run(f"Connect Four 5x4 midgame seed={seed}",
                      g54, _midgame(g54, plies=10, seed=seed))

    h3 = Hex(3)
    all_ok &= run("Hex 3x3 from empty", h3)

    o6 = Othello(6)
    all_ok &= run("Othello 6x6 endgame", o6, _midgame(o6, plies=26, seed=5))

    for seed in (11, 12, 13):
        inst = random_instance(4, 4, 0.15, horizon=6, seed=seed, max_faults=1)
        all_ok &= run(f"Planning 4x4 B1/H6 seed={seed}", inst)

    # Re-rooted positions: the defender is to move at the root.
    print("[Re-rooted (defender to move) Connect Four 5x4]")
    for seed in (21, 22):
        all_ok &= run(f"  reroot seed={seed}", g54, _midgame(g54, plies=11, seed=seed))

    # PNS+TT must agree with the tree engine position by position.
    print("\n[Agreement: PNS (tree) vs PNS+TT (DAG)]")
    agree = True
    for seed in range(30):
        st = _midgame(g54, plies=10, seed=100 + seed)
        a = PNSEngine(g54, Config(backup="sum", selection="standard",
                                  max_nodes=300_000, max_seconds=30.0),
                      start_state=st).solve()
        b = DAGPNSEngine(g54, Config(backup="sum", selection="standard",
                                     max_nodes=300_000, max_seconds=30.0),
                         start_state=st).solve()
        if a["result"] != "UNRESOLVED" and b["result"] != "UNRESOLVED" \
                and a["result"] != b["result"]:
            print(f"  DISAGREE seed={seed}: tree={a['result']} dag={b['result']}")
            agree = False
    print("  agreement on all seeds:", agree)
    all_ok &= agree

    print("\nNO CONFIG GAVE A WRONG ANSWER:", all_ok)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
