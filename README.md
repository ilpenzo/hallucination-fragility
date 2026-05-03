# Selective Hallucination Fragility in Frontier Language Models

This repository contains the code, data, and experimental framework for the paper:

> **Selective Hallucination Fragility in Frontier Language Models**
> Parsa Bakhtary
> arXiv preprint, 2026

## Overview

We demonstrate that hallucination resistance in frontier language models is not a single capability but comprises behaviorally dissociable failure modes. Through a three-paradigm framework testing five frontier models across 550 multi-turn conversations, we identify two failure modes that persist despite robust context memory:

- **Constraint maintenance failure**: Models detect conflicts with near-perfect accuracy (0.963–1.000) but cannot integrate revisions into a coherent constraint set.
- **Epistemic miscalibration**: Models fabricate selectively in response to implied-evidence gaps (7.7%) while correctly abstaining on other gap types (0–3.3%).

Cross-paradigm rank concordance is near-zero (Kendall's W = 0.089), and numeric fidelity and source fidelity are significantly inversely correlated (ρ = −0.895, p = 0.040).

## Models Evaluated

| Model | API Identifier |
|---|---|
| GPT-4o | `gpt-4o-2024-11-20` |
| Claude Sonnet 4.5 | `claude-sonnet-4-5-20250929` |
| DeepSeek-R1 | `deepseek-reasoner` |
| Gemini 2.5 Pro | `gemini-2.5-pro` |
| MiniMax M2.5 | `MiniMax-M2.5` |

## Repository Structure

```
├── paper/                      # LaTeX source and figures
├── scenarios/                  # Scenario generators and generated scenarios
│   ├── generate_p1_scenarios.py    # P1: financial analysis (template-based)
│   ├── generate_p2_scenarios.py    # P2: constraint satisfaction (reverse-generation)
│   ├── generate_supplementary_p3.py # P3 supplementary scenarios
│   ├── p1_scenarios/               # 50 generated P1 scenario files
│   ├── p2_scenarios/               # 40 generated P2 scenario files
│   ├── p3_source_data.json         # 20 core P3 document sets
│   └── p3_supplementary/           # 8 supplementary P3 scenarios (P3_021–028)
├── experiments/                # Experiment execution pipeline
│   ├── conversation_runner.py      # Multi-turn conversation driver
│   ├── run_api_models.py           # API-level model runner
│   ├── score_responses.py          # Automated scoring (P1/P2)
│   ├── run_p3_judge.py             # P3 LLM judge (Claude Opus 4.6)
│   ├── run_gpt52_p3_judge.py       # Cross-provider validation (GPT-5.2)
│   ├── p2_rescore.py               # Enhanced P2 parser + rescoring
│   └── run_supplementary_p3_pipeline.sh
├── analysis/                   # Analysis and figure generation
│   ├── analyze_three_paradigm.py   # Main cross-paradigm analysis
│   ├── supplementary_analyses.py   # Extended analyses
│   ├── recompute_kendalls_w.py     # Concordance statistics
│   ├── compute_kappa.py            # Inter-rater reliability
│   └── ...
├── results/                    # Raw conversation outputs (5 models × 110 scenarios)
├── results_replication/        # Targeted replication (20 scenarios × 5 models)
├── results_supplementary/      # Supplementary P3 results (P3_021–028)
├── gpt52_irr_results/          # GPT-5.2 cross-provider validation data
└── data/                       # Aggregated analysis outputs
```

## Three Paradigms

**Paradigm 1 — Progressive Numerical Analysis**: 50 scenarios × 20 turns of financial analysis with probe questions testing self-output retrieval. Automatically scored against precomputed ground truth with 1% tolerance.

**Paradigm 2 — Constraint Satisfaction Under Load**: 40 scenarios × 20 turns of scheduling with accumulating constraints and a mid-conversation conflict. Plans parsed with a format-tolerant extractor and verified against all active constraints.

**Paradigm 3 — Multi-Document Synthesis**: 20 core scenarios (+ 8 supplementary) with planted contradictions, information gaps, and authority manipulations. Evaluated by Claude Opus 4.6 as LLM judge, validated by GPT-5.2 (97.2% agreement, AC1 = 0.971).

## Reproducing Results

### Prerequisites

```bash
pip install openai anthropic google-generativeai
```

API keys are required for each provider. Set them as environment variables:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- `DEEPSEEK_API_KEY`
- `MINIMAX_API_KEY`

### Running Experiments

```bash
# Generate scenarios (already included in scenarios/)
python scenarios/generate_p1_scenarios.py
python scenarios/generate_p2_scenarios.py

# Run conversations (requires API keys)
python experiments/conversation_runner.py

# Score results
python experiments/score_responses.py
python experiments/run_p3_judge.py

# Analyze
python analysis/analyze_three_paradigm.py
```

### Using Pre-computed Results

All raw conversation outputs and scored results are included in `results/`, `results_replication/`, and `results_supplementary/`. To reproduce the analysis from scored data without re-running API calls:

```bash
python analysis/analyze_three_paradigm.py
python analysis/recompute_kendalls_w.py
python analysis/compute_kappa.py
```

## Citation

```bibtex
@article{bakhtary2026selective,
  title={Selective Hallucination Fragility in Frontier Language Models},
  author={Bakhtary, Parsa},
  journal={arXiv preprint arXiv:XXXX.XXXXX},
  year={2026}
}
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
