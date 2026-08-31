# ADDPNS application case study: fault-tolerant planning (AND/OR reachability)

_Robot must reach a goal within horizon H despite an adversary diverting up to B actions (k-fault robust planning). Same engine/solvers as the board domains; each instance is a distinct random grid. Sample run (small N for demo; scale via planning_benchmark.py)._

### planning_5x5_B1_H8 — 6 instances, budget 100000, cap 1.5s

**Table A — solved by all robust configs; 4 instances.**

| config | solve% | mean nodes | geomean vs PNS | 95% CI | Wilcoxon p | mean peak |
|---|---|---|---|---|---|---|
| PNS | 83% | 5754.5 | 1.0 | [1.0, 1.0] | 1.0 | 393.2 |
| WPNS | 100% | 1203.2 | 0.407 | [0.111, 0.969] | 0.1814 | 333.8 |
| DeepPN(R.4) | 17% | 2721 | 0.479 | [nan, nan] | 1.0 | 358 |
| +data | 100% | 1718.5 | 0.3 | [0.178, 0.507] | 0.1003 | 310.2 |
| +lambda | 83% | 3838.5 | 0.851 | [0.625, 1.0] | 0.3711 | 364.2 |
| +R | 67% | 6270 | 1.085 | [0.989, 1.29] | 1.0 | 399.8 |
| ADDPNS | 83% | 3838.5 | 0.851 | [0.625, 1.0] | 0.3711 | 364.2 |
| ADDPNS+data | 83% | 293.2 | 0.1 | [0.026, 0.306] | 0.1003 | 242.8 |
| ADDPNS+bandit | 83% | 3831.8 | 0.724 | [0.544, 0.921] | 0.1814 | 389 |
| df-pn | 100% | 338.8 | 0.157 | [0.044, 0.564] | 0.1003 | 201.5 |
| PN2 | 83% | 7578 | 1.962 | [1.261, 3.168] | 0.1003 | 53.8 |

**Table B — pairwise vs PNS (instances solved by it AND PNS).**

| config | solve% | own mean nodes | n paired | geomean vs PNS | 95% CI | Wilcoxon p |
|---|---|---|---|---|---|---|
| PNS | 83% | 10198.6 | 5 | 1.0 | [1.0, 1.0] | 1.0 |
| WPNS | 100% | 7178.5 | 5 | 0.275 | [0.089, 0.861] | 0.1003 |
| DeepPN(R.4) | 17% | 2721 | 1 | 0.479 | [nan, nan] | 1.0 |
| +data | 100% | 4280.3 | 5 | 0.257 | [0.153, 0.428] | 0.0591 |
| +lambda | 83% | 5524.6 | 5 | 0.745 | [0.538, 0.996] | 0.1814 |
| +R | 67% | 6270 | 4 | 1.085 | [0.989, 1.29] | 1.0 |
| ADDPNS | 83% | 5495.8 | 5 | 0.743 | [0.534, 0.996] | 0.1814 |
| ADDPNS+data | 83% | 403.2 | 5 | 0.079 | [0.027, 0.209] | 0.0591 |
| ADDPNS+bandit | 83% | 3397.4 | 5 | 0.439 | [0.159, 0.855] | 0.1003 |
| df-pn | 100% | 462.7 | 5 | 0.105 | [0.03, 0.378] | 0.0591 |
| PN2 | 83% | 12443.4 | 5 | 1.76 | [1.206, 2.877] | 0.0591 |
