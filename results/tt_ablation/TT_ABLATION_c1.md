# Transposition-table ablation (preset: c1)

_Generated 2026-08-31 08:08._

### planning_5x5_B2_H8 — 40 instances, budget 100000, cap 45.0s (wall 79.5s)

| config | solve% | mean nodes | vs PNS | 95% CI | p | vs PNS+TT | 95% CI | p | mean stored |
|---|---|---|---|---|---|---|---|---|---|
| PNS | 57.5% | 32587.8 | 1.0 | [1.0, 1.0] | 1.0 | 39.32 | [22.101, 69.563] | 0.0 | 926.7 |
| +data | 67.5% | 14011.6 | 0.398 | [0.329, 0.483] | 0.0 | 17.836 | [10.965, 28.132] | 0.0 | 873 |
| PNS+TT | 100.0% | 486.0 | 0.025 | [0.014, 0.045] | 0.0 | 1.0 | [1.0, 1.0] | 1.0 | 699.6 |
| PNS+TT+data | 100.0% | 412.7 | 0.019 | [0.011, 0.034] | 0.0 | 0.816 | [0.76, 0.875] | 0.0004 | 618.2 |
| ADDPNS+TT+data | 100.0% | 444.1 | 0.02 | [0.011, 0.036] | 0.0 | 0.871 | [0.815, 0.931] | 0.0198 | 660.7 |
| df-pn | 100.0% | 1161.5 | 0.06 | [0.034, 0.103] | 0.0 | 2.311 | [2.148, 2.487] | 0.0 | 537.3 |

**C1 headline** — data-driven initialization on the transposition-table substrate: nodes(PNS+TT+data)/nodes(PNS+TT) = **0.816** [0.760, 0.875], Wilcoxon p = 0.0004, n = 40 paired instances.

**Soundness by cross-configuration agreement**: 0 disagreement(s) among resolving configurations; 0 layered-DAG violation(s).

_(csv: tt_ablation_planning_5x5_B2_H8.csv)_
