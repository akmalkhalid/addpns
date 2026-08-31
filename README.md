# ADDPNS — Proof-Number Search Revisited

Reference implementation, benchmark domains, and result files for

> M. N. A. Khalid and H. Iida.
> *Proof-Number Search Revisited: A Unifying Framework and Empirical Study of
> Adaptive, Data-Driven Guidance.* ICGA Journal.

Every algorithm in the paper is a configuration of **one** engine, so the
comparisons differ only in the components under study — move generation,
terminal detection, and bookkeeping are shared. Every number in every table can
be regenerated from this repository with a single command.

---

## Quick start

```bash
git clone <this repo> && cd addpns-release
python3 -m pip install -r requirements.txt   # nothing but the standard library
cd addpns

python3 test_correctness.py       # soundness vs brute-force minimax  (~1 min)
python3 test_correctness_tt.py    # soundness of the node-sharing engine (~2 min)
python3 test_reroot.py            # both-polarity regression           (~1 min)

python3 run_tt_ablation.py --preset smoke --out ../results/smoke --workers 2
```

Python 3.9+ is required. There are **no third-party dependencies**: the engine,
the statistics (bootstrap CIs, Wilcoxon signed-rank), and the domains are all
pure standard library, so a fresh interpreter reproduces the results exactly.

---

## What is where

| File | Contents |
|---|---|
| `addpns/engine.py` | The configurable best-first PNS engine. Leaf initialization, backup rule, selection rule, and the adaptive parameters are all `Config` fields. |
| `addpns/engine_tt.py` | **New in the revision.** Best-first PNS over a DAG: identical control rule, but one node per distinct state (a real transposition table). This is the `+TT` option. |
| `addpns/dfpn.py` | df-pn and PN2 baselines, plus `CDFPN`, the data-driven/graph-aware df-pn variant. |
| `addpns/controller.py` | The lightweight online controller (λ from the table hit rate, R from the flip rate) and the contextual-bandit variant. |
| `addpns/games.py` | Hex, Connect Four, Othello, and the synthetic AND/OR trees used as correctness ground truth. |
| `addpns/planning.py` | The fault-tolerant planning domain and its instance generator. |
| `addpns/run_ablation.py` | Board-game ablation (Tables 3). |
| `addpns/planning_benchmark.py` | Planning ablation (Table 4). |
| `addpns/run_tt_ablation.py` | **New.** The controlled transposition-table comparison (Table 5) and the enlarged-instance study (Table 6). |
| `results/original/` | Raw CSVs and reports behind Tables 3 and 4. |
| `results/tt_ablation/` | Raw CSVs and reports behind Tables 5 and 6. |

---

## Reproducing each table

| Table | Command |
|---|---|
| 3 (board games) | `python3 run_ablation.py --out ../results/original --workers 4` |
| 4 (planning) | `python3 run_all.py --workers 4` (runs both halves; see `RUN_SETTINGS.md`) |
| 5 (controlled TT comparison) | `python3 run_tt_ablation.py --preset c1 --out ../results/tt_ablation --workers 4` |
| 6 (enlarged instances) | `python3 run_tt_ablation.py --preset c4 --out ../results/tt_ablation --workers 4` |

All runs are seeded. `run_tt_ablation.py` caches results per instance, so an
interrupted run resumes where it stopped; pass `--time-budget SECONDS` to stop
it deliberately and re-run to continue.

Expect several hours for the full set on 4 cores. This is a pure-Python
reference implementation: the paper's claims rest on **node expansion counts**,
which are implementation-independent, and wall-clock figures are used only for
same-machine relative comparisons.

---

## The configurations

| Name | Leaf init | Backup | Selection | Node sharing |
|---|---|---|---|---|
| `PNS` | uniform (1,1) | sum | most-proving | tree |
| `WPNS` | uniform | WPNS bound (λ≡1) | most-proving | tree |
| `DeepPN(R=0.4)` | uniform | sum | depth-aware, fixed R | tree |
| `+data` | logistic model | sum | most-proving | tree |
| `+λ` | uniform | adaptive blend | most-proving | tree |
| `+R` | uniform | sum | depth-aware, adaptive | tree |
| `ADDPNS` | uniform | adaptive blend | depth-aware, adaptive | tree |
| `ADDPNS+data` | logistic model | adaptive blend | depth-aware, adaptive | tree |
| `ADDPNS+bandit` | uniform | adaptive blend | depth-aware, bandit | tree |
| `PNS+TT` | uniform | sum | most-proving | **DAG** |
| `PNS+TT+data` | logistic model | sum | most-proving | **DAG** |
| `ADDPNS+TT+data` | logistic model | adaptive blend | depth-aware, adaptive | **DAG** |
| `df-pn` | — | thresholds | depth-first | DAG |
| `PN2` | level-2 search | sum | most-proving | tree (two-level) |

The adaptive parameters are defined in the paper and implemented in
`controller.py`:

