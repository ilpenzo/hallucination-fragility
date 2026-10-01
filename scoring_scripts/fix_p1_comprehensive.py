#!/usr/bin/env python3
"""
fix_p1_comprehensive.py — Fix ALL P1 number extraction bugs.

The root cause: score_responses.py's clean_number() takes the LAST number
from the response. This causes misscoring whenever the correct answer appears
earlier in the text and a different number (year, percentage, count, etc.)
appears later.

This script:
  1. For EVERY P1 turn scored 0.0, reloads the original response
  2. Extracts ALL numbers from the response
  3. Checks if ANY number matches the target within tolerance
  4. Reports all flips and writes corrected scored_results_fixed.json
  5. Recomputes entry-level metrics (overall_accuracy, probe_accuracy, phase_accuracy)

Usage:
  # Dry run (report only)
  python fix_p1_comprehensive.py --results-dir ./results \
      --scored-results ./results/scored_full/scored_results_enhanced.json \
      --dry-run

  # Write corrected file
  python fix_p1_comprehensive.py --results-dir ./results \
      --scored-results ./results/scored_full/scored_results_enhanced.json \
      --output ./results/scored_full/scored_results_fixed.json
"""

import json
import os
import re
import copy
import argparse
import glob
from typing import List, Optional, Tuple


def extract_all_numbers(text: str) -> List[float]:
    """Extract all numbers from response text after cleaning currency/formatting."""
    clean = text.replace("$", "").replace(",", "").replace("%", "")
    matches = re.findall(r'-?\d+(?:\.\d+)?', clean)
    return [float(m) for m in matches]


def find_best_match(numbers: List[float], target: float,
                    tol_pct: float = 0.01, tol_abs: float = 0.1) -> Optional[float]:
    """
    Check if any number matches the target within tolerance.
    Returns the closest matching value, or None.
    """
    if not numbers or target is None:
        return None

    if target == 0:
        matches = [n for n in numbers if abs(n) <= tol_abs]
    else:
        matches = [n for n in numbers
                   if (abs(n - target) / abs(target) <= tol_pct)
                   or (abs(n - target) <= tol_abs)]

    if not matches:
        return None
    return min(matches, key=lambda n: abs(n - target))


def load_response_text(results_dir: str, model: str, scenario_id: str,
                       turn_number: int) -> Optional[str]:
    """Load the original response text from result files."""
    glob_pattern = os.path.join(results_dir, "*", f"{scenario_id}.json")
    for path in sorted(glob.glob(glob_pattern)):
        if not os.path.exists(path):
            continue
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


