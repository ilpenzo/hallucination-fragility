# ContextFidelity-Bench

Code, data, and model outputs for:

> Parsa Bakhtary. ContextFidelity-Bench: A Three-Paradigm Framework for Evaluating Multi-Turn Hallucination Behavior in Language Models. *BenchCouncil Transactions on Benchmarks, Standards and Evaluations*, 2026. https://doi.org/10.66834/0azb3w20

This repository is the public release of the paper's supplementary artifact. It contains benchmark scenarios, prompt material, model outputs, scored outputs, replication outputs, and scripts for data collection, scoring, and analysis. Apart from the changes listed under "About this release" at the end, it is identical to the anonymized artifact reviewed with the paper.

The repository previously held an unpublished 2026 draft, "Selective Hallucination Fragility in Frontier Language Models", whose statistics the paper supersedes. Those files remain available at the git tag `v1-preprint-2026-05`.

## Start here: where the revised paper's numbers come from

| Result in the revised paper | Source in this archive |
|---|---|
| P1 numeric accuracy (Table 1; P1 column of Table 6) | `scored_results/core/scored_full/scored_results_p1_adjudicated.json` |
| P2 feasible-plan success, unsatisfiable requests, plan output types, capacity reading (Tables 2, 3, 10, 11; Figure 1) | `analysis_outputs/revision_round2/` |
| Cross-paradigm summary and rank stability (Table 6; Figure 2) | `analysis_outputs/revision_round2/cross_paradigm_v3.*` |
| P3 source fidelity (Table 4) | `scored_results/core/p3_judged/` (unchanged from the original submission) |
| P3 gap types, by batch (Table 5 and the contemporary supplement) | `analysis_outputs/revision_round2/gap_types_batched.*` |
| Judge agreement, replication, tolerance sweep (Tables 8, 9, 12; Appendix B) | `analysis_outputs/revision_round2/` and `analysis_outputs/gpt52_irr_results/` |

Everything is reproduced by the commands under "Reproducing the revised results" below. `analysis_outputs/revision_round2/inputs_manifest.md` lists every input those commands read, with its role and SHA-256 digest. Materials produced by the originally submitted scoring are kept unchanged and are described under "Historical materials" at the end; do not use them to reproduce the revised paper.

**Read this first.** During the revision the P2 (scheduling) scoring was audited and rebuilt (scoring protocol v3.1). Every P2 number in the revised paper comes from `analysis_outputs/revision_round2/`, produced by `analysis_scripts/revision_round2/`. The P2 values stored elsewhere in this archive (the P2 fields of `scored_results/*/scored_full/*.json`, `analysis_outputs/p2_parser_analysis/`, `analysis_outputs/p2_rescore_results/`, the P2 columns of `analysis_outputs/analysis/tables/`, `analysis_outputs/root_summaries/`, and the figures in `analysis_outputs/figures/`) were produced by the originally submitted scoring and are retained unchanged as historical records. No model output was replaced, removed, or selected; all raw responses in `model_outputs/` are the originals.

**What was corrected in P2.** (1) The original scorers kept checking a requirement that the user replaces at turn 12. (2) The turn-15 requirement was built to break the reference plan, not to be unsatisfiable; exhaustive search shows a satisfying plan still exists in 17 of 40 scenarios at turns 15 and 17 and in 12 at turn 20 (`p2_feasibility_classes.json`, with one witness plan per feasible request in `p2_feasibility_witnesses.json`). (3) The original plan extractor read assignments from outside the proposed plan. (4) Slot capacities were never checked. (5) The keyword conflict detector fired on almost every response. Protocol v3.1 scores feasible and infeasible requests separately, extracts only the plan the model proposes (with source spans), enforces capacities, and labels incompatibility claims with a frozen written rubric.

