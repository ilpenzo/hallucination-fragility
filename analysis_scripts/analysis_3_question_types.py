#!/usr/bin/env python3
"""
Analysis 3: Question-Type Decomposition (P1)

Separates the confound between context length and question complexity.
For each question type and phase, computes accuracy across turn positions.
Key question: is accuracy dropping because of context length, or because
questions are getting harder?

Reads: scored_results.json (original, for P1 turn_scores)
Outputs: analysis_3_question_types.json

Usage:
  python analysis_3_question_types.py --scored-results ./results/scored_full/scored_results.json
"""

import json
import argparse
from collections import defaultdict


# Map question types to complexity tiers
COMPLEXITY_TIERS = {
    "direct_lookup": "lookup",
    "max_quarter": "lookup",
    "count_above": "lookup",
    "year_total": "lookup",
    "compare_two": "single_step",
    "qoq_change": "single_step",
    "margin": "single_step",
    "ratio": "single_step",
    "year_average": "single_step",
    "yoy_growth": "single_step",
    "cumulative": "multi_step",
    "conditional_average": "multi_step",
    "top_k": "multi_step",
    "max_gap": "multi_step",
    "conditional_aggregate": "multi_step",
    "correction_intro": "correction",
    "correction_verify": "correction",
    "anomaly_detection": "synthesis",
    "half_comparison": "synthesis",
    "trend_summary": "synthesis",
}


def load_p1_entries(scored_path):
    with open(scored_path, "r") as f:
        data = json.load(f)
    return [e for e in data if e.get("paradigm") == "P1"]


def analyze_by_question_type(entries):
    """
    For each model, compute accuracy broken down by:
    (a) question_type
    (b) phase (as recorded in data)
    (c) complexity tier (our mapping above)
    (d) turn number
    (e) question_type × turn_number (the key cross-tabulation)
    """
    by_model = defaultdict(list)
    for e in entries:
        by_model[e["model"]].append(e)

    model_results = {}

    for model, model_entries in sorted(by_model.items()):
        # Collect all scorable turns
        all_turns = []
        for entry in model_entries:
            scenario_id = entry["scenario_id"]
            for t in entry.get("turn_scores", []):
                if t.get("score") is not None and t["score"] >= 0:
                    all_turns.append({
                        "scenario_id": scenario_id,
                        "turn_number": t["turn_number"],
                        "score": t["score"],
                        "question_type": t.get("question_type", "unknown"),
                        "phase": t.get("phase", "unknown"),
                        "is_probe": t.get("is_probe", False),
                        "complexity_tier": COMPLEXITY_TIERS.get(
                            t.get("question_type", ""), "unknown"
                        ),
                    })

        # (a) By question type
        by_qtype = defaultdict(list)
        for t in all_turns:
            by_qtype[t["question_type"]].append(t["score"])

        qtype_results = {}
        for qt in sorted(by_qtype.keys()):
            scores = by_qtype[qt]
            qtype_results[qt] = {
                "mean_accuracy": round(sum(scores) / len(scores), 4),
                "n": len(scores),
                "n_correct": sum(1 for s in scores if s >= 1.0),
                "n_partial": sum(1 for s in scores if 0 < s < 1.0),
                "n_wrong": sum(1 for s in scores if s == 0.0),
            }

        # (b) By phase
        by_phase = defaultdict(list)
        for t in all_turns:
            by_phase[t["phase"]].append(t["score"])

        phase_results = {}
        for ph in sorted(by_phase.keys()):
            scores = by_phase[ph]
            phase_results[ph] = {
                "mean_accuracy": round(sum(scores) / len(scores), 4),
                "n": len(scores),
            }

        # (c) By complexity tier
        by_tier = defaultdict(list)
        for t in all_turns:
            by_tier[t["complexity_tier"]].append(t["score"])

        tier_results = {}
        for tier in ["lookup", "single_step", "multi_step", "correction", "synthesis"]:
            if tier in by_tier:
                scores = by_tier[tier]
                tier_results[tier] = {
                    "mean_accuracy": round(sum(scores) / len(scores), 4),
                    "n": len(scores),
                }

        # (d) By turn number
        by_turn = defaultdict(list)
        for t in all_turns:
            by_turn[t["turn_number"]].append(t["score"])

        turn_results = {}
        for tn in sorted(by_turn.keys()):
            scores = by_turn[tn]
            turn_results[int(tn)] = {
                "mean_accuracy": round(sum(scores) / len(scores), 4),
                "n": len(scores),
            }

        # (e) CRITICAL: question_type × turn_number cross-tabulation
        # This separates "harder questions" from "longer context"
        by_qtype_turn = defaultdict(list)
        for t in all_turns:
            key = (t["question_type"], t["turn_number"])
            by_qtype_turn[key].append(t["score"])

        qtype_turn_results = {}
        for (qt, tn), scores in sorted(by_qtype_turn.items()):
            if qt not in qtype_turn_results:
                qtype_turn_results[qt] = {}
            qtype_turn_results[qt][int(tn)] = {
                "mean_accuracy": round(sum(scores) / len(scores), 4),
                "n": len(scores),
            }

        # (f) Complexity tier × turn position bucket
        # Group turns into early (1-5), mid (6-10), late (11-15), final (16-20)
        def turn_bucket(tn):
            if tn <= 5:
                return "early_1-5"
            elif tn <= 10:
                return "mid_6-10"
            elif tn <= 15:
                return "late_11-15"
            else:
                return "final_16-20"

        by_tier_bucket = defaultdict(list)
        for t in all_turns:
            key = (t["complexity_tier"], turn_bucket(t["turn_number"]))
            by_tier_bucket[key].append(t["score"])

        tier_bucket_results = {}
        for (tier, bucket), scores in sorted(by_tier_bucket.items()):
            if tier not in tier_bucket_results:
                tier_bucket_results[tier] = {}
            tier_bucket_results[tier][bucket] = {
                "mean_accuracy": round(sum(scores) / len(scores), 4),
                "n": len(scores),
            }

        model_results[model] = {
            "by_question_type": qtype_results,
            "by_phase": phase_results,
            "by_complexity_tier": tier_results,
            "by_turn_number": turn_results,
            "question_type_x_turn": qtype_turn_results,
            "complexity_tier_x_turn_bucket": tier_bucket_results,
            "total_scorable_turns": len(all_turns),
        }

    return model_results


