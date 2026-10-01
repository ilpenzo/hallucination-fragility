## P1 phase-end answers: 95/100 agree between runs
| Model | acc. original | acc. replication |
|---|---|---|
| Sonnet 4.5 | 0.95 | 0.95 |
| DeepSeek-V3.2 | 0.95 | 0.95 |
| Gemini 2.5 Pro | 0.95 | 1.00 |
| GPT-4o | 0.90 | 0.90 |
| MiniMax M2.5 | 0.80 | 0.90 |

## P2 (protocol v3.1): 10 replicated scenarios; feasible post-revision checkpoints among them: 1 [('P2_008', 17)]
| Model | feasible n | sat original | sat replication | change | max per-checkpoint change | all-checkpoint sat original | replication | valid plans (feasible) original | replication |
|---|---|---|---|---|---|---|---|---|---|
| Sonnet 4.5 | 21 | 0.741 | 0.922 | +0.181 | 1.00 | 0.549 | 0.766 | 14/21 | 15/21 |
| DeepSeek-V3.2 | 21 | 0.995 | 0.987 | -0.008 | 0.10 | 0.976 | 0.964 | 20/21 | 17/21 |
| Gemini 2.5 Pro | 21 | 0.917 | 0.975 | +0.058 | 0.53 | 0.556 | 0.674 | 16/21 | 18/21 |
| GPT-4o | 21 | 0.655 | 0.732 | +0.077 | 0.38 | 0.688 | 0.773 | 0/21 | 1/21 |
| MiniMax M2.5 | 21 | 0.970 | 0.973 | +0.003 | 0.15 | 0.851 | 0.867 | 15/21 | 12/21 |
- first in the original run: sat: DeepSeek-V3.2, sat_all: DeepSeek-V3.2, valid: DeepSeek-V3.2
- first in the replication run: sat: DeepSeek-V3.2, sat_all: DeepSeek-V3.2, valid: Gemini 2.5 Pro
