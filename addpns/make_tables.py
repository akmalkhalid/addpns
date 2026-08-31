"""Generate the manuscript result tables from benchmark CSVs (reproducible).

Reads the per-domain CSVs written by run_ablation.py and planning_benchmark.py
and emits two LaTeX table files (tab_games.tex, tab_planning.tex) that the
manuscript \\inputs. Re-run after any benchmark to refresh the paper's numbers:

    python make_tables.py --results results --out ..

Cells show the geometric-mean node ratio vs PNS (pairwise view); '*' marks a
significant reduction (p<0.05, Wilcoxon); the best (lowest) value per column is
bold; '---' means the method solved no instance that PNS also solved.
"""
import csv, os, argparse, math

ORDER = ["PNS", "WPNS", "DeepPN(R.4)", "+data", "+lambda", "+R",
         "ADDPNS", "ADDPNS+data", "ADDPNS+bandit", "df-pn", "PN2"]
DISPLAY = {"PNS": "PNS (baseline)", "WPNS": "WPNS", "DeepPN(R.4)": "DeepPN ($R{=}0.4$)",
           "+data": "+data", "+lambda": "+$\\lambda$", "+R": "+R", "ADDPNS": "ADDPNS",
           "ADDPNS+data": "ADDPNS+data", "ADDPNS+bandit": "ADDPNS+bandit",
           "df-pn": "df-pn", "PN2": "PN2"}
GROUP_AFTER = {"DeepPN(R.4)", "ADDPNS+bandit"}   # \midrule after these rows

GAMES = [("ablation_hex3", "Hex $3{\\times}3$"),
         ("ablation_hex4_mid", "Hex $4{\\times}4$"),
         ("ablation_connect4_5x4", "C4 $5{\\times}4$"),
         ("ablation_connect4_6x5_mid", "C4 $6{\\times}5$"),
         ("ablation_othello6_e10", "Othello")]
PLAN = [("planning_5x5_B1_H8", "B1/H8"),
        ("planning_5x5_B2_H8", "B2/H8"),
        ("planning_5x5_B3_H10", "B3/H10")]


def load(results, key):
    path = os.path.join(results, key + ".csv")
    if not os.path.exists(path):
        return None
    with open(path, newline="") as f:
        return {r["config"]: r for r in csv.DictReader(f)}


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def ratio_cell(row):
    if row is None:
        return None
    if int(float(row.get("n_paired_vs_PNS", 0) or 0)) == 0:
        return None
    g = _f(row.get("geomean_vs_PNS_paired"))
    if math.isnan(g):
        return None
    p = _f(row.get("wilcoxon_p_paired"))
    star = "$^\\ast$" if (p < 0.05 and g < 0.999) else ""
    return (g, f"{g:.2f}{star}")


def build(results, domains, caption, label, with_solve):
    cols = [load(results, k) for k, _ in domains]
    headers = [h for _, h in domains]
    # ratio cells + per-column best (min) for bolding
    cells = {c: [] for c in ORDER}
    mins = []
    for j, col in enumerate(cols):
        vals = []
        for c in ORDER:
            rc = ratio_cell(col.get(c)) if col else None
            cells[c].append(rc)
            if rc is not None:
                vals.append(rc[0])
        mins.append(min(vals) if vals else None)
    ncol = len(domains)
    lines = ["\\begin{table*}[t]", "\\centering", f"\\caption{{{caption}}}",
             f"\\label{{{label}}}", "\\footnotesize"]
    if with_solve:
        spec = "l" + "c" * ncol + "c" * ncol
        lines += ["\\begin{tabular}{" + spec + "}", "\\toprule",
                  f" & \\multicolumn{{{ncol}}}{{c}}{{\\textbf{{Node ratio vs.\\ PNS}}}}"
                  f" & \\multicolumn{{{ncol}}}{{c}}{{\\textbf{{Solve rate (\\%)}}}} \\\\",
                  f"\\cmidrule(lr){{2-{1+ncol}}}\\cmidrule(lr){{{2+ncol}-{1+2*ncol}}}",
                  "\\textbf{Configuration} & " + " & ".join(headers) + " & " + " & ".join(headers) + " \\\\",
                  "\\midrule"]
    else:
        lines += ["\\begin{tabular}{l" + "c" * ncol + "}", "\\toprule",
                  "\\textbf{Configuration} & " + " & ".join(headers) + " \\\\", "\\midrule"]
    for c in ORDER:
        parts = [DISPLAY[c]]
        for j in range(ncol):
            rc = cells[c][j]
            if rc is None:
                parts.append("---")
            else:
                g, txt = rc
                if mins[j] is not None and mins[j] < 0.995 and abs(g - mins[j]) < 1e-9:
                    txt = "\\textbf{" + txt.replace("$^\\ast$", "") + "}" + ("$^\\ast$" if "$^\\ast$" in txt else "")
                parts.append(txt)
        if with_solve:
            for col in cols:
                row = col.get(c) if col else None
                parts.append("---" if row is None else f"{_f(row.get('solve_pct')):.0f}")
        lines.append(" & ".join(parts) + " \\\\")
        if c in GROUP_AFTER:
            lines.append("\\midrule")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table*}", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--out", default="..")
    a = ap.parse_args()
    games = build(a.results, GAMES,
                  "Board games: geometric-mean node ratio vs.\\ PNS (pairwise view; lower is "
                  "better). $^\\ast$: significant reduction ($p<0.05$, Wilcoxon); best per column in bold; "
                  "`---' = no instance solved jointly with PNS. Auto-generated from benchmark CSVs.",
                  "tab:games", with_solve=False)
    plan = build(a.results, PLAN,
                 "Fault-tolerant planning ($5\\times5$; B = fault budget, H = horizon): geometric-mean "
                 "node ratio vs.\\ PNS (pairwise view) and solve rate within budget. $^\\ast$: significant "
                 "reduction ($p<0.05$); best per column in bold. Auto-generated from benchmark CSVs.",
                 "tab:planning", with_solve=True)
    open(os.path.join(a.out, "tab_games.tex"), "w").write(games)
    open(os.path.join(a.out, "tab_planning.tex"), "w").write(plan)
    print("wrote tab_games.tex and tab_planning.tex to", os.path.abspath(a.out))


if __name__ == "__main__":
    main()
