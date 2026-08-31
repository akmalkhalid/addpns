# Transposition-table ablation (preset: c4)

_Generated 2026-08-31 08:41._

### hex4_full — 16 instances, budget 200000, cap 20.0s (wall 0.0s)

| config | solve% | mean nodes | vs PNS | 95% CI | p | vs PNS+TT | 95% CI | p | mean stored |
|---|---|---|---|---|---|---|---|---|---|
| PNS | 6.2% | 104264 | 1.0 | [nan, nan] | 1.0 | 6.386 | [nan, nan] | 1.0 | 141829 |
| +data | 6.2% | 104264 | 1.0 | [nan, nan] | 1.0 | 6.386 | [nan, nan] | 1.0 | 141829 |
| PNS+TT | 100.0% | 29929.6 | 0.157 | [nan, nan] | 1.0 | 1.0 | [1.0, 1.0] | 1.0 | 145557.3 |
| PNS+TT+data | 100.0% | 29929.6 | 0.157 | [nan, nan] | 1.0 | 1.0 | [1.0, 1.0] | 1.0 | 145557.3 |
| ADDPNS+TT+data | 0.0% | nan | nan | [nan, nan] | 1.0 | nan | [nan, nan] | 1.0 | nan |
| df-pn | 100.0% | 62327.8 | 0.264 | [nan, nan] | 1.0 | 2.153 | [1.938, 2.411] | 0.0005 | 47276.8 |

**C1 headline** — data-driven initialization on the transposition-table substrate: nodes(PNS+TT+data)/nodes(PNS+TT) = **1.000** [1.000, 1.000], Wilcoxon p = 1.0000, n = 16 paired instances.

**Soundness by cross-configuration agreement**: 0 disagreement(s) among resolving configurations; 0 layered-DAG violation(s).

_(csv: tt_ablation_hex4_full.csv)_

### connect4_6x5 — 20 instances, budget 200000, cap 20.0s (wall 0.0s)

| config | solve% | mean nodes | vs PNS | 95% CI | p | vs PNS+TT | 95% CI | p | mean stored |
|---|---|---|---|---|---|---|---|---|---|
| PNS | 65.0% | 26601.2 | 1.0 | [1.0, 1.0] | 1.0 | 1.822 | [1.304, 2.601] | 0.0225 | 31101.8 |
| +data | 65.0% | 30283.1 | 1.022 | [0.955, 1.097] | 0.4469 | 1.863 | [1.319, 2.675] | 0.0225 | 33088.8 |
| PNS+TT | 100.0% | 28858.5 | 0.549 | [0.384, 0.767] | 0.0225 | 1.0 | [1.0, 1.0] | 1.0 | 88426.9 |
| PNS+TT+data | 100.0% | 27553.2 | 0.573 | [0.408, 0.787] | 0.0225 | 1.003 | [0.95, 1.056] | 0.7064 | 85255.7 |
| ADDPNS+TT+data | 35.0% | 696.4 | 0.927 | [0.796, 1.0] | 1.0 | 1.044 | [1.0, 1.137] | 1.0 | 2666.7 |
| df-pn | 95.0% | 47652.2 | 0.712 | [0.563, 0.879] | 0.0346 | 1.473 | [1.276, 1.693] | 0.0021 | 26037.2 |

**C1 headline** — data-driven initialization on the transposition-table substrate: nodes(PNS+TT+data)/nodes(PNS+TT) = **1.003** [0.950, 1.056], Wilcoxon p = 0.7064, n = 20 paired instances.

**Soundness by cross-configuration agreement**: 0 disagreement(s) among resolving configurations; 0 layered-DAG violation(s).

_(csv: tt_ablation_connect4_6x5.csv)_

### connect4_7x6_mid — 20 instances, budget 200000, cap 20.0s (wall 0.0s)

| config | solve% | mean nodes | vs PNS | 95% CI | p | vs PNS+TT | 95% CI | p | mean stored |
|---|---|---|---|---|---|---|---|---|---|
| PNS | 75.0% | 8565.5 | 1.0 | [1.0, 1.0] | 1.0 | 1.385 | [1.071, 1.991] | 0.0591 | 15036.8 |
| +data | 75.0% | 8141.5 | 1.028 | [0.97, 1.099] | 0.4017 | 1.424 | [1.111, 2.005] | 0.036 | 14484.3 |
| PNS+TT | 85.0% | 11066.6 | 0.722 | [0.502, 0.933] | 0.0591 | 1.0 | [1.0, 1.0] | 1.0 | 43593.1 |
| PNS+TT+data | 80.0% | 5200.5 | 0.761 | [0.515, 1.001] | 0.1422 | 1.061 | [1.0, 1.137] | 0.1508 | 21292.3 |
| ADDPNS+TT+data | 55.0% | 20.7 | 1.051 | [1.0, 1.136] | 0.3711 | 1.052 | [1.0, 1.137] | 0.3711 | 130.7 |
| df-pn | 80.0% | 8097.4 | 0.873 | [0.676, 1.059] | 0.1422 | 1.244 | [1.094, 1.407] | 0.0225 | 4970.4 |

**C1 headline** — data-driven initialization on the transposition-table substrate: nodes(PNS+TT+data)/nodes(PNS+TT) = **1.061** [1.000, 1.137], Wilcoxon p = 0.1508, n = 16 paired instances.

**Soundness by cross-configuration agreement**: 0 disagreement(s) among resolving configurations; 0 layered-DAG violation(s).

