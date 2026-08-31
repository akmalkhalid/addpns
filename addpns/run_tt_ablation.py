"""Controlled comparison requested by Reviewer 1 (C1) and the scaling study (C4).

C1. The submitted paper compared a TREE-based, frontier-driven best-first family
against a DAG-based, threshold-driven df-pn, so tree-vs-DAG and frontier-vs-threshold
were confounded. This runner removes the confound by adding `PNS+TT` -- best-first
PNS with a real node-sharing transposition table (engine_tt.DAGPNSEngine) -- and
running it WITH and WITHOUT the data-driven leaf initialization. The reported
headline is the paired ratio

        nodes(PNS+TT+data) / nodes(PNS+TT)

on instances both configurations solved: the initialization is then the ONLY
difference between the two arms.

C4. Board sizes in the submission were capped by the cost of the brute-force minimax
oracle. Soundness only needs instances small enough for that oracle; efficiency does
not. This runner therefore also supports sizes above the oracle ceiling and certifies
those runs by CROSS-CONFIGURATION AGREEMENT: every configuration that resolves an
instance must return the same verdict. Disagreements are counted and reported; a
non-zero count invalidates the run.

Usage
-----
    python3 run_tt_ablation.py --preset c1        # oracle-checked sizes
    python3 run_tt_ablation.py --preset c4        # above the oracle ceiling
    python3 run_tt_ablation.py --preset smoke     # ~1 minute sanity check

Outputs `tt_ablation_<name>.csv` and a markdown report per domain in --out.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import statistics
import time
from multiprocessing import Pool

from games import ConnectFour, Hex, Othello
from planning import random_instance
from engine import PNSEngine, Config
from engine_tt import DAGPNSEngine
from controller import HeuristicController, make_logistic_leaf_model
from dfpn import dfpn_solve
from run_ablation import wilcoxon, geomean, boot_ci

LEAF = make_logistic_leaf_model(weights=[0.0, 0.8, 1.2, -0.3], bias=0.0)

# Order matters: the report prints configurations in this order.
CONFIG_ORDER = ["PNS", "+data", "PNS+TT", "PNS+TT+data", "ADDPNS+TT+data", "df-pn"]


def config_matrix(budget, seconds):
    C = lambda **k: Config(max_nodes=budget, max_seconds=seconds, **k)
    return {
        # --- tree substrate (as in the submitted paper) ---
        "PNS":            ("tree", C(backup="sum", selection="standard"), None),
        "+data":          ("tree", C(backup="sum", selection="standard",
                                     leaf_init="data", leaf_model=LEAF), None),
        # --- DAG substrate: identical search discipline, node sharing added ---
        "PNS+TT":         ("dag", C(backup="sum", selection="standard"), None),
        "PNS+TT+data":    ("dag", C(backup="sum", selection="standard",
                                    leaf_init="data", leaf_model=LEAF), None),
        "ADDPNS+TT+data": ("dag", C(backup="blend", selection="deeppn",
                                    lambda_mode="adaptive", R_mode="adaptive",
                                    leaf_init="data", leaf_model=LEAF), "heur"),
        # --- reference point ---
        "df-pn":          ("dfpn", None, None),
    }


def _solve_one(args):
    game, state, budget, seconds, seed = args
    out = {}
    for name, (kind, cfg, ctrl_kind) in config_matrix(budget, seconds).items():
        ctrl = HeuristicController() if ctrl_kind == "heur" else None
        if kind == "dfpn":
            o = dfpn_solve(game, max_nodes=budget, max_seconds=seconds, start_state=state)
        elif kind == "dag":
            o = DAGPNSEngine(game, cfg, controller=ctrl, start_state=state).solve()
        else:
            o = PNSEngine(game, cfg, controller=ctrl, start_state=state).solve()
        solved = o["result"] in ("PROVEN", "DISPROVEN")
        out[name] = (solved, o["result"], o["nodes_expanded"], o["time_s"],
                     o["peak_nodes"], o.get("layer_violations", 0))
    return out


def gen_positions(game, n, plies, seed):
    rng = random.Random(seed)
    out, tries = [], 0
    while len(out) < n and tries < n * 100:
        tries += 1
        s = game.initial_state()
        ok = True
        for _ in range(plies):
            if game.terminal(s) is not None:
                ok = False
                break
            s = game.apply(s, rng.choice(game.legal_moves(s)))
        if ok and game.terminal(s) is None and s not in out:
            out.append(s)
    return out


def paired_stats(rec, a, b, idxs):
    """Geometric-mean ratio nodes(a)/nodes(b) over instances both solved."""
    pair = [i for i in idxs if i in rec[a]["nodes"] and i in rec[b]["nodes"]]
    if not pair:
        return dict(n=0, gm=float("nan"), lo=float("nan"), hi=float("nan"), p=1.0)
    ratios = [rec[a]["nodes"][i] / rec[b]["nodes"][i] for i in pair]
    lo, hi = boot_ci(ratios)
    p = wilcoxon([rec[a]["nodes"][i] for i in pair], [rec[b]["nodes"][i] for i in pair])
    return dict(n=len(pair), gm=geomean(ratios), lo=lo, hi=hi, p=p)


def _cache_path(out_dir, name):
    return os.path.join(out_dir, f".cache_{name}.json")


def _load_cache(out_dir, name):
    p = _cache_path(out_dir, name)
    if not os.path.exists(p):
        return {}
    with open(p) as f:
        return {int(k): v for k, v in json.load(f).items()}


def _save_cache(out_dir, name, cache):
    os.makedirs(out_dir, exist_ok=True)
    with open(_cache_path(out_dir, name), "w") as f:
        json.dump(cache, f)


def run_domain(name, tasks_spec, budget, seconds, workers, out_dir,
               time_budget=0.0):
    """tasks_spec: list of (game, start_state). One entry per instance.

    Results are cached per instance in `.cache_<name>.json`, so a run that is
    interrupted (or stopped by `--time-budget`) resumes exactly where it left
    off on the next invocation. Returns (markdown, csv_path, n_disagreements)
    once every instance is done, or (None, None, None) while still incomplete.
    """
    cache = _load_cache(out_dir, name)
    todo = [i for i in range(len(tasks_spec)) if i not in cache]
    t0 = time.perf_counter()
    if todo:
        chunk = max(1, workers)
        for start in range(0, len(todo), chunk):
            batch = todo[start:start + chunk]
            tasks = [(tasks_spec[i][0], tasks_spec[i][1], budget, seconds, 1000 + i)
                     for i in batch]
            if workers > 1 and len(tasks) > 1:
                with Pool(workers) as pool:
                    out = pool.map(_solve_one, tasks)
            else:
                out = [_solve_one(t) for t in tasks]
            for i, res in zip(batch, out):
                cache[i] = res
            _save_cache(out_dir, name, cache)
            done = len(cache)
            print(f"  [{name}] {done}/{len(tasks_spec)} instances "
                  f"({time.perf_counter() - t0:.0f}s elapsed)", flush=True)
            if time_budget and time.perf_counter() - t0 > time_budget:
                print(f"  [{name}] time budget reached; resume by re-running.",
                      flush=True)
                return None, None, None
    results = [cache[i] for i in range(len(tasks_spec))]
    wall = time.perf_counter() - t0

    cfgs = list(config_matrix(budget, seconds).keys())
    rec = {k: {"solved": 0, "nodes": {}, "time": {}, "peak": {}} for k in cfgs}
    disagreements, layer_violations = [], 0
    for idx, res in enumerate(results):
        verdicts = {}
        for k, (solved, verdict, nodes, tsec, peak, lv) in res.items():
            layer_violations += lv
            if solved:
                rec[k]["solved"] += 1
                rec[k]["nodes"][idx] = nodes
                rec[k]["time"][idx] = tsec
                rec[k]["peak"][idx] = peak
                verdicts[k] = verdict
        if len(set(verdicts.values())) > 1:
            disagreements.append((idx, dict(verdicts)))

    npos = len(tasks_spec)
    allidx = range(npos)
    rows = []
    for k in CONFIG_ORDER:
        own = sorted(rec[k]["nodes"].keys())
        vs_pns = paired_stats(rec, k, "PNS", allidx)
        vs_tt = paired_stats(rec, k, "PNS+TT", allidx)
        rows.append({
            "config": k,
            "solve_pct": round(rec[k]["solved"] / npos * 100, 1),
            "own_solved_n": len(own),
            "own_mean_nodes": round(statistics.mean(rec[k]["nodes"][i] for i in own), 1) if own else float("nan"),
            "n_paired_vs_PNS": vs_pns["n"],
            "geomean_vs_PNS": round(vs_pns["gm"], 3),
            "PNS_ci_lo": round(vs_pns["lo"], 3), "PNS_ci_hi": round(vs_pns["hi"], 3),
            "wilcoxon_p_vs_PNS": round(vs_pns["p"], 4),
            "n_paired_vs_PNS_TT": vs_tt["n"],
            "geomean_vs_PNS_TT": round(vs_tt["gm"], 3),
            "TT_ci_lo": round(vs_tt["lo"], 3), "TT_ci_hi": round(vs_tt["hi"], 3),
            "wilcoxon_p_vs_PNS_TT": round(vs_tt["p"], 4),
            "mean_stored_nodes": round(statistics.mean(rec[k]["peak"][i] for i in own), 1) if own else float("nan"),
            "mean_time_s": round(statistics.mean(rec[k]["time"][i] for i in own), 4) if own else float("nan"),
        })

    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, f"tt_ablation_{name}.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    head = paired_stats(rec, "PNS+TT+data", "PNS+TT", allidx)
    md = [f"### {name} — {npos} instances, budget {budget}, cap {seconds}s "
          f"(wall {wall:.1f}s)",
          "",
          "| config | solve% | mean nodes | vs PNS | 95% CI | p | vs PNS+TT | 95% CI | p | mean stored |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(
            f"| {r['config']} | {r['solve_pct']}% | {r['own_mean_nodes']} | "
            f"{r['geomean_vs_PNS']} | [{r['PNS_ci_lo']}, {r['PNS_ci_hi']}] | {r['wilcoxon_p_vs_PNS']} | "
            f"{r['geomean_vs_PNS_TT']} | [{r['TT_ci_lo']}, {r['TT_ci_hi']}] | {r['wilcoxon_p_vs_PNS_TT']} | "
            f"{r['mean_stored_nodes']} |")
    md += ["",
           f"**C1 headline** — data-driven initialization on the transposition-table "
           f"substrate: nodes(PNS+TT+data)/nodes(PNS+TT) = **{head['gm']:.3f}** "
           f"[{head['lo']:.3f}, {head['hi']:.3f}], Wilcoxon p = {head['p']:.4f}, "
           f"n = {head['n']} paired instances.",
           "",
           f"**Soundness by cross-configuration agreement**: "
           f"{len(disagreements)} disagreement(s) among resolving configurations; "
           f"{layer_violations} layered-DAG violation(s).",
           ]
    if disagreements:
        md.append("")
        for idx, v in disagreements[:10]:
            md.append(f"  - instance {idx}: {v}")
    return "\n".join(md), csv_path, len(disagreements)


def build_plan(preset):
    """Return [(name, [(game, start_state), ...], budget, seconds)]."""
    def board(game, n, plies, seed=7):
        return [(game, s) for s in gen_positions(game, n, plies, seed)]

    def plan(w, faults, horizon, n, density=0.12, seed=0):
        insts = [random_instance(w, w, density, horizon, seed + s, max_faults=faults)
                 for s in range(n)]
        return [(g, g.initial_state()) for g in insts]

    if preset == "smoke":
        return [
            ("hex3", board(Hex(3), 9, 1), 100_000, 20.0),
            ("connect4_5x4", board(ConnectFour(5, 4, 4), 10, 6), 60_000, 20.0),
            ("planning_5x5_B1_H8", plan(5, 1, 8, 10), 60_000, 20.0),
        ]
    if preset == "c1":
        # Same domains and sizes as the submitted paper: within the minimax
        # oracle's reach, so soundness is oracle-certified as before.
        return [
            ("hex3", board(Hex(3), 9, 1), 300_000, 45.0),
            ("connect4_5x4", board(ConnectFour(5, 4, 4), 40, 6), 200_000, 45.0),
            ("othello6_e10", board(Othello(6), 30, 26), 200_000, 45.0),
            ("planning_5x5_B1_H8", plan(5, 1, 8, 40), 150_000, 45.0),
            ("planning_5x5_B2_H8", plan(5, 2, 8, 40), 200_000, 45.0),
        ]
    if preset == "c4":
        # Above the brute-force minimax ceiling: soundness certified by
        # cross-configuration agreement instead of by the oracle.
        return [
            ("hex4_full", board(Hex(4), 16, 1), 200_000, 20.0),
            ("connect4_6x5", board(ConnectFour(6, 5, 4), 20, 8), 200_000, 20.0),
            ("connect4_7x6_mid", board(ConnectFour(7, 6, 4), 20, 14), 200_000, 20.0),
            ("othello8_e16", board(Othello(8), 20, 48), 200_000, 20.0),
            ("planning_6x6_B2_H10", plan(6, 2, 10, 20), 200_000, 20.0),
            ("planning_7x7_B3_H12", plan(7, 3, 12, 20), 200_000, 20.0),
        ]
    raise SystemExit(f"unknown preset {preset}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="c1", choices=["smoke", "c1", "c4"])
    ap.add_argument("--out", default="results")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--only", default="", help="comma-separated domain names to run")
    ap.add_argument("--time-budget", type=float, default=0.0,
                    help="stop after roughly this many seconds per domain; "
                         "re-run to resume from the per-instance cache")
    a = ap.parse_args()

    plan = build_plan(a.preset)
    if a.only:
        keep = {x.strip() for x in a.only.split(",")}
        plan = [p for p in plan if p[0] in keep]

    parts = [f"# Transposition-table ablation (preset: {a.preset})",
             f"\n_Generated {time.strftime('%Y-%m-%d %H:%M')}._\n"]
    total_disagree, incomplete = 0, []
    for name, tasks_spec, budget, seconds in plan:
        md, csvp, dis = run_domain(name, tasks_spec, budget, seconds, a.workers,
                                   a.out, time_budget=a.time_budget)
        if md is None:
            incomplete.append(name)
            break
        total_disagree += dis
        parts.append(md + f"\n\n_(csv: {os.path.basename(csvp)})_\n")
        print(md, flush=True)
        print(flush=True)
        # rewrite after every domain so partial progress survives an early stop
        with open(os.path.join(a.out, f"TT_ABLATION_{a.preset}.md"), "w") as f:
            f.write("\n".join(parts))
    if incomplete:
        print("INCOMPLETE (re-run to resume):", ", ".join(incomplete))
        return 2
    print("TOTAL cross-configuration disagreements:", total_disagree)
    return 0 if total_disagree == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
