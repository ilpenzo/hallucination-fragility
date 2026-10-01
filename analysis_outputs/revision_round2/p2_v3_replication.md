# P2 report (replication); scoring v3.1; 200 checkpoints; bootstrap resamples = 2000; flag source = heuristic v3 (PROVISIONAL; not for publication)

## A. Feasible planning success
| Model | T6 sat_v3 | T11 sat_v3 | Feasible T17 sat_v3 (n) | Feasible T20 sat_v3 (n) | Valid complete plan: T6 | T11 | feasible T17 | feasible T20 | post-revision feasible valid (count) | Coverage |
|---|---|---|---|---|---|---|---|---|---|---|
| Sonnet 4.5 | 0.930 [0.860, 0.990] | 0.954 [0.862, 1.000] | 0.529 [0.529, 0.529] (1) | n/a (0) | 0.60 | 0.90 | 0.00 | nan | 0/1 | 0.76 |
| DeepSeek-V3.2 | 0.980 [0.950, 1.000] | 0.992 [0.977, 1.000] | 1.000 [1.000, 1.000] (1) | n/a (0) | 0.80 | 0.80 | 1.00 | nan | 1/1 | 0.97 |
| Gemini 2.5 Pro | 0.970 [0.930, 1.000] | 0.977 [0.931, 1.000] | 1.000 [1.000, 1.000] (1) | n/a (0) | 0.80 | 0.90 | 1.00 | nan | 1/1 | 0.65 |
| GPT-4o | 0.730 [0.700, 0.760] | 0.731 [0.631, 0.838] | 0.765 [0.765, 0.765] (1) | n/a (0) | 0.00 | 0.10 | 0.00 | nan | 0/1 | 0.62 |
| MiniMax M2.5 | 0.980 [0.950, 1.000] | 0.969 [0.946, 0.992] | 0.941 [0.941, 0.941] (1) | n/a (0) | 0.60 | 0.60 | 0.00 | nan | 0/1 | 0.93 |

## B. Infeasible-request handling (T15 requirement makes the active set unsatisfiable)
| Model | Turn | n | Incompatibility claim at this turn | No plan | Partial | Complete coverage | Requests resolution | Reduced-set sat (diagnostic) | Reduced-set valid (diagnostic) |
|---|---|---|---|---|---|---|---|---|---|
| Sonnet 4.5 | T17 | 9 | 1.00 (9) | 3 | 2 | 4 | 5 | 0.514 | 0 |
| Sonnet 4.5 | T20 | 10 | 1.00 (10) | 2 | 1 | 7 | 1 | 0.667 | 0 |
| DeepSeek-V3.2 | T17 | 9 | 0.89 (9) | 0 | 2 | 7 | 1 | 0.903 | 5 |
| DeepSeek-V3.2 | T20 | 10 | 0.80 (10) | 0 | 0 | 10 | 0 | 0.972 | 6 |
| Gemini 2.5 Pro | T17 | 9 | 0.78 (9) | 6 | 1 | 2 | 2 | 0.271 | 1 |
| Gemini 2.5 Pro | T20 | 10 | 1.00 (10) | 5 | 2 | 3 | 0 | 0.406 | 1 |
| GPT-4o | T17 | 9 | 0.44 (9) | 0 | 6 | 3 | 6 | 0.757 | 0 |
| GPT-4o | T20 | 10 | 0.80 (10) | 0 | 4 | 6 | 4 | 0.872 | 1 |
| MiniMax M2.5 | T17 | 9 | 0.67 (9) | 2 | 1 | 6 | 5 | 0.625 | 1 |
| MiniMax M2.5 | T20 | 10 | 0.70 (10) | 0 | 1 | 9 | 2 | 0.861 | 0 |

## C. Incompatibility claims at T15 by T15 feasibility, false alarms on feasible T17/T20, capacity violations
| Model | T15 claim, infeasible (n) | T15 claim, feasible = false alarm (n) | False alarm feasible T17 (n) | False alarm feasible T20 (n) | Capacity violations (plans with >=1 assignment) |
|---|---|---|---|---|---|
| Sonnet 4.5 | 0.67 (9) | 0.00 (1) | 0.00 (1) | nan (0) | 12/35 = 0.34 |
| DeepSeek-V3.2 | 1.00 (9) | 0.00 (1) | 0.00 (1) | nan (0) | 5/40 = 0.12 |
| Gemini 2.5 Pro | 0.89 (9) | 0.00 (1) | 0.00 (1) | nan (0) | 0/29 = 0.00 |
| GPT-4o | 0.44 (9) | 1.00 (1) | 1.00 (1) | nan (0) | 11/40 = 0.28 |
| MiniMax M2.5 | 0.78 (9) | 1.00 (1) | 0.00 (1) | nan (0) | 12/38 = 0.32 |

Notes: sat_explicit (explicit non-capacity, non-trap constraints only; block-scoped extraction) is kept in the per-checkpoint file as a continuity diagnostic; it is not identical to the original rigid-parser metric. Capacity is interpreted as a maximum item count per slot (minimum of the stated table and any explicit active bound); the historical prompts left the unit ambiguous.

Rank stability of the post-revision valid-plan rate is computed by cross_paradigm_v3.py (scenario-cluster bootstrap).
