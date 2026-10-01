| Role | Path | Files | SHA-256 (first 16) |
|---|---|---|---|
| P1 scores after the extraction fix (input to adjudication, tolerance sweep, replication comparison) | `scored_results/core/scored_full/scored_results_enhanced.json` | 1 | `d07632776a7f53f6` |
| P1 scores with the seven AI-review corrections (source of Table 1 and of the P1 column of Table 6) | `scored_results/core/scored_full/scored_results_p1_adjudicated.json` | 1 | `1f6a65b33127c5e5` |
| P1 replication scores, same extraction rule | `scored_results/replication/scored_full/scored_results_fixed.json` | 1 | `a2c2915d2977f198` |
| Case-level P1 adjudication records (AI review) | `analysis_outputs/revision_round2/p1_adjudication_records.json` | 1 | `27bac976cf3e573f` |
| Verified feasibility labels (output of p2_feasibility.py; read by every P2 script) | `analysis_outputs/revision_round2/p2_feasibility_classes.json` | 1 | `56ac2c1dfbf9d8f4` |
| Rubric labels for the 400 turn-15/turn-17 responses, core batch only | `analysis_outputs/revision_round2/incompatibility_llm_labels_core_feb2026.json` | 1 | `cb389719cde2f488` |
| Cross-judge comparison table (Appendix A) | `analysis_outputs/gpt52_irr_results/irr_comparison.csv` | 1 | `0b480c19479aee7d` |
| Raw P2 responses, core run (never modified) | `model_outputs/core/*/P2_*.json` | 200 | `211b560d8f013ea1` |
| Raw P1 responses, core run (never modified) | `model_outputs/core/*/P1_*.json` | 250 | `4c5ef0006e3c1297` |
| Raw P2 responses, replication run | `model_outputs/replication/*/P2_*.json` | 50 | `f9423bdd20459812` |
| Historical P2 scenarios (unchanged) | `scenarios/p2_scenarios/P2_*.json` | 40 | `93c6aca1435d85dc` |
| P3 judge outputs, core batch | `scored_results/core/p3_judged/individual/*.json` | 100 | `aecdd6adf9b4aff7` |
| P3 judge outputs, supplementary batch (February 2026) | `scored_results/supplementary/p3_judged/individual/*.json` | 40 | `942844633ddf9677` |
| P3 judge outputs, contemporary batch: new scenarios | `scored_results/supplementary_r2/p3_judged/individual/*.json` | 32 | `77650c9ee0299554` |
| P3 judge outputs, contemporary batch: comparison scenarios | `scored_results/supplementary_r2_controls/p3_judged/individual/*.json` | 32 | `be01589bd3dfe908` |
