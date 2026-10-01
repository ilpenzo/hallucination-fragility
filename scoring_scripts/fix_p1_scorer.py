#!/usr/bin/env python3
"""
fix_p1_scorer.py — Diagnose and fix the 'last number' extraction bug.

The bug: score_responses.py extracts the LAST number from the full response text.
When models mention years (Q3 2023, Q2 2024) in their analysis, the last number
is often the year rather than the answer. This causes correct answers to be
scored as wrong (56.1% of all P1 errors have model_value of a year).

The fix: For each response, extract ALL numbers, filter out year-like values
that appear in quarter references (Q1-Q4 2020-2030), and check whether ANY
remaining number matches the target within tolerance.

Approach:
  1. Load scored_results_enhanced.json
  2. For every P1 turn that was scored 0.0, reload the original response text
  3. Re-extract numbers with the improved method
  4. Report: how many scores flip from 0 to 1? What do new metrics look like?
  5. Optionally write corrected scored_results_enhanced.json

Usage:
  python fix_p1_scorer.py --results-dir ./results \
      --scored-results ./results/scored_full/scored_results_enhanced.json \
      --dry-run          # just report, don't write
  python fix_p1_scorer.py --results-dir ./results \
      --scored-results ./results/scored_full/scored_results_enhanced.json \
      --output ./results/scored_full/scored_results_fixed.json
"""

import json
import os
import re
import copy
import argparse
import glob
from typing import List, Optional, Dict, Tuple


def extract_numbers_improved(text: str) -> Tuple[List[float], List[float]]:
    """
    Extract numbers from response text, separating answer candidates from
    year references.

    Returns:
        (candidate_numbers, filtered_years)

    A number is classified as a year reference if:
      - It's a 4-digit integer in range 2020-2030, AND
      - It appears immediately after 'Q1'/'Q2'/'Q3'/'Q4' or 'FY' or 'fiscal'
        or at the start of a quarter reference pattern
    """
    clean = text.replace("$", "").replace(",", "").replace("%", "")

    # Find all numbers with their positions
    all_matches = list(re.finditer(r'-?\d+(?:\.\d+)?', clean))
    if not all_matches:
        return [], []

    candidates = []
    years = []

    for m in all_matches:
        val = float(m.group())
        start = m.start()

        # Check if this looks like a year in a quarter reference
        is_year_ref = False
        if 2020 <= val <= 2030 and val == int(val):
            # Look at preceding text (up to 10 chars back)
            prefix = clean[max(0, start - 10):start].strip().lower()
            # Quarter patterns: "q3 ", "q3-", "q3_"
            if re.search(r'q[1-4]\s*$', prefix):
                is_year_ref = True
            # Fiscal year patterns
            elif re.search(r'(fy|fiscal)\s*$', prefix):
                is_year_ref = True
            # Standalone year at sentence boundary or after common prepositions
            elif re.search(r'(in|of|for|from|to|through|during|year|vs\.?)\s*$', prefix):
                is_year_ref = True
            # Year followed by quarter references or as part of date
            suffix = clean[m.end():m.end() + 5].strip().lower()
            if re.match(r'^[:\-/]', suffix):
                is_year_ref = True

        if is_year_ref:
            years.append(val)
        else:
            candidates.append(val)

    return candidates, years


def check_any_match(candidates: List[float], target: float,
                    tol_pct: float = 0.01, tol_abs: float = 0.1) -> Optional[float]:
    """
    Check if any candidate number matches the target within tolerance.
    Returns the matching value, or None.

    Search strategy: check all candidates. If multiple match, prefer
    the one closest to target.
    """
    if target == 0:
        matches = [c for c in candidates if abs(c) <= tol_abs]
    else:
        matches = [c for c in candidates
                   if (abs(c - target) / abs(target) <= tol_pct)
                   or (abs(c - target) <= tol_abs)]

    if not matches:
        return None
    # Return closest match
    return min(matches, key=lambda c: abs(c - target))


