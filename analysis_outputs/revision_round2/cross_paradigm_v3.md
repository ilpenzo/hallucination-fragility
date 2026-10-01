| Model | P1 phase-end acc. (rank) | P2 valid plans, feasible post-revision (rank) | P2 sat. (same checkpoints) | P3 gap abstention (rank) |
|---|---|---|---|---|
| Sonnet 4.5 | 0.985 (2) | 16/29 = 0.55 (2) | 0.959 | 0.885 (3) |
| DeepSeek-V3.2 | 0.995 (1) | 24/29 = 0.83 (1) | 0.990 | 0.875 (4.5) |
| Gemini 2.5 Pro | 0.965 (3) | 15/29 = 0.52 (3) | 0.818 | 0.930 (2) |
| GPT-4o | 0.955 (4) | 3/29 = 0.10 (5) | 0.860 | 0.875 (4.5) |
| MiniMax M2.5 | 0.880 (5) | 10/29 = 0.34 (4) | 0.914 | 0.975 (1) |

## Rank statistics (5 models; descriptive)
- Spearman P1-P2: rho = +0.90, exact two-sided permutation p = 0.083
- Spearman P1-P3: rho = -0.56, exact two-sided permutation p = 0.400
- Spearman P2-P3: rho = -0.21, exact two-sided permutation p = 0.733
- Kendall's W (tie-corrected) = 0.367; chi2 = 4.41, df = 4, p = 0.354 (chi-square approx.); exact permutation p = 0.405

## Scenario-level bootstrap rank stability (2000 resamples; P1 n=50 scenarios, P2 n=17 scenarios / 29 checkpoints, P3 n=20 scenarios)
- MiniMax last on P1: 0.995
- MiniMax first on P3: 0.940
- MiniMax last on P1 and first on P3: 0.934
- DeepSeek first on P2 valid-plan rate: 0.984
- GPT-4o last on P2 valid-plan rate: 0.985
- Sonnet second on P2 valid-plan rate: 0.512
- DeepSeek top-2 on P1: 1.000