**Model identification.** The directory and key name `deepseek-r1` is historical. The `deepseek-reasoner` endpoint used for all February 2026 runs served DeepSeek-V3.2 in thinking mode according to the provider's change log; the paper labels this model DeepSeek-V3.2. Names inside the archive were left unchanged so that every file reference keeps working. Relabelling does not alter the recorded responses or their scores.

**P1.** `scored_results/core/scored_full/scored_results_enhanced.json` is the post-fix P1 score file. `scored_results_p1_adjudicated.json` additionally applies the seven case-level corrections in `analysis_outputs/revision_round2/p1_adjudication_records.json` (an accepted number that was not the final asserted answer). Those corrections come from AI-assisted inspection of 22 selected cases; each record has an `author_confirmed` field, which is empty.

**AI-assisted review is labelled as such.** `analysis_outputs/revision_round2/ai_review/` holds case-level verdicts produced by an AI assistant (`human_validation: false`). They are the reference used by `validate_incompatibility_labels.py` and the source of the P1 corrections. The audit packets that were reviewed are the `*_packet.md` files. Nothing in the revision materials is human annotation unless it says so. The one human record is `analysis_outputs/revision_round2/stepA_fabrication_flag_audit_packet.md`: the author's unblinded verdict on the single fabrication flag of the contemporary P3 supplement, kept separate from the LLM judge's label, which is unchanged.

## Reproducing the revised results

Python 3.10 or newer; only the standard library is needed for everything except figures (matplotlib, numpy). Run from the archive root; the scripts detect the archive layout automatically and write to `analysis_outputs/revision_round2/`.

```bash
cd analysis_scripts/revision_round2
python inputs_manifest.py               # which files each analysis reads, with SHA-256 digests and roles
python p2_feasibility.py                 # verified feasibility labels and witness plans (exhaustive search)
python p2_v3_report.py --tag core        # Tables 2, 3 (output types), 10; per-checkpoint file p2_v3_checkpoints_core.json
python p2_v3_report.py --tag replication --results-dir ../../model_outputs/replication
python capacity_rule_sensitivity.py      # Table 2 "alt. cap." column and Table 11
python apply_p1_overrides.py             # Table 1 (writes scored_results_p1_adjudicated.json)
python cross_paradigm_v3.py              # Table 6; exact permutation p-values; scenario-level bootstrap rank stability
python replication_v3.py                 # Appendix B
python validate_incompatibility_labels.py core_feb2026   # Table 3 claim columns; agreement with the AI-review samples
python plan_extraction_changes.py        # every extraction changed by extractor revision b, with its source text
python tolerance_sweep.py                # Table 12 (uses the seven adjudicated answers; `--pre-adjudication` reproduces the archived earlier sweep)
python irr_raw_agreement.py              # Table 9
python gap_types_batched.py              # Table 5 (historical batch) and the contemporary batch, never pooled
python make_tex_tables.py                # LaTeX rows and sentences used in the paper -> tex_regions.tex
python make_figures.py                   # Figures 1 and 2 -> figures/
```

`classify_incompatibility_llm.py` contains the frozen rubric and the exact prompt used to label the 400 turn-15 and turn-17 responses (`incompatibility_llm_labels_core_feb2026.json`: label, verbatim supporting quote, quote verification, content hash). Of the 400 quotes, 396 were verified; the four responses with an unverifiable quote carry `effective_label: UNCLEAR`, as do three that the classifier labelled unclear, and the seven are excluded from every reported rate (`incompatibility_rates.md` shows YES over decided labels). Re-running it needs an API key and is not required to reproduce any table. Labels are batch-specific and are never reused for the replication responses.

Bootstrap intervals use fixed seeds and a separate generator per interval, so they reproduce exactly.

## Contents