def load_response_text(results_dir: str, model: str, scenario_id: str,
                       turn_number: int) -> Optional[str]:
    """Load the original response text from result files."""
    # Try different path patterns
    paths_to_try = [
        os.path.join(results_dir, model, f"{scenario_id}.json"),
    ]
    # Also try glob
    glob_pattern = os.path.join(results_dir, "*", f"{scenario_id}.json")
    for p in glob.glob(glob_pattern):
        if model in p:
            paths_to_try.insert(0, p)

    for path in paths_to_try:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                if data.get("model") != model:
                    continue
                for turn in data.get("turns", []):
                    if turn.get("turn_number") == turn_number:
                        return turn.get("response", "")
            except (json.JSONDecodeError, KeyError):
                continue
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="./results")
    parser.add_argument("--scored-results",
                        default="./results/scored_full/scored_results_enhanced.json")
    parser.add_argument("--output", default=None,
                        help="Path to write fixed scored results (omit for dry-run)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only report, don't write")
    args = parser.parse_args()

    with open(args.scored_results) as f:
        scored = json.load(f)

    # ---------- Phase 1: Identify affected turns ----------
    print("=" * 70)
    print("PHASE 1: Identifying turns affected by year-extraction bug")
    print("=" * 70)

    p1_entries = [e for e in scored if e.get("paradigm") == "P1"]
    print(f"Total P1 entries: {len(p1_entries)}")

    # Count wrong turns with year-like model_value
    wrong_turns = []
    for entry in p1_entries:
        model = entry["model"]
        sid = entry["scenario_id"]
        for turn in entry.get("turn_scores", []):
            if turn.get("score", 1.0) == 0.0:
                mv = turn.get("details", {}).get("model_value")
                tv = turn.get("details", {}).get("target_value")
                is_year = mv is not None and mv in [2022.0, 2023.0, 2024.0, 2025.0]
                wrong_turns.append({
                    "model": model,
                    "scenario_id": sid,
                    "turn_number": turn["turn_number"],
                    "model_value": mv,
                    "target_value": tv,
                    "is_year": is_year,
                    "scoring_type": turn.get("question_type", ""),
                    "is_probe": turn.get("is_probe", False),
                    "phase": turn.get("phase", ""),
                })

    year_turns = [t for t in wrong_turns if t["is_year"]]
    non_year_turns = [t for t in wrong_turns if not t["is_year"]]

    print(f"\nTotal wrong P1 turns: {len(wrong_turns)}")
    print(f"  Year-extraction suspected: {len(year_turns)} ({100*len(year_turns)/len(wrong_turns):.1f}%)")
    print(f"  Other errors: {len(non_year_turns)}")

    # Break down by model
    print("\nYear-extraction errors by model:")
    by_model = {}
    for t in year_turns:
        by_model.setdefault(t["model"], []).append(t)
    for model, turns in sorted(by_model.items()):
        print(f"  {model}: {len(turns)} turns")

    print("\nYear-extraction errors by phase:")
    by_phase = {}
    for t in year_turns:
        by_phase.setdefault(t["phase"], []).append(t)
    for phase, turns in sorted(by_phase.items()):
        probes = sum(1 for t in turns if t["is_probe"])
        print(f"  {phase}: {len(turns)} ({probes} probes)")

    # ---------- Phase 2: Re-extract and re-score ----------
    print("\n" + "=" * 70)
    print("PHASE 2: Re-scoring with improved number extraction")
    print("=" * 70)

    flipped = []
    still_wrong = []
    load_failures = []

    for t in year_turns:
        response = load_response_text(
            args.results_dir, t["model"], t["scenario_id"], t["turn_number"]
        )
        if response is None:
            load_failures.append(t)
            continue

        candidates, filtered_years = extract_numbers_improved(response)
        target = t["target_value"]

        if target is None:
            still_wrong.append({**t, "reason": "no target value"})
            continue

        # Determine tolerance from the turn's scoring context
        # Default tolerances from score_responses.py
        tol_pct = 0.01  # 1%
        tol_abs = 0.5 if abs(target) >= 5 else 0.1

        match = check_any_match(candidates, target, tol_pct, tol_abs)

        if match is not None:
            flipped.append({
                **t,
                "new_model_value": match,
                "old_model_value": t["model_value"],
                "n_candidates": len(candidates),
                "n_years_filtered": len(filtered_years),
            })
        else:
            # Also try: maybe the correct number was classified as a year
            # (edge case: target IS a year-like number)
            all_nums = candidates + filtered_years
            match_all = check_any_match(all_nums, target, tol_pct, tol_abs)
            if match_all is not None:
                flipped.append({
                    **t,
                    "new_model_value": match_all,
                    "old_model_value": t["model_value"],
                    "n_candidates": len(candidates),
                    "n_years_filtered": len(filtered_years),
                    "note": "matched in year-filtered set",
                })
            else:
                still_wrong.append({
                    **t,
                    "reason": "no matching number found even after fix",
                    "candidates": candidates[:10],
                    "target": target,
                })

    print(f"\nResults:")
    print(f"  Scores flipped 0 -> 1: {len(flipped)}")
    print(f"  Still wrong after fix: {len(still_wrong)}")
    print(f"  Could not load response: {len(load_failures)}")

    print(f"\nFlipped by model:")
    flip_by_model = {}
    for f in flipped:
        flip_by_model.setdefault(f["model"], []).append(f)
    for model, turns in sorted(flip_by_model.items()):
        probes = sum(1 for t in turns if t["is_probe"])
        print(f"  {model}: {len(turns)} flipped ({probes} probes)")

    print(f"\nFlipped by phase:")
    flip_by_phase = {}
    for f in flipped:
        flip_by_phase.setdefault(f["phase"], []).append(f)
    for phase, turns in sorted(flip_by_phase.items()):
        print(f"  {phase}: {len(turns)}")

    # ---------- Phase 3: Compute corrected metrics ----------
    print("\n" + "=" * 70)
    print("PHASE 3: Impact on paper metrics")
    print("=" * 70)

    # Build lookup of flipped turns
    flip_set = set()
    for f in flipped:
        flip_set.add((f["model"], f["scenario_id"], f["turn_number"]))

    # Recompute per-model P1 metrics
    print("\nCorrected P1 metrics:")
    print(f"{'Model':<20} {'Old Acc':>8} {'New Acc':>8} {'Δ':>6} "
          f"{'Old Probe':>10} {'New Probe':>10} {'Δ':>6}")
    print("-" * 72)

    for model_name in ["claude-sonnet-4.5", "deepseek-r1", "gemini-2.5-pro",
                        "gpt-4o", "minimax-m2.5"]:
        entries = [e for e in p1_entries if e["model"] == model_name]
        if not entries:
            continue

        old_correct = 0
        new_correct = 0
        old_probe_correct = 0
        new_probe_correct = 0
        total_scorable = 0
        total_probes = 0

        for entry in entries:
            for turn in entry.get("turn_scores", []):
                score = turn.get("score", 0)
                tn = turn["turn_number"]
                is_probe = turn.get("is_probe", False)
                was_flipped = (model_name, entry["scenario_id"], tn) in flip_set

                total_scorable += 1
                old_correct += score
                new_correct += (1.0 if was_flipped else score)

                if is_probe:
                    total_probes += 1
                    old_probe_correct += score
                    new_probe_correct += (1.0 if was_flipped else score)

        old_acc = old_correct / total_scorable if total_scorable else 0
        new_acc = new_correct / total_scorable if total_scorable else 0
        old_probe = old_probe_correct / total_probes if total_probes else 0
        new_probe = new_probe_correct / total_probes if total_probes else 0

        print(f"{model_name:<20} {old_acc:>8.3f} {new_acc:>8.3f} {new_acc-old_acc:>+6.3f} "
              f"{old_probe:>10.3f} {new_probe:>10.3f} {new_probe-old_probe:>+6.3f}")

    # ---------- Phase 4: Show some still-wrong cases for sanity check ----------
    print("\n" + "=" * 70)
    print("PHASE 4: Sample of still-wrong turns (sanity check)")
    print("=" * 70)
    for sw in still_wrong[:10]:
        print(f"  {sw['model']}/{sw['scenario_id']} T{sw['turn_number']}: "
              f"target={sw.get('target')}, candidates={sw.get('candidates', [])[:5]}, "
              f"reason={sw.get('reason', '?')}")

    # ---------- Phase 5: Write corrected file ----------
    if args.output and not args.dry_run:
        print(f"\n{'='*70}")
        print(f"PHASE 5: Writing corrected scored results to {args.output}")
        print(f"{'='*70}")

        corrected = copy.deepcopy(scored)
        n_patched = 0

        for entry in corrected:
            if entry.get("paradigm") != "P1":
                continue
            model = entry["model"]
            sid = entry["scenario_id"]

            any_changed = False
            for turn in entry.get("turn_scores", []):
                key = (model, sid, turn["turn_number"])
                if key in flip_set:
                    # Find the flip record
                    flip_rec = next(f for f in flipped
                                    if (f["model"], f["scenario_id"],
                                        f["turn_number"]) == key)
                    turn["score"] = 1.0
                    turn["reason"] = (f"FIXED: Was {turn['reason']}. "
                                      f"Correct value {flip_rec['new_model_value']} "
                                      f"found in response (year {flip_rec['old_model_value']:.0f} "
                                      f"was incorrectly extracted).")
                    turn["details"]["model_value"] = flip_rec["new_model_value"]
                    turn["details"]["is_close"] = True
                    any_changed = True
                    n_patched += 1

            if any_changed:
                # Recompute entry-level metrics
                turns = entry["turn_scores"]
                scorable = [t for t in turns if t.get("score") is not None]
                probes = [t for t in turns if t.get("is_probe")]

                entry["overall_accuracy"] = (
                    sum(t["score"] for t in scorable) / len(scorable)
                    if scorable else 0
                )
                entry["probe_accuracy"] = (
                    sum(t["score"] for t in probes) / len(probes)
                    if probes else 0
                )

                # Recompute phase_accuracy
                phases = {}
                for t in turns:
                    phase = t.get("phase", "unknown")
                    phases.setdefault(phase, []).append(t["score"])
                entry["phase_accuracy"] = {
                    phase: sum(scores) / len(scores)
                    for phase, scores in phases.items()
                }

        print(f"Patched {n_patched} turn scores across {len(corrected)} entries")

        # Safe JSON write
        class SafeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, float):
                    if obj != obj:  # NaN
                        return None
                    if obj == float('inf') or obj == float('-inf'):
                        return None
                return super().default(obj)

        with open(args.output, "w") as f:
            json.dump(corrected, f, indent=2, cls=SafeEncoder)
        print(f"Written to {args.output}")

    elif not args.output:
        print("\n(Dry run: pass --output <path> to write corrected file)")


if __name__ == "__main__":
    main()
