#!/usr/bin/env python3
"""
Analysis 3b: Retrieval vs. Fresh Computation Deep Dive (P1)

The core finding from Analysis 3 is that probe accuracy declines are NOT
simply "context rot" — models maintain fresh computation ability even as
probe (retrieval) accuracy drops. This script quantifies the dissociation
precisely using paired within-scenario comparisons.

Key insight: probes re-ask previously answered questions (testing retrieval
of self-generated prior outputs), while non-probe questions test fresh
computation from the original data. Comparing these at the same conversation
depth separates retrieval failure from reasoning failure.

Reads: scored_results_enhanced.json
Outputs: analysis_3b_retrieval_vs_computation.json

Usage:
  python analysis_3b_retrieval_vs_computation.py \
      --scored-results ./results/scored_full/scored_results_enhanced.json
"""

import json
import argparse
from collections import defaultdict


def load_p1_entries(scored_path):
    with open(scored_path, "r") as f:
        data = json.load(f)
    return [e for e in data if e.get("paradigm") == "P1"]


def paired_probe_analysis(entries):
    """
    For each probe turn, compare to the adjacent fresh turn in the SAME scenario.
    This is a paired within-scenario test (n=50 per model).

    Probe map:
      T5  (probe: direct_lookup)       vs T4  (fresh: lookup-tier)
      T10 (probe: yoy_growth)          vs T9  (fresh: single_step-tier)
      T15 (probe: conditional_aggregate) vs T14 (fresh: multi_step-tier)
      T20 (probe: correction_verify)   vs T19 (fresh: correction_intro)
    """
    probe_pairs = [
        {"probe_turn": 5, "fresh_turn": 4, "phase": "lookup",
         "probe_type": "direct_lookup", "description": "Retrieval of recent lookup (5 turns back)"},
        {"probe_turn": 10, "fresh_turn": 9, "phase": "single_step",
         "probe_type": "yoy_growth", "description": "Retrieval of single-step computation (10 turns back)"},
        {"probe_turn": 15, "fresh_turn": 14, "phase": "multi_step",
         "probe_type": "conditional_aggregate", "description": "Retrieval of multi-step computation (15 turns back)"},
        {"probe_turn": 20, "fresh_turn": 19, "phase": "correction",
         "probe_type": "correction_verify", "description": "Application of correction to prior computation"},
    ]

    by_model = defaultdict(list)
    for e in entries:
        by_model[e["model"]].append(e)

    all_results = {}
    for model, model_entries in sorted(by_model.items()):
        model_pairs = {}

        for pair_def in probe_pairs:
            pt = pair_def["probe_turn"]
            ft = pair_def["fresh_turn"]

            fresh_right_probe_right = 0
            fresh_right_probe_wrong = 0
            fresh_wrong_probe_right = 0
            fresh_wrong_probe_wrong = 0

            probe_scores = []
            fresh_scores = []

            for entry in model_entries:
                turn_map = {t["turn_number"]: t for t in entry.get("turn_scores", [])}
                f_turn = turn_map.get(ft, {})
                p_turn = turn_map.get(pt, {})

                # Skip if either is not scorable
                if f_turn.get("score") is None or f_turn["score"] < 0:
                    continue
                if p_turn.get("score") is None or p_turn["score"] < 0:
                    continue

                f_ok = f_turn["score"] >= 1.0
                p_ok = p_turn["score"] >= 1.0

                probe_scores.append(p_turn["score"])
                fresh_scores.append(f_turn["score"])

                if f_ok and p_ok:
                    fresh_right_probe_right += 1
                elif f_ok and not p_ok:
                    fresh_right_probe_wrong += 1
                elif not f_ok and p_ok:
                    fresh_wrong_probe_right += 1
                else:
                    fresh_wrong_probe_wrong += 1

            total = (fresh_right_probe_right + fresh_right_probe_wrong +
                     fresh_wrong_probe_right + fresh_wrong_probe_wrong)

            if total == 0:
                continue

            fresh_pass = fresh_right_probe_right + fresh_right_probe_wrong
            probe_pass = fresh_right_probe_right + fresh_wrong_probe_right

            # Key metric: P(probe fail | fresh pass) — retrieval-specific failure rate
            retrieval_failure_rate = (
                fresh_right_probe_wrong / fresh_pass if fresh_pass > 0 else None
            )

            def _safe_round(v, n=4):
                return round(v, n) if v is not None else None

            model_pairs[f"T{ft}_vs_T{pt}"] = {
                "phase": pair_def["phase"],
                "description": pair_def["description"],
                "probe_type": pair_def["probe_type"],
                "fresh_turn": ft,
                "probe_turn": pt,
                "n_scenarios": total,
                "contingency_table": {
                    "fresh_pass_probe_pass": fresh_right_probe_right,
                    "fresh_pass_probe_fail": fresh_right_probe_wrong,
                    "fresh_fail_probe_pass": fresh_wrong_probe_right,
                    "fresh_fail_probe_fail": fresh_wrong_probe_wrong,
                },
                "fresh_accuracy": _safe_round(sum(fresh_scores) / len(fresh_scores)),
                "probe_accuracy": _safe_round(sum(probe_scores) / len(probe_scores)),
                "delta": _safe_round(
                    sum(probe_scores) / len(probe_scores) - sum(fresh_scores) / len(fresh_scores)
                ),
                "retrieval_failure_rate": _safe_round(retrieval_failure_rate),
                "fresh_pass_count": fresh_pass,
                "probe_pass_count": probe_pass,
            }

        all_results[model] = model_pairs

    return all_results


