"""Regression test for the root-polarity bug: solvers must be correct when the
search is rooted at a position where EITHER player is to move (PN2 sub-searches
and odd-ply positions hit this). A WRONG definite answer is a failure; UNRESOLVED
(budget/time) is fine.

Fast by design: deeper Connect Four / Othello plies (cheap minimax), a per-solve
node+time cap, and progress printing so it never looks hung.
"""
import random, time
from games import Hex, ConnectFour, Othello
from engine import PNSEngine, Config
from controller import HeuristicController
from dfpn import dfpn_solve, pn2_solve
from test_correctness import minimax, CONFIGS

CAP_NODES, CAP_SECS = 50_000, 5.0


def reroot(game, plies, seed):
    rng = random.Random(seed); s = game.initial_state()
    for _ in range(plies):
        if game.terminal(s) is not None:
            return None
        s = game.apply(s, rng.choice(game.legal_moves(s)))
    if game.terminal(s) is not None:
        return None
    return s, game.player_to_move(s)


def main():
    ok = True; n = 0; pol = set()
    # plies chosen to include BOTH polarities while keeping minimax cheap
    plan = [("Hex3", Hex(3), [1, 2]),
            ("Connect4_5x4", ConnectFour(5, 4, 4), [6, 7]),
            ("Othello6", Othello(6), [24, 25])]
    for label, game, plyset in plan:
        for plies in plyset:
            for seed in range(2):
                rr = reroot(game, plies, seed)
                if rr is None:
                    continue
                ss, ptm = rr; pol.add(ptm)
                t0 = time.perf_counter()
                exp = "PROVEN" if minimax(game, ss) else "DISPROVEN"
                results = {}
                for name, cfg in CONFIGS.items():
                    cfg.max_nodes, cfg.max_seconds = CAP_NODES, CAP_SECS
                    results[name] = PNSEngine(game, cfg, controller=HeuristicController(),
                                              start_state=ss).solve()["result"]
                results["df-pn"] = dfpn_solve(game, CAP_NODES, CAP_SECS, start_state=ss)["result"]
                results["PN2"] = pn2_solve(game, CAP_NODES, 20000, CAP_SECS, start_state=ss)["result"]
                bad = {k: v for k, v in results.items() if v not in (exp, "UNRESOLVED")}
                n += 1
                status = "WRONG -> " + str(bad) if bad else "ok"
                if bad:
                    ok = False
                print(f"  {label:13s} plies={plies} seed={seed} ptm={ptm} exp={exp:10s} "
                      f"[{time.perf_counter()-t0:4.1f}s] {status}", flush=True)
    print(f"\nChecked {n} re-rooted cases (polarities seen={sorted(pol)}). "
          f"NO WRONG ANSWERS: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