- `scenario_generators/`: scripts that generate P1, P2, and supplementary P3 scenarios, including the corrected P2 generator (`generate_p2_scenarios_v2.py`).
- `scenarios/`: benchmark scenario files and source materials, including P1, P2, P3, the supplementary P3 sets, and replication subsets.
- `prompts/`: saved P3 judge prompts. P1 and P2 task prompts are embedded in their scenario JSON files.
- `model_outputs/`: raw model responses for the core benchmark, the supplementary and replication runs, and the contemporary P3 supplement. These are the original responses; none was replaced, removed, or selected.
- `scored_results/`: scored outputs and P3 judged outputs. The P2 fields of these files come from the originally submitted scoring and are historical.
- `scoring_scripts/`: the original deterministic scoring scripts for P1 and P2 and utilities for preparing P3 judge inputs. `p2_rescore.py` is imported by the revised P2 scripts only for its domain tables and constraint checker.
- `analysis_scripts/revision_round2/`: the corrected P2 scoring protocol (version 3.1) and every analysis of the revised paper. `analysis_scripts/` otherwise holds the original submission's analysis scripts.
- `analysis_outputs/revision_round2/`: outputs of the revised analyses, audit packets, AI-review records, classification labels, and regenerated figures. `analysis_outputs/` otherwise holds the original submission's outputs.
- `replication_scripts/`: the data-collection scripts (see "Data collection scripts" below), scripts for preparing and comparing the replication subset, and the plan, launch record, execution record, and collection wrapper of the contemporary P3 supplement.

## Benchmark paradigms

P1 numeric accuracy: a 20-turn financial analysis with exact answers. Scenarios are in `scenarios/p1_scenarios/`, raw outputs in `model_outputs/core/*/P1_*.json`.

P2 constraint satisfaction under revision: a 20-turn scheduling task with checkpoints at turns 6, 11, 17, and 20. Scenarios are in `scenarios/p2_scenarios/` (unchanged), raw outputs in `model_outputs/core/*/P2_*.json`, verified feasibility labels and all revised scores in `analysis_outputs/revision_round2/`.

P3 multi-document synthesis: source material is in `scenarios/p3_source_data.json`, `scenarios/p3_supplementary/`, and `scenarios/p3_supplementary_r2/`; raw outputs in `model_outputs/core/*/P3_*.json` and the supplementary folders; judge prompts in `prompts/p3_judge_prompts/`; judged outputs in `scored_results/*/p3_judged/`.

## Other additions in the revision

- `scenario_generators/generate_p2_scenarios_v2.py`: corrected generator for future collections (not used for the reported results). It verifies the feasibility of every checkpoint by exhaustive search and can force the turn-15 requirement to be genuinely unsatisfiable or genuinely satisfiable (`--conflict-mode`), stores the effective requirements with the turn-12 replacement applied, gives each slot a single capacity value with a stated unit, and adds an explicit priority rule to the system prompt.
- `analysis_scripts/revision_round2/superseded/`: withdrawn analyses and the first extractor release, kept for provenance (see its README).
- `scenario_generators/generate_supplementary_p3_round2.py` and `scenarios/p3_supplementary_r2/`: eight new P3 scenarios (P3_029 to P3_032 missing reason; P3_033 to P3_036 implied not stated). `replication_scripts/stepA_protocol.md` is the collection and analysis plan fixed before collection, `stepA_launch_record.json` the hashes recorded at launch, and `stepA_collect.py` the collection wrapper (it imports `conversation_runner.py` from the same folder). `replication_scripts/stepA_execution_record.md` is the dated record of what was actually run and every deviation from the plan. The contemporary batch (September 2026) currently covers four of the five models: conversations are in `model_outputs/supplementary_r2/` and `model_outputs/supplementary_r2_controls/`, judge outputs in `scored_results/supplementary_r2*/p3_judged/individual/`. Because the panel is incomplete, `gap_types_batched.py` excludes every contemporary scenario from the prespecified scenario-level endpoint and prints a separate, explicitly descriptive table. The batch is never pooled with the February 2026 batch.
- `analysis_scripts/recompute_kendalls_w.py` computes the exact chi-square p-value; the statistics in the revised paper come from `cross_paradigm_v3.py`.

