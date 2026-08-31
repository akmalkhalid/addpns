"""Scaled benchmark + ablation runner for ADDPNS.

Outputs, per domain: solve%, mean nodes (on positions solved by ALL configs),
geometric-mean node ratio vs PNS, 95% bootstrap CI on that ratio, Wilcoxon p
vs PNS, mean wall-time, and mean per-node overhead vs PNS. Writes a CSV and a
markdown table to --out.

Ablation matrix isolates each ADDPNS component:
  PNS                  sum   / standard / uniform     (baseline)
  +data                sum   / standard / data        (leaf init only)
  +lambda              blend / standard / uniform      (graph-aware only)
  +R                   sum   / deeppn   / uniform      (depth-aware only)
  ADDPNS               blend / deeppn   / uniform      (all structural)
  ADDPNS+data          blend / deeppn   / data         (full)
  ADDPNS+bandit        blend / deeppn   / uniform + BanditController
Specialist baselines: WPNS, DeepPN(R=0.4 fixed).
"""
import random, statistics, math, csv, os, time, argparse
from multiprocessing import Pool
from games import ConnectFour, Hex, Othello
from engine import PNSEngine, Config
from controller import HeuristicController, BanditController, make_logistic_leaf_model
from dfpn import dfpn_solve, pn2_solve

LEAF = make_logistic_leaf_model(weights=[0.0, 0.8, 1.2, -0.3], bias=0.0)

def config_matrix(budget, seconds=0.0):
    C = lambda **k: Config(max_nodes=budget, max_seconds=seconds, **k)
    return {
        "PNS":          (C(backup="sum",  selection="standard"), None),
        "WPNS":         (C(backup="wpns", selection="standard"), None),
        "DeepPN(R.4)":  (C(backup="sum",  selection="deeppn", R_value=0.4), None),
        "+data":        (C(backup="sum",  selection="standard", leaf_init="data", leaf_model=LEAF), None),
        "+lambda":      (C(backup="blend", selection="standard", lambda_mode="adaptive"), "heur"),
        "+R":           (C(backup="sum",  selection="deeppn", R_mode="adaptive"), "heur"),
        "ADDPNS":       (C(backup="blend", selection="deeppn", lambda_mode="adaptive", R_mode="adaptive"), "heur"),
        "ADDPNS+data":  (C(backup="blend", selection="deeppn", lambda_mode="adaptive", R_mode="adaptive",
                           leaf_init="data", leaf_model=LEAF), "heur"),
        "ADDPNS+bandit":(C(backup="blend", selection="deeppn", lambda_mode="adaptive", R_mode="adaptive"), "bandit"),
        "df-pn":        (None, "dfpn"),
        "PN2":          (None, "pn2"),
    }


def _solve_one(args):
    """Worker: solve every config for a single position. Returns dict
    {config: (solved_bool, nodes, time_s, peak)}. Picklable inputs only."""
    game, state, budget, seconds, seed = args
    cfgs = config_matrix(budget, seconds)
    out = {}
    for k, (cfg, kind) in cfgs.items():
        if kind == "dfpn":
            o = dfpn_solve(game, max_nodes=budget, max_seconds=seconds, start_state=state)
        elif kind == "pn2":
            o = pn2_solve(game, max_nodes=budget, max_seconds=seconds, start_state=state)
        else:
            ctrl = make_ctrl(kind, seed)
            o = PNSEngine(game, cfg, controller=ctrl, start_state=state).solve()
        solved = o["result"] in ("PROVEN", "DISPROVEN")
        out[k] = (solved, o["nodes_expanded"], o["time_s"], o["peak_nodes"])
    return out

def make_ctrl(kind, seed):
    if kind == "heur":   return HeuristicController()
    if kind == "bandit": return BanditController(seed=seed)
    return None

def clone(game, s):
    g2 = type(game).__new__(type(game)); g2.__dict__.update(game.__dict__)
    g2.initial_state = lambda s=s: s
    return g2

def gen_positions(game, n, plies, seed):
    rng = random.Random(seed); out = []; tries = 0
    while len(out) < n and tries < n * 100:
        tries += 1
        s = game.initial_state(); ok = True
        for _ in range(plies):
            if game.terminal(s) is not None: ok = False; break
            s = game.apply(s, rng.choice(game.legal_moves(s)))
        if ok and game.terminal(s) is None and s not in out:
            out.append(s)
    return out

