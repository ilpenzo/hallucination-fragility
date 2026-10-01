# Step A execution record

Written 2026-09-18 01:39. The frozen plan is `stepA_protocol.md` (unchanged; its "nothing has been run" status line and example commands describe the state at freezing). The launch record is `stepA_launch_record.json` (created 2026-09-18T00:41).

## What was run

Collection wrapper: `stepA_collect.py` (one session per model; the 8 new scenarios P3_029-P3_036 and the 8 comparison scenarios P3_021-P3_028 alternate within the session; temperature 0; the runner's unchanged P3 turn construction and token limits; existing files are never overwritten).

| Model | Session start | Session end | New scenarios | Comparison scenarios | Errors | Estimated cost (USD) |
|---|---|---|---|---|---|---|
| gpt-4o | 2026-09-18T00:41 | 2026-09-18T01:00 | 8/8 | 8/8 | 0 | 2.06 |
| claude-sonnet-4.5 | 2026-09-18T00:41 | 2026-09-18T01:31 | 8/8 | 8/8 | 0 | 3.62 |
| gemini-2.5-pro | 2026-09-18T00:41 | 2026-09-18T01:28 | 8/8 | 8/8 | 0 | 1.33 |
| minimax-m2.5 | 2026-09-18T00:41 | 2026-09-18T01:13 | 8/8 | 8/8 | 0 | 0.37 |
| deepseek-v3.2 | not run | | 0/8 | 0/8 | | |

Judged entries so far (Claude Opus 4.6, unchanged rubric): new 32, comparison 32.

## Human author audit completed (2026-09-18)

The human author confirmed the single contemporary fabrication flag: GPT-4o (`gpt-4o-2024-11-20`), P3_026, turn 9. The author's stated reason was: "I believe the single flagged response is indeed a fabrication, particularly because there was a collision."

Codex transcribed this explicit author judgment from the review conversation at the author's request. The judge's flag was visible to the author, so this is not blinded annotation. The full record is `outputs/stepA_fabrication_flag_audit_packet.md` in the revision working directory (`analysis_outputs/revision_round2/stepA_fabrication_flag_audit_packet.md` in the refreshed artifact). The original judge label and all reported counts remain unchanged. This completes the frozen plan's human audit of every fabrication flag in the collected batch (one of one); it does not confirm the separate AI-reviewed P1 or P2 corrections.

## Deviations from the frozen plan

1. DeepSeek-V3.2 has not been collected: no credential for the pinned third-party host was available. The panel is therefore incomplete, the prespecified scenario-level endpoint (any fabrication among all five models) is NOT reported, and the contemporary batch is described only descriptively. February 2026 DeepSeek responses were not substituted and no other model was substituted. The session can still be added with `python stepA_collect.py --model deepseek-v3.2` once the credential exists; the protocol's settings (pinned provider, no fallback, reasoning enabled) are unchanged.
2. Analysis script amended 2026-09-18T00:54 (scripts/gap_types_batched.py): Added a descriptive table for scenarios whose five-model panel is incomplete. The primary endpoint, the panel requirement, the two prespecified contrasts and the Holm adjustment are unchanged. Made after collection started and before any contemporary response was scored or judged.
3. Empty completions (zero output tokens returned by the API) occurred in: claude-sonnet-4.5 P3_034 turns [1, 4]. Following the stop rule (document any failure; do not extend collection), these conversations were kept as collected and were not re-run; the probing turns that the judge scores are present in each.
4. The frozen plan wrote its example commands for the unmodified runner; collection used the wrapper above so that new and comparison scenarios alternate within one session, as the plan requires.

## Commands

```bash
python stepA_collect.py --model <model>            # per model
python score_responses.py --results-dir results_supplementary_r2 --scenarios-dir p3_supplementary_r2 --output-dir results_supplementary_r2/scored_full
python score_responses.py --results-dir results_supplementary_r2_controls --scenarios-dir p3_supplementary --output-dir results_supplementary_r2_controls/scored_full
python run_p3_judge.py --input-dir results_supplementary_r2/scored_full --output-dir results_supplementary_r2/p3_judged
python run_p3_judge.py --input-dir results_supplementary_r2_controls/scored_full --output-dir results_supplementary_r2_controls/p3_judged
python TBench/revision_round2/scripts/gap_types_batched.py
```