def classify_bug(model_value, target_value, all_numbers, matched_value):
    """Classify the type of extraction bug for reporting."""
    if model_value in [2022.0, 2023.0, 2024.0, 2025.0]:
        return "year_extraction"
    elif model_value is not None and target_value is not None:
        # Check if model_value is a number that appears later in the response
        return "wrong_number_selected"
    return "unknown"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="./results")
    parser.add_argument("--scored-results",
                        default="./results/scored_full/scored_results_enhanced.json")
    parser.add_argument("--output", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(args.scored_results) as f:
        scored = json.load(f)

    p1_entries = [e for e in scored if e.get("paradigm") == "P1"]
    print(f"Total P1 entries: {len(p1_entries)}")

    # ---- Collect ALL wrong turns ----
    wrong_turns = []
    for entry in p1_entries:
        for turn in entry.get("turn_scores", []):
            if turn.get("score", 1.0) == 0.0:
                details = turn.get("details", {})
                wrong_turns.append({
                    "model": entry["model"],
                    "scenario_id": entry["scenario_id"],
                    "turn_number": turn["turn_number"],
                    "model_value": details.get("model_value"),
                    "target_value": details.get("target_value"),
                    "is_probe": turn.get("is_probe", False),
                    "phase": turn.get("phase", ""),
                    "question_type": turn.get("question_type", ""),
                    "scoring_type": turn.get("question_type", ""),
                })

    print(f"Total wrong P1 turns to check: {len(wrong_turns)}")

    year_count = sum(1 for t in wrong_turns
                     if t["model_value"] in [2022.0, 2023.0, 2024.0, 2025.0])
    print(f"  Year-extraction suspected: {year_count}")
    print(f"  Other: {len(wrong_turns) - year_count}")

    # ---- Re-extract and re-score ALL wrong turns ----
    flipped = []
    genuinely_wrong = []
    load_failures = []

    for t in wrong_turns:
        response = load_response_text(
            args.results_dir, t["model"], t["scenario_id"], t["turn_number"]
        )
        if response is None:
            load_failures.append(t)
            continue

        target = t["target_value"]
        if target is None:
            genuinely_wrong.append({**t, "reason": "no target value"})
            continue

        all_numbers = extract_all_numbers(response)

        # Determine tolerance
        tol_pct = 0.01  # 1%
        tol_abs = 0.5 if abs(target) >= 5 else 0.1

        match = find_best_match(all_numbers, target, tol_pct, tol_abs)

        if match is not None:
            bug_type = classify_bug(t["model_value"], target, all_numbers, match)
            flipped.append({
                **t,
                "new_model_value": match,
                "old_model_value": t["model_value"],
                "bug_type": bug_type,
            })
        else:
            genuinely_wrong.append({
                **t,
                "reason": "no matching number in response",
                "candidates_sample": all_numbers[:10],
            })

    # ---- Report ----
    print(f"\n{'='*70}")
    print("RESULTS")
    print(f"{'='*70}")
    print(f"  Scores flipped 0 -> 1: {len(flipped)}")
    print(f"  Genuinely wrong: {len(genuinely_wrong)}")
    print(f"  Could not load response: {len(load_failures)}")

    # Break down flips
    print(f"\nFlipped by bug type:")
    by_bug = {}
    for f in flipped:
        by_bug.setdefault(f["bug_type"], []).append(f)
    for bug, cases in sorted(by_bug.items()):
        print(f"  {bug}: {len(cases)}")

    print(f"\nFlipped by model:")
    by_model = {}
    for f in flipped:
        by_model.setdefault(f["model"], []).append(f)
    for model, cases in sorted(by_model.items()):
        probes = sum(1 for c in cases if c["is_probe"])
        print(f"  {model}: {len(cases)} flipped ({probes} probes)")

    print(f"\nFlipped by phase:")
    by_phase = {}
    for f in flipped:
        by_phase.setdefault(f["phase"], []).append(f)
    for phase, cases in sorted(by_phase.items()):
        print(f"  {phase}: {len(cases)}")

    # ---- Compute corrected metrics ----
    flip_set = set()
    flip_lookup = {}
    for f in flipped:
        key = (f["model"], f["scenario_id"], f["turn_number"])
        flip_set.add(key)
        flip_lookup[key] = f

    print(f"\n{'='*70}")
    print("CORRECTED P1 METRICS")
    print(f"{'='*70}")
    print(f"{'Model':<20} {'Old Probe':>10} {'New Probe':>10} {'Delta':>7} "
          f"{'Flipped':>8}")
    print("-" * 60)

    model_order = ["gemini-2.5-pro", "deepseek-r1", "gpt-4o",
                    "claude-sonnet-4.5", "minimax-m2.5"]

    for model_name in model_order:
        entries = [e for e in p1_entries if e["model"] == model_name]
        if not entries:
            continue

        old_probe_correct = 0
        new_probe_correct = 0
        total_probes = 0
        n_flipped = 0

        for entry in entries:
            for turn in entry.get("turn_scores", []):
                if not turn.get("is_probe"):
                    continue
                total_probes += 1
                score = turn.get("score", 0)
                key = (model_name, entry["scenario_id"], turn["turn_number"])
                was_flipped = key in flip_set

                old_probe_correct += score
                new_probe_correct += (1.0 if was_flipped else score)
                if was_flipped:
                    n_flipped += 1

        old_probe = old_probe_correct / total_probes if total_probes else 0
        new_probe = new_probe_correct / total_probes if total_probes else 0

        print(f"{model_name:<20} {old_probe:>10.3f} {new_probe:>10.3f} "
              f"{new_probe-old_probe:>+7.3f} {n_flipped:>8}")

    # ---- Phase accuracy by model (for question-type table) ----
    print(f"\n{'='*70}")
    print("CORRECTED PHASE ACCURACY (for Table 1 in paper)")
    print(f"{'='*70}")
    print(f"{'Model':<20} {'Lookup':>8} {'Single':>8} {'Multi':>8} {'Corr.':>8}")
    print("-" * 56)

    for model_name in model_order:
        entries = [e for e in p1_entries if e["model"] == model_name]
        phase_correct = {}
        phase_total = {}
        for entry in entries:
            for turn in entry.get("turn_scores", []):
                phase = turn.get("phase", "unknown")
                score = turn.get("score", 0)
                key = (model_name, entry["scenario_id"], turn["turn_number"])
                new_score = 1.0 if key in flip_set else score
                phase_correct[phase] = phase_correct.get(phase, 0) + new_score
                phase_total[phase] = phase_total.get(phase, 0) + 1

        lookup = phase_correct.get("lookup", 0) / phase_total.get("lookup", 1)
        single = phase_correct.get("single_step", 0) / phase_total.get("single_step", 1)
        multi = phase_correct.get("multi_step", 0) / phase_total.get("multi_step", 1)
        corr = phase_correct.get("correction", 0) / phase_total.get("correction", 1)
        print(f"{model_name:<20} {lookup:>8.3f} {single:>8.3f} {multi:>8.3f} {corr:>8.3f}")

    # ---- Retrieval failure profiles (for Table 2 in paper) ----
    print(f"\n{'='*70}")
    print("CORRECTED RETRIEVAL FAILURE RATE P(probe_fail | fresh_pass)")
    print(f"{'='*70}")
    print(f"{'Model':<20} {'T5':>6} {'T10':>6} {'T15':>6} {'T20':>6}")
    print("-" * 48)

    for model_name in model_order:
        entries = [e for e in p1_entries if e["model"] == model_name]
        rates = {}
        for probe_tn in [5, 10, 15, 20]:
            probe_fail_fresh_pass = 0
            fresh_pass = 0

            for entry in entries:
                turns_by_num = {}
                for turn in entry.get("turn_scores", []):
                    tn = turn["turn_number"]
                    key = (model_name, entry["scenario_id"], tn)
                    corrected_score = 1.0 if key in flip_set else turn.get("score", 0)
                    turns_by_num[tn] = {**turn, "corrected_score": corrected_score}

                probe = turns_by_num.get(probe_tn)
                if not probe or not probe.get("is_probe"):
                    continue

                # Find adjacent fresh turns
                if probe_tn == 5:
                    fresh_tns = [6, 7]
                elif probe_tn == 10:
                    fresh_tns = [11, 12]
                elif probe_tn == 15:
                    fresh_tns = [16, 17]
                elif probe_tn == 20:
                    fresh_tns = [18]  # T19 is correction ID, T18 is last fresh

                any_fresh_pass = any(
                    turns_by_num.get(ftn, {}).get("corrected_score", 0) == 1.0
                    for ftn in fresh_tns
                )

                if any_fresh_pass:
                    fresh_pass += 1
                    if probe["corrected_score"] == 0.0:
                        probe_fail_fresh_pass += 1

            rate = probe_fail_fresh_pass / fresh_pass if fresh_pass > 0 else None
            rates[probe_tn] = rate

        vals = []
        for tn in [5, 10, 15, 20]:
            r = rates[tn]
            vals.append(f"{r:>6.2f}" if r is not None else "   N/A")
        print(f"{model_name:<20} {''.join(vals)}")

    # ---- Correction dissociation (T19 vs T20) ----
    print(f"\n{'='*70}")
    print("CORRECTED T19 vs T20 (Correction Dissociation)")
    print(f"{'='*70}")
    print(f"{'Model':<20} {'T19 (ID)':>9} {'T20 (Prop)':>11} {'Gap':>6}")
    print("-" * 50)

    for model_name in model_order:
        entries = [e for e in p1_entries if e["model"] == model_name]
        t19_correct = 0
        t20_correct = 0
        t19_total = 0
        t20_total = 0
        for entry in entries:
            for turn in entry.get("turn_scores", []):
                key = (model_name, entry["scenario_id"], turn["turn_number"])
                corrected = 1.0 if key in flip_set else turn.get("score", 0)
                if turn["turn_number"] == 19:
                    t19_total += 1
                    t19_correct += corrected
                elif turn["turn_number"] == 20:
                    t20_total += 1
                    t20_correct += corrected
        t19_rate = t19_correct / t19_total if t19_total else 0
        t20_rate = t20_correct / t20_total if t20_total else 0
        print(f"{model_name:<20} {t19_rate:>9.3f} {t20_rate:>11.3f} {t19_rate-t20_rate:>+6.3f}")

    # ---- Error cascade analysis ----
    print(f"\n{'='*70}")
    print("CORRECTED ERROR CASCADE ANALYSIS")
    print(f"{'='*70}")
    print(f"{'Model':<20} {'Cascade':>9} {'Base':>6} {'Mult':>7} {'MeanStrk':>9}")
    print("-" * 55)

    for model_name in model_order:
        entries = [e for e in p1_entries if e["model"] == model_name]
        after_err_err = 0
        after_err_total = 0
        after_ok_err = 0
        after_ok_total = 0
        all_streaks = []

        for entry in entries:
            turns = sorted(entry.get("turn_scores", []), key=lambda t: t["turn_number"])
            current_streak = 0
            prev_score = None
            for turn in turns:
                key = (model_name, entry["scenario_id"], turn["turn_number"])
                score = 1.0 if key in flip_set else turn.get("score", 0)
                is_err = score == 0.0

                if prev_score is not None:
                    if prev_score == 0.0:
                        after_err_total += 1
                        if is_err:
                            after_err_err += 1
                    else:
                        after_ok_total += 1
                        if is_err:
                            after_ok_err += 1

                if is_err:
                    current_streak += 1
                else:
                    if current_streak > 0:
                        all_streaks.append(current_streak)
                    current_streak = 0
                prev_score = score

            if current_streak > 0:
                all_streaks.append(current_streak)

        cascade_rate = after_err_err / after_err_total if after_err_total else 0
        base_rate = after_ok_err / after_ok_total if after_ok_total else 0
        mult = cascade_rate / base_rate if base_rate > 0 else float('inf')
        mean_streak = sum(all_streaks) / len(all_streaks) if all_streaks else 0

        mult_str = f"{mult:.2f}x" if mult != float('inf') else "inf"
        print(f"{model_name:<20} {cascade_rate:>9.3f} {base_rate:>6.3f} "
              f"{mult_str:>7} {mean_streak:>9.2f}")

    # ---- Genuinely wrong turns sample ----
    print(f"\n{'='*70}")
    print(f"GENUINELY WRONG TURNS: {len(genuinely_wrong)} "
          f"(sample of first 15)")
    print(f"{'='*70}")
    for gw in genuinely_wrong[:15]:
        print(f"  {gw['model']}/{gw['scenario_id']} T{gw['turn_number']} "
              f"[{gw['phase']}/{gw['question_type']}]: "
              f"target={gw.get('target_value')}, "
              f"old_extracted={gw.get('model_value')}, "
              f"candidates={gw.get('candidates_sample', [])[:6]}")

    if load_failures:
        print(f"\nLoad failures: {len(load_failures)}")
        for lf in load_failures[:5]:
            print(f"  {lf['model']}/{lf['scenario_id']} T{lf['turn_number']}")

    # ---- Write corrected file ----
    if args.output and not args.dry_run:
        print(f"\n{'='*70}")
        print(f"Writing corrected file to {args.output}")
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
                    frec = flip_lookup[key]
                    old_reason = turn.get("reason", "")
                    turn["score"] = 1.0
                    turn["reason"] = (
                        f"FIXED ({frec['bug_type']}): {old_reason}. "
                        f"Correct value {frec['new_model_value']} found in response."
                    )
                    if "details" in turn and isinstance(turn["details"], dict):
                        turn["details"]["model_value"] = frec["new_model_value"]
                        turn["details"]["is_close"] = True
                    any_changed = True
                    n_patched += 1

            if any_changed:
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
                phases = {}
                for t in turns:
                    phase = t.get("phase", "unknown")
                    phases.setdefault(phase, []).append(t["score"])
                entry["phase_accuracy"] = {
                    p: sum(s) / len(s) for p, s in phases.items()
                }

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
        print(f"Patched {n_patched} turns. Written to {args.output}")

    elif not args.output:
        print("\n(Dry run. Pass --output <path> to write corrected file.)")


if __name__ == "__main__":
    main()