_(csv: tt_ablation_connect4_7x6_mid.csv)_

### othello8_e16 — 20 instances, budget 200000, cap 20.0s (wall 0.0s)

| config | solve% | mean nodes | vs PNS | 95% CI | p | vs PNS+TT | 95% CI | p | mean stored |
|---|---|---|---|---|---|---|---|---|---|
| PNS | 100.0% | 11986.9 | 1.0 | [1.0, 1.0] | 1.0 | 1.5 | [1.331, 1.701] | 0.0001 | 24409.3 |
| +data | 100.0% | 11626.1 | 0.976 | [0.911, 1.052] | 0.2432 | 1.464 | [1.277, 1.674] | 0.0007 | 23320.9 |
| PNS+TT | 100.0% | 5963.3 | 0.667 | [0.588, 0.752] | 0.0001 | 1.0 | [1.0, 1.0] | 1.0 | 20217.6 |
| PNS+TT+data | 100.0% | 5857.7 | 0.656 | [0.579, 0.752] | 0.0002 | 0.984 | [0.913, 1.06] | 0.6632 | 19588.5 |
| ADDPNS+TT+data | 75.0% | 3923.1 | 0.711 | [0.626, 0.803] | 0.002 | 0.992 | [0.934, 1.051] | 0.6293 | 14161.2 |
| df-pn | 100.0% | 11389.4 | 1.281 | [1.153, 1.434] | 0.0594 | 1.921 | [1.801, 2.055] | 0.0001 | 6326.7 |

**C1 headline** — data-driven initialization on the transposition-table substrate: nodes(PNS+TT+data)/nodes(PNS+TT) = **0.984** [0.913, 1.060], Wilcoxon p = 0.6632, n = 20 paired instances.

**Soundness by cross-configuration agreement**: 0 disagreement(s) among resolving configurations; 30 layered-DAG violation(s).

_(csv: tt_ablation_othello8_e16.csv)_

### planning_6x6_B2_H10 — 20 instances, budget 200000, cap 20.0s (wall 0.0s)

| config | solve% | mean nodes | vs PNS | 95% CI | p | vs PNS+TT | 95% CI | p | mean stored |
|---|---|---|---|---|---|---|---|---|---|
| PNS | 45.0% | 54843.1 | 1.0 | [1.0, 1.0] | 1.0 | 42.523 | [17.676, 101.609] | 0.0092 | 1123.8 |
| +data | 70.0% | 50127.4 | 0.575 | [0.409, 0.71] | 0.0092 | 37.316 | [17.582, 77.99] | 0.0011 | 1245.5 |
| PNS+TT | 100.0% | 675.8 | 0.024 | [0.01, 0.057] | 0.0092 | 1.0 | [1.0, 1.0] | 1.0 | 965.2 |
| PNS+TT+data | 100.0% | 517.5 | 0.017 | [0.007, 0.042] | 0.0092 | 0.772 | [0.703, 0.842] | 0.0003 | 796.5 |
| ADDPNS+TT+data | 100.0% | 536.5 | 0.017 | [0.007, 0.045] | 0.0092 | 0.799 | [0.713, 0.89] | 0.0029 | 823.8 |
| df-pn | 100.0% | 1735.8 | 0.072 | [0.032, 0.168] | 0.0092 | 2.508 | [2.1, 2.969] | 0.0001 | 793.5 |

**C1 headline** — data-driven initialization on the transposition-table substrate: nodes(PNS+TT+data)/nodes(PNS+TT) = **0.772** [0.703, 0.842], Wilcoxon p = 0.0003, n = 20 paired instances.

**Soundness by cross-configuration agreement**: 0 disagreement(s) among resolving configurations; 0 layered-DAG violation(s).

_(csv: tt_ablation_planning_6x6_B2_H10.csv)_

### planning_7x7_B3_H12 — 20 instances, budget 200000, cap 20.0s (wall 75.2s)

| config | solve% | mean nodes | vs PNS | 95% CI | p | vs PNS+TT | 95% CI | p | mean stored |
|---|---|---|---|---|---|---|---|---|---|
| PNS | 0.0% | nan | nan | [nan, nan] | 1.0 | nan | [nan, nan] | 1.0 | nan |
| +data | 30.0% | 128624.7 | nan | [nan, nan] | 1.0 | 94.565 | [59.706, 153.972] | 0.036 | 3101.5 |
| PNS+TT | 100.0% | 1542.7 | nan | [nan, nan] | 1.0 | 1.0 | [1.0, 1.0] | 1.0 | 2118.6 |
| PNS+TT+data | 100.0% | 1456.6 | nan | [nan, nan] | 1.0 | 0.934 | [0.818, 1.087] | 0.3803 | 2062.3 |
| ADDPNS+TT+data | 100.0% | 1617.7 | nan | [nan, nan] | 1.0 | 1.043 | [0.904, 1.224] | 0.9553 | 2264.2 |
| df-pn | 100.0% | 5383.2 | nan | [nan, nan] | 1.0 | 3.412 | [3.041, 3.859] | 0.0001 | 1894.2 |

**C1 headline** — data-driven initialization on the transposition-table substrate: nodes(PNS+TT+data)/nodes(PNS+TT) = **0.934** [0.818, 1.087], Wilcoxon p = 0.3803, n = 20 paired instances.

**Soundness by cross-configuration agreement**: 0 disagreement(s) among resolving configurations; 0 layered-DAG violation(s).

_(csv: tt_ablation_planning_7x7_B3_H12.csv)_
