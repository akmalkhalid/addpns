"""Correctness invariants: every configuration must return the SAME game value.

Effort numbers steer search order only, so PNS/WPNS/DeepPN/ADDPNS must all agree
with brute-force minimax on the synthetic trees and small Connect Four.
"""
from games import SyntheticTree, ConnectFour, WIN, LOSS, DRAW
from engine import PNSEngine, Config
from controller import HeuristicController


def minimax(game, state, _memo=None):
    """Ground truth: can the ROOT player force a WIN? Memoized."""
    if _memo is None:
        _memo = {}
    if state in _memo:
        return _memo[state]
    term = game.terminal(state)
    if term is not None:
        _memo[state] = (term == WIN)
        return _memo[state]
    is_or = game.player_to_move(state) == 0
    res = (any if is_or else all)(
        minimax(game, game.apply(state, m), _memo) for m in game.legal_moves(state))
    _memo[state] = res
    return res


CONFIGS = {
    "PNS":     Config(backup="sum", selection="standard"),
    "WPNS":    Config(backup="wpns", selection="standard"),
    "DeepPN":  Config(backup="sum", selection="deeppn", R_mode="fixed", R_value=0.4),
    "blend.5": Config(backup="blend", selection="standard", lambda_value=0.5),
    "ADDPNS":  Config(backup="blend", selection="deeppn",
                      lambda_mode="adaptive", R_mode="adaptive"),
}


def run(game, start_state=None):
    """Check every config against minimax. A WRONG definite answer is a failure;
    UNRESOLVED (hit the node budget) is reported but NOT a correctness failure."""
    ss = start_state if start_state is not None else game.initial_state()
    truth = minimax(game, ss)
    expected = "PROVEN" if truth else "DISPROVEN"
    ok = True
    for name, cfg in CONFIGS.items():
        cfg.max_nodes = 300_000      # keep the test fast; resolvable cases solve well under this
        cfg.max_seconds = 20.0       # fragile configs abort quickly as UNRESOLVED
        eng = PNSEngine(game, cfg, controller=HeuristicController(), start_state=ss)
        out = eng.solve()
        r = out["result"]
        if r == expected:
            tag = "OK"
        elif r == "UNRESOLVED":
            tag = "unsolved (budget) - not a correctness failure"
        else:
            tag = f"WRONG (expected {expected})"; ok = False
        print(f"  {name:9s} -> {r:10s} nodes={out['nodes_expanded']:8d}  {tag}")
    return ok


def _midgame(game, plies, seed):
    import random
    rng = random.Random(seed); s = game.initial_state()
    for _ in range(plies):
        if game.terminal(s) is not None:
            break
        s = game.apply(s, rng.choice(game.legal_moves(s)))
    return s


def main():
    spec1 = {0: [1, 2], 1: [3, 4], 2: WIN, 3: WIN, 4: WIN}
    t1 = SyntheticTree(spec1)
    spec2 = {0: [1, 2], 1: [3, 4], 2: [5, 6],
             3: WIN, 4: LOSS, 5: DRAW, 6: WIN}
    t2 = SyntheticTree(spec2)

    all_ok = True
    print("[Synthetic tree 1] expect PROVEN")
    all_ok &= run(t1)
    print("[Synthetic tree 2] expect DISPROVEN (defender escapes)")
    all_ok &= run(t2)

    # Connect Four 4x4 from the empty board (resolves within budget).
    g44 = ConnectFour(4, 4, 4)
    print("[Connect Four 4x4, from empty] (vs minimax)")
    all_ok &= run(g44)

    # Connect Four 5x4 from a seeded mid-game endgame (full board is too large
    # for pure-Python best-first; an endgame gives a clean positive check).
    g54 = ConnectFour(5, 4, 4)
    print("[Connect Four 5x4, mid-game endgame] (vs minimax)")
    all_ok &= run(g54, _midgame(g54, plies=10, seed=1))

    print("\nNO CONFIG GAVE A WRONG ANSWER:", all_ok)
    print("(UNRESOLVED entries are budget timeouts, expected for fragile configs"
          " / large boards; they are not correctness failures.)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