def wilcoxon(a, b):
    diffs = [x - y for x, y in zip(a, b) if x - y != 0]; n = len(diffs)
    if n == 0: return 1.0
    order = sorted(range(n), key=lambda i: abs(diffs[i])); ranks = [0.0]*n; i = 0
    while i < n:
        j = i
        while j+1 < n and abs(diffs[order[j+1]]) == abs(diffs[order[i]]): j += 1
        avg = (i+j)/2 + 1
        for k in range(i, j+1): ranks[order[k]] = avg
        i = j+1
    wp = sum(r for d, r in zip(diffs, ranks) if d > 0)
    wn = sum(r for d, r in zip(diffs, ranks) if d < 0)
    W = min(wp, wn); mean = n*(n+1)/4; var = n*(n+1)*(2*n+1)/24
    if var == 0: return 1.0
    z = (W - mean + 0.5)/math.sqrt(var)
    return max(0.0, min(1.0, 2*(1 - 0.5*(1+math.erf(abs(z)/math.sqrt(2))))))

def geomean(xs):
    return math.exp(sum(math.log(x) for x in xs)/len(xs)) if xs else float("nan")

def boot_ci(ratios, iters=2000, seed=0):
    if len(ratios) < 2: return (float("nan"), float("nan"))
    rng = random.Random(seed); gms = []
    for _ in range(iters):
        sample = [ratios[rng.randrange(len(ratios))] for _ in ratios]
        gms.append(geomean(sample))
    gms.sort()
    return (gms[int(0.025*iters)], gms[int(0.975*iters)])

