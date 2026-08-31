"""Overnight driver: runs the full ADDPNS games ablation + planning case study,
writes per-setting CSVs and one combined markdown (results/FULL_RESULTS.md).

Tuned defaults for ~4 cores / overnight. Override with --workers, --seconds,
--scale (multiplies instance counts), or --quick (tiny smoke test).

  python3 run_all.py --workers 4              # the real overnight run
  python3 run_all.py --quick                  # ~1 min sanity check
"""
import argparse, os, time
from games import Hex, ConnectFour, Othello
from planning import random_instance
import run_ablation as RA
import planning_benchmark as PB


def games_plan(scale):
    s = lambda n: max(4, int(n * scale))
    # (name, game, n, plies, budget)
    return [
        ("hex3",             Hex(3),               9,        1, 500_000),
        ("hex4_mid",         Hex(4),            s(40),      10, 500_000),
        ("connect4_5x4",     ConnectFour(5,4,4), s(50),      6, 300_000),
        ("connect4_6x5_mid", ConnectFour(6,5,4), s(40),     12, 500_000),
        ("othello6_e10",     Othello(6),         s(40),     26, 400_000),
    ]

def planning_plan(scale):
    s = lambda n: max(4, int(n * scale))
    # (w, faults, horizon, density, n, budget)
    return [
        (5, 1, 8,  0.12, s(40), 200_000),
        (5, 2, 8,  0.12, s(40), 300_000),
        (5, 3, 10, 0.12, s(40), 400_000),
    ]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seconds", type=float, default=60.0, help="per-solve wall-clock cap (games)")
    ap.add_argument("--plan-seconds", type=float, default=45.0, help="cap for planning regimes")
    ap.add_argument("--scale", type=float, default=1.0, help="multiply instance counts")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="results")
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    if a.quick:
        a.scale, a.seconds, a.plan_seconds = 0.0, 3.0, 2.0   # scale 0 -> floor of 4

    os.makedirs(a.out, exist_ok=True)
    blocks = [f"# ADDPNS FULL RESULTS  (workers={a.workers}, "
              f"game-cap={a.seconds}s, plan-cap={a.plan_seconds}s, scale={a.scale}, seed={a.seed})",
              f"_generated {time.strftime('%Y-%m-%d %H:%M')}_\n"]
    t_start = time.perf_counter()

    blocks.append("## Games (ablation across PNS / WPNS / df-pn / PN2 / DeepPN / ADDPNS family)\n")
    for name, game, n, plies, budget in games_plan(a.scale):
        t0 = time.perf_counter()
        md, _ = RA.run_domain(name, game, n, plies, budget, a.seed, a.out,
                              seconds=a.seconds, workers=a.workers)
        dt = time.perf_counter() - t0
        blocks.append(md + f"\n\n_(wall {dt:.1f}s)_\n")
        print(f"[games] {name}: {dt:.1f}s", flush=True)
        _flush(blocks, a.out)

    blocks.append("\n## Planning case study (fault-tolerant strong planning)\n")
    for w, B, H, dens, n, budget in planning_plan(a.scale):
        insts = [random_instance(w, w, dens, H, a.seed + i, max_faults=B) for i in range(n)]
        name = f"planning_{w}x{w}_B{B}_H{H}"
        t0 = time.perf_counter()
        md, _ = PB.run(name, insts, budget, a.plan_seconds, a.seed, a.workers, a.out)
        dt = time.perf_counter() - t0
        blocks.append(md + f"\n\n_(wall {dt:.1f}s)_\n")
        print(f"[planning] {name}: {dt:.1f}s", flush=True)
        _flush(blocks, a.out)

    total = time.perf_counter() - t_start
    blocks.append(f"\n_Total wall-time: {total/60:.1f} min._")
    _flush(blocks, a.out)
    print(f"DONE in {total/60:.1f} min. See {os.path.join(a.out,'FULL_RESULTS.md')} + per-setting CSVs.")


def _flush(blocks, out):
    with open(os.path.join(out, "FULL_RESULTS.md"), "w") as f:
        f.write("\n".join(blocks))


if __name__ == "__main__":
    main()
