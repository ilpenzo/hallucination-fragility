# Superseded revision scripts (retained for provenance)

These scripts belong to analyses that were withdrawn during the revision and are NOT used for any number in the
revised manuscript. They are kept so that the history of the corrections can be inspected.

- `p2_plan_extractor_v31a.py`: first release of the block-scoped plan extractor. `../plan_extraction_changes.py`
  loads it to list every extraction that revision b changed.
- `conflict_detector_v2.py`: frozen keyword/heuristic incompatibility detector. Rejected for publication after
  comparison with AI-review labels; replaced by the rubric classification in `../classify_incompatibility_llm.py`.
- `parser_comparison.py`, `refusal_decomposition.py`, `bootstrap_robustness.py`, `p2_multirun.py`: analyses built on the
  originally submitted P2 scoring, which did not apply the turn-12 replacement and treated satisfiable turn-15
  requests as conflicts.
- `gap_type_stats.py`, `gap_types_round2.py`: pair-level gap-type tests, replaced by the scenario-level, batch-separated
  analysis in `../gap_types_batched.py`.
- `fill_claim_placeholders.py`: replaced by `../make_tex_tables.py`.

Several of them read development-only inputs and are not expected to run from the released archive.