def run_domain(name, game, n, plies, budget, seed, out_dir, seconds=0.0, workers=1):
    cfgs = config_matrix(budget, seconds)
    pos = gen_positions(game, n, plies, seed)
    rec = {k: {"solved":0, "nodes":{}, "time":{}, "peak":{}} for k in cfgs}
    tasks = [(game, s, budget, seconds, seed + idx) for idx, s in enumerate(pos)]
    if workers and workers > 1:
        with Pool(workers) as pool:
            results = pool.map(_solve_one, tasks)
    else:
        results = [_solve_one(t) for t in tasks]
    for idx, res in enumerate(results):
        for k, (solved, nodes, tsec, peak) in res.items():
            if solved:
                rec[k]["solved"] += 1
                rec[k]["nodes"][idx] = nodes
                rec[k]["time"][idx] = tsec
                rec[k]["peak"][idx] = peak
    pns_idx = set(rec["PNS"]["nodes"].keys())
    # Table A common set uses only ROBUST configs (solve >= 50% of positions), so
    # deliberately fragile baselines (fixed-R DeepPN, bandit) don't empty it.
    core = [k for k in cfgs if rec[k]["solved"] >= 0.5 * len(pos)]
    common = set(range(len(pos)))
    for k in core: common &= set(rec[k]["nodes"].keys())
    common &= set(rec["PNS"]["nodes"].keys())   # ratios are vs PNS -> PNS must have solved it
    common = sorted(common)
    base_common = [rec["PNS"]["nodes"][i] for i in common]

    rows = []
    for k in cfgs:
        own = sorted(rec[k]["nodes"].keys())
        # --- solved-by-all (common) set: fair across ALL methods ---
        ck = [i for i in common if i in rec[k]["nodes"]]   # common positions THIS config solved
        ns_c = [rec[k]["nodes"][i] for i in ck]
        ts_c = [rec[k]["time"][i] for i in ck]
        ratios_c = [rec[k]["nodes"][i] / rec["PNS"]["nodes"][i] for i in ck]
        gm_c = geomean(ratios_c) if ratios_c else float("nan")
        lo_c, hi_c = boot_ci(ratios_c)
        p_c = 1.0 if k == "PNS" else wilcoxon(ns_c, [rec["PNS"]["nodes"][i] for i in ck])
        pns_tpn = (statistics.mean(rec["PNS"]["time"][i]/max(1,rec["PNS"]["nodes"][i]) for i in common)) if common else float("nan")
        k_tpn = (statistics.mean(rec[k]["time"][i]/max(1,rec[k]["nodes"][i]) for i in ck)) if ck else float("nan")
        # --- pairwise-vs-PNS set: positions solved by BOTH k and PNS ---
        paired = sorted(set(own) & pns_idx)
        ratios_p = [rec[k]["nodes"][i] / rec["PNS"]["nodes"][i] for i in paired]
        gm_p = geomean(ratios_p) if ratios_p else float("nan")
        lo_p, hi_p = boot_ci(ratios_p)
        ns_p = [rec[k]["nodes"][i] for i in paired]
        base_p = [rec["PNS"]["nodes"][i] for i in paired]
        p_p = 1.0 if k == "PNS" else wilcoxon(ns_p, base_p)
        rows.append({
            "config": k,
            "solve_pct": round(rec[k]["solved"]/len(pos)*100, 1) if pos else 0,
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
            "mean_time_s": round(statistics.mean(ts_c), 4) if ts_c else float("nan"),
            "mean_peak_nodes": round(statistics.mean(rec[k]["peak"][i] for i in ck), 1) if ck else float("nan"),
            "overhead_per_node_vs_PNS": round(k_tpn/pns_tpn, 3) if pns_tpn else float("nan"),
        })

    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, f"ablation_{name}.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    md = [f"### {name} — {len(pos)} positions @ {plies} plies, budget {budget}",
          f"\n**Table A — solved by all robust configs (>=50% solve); {len(common)} positions.**\n",
          "| config | solve% | mean nodes | geomean vs PNS | 95% CI | Wilcoxon p | mean peak | overhead/node |",
          "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['config']} | {r['solve_pct']}% | {r['mean_nodes_common']} | "
                  f"{r['geomean_vs_PNS_common']} | [{r['common_ci_lo']}, {r['common_ci_hi']}] | "
                  f"{r['wilcoxon_p_common']} | {r['mean_peak_nodes']} | {r['overhead_per_node_vs_PNS']} |")
    md += [f"\n**Table B — pairwise vs PNS (each method on positions it AND PNS both solved): "
           f"robust to aborts.**\n",
           "| config | solve% | own mean nodes | n paired | geomean vs PNS | 95% CI | Wilcoxon p |",
           "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['config']} | {r['solve_pct']}% | {r['own_mean_nodes']} | {r['n_paired_vs_PNS']} | "
                  f"{r['geomean_vs_PNS_paired']} | [{r['paired_ci_lo']}, {r['paired_ci_hi']}] | "
                  f"{r['wilcoxon_p_paired']} |")
    return "\n".join(md), csv_path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results")
    ap.add_argument("--quick", action="store_true", help="small sizes for validation")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--workers", type=int, default=1, help="parallel processes")
    ap.add_argument("--seconds", type=float, default=20.0, help="per-solve wall-clock cap (0=off)")
    a = ap.parse_args()
    if a.quick:
        plan = [("hex3", Hex(3), 20, 1, 200000),
                ("connect4_5x4", ConnectFour(5,4,4), 20, 6, 80000),
                ("othello6_e10", Othello(6), 12, 26, 150000)]
    else:
        plan = [("hex3", Hex(3), 60, 1, 500000),
                ("hex4_mid", Hex(4), 40, 10, 800000),
                ("connect4_5x4", ConnectFour(5,4,4), 60, 6, 300000),
                ("connect4_6x5_mid", ConnectFour(6,5,4), 40, 12, 800000),
                ("othello6_e10", Othello(6), 40, 26, 400000)]
    all_md = ["# ADDPNS scaled benchmark + ablation results\n",
              f"_Generated {time.strftime('%Y-%m-%d %H:%M')}; seed {a.seed}._\n"]
    for name, game, n, plies, budget in plan:
        t0 = time.perf_counter()
        md, csvp = run_domain(name, game, n, plies, budget, a.seed, a.out, seconds=a.seconds, workers=a.workers)
        all_md.append(md + f"\n\n_(domain wall-time {time.perf_counter()-t0:.1f}s; csv: {os.path.basename(csvp)})_\n")
        print(md); print()
    with open(os.path.join(a.out, "ablation_summary.md"), "w") as f:
        f.write("\n".join(all_md))
    print("Wrote", os.path.join(a.out, "ablation_summary.md"))

if __name__ == "__main__":
    main()
