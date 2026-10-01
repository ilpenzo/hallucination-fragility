# P2 report (core); scoring v3.1; 800 checkpoints; bootstrap resamples = 2000; flag source = LLM rubric labels

## A. Feasible planning success
| Model | T6 sat_v3 | T11 sat_v3 | Feasible T17 sat_v3 (n) | Feasible T20 sat_v3 (n) | Valid complete plan: T6 | T11 | feasible T17 | feasible T20 | post-revision feasible valid (count) | Coverage |
|---|---|---|---|---|---|---|---|---|---|---|
| Sonnet 4.5 | 0.882 [0.782, 0.963] | 0.906 [0.821, 0.971] | 0.958 [0.934, 0.983] (17) | 0.961 [0.921, 0.991] (12) | 0.78 | 0.78 | 0.53 | 0.58 | 16/29 | 0.80 |
| DeepSeek-V3.2 | 0.982 [0.970, 0.993] | 0.992 [0.985, 0.998] | 0.986 [0.972, 0.997] (17) | 0.996 [0.987, 1.000] (12) | 0.82 | 0.90 | 0.76 | 0.92 | 24/29 | 1.00 |
| Gemini 2.5 Pro | 0.955 [0.927, 0.980] | 0.923 [0.871, 0.965] | 0.789 [0.640, 0.920] (17) | 0.860 [0.737, 0.965] (12) | 0.65 | 0.68 | 0.47 | 0.58 | 15/29 | 0.68 |
| GPT-4o | 0.765 [0.740, 0.790] | 0.675 [0.631, 0.719] | 0.844 [0.796, 0.889] (17) | 0.882 [0.833, 0.925] (12) | 0.03 | 0.03 | 0.06 | 0.17 | 3/29 | 0.56 |
| MiniMax M2.5 | 0.978 [0.953, 0.995] | 0.971 [0.946, 0.990] | 0.896 [0.824, 0.952] (17) | 0.939 [0.873, 0.982] (12) | 0.75 | 0.80 | 0.29 | 0.42 | 10/29 | 0.93 |

## B. Infeasible-request handling (T15 requirement makes the active set unsatisfiable)
| Model | Turn | n | Incompatibility claim at this turn | No plan | Partial | Complete coverage | Requests resolution | Reduced-set sat (diagnostic) | Reduced-set valid (diagnostic) |
|---|---|---|---|---|---|---|---|---|---|
| Sonnet 4.5 | T17 | 23 | 0.96 (23) | 11 | 5 | 7 | 14 | 0.391 | 0 |
| Sonnet 4.5 | T20 | 28 | nan (0) | 4 | 4 | 20 | 0 | 0.744 | 2 |
| DeepSeek-V3.2 | T17 | 23 | 0.95 (21) | 0 | 1 | 22 | 6 | 0.951 | 13 |
| DeepSeek-V3.2 | T20 | 28 | nan (0) | 0 | 0 | 28 | 1 | 0.972 | 16 |
| Gemini 2.5 Pro | T17 | 23 | 1.00 (23) | 12 | 10 | 1 | 5 | 0.250 | 1 |
| Gemini 2.5 Pro | T20 | 28 | nan (0) | 10 | 12 | 6 | 1 | 0.468 | 2 |
| GPT-4o | T17 | 23 | 0.52 (23) | 0 | 19 | 4 | 17 | 0.620 | 0 |
| GPT-4o | T20 | 28 | nan (0) | 0 | 11 | 17 | 16 | 0.833 | 1 |
| MiniMax M2.5 | T17 | 23 | 0.83 (23) | 4 | 2 | 17 | 16 | 0.731 | 2 |
| MiniMax M2.5 | T20 | 28 | nan (0) | 1 | 2 | 25 | 3 | 0.849 | 5 |

## C. Incompatibility claims at T15 by T15 feasibility, false alarms on feasible T17/T20, capacity violations
| Model | T15 claim, infeasible (n) | T15 claim, feasible = false alarm (n) | False alarm feasible T17 (n) | False alarm feasible T20 (n) | Capacity violations (plans with >=1 assignment) |
|---|---|---|---|---|---|
| Sonnet 4.5 | 0.87 (23) | 0.12 (17) | 0.24 (17) | nan (0) | 24/139 = 0.17 |
| DeepSeek-V3.2 | 0.91 (22) | 0.06 (17) | 0.00 (17) | nan (0) | 24/160 = 0.15 |
| Gemini 2.5 Pro | 1.00 (23) | 0.35 (17) | 0.35 (17) | nan (0) | 17/137 = 0.12 |
| GPT-4o | 0.41 (22) | 0.00 (16) | 0.41 (17) | nan (0) | 37/160 = 0.23 |
| MiniMax M2.5 | 0.82 (22) | 0.12 (17) | 0.31 (16) | nan (0) | 39/155 = 0.25 |

Notes: sat_explicit (explicit non-capacity, non-trap constraints only; block-scoped extraction) is kept in the per-checkpoint file as a continuity diagnostic; it is not identical to the original rigid-parser metric. Capacity is interpreted as a maximum item count per slot (minimum of the stated table and any explicit active bound); the historical prompts left the unit ambiguous.

Rank stability of the post-revision valid-plan rate is computed by cross_paradigm_v3.py (scenario-cluster bootstrap).
