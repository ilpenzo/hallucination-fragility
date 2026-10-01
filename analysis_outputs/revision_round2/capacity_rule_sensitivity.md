Explicit capacity sentence vs opening table (40 scenarios): {'equal': 17, 'looser': 19, 'tighter': 4}

## Capacity rule: minimum. Feasible requests: T15 17/40, T17 17/40, T20 12/40
| Model | T6 valid | T11 valid | post-revision feasible valid | post-revision feasible sat | capacity violations (plans with items) |
|---|---|---|---|---|---|
| Sonnet 4.5 | 31/40 | 31/40 | 16/29 = 0.55 | 0.959 | 24/139 |
| DeepSeek-V3.2 | 33/40 | 36/40 | 24/29 = 0.83 | 0.990 | 24/160 |
| Gemini 2.5 Pro | 26/40 | 27/40 | 15/29 = 0.52 | 0.818 | 17/137 |
| GPT-4o | 1/40 | 1/40 | 3/29 = 0.10 | 0.860 | 37/160 |
| MiniMax M2.5 | 30/40 | 32/40 | 10/29 = 0.34 | 0.914 | 39/155 |

## Capacity rule: explicit_replaces_table. Feasible requests: T15 17/40, T17 17/40, T20 12/40
| Model | T6 valid | T11 valid | post-revision feasible valid | post-revision feasible sat | capacity violations (plans with items) |
|---|---|---|---|---|---|
| Sonnet 4.5 | 33/40 | 34/40 | 19/29 = 0.66 | 0.971 | 11/139 |
| DeepSeek-V3.2 | 40/40 | 40/40 | 29/29 = 1.00 | 1.000 | 2/160 |
| Gemini 2.5 Pro | 32/40 | 32/40 | 19/29 = 0.66 | 0.826 | 2/137 |
| GPT-4o | 1/40 | 1/40 | 4/29 = 0.14 | 0.869 | 31/160 |
| MiniMax M2.5 | 31/40 | 34/40 | 13/29 = 0.45 | 0.922 | 27/155 |

Feasibility labels identical under both rules: True
Spearman P1-P2 under the alternative rule: rho = +0.87 (exact permutation p = 0.067); P2 ranks [2.5, 1.0, 2.5, 5.0, 4.0]

## No-plan outputs at the feasible checkpoints T6 and T11, by relation of the two capacity statements
| Model | no plan: looser (of 38) | equal (of 34) | tighter (of 8) |
|---|---|---|---|
| Sonnet 4.5 | 6 | 0 | 0 |
| DeepSeek-V3.2 | 0 | 0 | 0 |
| Gemini 2.5 Pro | 0 | 0 | 0 |
| GPT-4o | 0 | 0 | 0 |
| MiniMax M2.5 | 0 | 0 | 0 |