## Historical materials from the original submission

These are retained unchanged for provenance. They reproduce the ORIGINAL submission, not the revised paper.

- `scored_results/core/scored_full/scored_results_enhanced.json`: the originally released scored file. Its P1 fields are the post-fix P1 scores before the seven adjudicated corrections; its P2 fields come from the superseded P2 scoring.
- `analysis_outputs/p2_parser_analysis/`, `analysis_outputs/p2_rescore_results/`, `analysis_outputs/analysis/`, `analysis_outputs/figure_data/`, `analysis_outputs/figures/`, `analysis_outputs/root_summaries/`: tables, figure data, and figures of the original submission.
- Original scoring and aggregate-analysis commands (historical):

```bash
python -m pip install -r requirements.txt
python scoring_scripts/score_responses.py --results-dir model_outputs/core --scenarios-dir scenarios --output-dir scored_results/recomputed_core
python analysis_scripts/analyze_three_paradigm.py --scored-results scored_results/core/scored_full/scored_results_enhanced.json --output-dir analysis_outputs/recomputed
```

- Original figure scripts (historical): `analysis_scripts/regenerate_all_figures.py`, `generate_heatmap.py`, `generate_radar_chart.py`, `generate_retrieval_figure.py`. Some original scripts assume the development layout; pass explicit paths as above.

## Data collection scripts

`replication_scripts/` includes the provider-client scripts that collected the model responses and the P3 judgments. They read credentials only from environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, `MINIMAX_API_KEY`, `OPENROUTER_API_KEY`); no credentials are included. They are released as executed, so some default paths assume the original development layout; pass explicit paths.

- `conversation_runner.py`: runs the multi-turn conversations (`--scenarios-dir`, `--output-dir`, `--model`, `--paradigm`; `--mock` runs without API calls). This is the version used for the September 2026 contemporary supplement. It adds a provider-pinned client for DeepSeek-V3.2 and records serving provenance for each turn.
- `conversation_runner_feb2026.py`: the version used for the February 2026 core, supplementary, and replication collections, in its state after the 17 February 2026 Gemini fixes (a retry for empty responses and the 8,192-token output limit; both affect only the Gemini client). It is the same file as `experiments/conversation_runner.py` at the tag `v1-preprint-2026-05`.
- `run_p3_judge.py`: the P3 judge runner (Claude Opus 4.6).
- `run_gpt52_p3_judge.py`: the cross-provider re-judging with GPT-5.2 (Appendix A of the paper).
- `stepA_collect.py`: the collection wrapper for the contemporary P3 supplement.

Re-running these scripts is not needed to reproduce any reported table or figure, and new collections will not reproduce the original responses exactly: providers update models behind stable names, and the `deepseek-reasoner` alias used in February 2026 now serves a different model (see "Model identification" above). Credential files, cache files, and old manuscript drafts are not included.

## Citation

Please cite the paper above. `CITATION.cff` contains the citation metadata.

## License

MIT License; see `LICENSE`. Model outputs were generated through the providers' public APIs, and their use may also be subject to those providers' terms.

## About this release

This release is the anonymized artifact reviewed with the paper (`ContextFidelity_Bench_Artifact_Anonymous_R2.zip`, SHA-256 `273d7c645aef5fbeb898d85608507200abb07ae2b5b5c3bebd9f47ac082ee0ef`) with these changes only: the archive's top-level folder was removed so that its contents sit at the repository root; this README was de-anonymized and its review-copy notes replaced by the sections "Data collection scripts", "Citation", "License", and this one; `LICENSE_PLACEHOLDER.txt` was replaced by `LICENSE`; the four collection scripts listed above were added; and `CITATION.cff`, `.zenodo.json`, and `.gitignore` were added. No scenario, model output, score, analysis script, or analysis output changed.
