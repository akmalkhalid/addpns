# Recommended run settings (4 cores, overnight, games + planning)

## One command

```
cd addpns
python run_all.py --workers 4
```

(Use `python3` if that's your launcher.) Everything below is already baked into
`run_all.py` as defaults — you only need `--workers 4`.

First, a 1-minute sanity check that nothing is broken on your machine:

```
python test_correctness.py        # soundness vs minimax
python test_reroot.py             # both-polarity regression
python run_all.py --quick --workers 4
```

## What it runs and why these numbers

Per-solve **node budget** and **time cap** are aligned so a *robust* config
finishes on the node budget rather than being cut off by the clock
(~12k nodes/s in pure Python ⇒ ~500k nodes ≈ 42s, under the 60s games cap).
The time cap exists to stop deliberately-fragile baselines (fixed-R DeepPN,
bandit) from grinding forever; they abort as UNRESOLVED and are reported by
solve-rate.

**Games ablation** (`run_ablation.run_domain`, cap 60s):
| domain | instances | plies | budget | exercises |
|---|---|---|---|---|
| hex3 | 9 (all openings) | 1 | 500k | R / regression |
| hex4_mid | 40 | 10 | 500k | seesaw → R |
| connect4_5x4 | 50 | 6 | 300k | transpositions → λ |
| connect4_6x5_mid | 40 | 12 | 500k | transpositions → λ |
| othello6_e10 | 40 | 26 | 400k | DAG + draws → λ, R |

**Planning case study** (`planning_benchmark.run`, cap 45s):
| setting | instances | budget | regime |
|---|---|---|---|
| 5×5, B=1, H=8 | 40 | 200k | easy (mostly solvable) |
| 5×5, B=2, H=8 | 40 | 300k | near threshold (the hard, informative one) |
| 5×5, B=3, H=10 | 40 | 400k | hard (many unsolvable) |

11 comparators each: PNS, WPNS, df-pn, PN2, DeepPN(R=0.4), +data, +λ, +R,
ADDPNS, ADDPNS+data, ADDPNS+bandit.

## Expected wall-time

On 4 cores, roughly **5–9 hours** total — comfortably overnight. The long poles
are `hex4_mid` / `connect4_6x5_mid` and the `B=3,H=10` planning regime, because
the fragile baselines burn their full cap on the hardest instances. `run_all.py`
prints each setting's wall-time as it goes, so you'll see progress.

## Outputs (in `addpns/results/`)

- `FULL_RESULTS.md` — combined report (both tables per setting), **rewritten
  after every setting**, so partial progress is safe if you stop early.
- `ablation_<domain>.csv` and `planning_5x5_B*_H*.csv` — one CSV per setting with
  all columns (solve%, mean nodes, geomean-vs-PNS + 95% CI, Wilcoxon p for both
  the common and pairwise views, mean peak). These are your record-keeping files.

## Knobs if you want to adjust

- `--scale 1.5` → 50% more instances per setting (tighter CIs, longer run).
- `--seconds 90 --plan-seconds 60` → larger caps so even slow configs finish
  (longer run, fewer aborts).
- Fewer/more workers: `--workers N`.
- To run only one half, call `run_ablation.py` or `planning_benchmark.py`
  directly (see their `--help`).

## Reading the results for the paper

- **Headline ADDPNS-vs-PNS:** use **Table B** (pairwise) — robust to the fragile
  baselines aborting.
- **All-methods comparison:** **Table A** (solved-by-all robust core).
- **Memory story (PN2):** the `mean peak` column.
- **Robustness story:** the `solve%` column (fixed-R DeepPN should be visibly
  fragile; ADDPNS should be 100% and ≤ PNS on nodes).

Tip: run it in a window you can leave open, capturing a log too:

```
python run_all.py --workers 4 > results\run_log.txt 2>&1
```