def phase_level_comparison(entries):
    """
    Broader comparison: within each phase, compare aggregate probe accuracy
    to aggregate fresh (non-probe) accuracy.
    """
    by_model = defaultdict(list)
    for e in entries:
        by_model[e["model"]].append(e)

    probe_turns = {5, 10, 15, 20}
    results = {}

    for model, model_entries in sorted(by_model.items()):
        phase_data = defaultdict(lambda: {"probe_scores": [], "fresh_scores": []})

        for entry in model_entries:
            for t in entry.get("turn_scores", []):
                if t.get("score") is None or t["score"] < 0:
                    continue
                phase = t.get("phase", "unknown")
                if t["turn_number"] in probe_turns:
                    phase_data[phase]["probe_scores"].append(t["score"])
                else:
                    phase_data[phase]["fresh_scores"].append(t["score"])

        model_phases = {}
        for phase in ["lookup", "single_step", "multi_step", "correction"]:
            d = phase_data[phase]
            if d["probe_scores"] and d["fresh_scores"]:
                p_avg = sum(d["probe_scores"]) / len(d["probe_scores"])
                f_avg = sum(d["fresh_scores"]) / len(d["fresh_scores"])
                model_phases[phase] = {
                    "fresh_accuracy": round(f_avg, 4),
                    "fresh_n": len(d["fresh_scores"]),
                    "probe_accuracy": round(p_avg, 4),
                    "probe_n": len(d["probe_scores"]),
                    "delta": round(p_avg - f_avg, 4),
                    "direction": (
                        "probe_better" if p_avg - f_avg > 0.02
                        else "probe_worse" if p_avg - f_avg < -0.02
                        else "similar"
                    ),
                }

        results[model] = model_phases

    return results