- **λ** = (table hits) / (table look-ups), a running estimate of transposition
  density. It starts at 0, so the search begins as exact classical PNS.
  `Config.lambda_freeze_after=N` freezes λ after N look-ups for anyone who wants
  strictly monotone effort estimates; soundness is unaffected either way.
- **R** = 1 while the node's flip rate ρ = flips/visits stays at or below
  τ = 0.30 (or during the first `v₀ = 8` visits), and
  `max(R_min, 1 − α(ρ − τ))` otherwise, with α = 2 and R_min = 0.2. These four
  constants are fixed across every domain; no per-domain tuning was performed.

---

## The fault-tolerant planning domain

This is a domain of our own construction, not a community benchmark. It is
included here in full so the results are exactly reproducible, and it is
generated rather than distributed as files — `planning.random_instance(w, h,
obstacle_density, horizon, seed, max_faults)` is deterministic given its seed.

A robot on a `w × h` grid with static obstacles must reach a goal cell within a
horizon of `H` moves. Actions are reliable except that an adversarial
environment may divert at most `B` of them to a cell perpendicular to the
intended direction, each diversion spending one of its `B` faults. Proving the
root proves that a **strong plan** exists: a policy reaching the goal for every
way the adversary can spend its budget. This is the *k*-fault-tolerant planning
problem class (Jensen, Veloso and Bryant 2004; Domshlak 2013), which
interpolates between classical planning (`B=0`) and full nondeterminism.

State: `(cell, steps, pending_direction, faults_left)`. `pending_direction is
None` marks the robot's turn (an OR node); otherwise it is the environment's
turn (an AND node). `WIN` = robot on goal, `LOSS` = horizon exhausted.

Settings used in the paper — all on a 5×5 grid, obstacle density 0.12, 60
instances each:

| Label | Fault budget B | Horizon H | Character |
|---|---|---|---|
| B=1 | 1 | 8 | easy, mostly solvable |
| B=2 | 2 | 8 | near the solvability threshold |
| B=3 | 3 | 10 | hard, many instances unsolved within budget |

Enlarged settings (Table 6): 6×6 with B=2, H=10; and 7×7 with B=3, H=12.

**Features for the data-driven leaf model** (`FONDGrid.features`): a bias term,
the fraction of the horizon remaining, closeness to the goal (1 − normalised
Manhattan distance), and the fraction of the fault budget remaining. The
Manhattan distance term is the one that carries the effect reported in the
paper.

For contrast, the board-game feature vectors are deliberately minimal, and two
of them are too weak to discriminate: `Hex.features` returns only a bias and the
fraction of empty cells, which is a function of ply count alone, so at a fixed
depth every leaf receives an identical initialization and `+data` is
*definitionally* equivalent to uniform initialization there. `Othello.features`
returns a bias and the normalised disc differential. This is discussed in
Section 5.1 of the paper and is the reason the initialization helps on planning
but not on the board games.

---

## Soundness

Proof and disproof numbers influence only the *order* of expansion, never the
verdict. Two certificates are used:

1. **Oracle certification.** `test_correctness.py` and `test_correctness_tt.py`
   check every configuration against brute-force minimax on synthetic AND/OR
   trees with known values, on small board positions, on planning instances, and
   on re-rooted positions with either player to move. `test_correctness_tt.py`
   additionally checks the node-sharing engine against the tree engine position
   by position.

2. **Cross-configuration agreement**, for instances beyond the oracle's reach.
   Every configuration that resolves an instance within budget must return the
   same verdict. `run_tt_ablation.py` reports the disagreement count for every
   domain and exits non-zero if any is found. Across the 116 enlarged instances
   of Table 6 there were zero disagreements.

A note on the node-sharing engine: its backup sweeps the DAG one depth layer at
a time, which assumes all paths from the root to a state have the same length.
This holds in every domain here except Othello, where a pass move breaks it. The
engine detects such violations, reports them in `layer_violations`, and falls
back to the shallowest recorded depth. Verdicts are unaffected — a state's
game-theoretic value does not depend on the path taken to reach it — but backup
is not guaranteed to converge in the fewest sweeps in that case.

---

## Metrics

- **Node expansions** — the primary metric, hardware- and language-independent.
- **Stored nodes** — the number of *distinct states* held at peak occupancy.
  This is the natural measure for the transposition-table methods; for the
  tree-based configurations it is a lower bound on true occupancy, since a tree
  stores one node per path rather than one per state.
- **Node ratios** — geometric means over instances that *both* configurations
  solved, with 95% bootstrap confidence intervals (2000 resamples) and a
  two-sided Wilcoxon signed-rank test.

---

## Citation

```bibtex
@article{Khalid2026PNSRevisited,
  author  = {Khalid, Mohd Nor Akmal and Iida, Hiroyuki},
  title   = {Proof-Number Search Revisited: A Unifying Framework and Empirical
             Study of Adaptive, Data-Driven Guidance},
  journal = {ICGA Journal},
  year    = {2026}
}
```

## License

MIT — see `LICENSE`.
