#!/usr/bin/env python3
"""
Analysis 1: Error Cascade Analysis (P1)

When a model first gets a turn wrong, what happens next?
Computes conditional probability of error on turn t+1 given error on turn t,
distinguishing "isolated mistakes" from "cascade failures."

Reads: scored_results.json (original, for P1 turn_scores)
Outputs: analysis_1_error_cascades.json

Usage:
  python analysis_1_error_cascades.py --scored-results ./results/scored_full/scored_results.json
"""

import json
import argparse
import os
from collections import defaultdict


def load_p1_entries(scored_path):
    """Load all P1 entries with their per-turn scores."""
    with open(scored_path, "r") as f:
        data = json.load(f)
    return [e for e in data if e.get("paradigm") == "P1"]


def analyze_cascades(entries):
    """
    For each model, compute:
    - P(error at t+1 | error at t)  — cascade rate
    - P(error at t+1 | correct at t) — baseline error rate
    - P(recovery at t+1 | error at t) — recovery rate
    - Streak analysis: distribution of consecutive error lengths
    """
    model_results = {}

    by_model = defaultdict(list)
    for e in entries:
        by_model[e["model"]].append(e)

    for model, model_entries in sorted(by_model.items()):
        # Collect all consecutive turn pairs across scenarios
        error_then_error = 0
        error_then_correct = 0
        correct_then_error = 0
        correct_then_correct = 0

        # Streak tracking
        all_streaks = []  # list of consecutive-error streak lengths
        # Per-turn cascade rates (for position-specific analysis)
        turn_transition_counts = defaultdict(lambda: {"ee": 0, "ec": 0, "ce": 0, "cc": 0})

        for entry in model_entries:
            turns = entry.get("turn_scores", [])
            # Filter to scorable turns (score is not None and not -1.0 sentinel)
            scorable = [
                t for t in turns
                if t.get("score") is not None and t["score"] >= 0
            ]
            # Sort by turn number
            scorable.sort(key=lambda t: t["turn_number"])

            # Track streaks
            current_streak = 0

            for i in range(len(scorable)):
                is_error = scorable[i]["score"] < 1.0

                if is_error:
                    current_streak += 1
                else:
                    if current_streak > 0:
                        all_streaks.append(current_streak)
                    current_streak = 0

                # Transitions (need previous turn)
                if i > 0:
                    prev_error = scorable[i - 1]["score"] < 1.0
                    curr_error = is_error
                    turn_num = scorable[i]["turn_number"]

                    if prev_error and curr_error:
                        error_then_error += 1
                        turn_transition_counts[turn_num]["ee"] += 1
                    elif prev_error and not curr_error:
                        error_then_correct += 1
                        turn_transition_counts[turn_num]["ec"] += 1
                    elif not prev_error and curr_error:
                        correct_then_error += 1
                        turn_transition_counts[turn_num]["ce"] += 1
                    else:
                        correct_then_correct += 1
                        turn_transition_counts[turn_num]["cc"] += 1

            # Final streak if conversation ended in errors
            if current_streak > 0:
                all_streaks.append(current_streak)

        # Compute rates
        total_after_error = error_then_error + error_then_correct
        total_after_correct = correct_then_error + correct_then_correct

        cascade_rate = (
            error_then_error / total_after_error if total_after_error > 0 else None
        )
        recovery_rate = (
            error_then_correct / total_after_error if total_after_error > 0 else None
        )
        baseline_error_rate = (
            correct_then_error / total_after_correct
            if total_after_correct > 0
            else None
        )
        # "Cascade multiplier" — how much more likely is an error after an error
        # vs after a correct answer?
        cascade_multiplier = (
            cascade_rate / baseline_error_rate
            if cascade_rate is not None
            and baseline_error_rate is not None
            and baseline_error_rate > 0
            else None
        )

        # Streak statistics
        streak_distribution = defaultdict(int)
        for s in all_streaks:
            streak_distribution[s] += 1

        avg_streak = (
            sum(all_streaks) / len(all_streaks) if all_streaks else 0
        )
        max_streak = max(all_streaks) if all_streaks else 0

        # Per-turn cascade rates (for turns with enough data)
        per_turn_cascade = {}
        for turn_num in sorted(turn_transition_counts.keys()):
            tc = turn_transition_counts[turn_num]
            after_err = tc["ee"] + tc["ec"]
            after_corr = tc["ce"] + tc["cc"]
            per_turn_cascade[int(turn_num)] = {
                "cascade_rate": round(tc["ee"] / after_err, 4) if after_err > 0 else None,
                "baseline_error_rate": round(tc["ce"] / after_corr, 4) if after_corr > 0 else None,
                "n_after_error": after_err,
                "n_after_correct": after_corr,
            }

        def _safe_round(v, n=4):
            return round(v, n) if v is not None else None

        model_results[model] = {
            "transition_counts": {
                "error_then_error": error_then_error,
                "error_then_correct": error_then_correct,
                "correct_then_error": correct_then_error,
                "correct_then_correct": correct_then_correct,
            },
            "cascade_rate": _safe_round(cascade_rate),
            "recovery_rate": _safe_round(recovery_rate),
            "baseline_error_rate": _safe_round(baseline_error_rate),
            "cascade_multiplier": _safe_round(cascade_multiplier, 2),
            "streak_stats": {
                "mean_streak_length": round(avg_streak, 2),
                "max_streak_length": max_streak,
                "n_streaks": len(all_streaks),
                "distribution": {str(k): v for k, v in sorted(streak_distribution.items())},
            },
            "per_turn_cascade_rate": per_turn_cascade,
            "n_scenarios": len(model_entries),
        }

    return model_results