def classify_failure_profiles(paired_results):
    """
    Classify each model into a failure profile based on WHERE
    retrieval-specific degradation first appears.
    """
    profiles = {}
    for model, pairs in paired_results.items():
        first_degradation = None
        degradation_phases = []

        for pair_key in ["T4_vs_T5", "T9_vs_T10", "T14_vs_T15", "T19_vs_T20"]:
            pair = pairs.get(pair_key, {})
            rfr = pair.get("retrieval_failure_rate")
            if rfr is not None and rfr > 0.15:  # >15% retrieval-specific failure
                phase = pair.get("phase", "unknown")
                degradation_phases.append({
                    "phase": phase,
                    "pair": pair_key,
                    "retrieval_failure_rate": rfr,
                })
                if first_degradation is None:
                    first_degradation = phase

        if not degradation_phases:
            profile = "robust"
            description = "No significant retrieval-specific degradation at any checkpoint"
        elif first_degradation == "correction":
            profile = "correction_only"
            description = ("Retrieval is intact through multi-step phase; "
                           "only correction propagation shows degradation")
        elif first_degradation == "multi_step":
            profile = "late_retrieval_failure"
            description = ("Retrieval degrades at multi-step phase; "
                           "fresh computation remains strong")
        elif first_degradation == "single_step":
            profile = "early_retrieval_failure"
            description = ("Retrieval degrades early (single-step phase); "
                           "widespread retrieval-specific vulnerability")
        else:
            profile = "other"
            description = f"First degradation at {first_degradation}"

        profiles[model] = {
            "profile": profile,
            "description": description,
            "degradation_phases": degradation_phases,
            "first_degradation_phase": first_degradation,
        }

    return profiles


def main():
    parser = argparse.ArgumentParser(
        description="P1 Retrieval vs. Fresh Computation Deep Dive"
    )
    parser.add_argument("--scored-results", required=True,
                        help="Path to scored_results_enhanced.json")
    parser.add_argument("--output", default="analysis_3b_retrieval_vs_computation.json",
                        help="Output JSON path")
    args = parser.parse_args()

    print(f"Loading P1 data from {args.scored_results}...")
    entries = load_p1_entries(args.scored_results)
    print(f"  Found {len(entries)} P1 entries")

    print("\n=== Paired Probe vs. Fresh Analysis (within-scenario) ===")
    paired = paired_probe_analysis(entries)

    for model, pairs in sorted(paired.items()):
        print(f"\n{model}:")
        for pair_key, p in pairs.items():
            rfr = p.get("retrieval_failure_rate")
            rfr_str = f"{rfr:.3f}" if rfr is not None else "N/A"
            marker = " *** RETRIEVAL FAILURE" if rfr is not None and rfr > 0.15 else ""
            print(f"  {pair_key} [{p['phase']}]: "
                  f"fresh={p['fresh_accuracy']:.3f} probe={p['probe_accuracy']:.3f} "
                  f"delta={p['delta']:+.3f} "
                  f"P(probe_fail|fresh_pass)={rfr_str}{marker}")

    print("\n=== Phase-Level Comparison ===")
    phase_comp = phase_level_comparison(entries)

    for model, phases in sorted(phase_comp.items()):
        print(f"\n{model}:")
        for phase, stats in phases.items():
            print(f"  {phase:15s}: fresh={stats['fresh_accuracy']:.3f} "
                  f"probe={stats['probe_accuracy']:.3f} "
                  f"delta={stats['delta']:+.3f} ({stats['direction']})")

    print("\n=== Failure Profile Classification ===")
    profiles = classify_failure_profiles(paired)

    for model, p in sorted(profiles.items()):
        print(f"\n{model}: {p['profile'].upper()}")
        print(f"  {p['description']}")
        for dp in p["degradation_phases"]:
            print(f"  - {dp['phase']}: retrieval_failure_rate={dp['retrieval_failure_rate']:.3f}")

    # Save
    output = {
        "analysis": "P1 Retrieval vs. Fresh Computation Deep Dive",
        "description": (
            "Separates retrieval failure (inability to recover self-generated "
            "prior outputs) from reasoning failure (inability to compute fresh "
            "answers). Uses paired within-scenario comparisons at each probe "
            "checkpoint (n=50 per model per checkpoint)."
        ),
        "key_finding": (
            "Probe accuracy decline is NOT uniform context rot. Models maintain "
            "fresh computation ability even when probe (retrieval) accuracy drops. "
            "Three distinct failure profiles emerge: early_retrieval_failure "
            "(MiniMax), late_retrieval_failure (Gemini), and correction_only "
            "(Sonnet, DeepSeek, GPT-4o)."
        ),
        "paired_probe_analysis": paired,
        "phase_level_comparison": phase_comp,
        "failure_profiles": profiles,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