def compute_lookup_longevity(entries):
    """
    Key test: how well do models perform on LOOKUP questions at late turns?
    If lookups stay accurate even as overall accuracy drops, the problem
    is computational complexity, not context rot.
    If lookups also drop, the problem is genuine context memory loss.
    """
    by_model = defaultdict(list)
    for e in entries:
        by_model[e["model"]].append(e)

    results = {}
    for model, model_entries in sorted(by_model.items()):
        lookup_by_turn = defaultdict(list)
        non_lookup_by_turn = defaultdict(list)

        for entry in model_entries:
            for t in entry.get("turn_scores", []):
                if t.get("score") is None or t["score"] < 0:
                    continue
                qt = t.get("question_type", "")
                tn = t["turn_number"]
                tier = COMPLEXITY_TIERS.get(qt, "unknown")

                if tier == "lookup":
                    lookup_by_turn[tn].append(t["score"])
                elif tier in ("single_step", "multi_step"):
                    non_lookup_by_turn[tn].append(t["score"])

        def _summarize(by_turn):
            out = {}
            for tn in sorted(by_turn.keys()):
                scores = by_turn[tn]
                out[int(tn)] = {
                    "accuracy": round(sum(scores) / len(scores), 4),
                    "n": len(scores),
                }
            return out

        results[model] = {
            "lookup_by_turn": _summarize(lookup_by_turn),
            "computation_by_turn": _summarize(non_lookup_by_turn),
        }

    return results


def main():
    parser = argparse.ArgumentParser(description="P1 Question-Type Decomposition")
    parser.add_argument("--scored-results", required=True,
                        help="Path to scored_results.json")
    parser.add_argument("--output", default="analysis_3_question_types.json",
                        help="Output JSON path")
    args = parser.parse_args()

    print(f"Loading P1 data from {args.scored_results}...")
    entries = load_p1_entries(args.scored_results)
    print(f"  Found {len(entries)} P1 entries")

    print("\n=== Question-Type Analysis ===")
    qtype_results = analyze_by_question_type(entries)

    for model, r in sorted(qtype_results.items()):
        print(f"\n{model} ({r['total_scorable_turns']} scorable turns):")
        print(f"  By complexity tier:")
        for tier, stats in r["by_complexity_tier"].items():
            print(f"    {tier:15s}: {stats['mean_accuracy']:.3f} (n={stats['n']})")

        print(f"  Tier × Turn bucket:")
        for tier, buckets in r["complexity_tier_x_turn_bucket"].items():
            parts = []
            for bucket in ["early_1-5", "mid_6-10", "late_11-15", "final_16-20"]:
                if bucket in buckets:
                    parts.append(f"{bucket}={buckets[bucket]['mean_accuracy']:.3f}")
            print(f"    {tier:15s}: {', '.join(parts)}")

    print("\n=== Lookup Longevity (Context Rot vs. Complexity) ===")
    longevity = compute_lookup_longevity(entries)

    for model, r in sorted(longevity.items()):
        print(f"\n{model}:")
        lookup_turns = r["lookup_by_turn"]
        comp_turns = r["computation_by_turn"]
        # Show early vs late for lookups
        early_lookup = [v["accuracy"] for k, v in lookup_turns.items() if k <= 5]
        late_lookup = [v["accuracy"] for k, v in lookup_turns.items() if k > 10]
        early_comp = [v["accuracy"] for k, v in comp_turns.items() if k <= 10]
        late_comp = [v["accuracy"] for k, v in comp_turns.items() if k > 10]

        if early_lookup and late_lookup:
            print(f"  Lookup early (T1-5):  {sum(early_lookup)/len(early_lookup):.3f}")
            print(f"  Lookup late (T11+):   {sum(late_lookup)/len(late_lookup):.3f}")
        if early_comp and late_comp:
            print(f"  Computation early:    {sum(early_comp)/len(early_comp):.3f}")
            print(f"  Computation late:     {sum(late_comp)/len(late_comp):.3f}")

    # Save
    output = {
        "analysis": "P1 Question-Type Decomposition",
        "description": (
            "Separates the effects of context length from question complexity. "
            "If lookup accuracy drops at late turns, the problem is context memory loss. "
            "If only multi-step accuracy drops, the problem is computational complexity."
        ),
        "by_model": qtype_results,
        "lookup_longevity": longevity,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