def compute_phase_cascades(entries):
    """
    Do errors cascade differently across phase boundaries?
    e.g., does an error in 'single_step' predict an error in 'multi_step'?
    """
    by_model = defaultdict(list)
    for e in entries:
        by_model[e["model"]].append(e)

    model_phase_results = {}

    for model, model_entries in sorted(by_model.items()):
        # Track transitions across phase boundaries
        phase_transitions = defaultdict(lambda: {"error_error": 0, "error_correct": 0,
                                                  "correct_error": 0, "correct_correct": 0})
        # Track within-phase transitions
        within_phase = defaultdict(lambda: {"error_error": 0, "error_correct": 0,
                                             "correct_error": 0, "correct_correct": 0})

        for entry in model_entries:
            turns = entry.get("turn_scores", [])
            scorable = [
                t for t in turns
                if t.get("score") is not None and t["score"] >= 0
            ]
            scorable.sort(key=lambda t: t["turn_number"])

            for i in range(1, len(scorable)):
                prev = scorable[i - 1]
                curr = scorable[i]
                prev_err = prev["score"] < 1.0
                curr_err = curr["score"] < 1.0

                prev_phase = prev.get("phase", "unknown")
                curr_phase = curr.get("phase", "unknown")

                if prev_phase == curr_phase:
                    target = within_phase[curr_phase]
                else:
                    target = phase_transitions[f"{prev_phase}->{curr_phase}"]

                if prev_err and curr_err:
                    target["error_error"] += 1
                elif prev_err and not curr_err:
                    target["error_correct"] += 1
                elif not prev_err and curr_err:
                    target["correct_error"] += 1
                else:
                    target["correct_correct"] += 1

        # Compute rates
        def _rate(d):
            after_err = d["error_error"] + d["error_correct"]
            after_corr = d["correct_error"] + d["correct_correct"]
            return {
                "cascade_rate": round(d["error_error"] / after_err, 4) if after_err > 0 else None,
                "baseline_error_rate": round(d["correct_error"] / after_corr, 4) if after_corr > 0 else None,
                "n_after_error": after_err,
                "n_after_correct": after_corr,
            }

        model_phase_results[model] = {
            "within_phase": {k: _rate(v) for k, v in sorted(within_phase.items())},
            "across_phase": {k: _rate(v) for k, v in sorted(phase_transitions.items())},
        }

    return model_phase_results


def main():
    parser = argparse.ArgumentParser(description="P1 Error Cascade Analysis")
    parser.add_argument("--scored-results", required=True,
                        help="Path to scored_results.json")
    parser.add_argument("--output", default="analysis_1_error_cascades.json",
                        help="Output JSON path")
    args = parser.parse_args()

    print(f"Loading P1 data from {args.scored_results}...")
    entries = load_p1_entries(args.scored_results)
    print(f"  Found {len(entries)} P1 entries")

    print("\n=== Overall Cascade Analysis ===")
    cascade_results = analyze_cascades(entries)

    for model, r in sorted(cascade_results.items()):
        print(f"\n{model}:")
        print(f"  Cascade rate (P(err|prev_err)):  {r['cascade_rate']}")
        print(f"  Baseline error (P(err|prev_ok)): {r['baseline_error_rate']}")
        print(f"  Cascade multiplier:              {r['cascade_multiplier']}x")
        print(f"  Recovery rate:                   {r['recovery_rate']}")
        print(f"  Mean error streak:               {r['streak_stats']['mean_streak_length']}")
        print(f"  Max error streak:                {r['streak_stats']['max_streak_length']}")

    print("\n=== Phase Boundary Analysis ===")
    phase_results = compute_phase_cascades(entries)

    for model, r in sorted(phase_results.items()):
        print(f"\n{model}:")
        print(f"  Within-phase cascades:")
        for phase, rates in r["within_phase"].items():
            if rates["n_after_error"] > 5:
                print(f"    {phase}: cascade={rates['cascade_rate']}, "
                      f"baseline={rates['baseline_error_rate']}, "
                      f"n_after_err={rates['n_after_error']}")
        print(f"  Across-phase cascades:")
        for transition, rates in r["across_phase"].items():
            if rates["n_after_error"] > 5:
                print(f"    {transition}: cascade={rates['cascade_rate']}, "
                      f"baseline={rates['baseline_error_rate']}, "
                      f"n_after_err={rates['n_after_error']}")

    # Save
    output = {
        "analysis": "P1 Error Cascade Analysis",
        "description": "Conditional error probabilities and streak analysis across P1 turns",
        "overall_cascades": cascade_results,
        "phase_cascades": phase_results,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
