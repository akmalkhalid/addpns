"""Benchmark the PNS family on the fault-tolerant planning case study.

Each 'position' is a distinct random planning INSTANCE (grid). Reuses the solver
matrix, controllers, time cap, multiprocessing, and stats from run_ablation, and
emits the same two tables (solved-by-all robust core; pairwise vs PNS) PLUS a CSV
for record keeping.
"""
import statistics, argparse, os, time, csv
from multiprocessing import Pool
from planning import random_instance
from run_ablation import (config_matrix, _solve_one, wilcoxon, geomean, boot_ci)


def _rows(rec, npos, cfgs):
    """Build a per-config stats row (used for both CSV and markdown)."""
    pns_idx = set(rec["PNS"]["nodes"].keys())
    core = [k for k in cfgs if rec[k]["solved"] >= 0.5 * npos]
    common = set(range(npos))
    for k in core:
        common &= set(rec[k]["nodes"].keys())
    common &= set(rec["PNS"]["nodes"].keys())   # ratios are vs PNS -> PNS must have solved it
    common = sorted(common)
    rows = []
    for k in cfgs:
        own = sorted(rec[k]["nodes"].keys())
        ck = [i for i in common if i in rec[k]["nodes"]]
        ns_c = [rec[k]["nodes"][i] for i in ck]
        ratios_c = [rec[k]["nodes"][i] / rec["PNS"]["nodes"][i] for i in ck]
        gm_c = geomean(ratios_c) if ratios_c else float("nan")
        lo_c, hi_c = boot_ci(ratios_c)
        p_c = 1.0 if k == "PNS" else wilcoxon(ns_c, [rec["PNS"]["nodes"][i] for i in ck])
        paired = sorted(set(own) & pns_idx)
        ratios_p = [rec[k]["nodes"][i] / rec["PNS"]["nodes"][i] for i in paired]
        gm_p = geomean(ratios_p) if ratios_p else float("nan")
        lo_p, hi_p = boot_ci(ratios_p)
        ns_p = [rec[k]["nodes"][i] for i in paired]
        p_p = 1.0 if k == "PNS" else wilcoxon(ns_p, [rec["PNS"]["nodes"][i] for i in paired])
        rows.append({
            "config": k,
            "solve_pct": round(rec[k]["solved"] / npos * 100, 1),
            "own_solved_n": len(own),
            "own_mean_nodes": round(statistics.mean(rec[k]["nodes"][i] for i in own), 1) if own else float("nan"),
            "mean_nodes_common": round(statistics.mean(ns_c), 1) if ns_c else float("nan"),
            "geomean_vs_PNS_common": round(gm_c, 3),
            "common_ci_lo": round(lo_c, 3), "common_ci_hi": round(hi_c, 3),
            "wilcoxon_p_common": round(p_c, 4),
            "n_paired_vs_PNS": len(paired),
            "geomean_vs_PNS_paired": round(gm_p, 3),
            "paired_ci_lo": round(lo_p, 3), "paired_ci_hi": round(hi_p, 3),
            "wilcoxon_p_paired": round(p_p, 4),
            "mean_peak_nodes": round(statistics.mean(rec[k]["peak"][i] for i in ck), 1) if ck else float("nan"),
        })
    return rows, common


def run(name, instances, budget, seconds, seed, workers, out_dir):
    cfgs = config_matrix(budget, seconds)
    tasks = [(g, g.initial_state(), budget, seconds, seed + i) for i, g in enumerate(instances)]
    if workers > 1:
        with Pool(workers) as pool:
            results = pool.map(_solve_one, tasks)
    else:
        results = [_solve_one(t) for t in tasks]
    rec = {k: {"solved": 0, "nodes": {}, "peak": {}} for k in cfgs}
    for idx, res in enumerate(results):
        for k, (solved, nodes, tsec, peak) in res.items():
            if solved:
                rec[k]["solved"] += 1
                rec[k]["nodes"][idx] = nodes
                rec[k]["peak"][idx] = peak
    npos = len(instances)
    rows, common = _rows(rec, npos, cfgs)

    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, f"{name}.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    by = {r["config"]: r for r in rows}
    lines = [f"### {name} — {npos} instances, budget {budget}, cap {seconds}s",
             f"\n**Table A — solved by all robust configs; {len(common)} instances.**\n",
             "| config | solve% | mean nodes | geomean vs PNS | 95% CI | Wilcoxon p | mean peak |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['config']} | {r['solve_pct']}% | {r['mean_nodes_common']} | "
                     f"{r['geomean_vs_PNS_common']} | [{r['common_ci_lo']}, {r['common_ci_hi']}] | "
                     f"{r['wilcoxon_p_common']} | {r['mean_peak_nodes']} |")
    lines += ["\n**Table B — pairwise vs PNS (instances solved by it AND PNS).**\n",
              "| config | solve% | own mean nodes | n paired | geomean vs PNS | 95% CI | Wilcoxon p |",
              "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['config']} | {r['solve_pct']}% | {r['own_mean_nodes']} | {r['n_paired_vs_PNS']} | "
                     f"{r['geomean_vs_PNS_paired']} | [{r['paired_ci_lo']}, {r['paired_ci_hi']}] | "
                     f"{r['wilcoxon_p_paired']} |")
    lines.append(f"\n_(csv: {os.path.basename(csv_path)})_")
    return "\n".join(lines), csv_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--w", type=int, default=5); ap.add_argument("--faults", type=int, default=2)
    ap.add_argument("--horizon", type=int, default=8); ap.add_argument("--density", type=float, default=0.12)
    ap.add_argument("--n", type=int, default=20); ap.add_argument("--budget", type=int, default=300000)
    ap.add_argument("--seconds", type=float, default=20.0); ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--out", default="results")
    a = ap.parse_args()
    insts = [random_instance(a.w, a.w, a.density, a.horizon, a.seed + s, max_faults=a.faults) for s in range(a.n)]
    name = f"planning_{a.w}x{a.w}_B{a.faults}_H{a.horizon}"
    t0 = time.perf_counter()
    md, csvp = run(name, insts, a.budget, a.seconds, a.seed, a.workers, a.out)
    print(md); print(f"\n_(wall {time.perf_counter()-t0:.1f}s)_")
