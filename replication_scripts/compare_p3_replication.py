#!/usr/bin/env python3
"""
compare_p3_replication.py — Proper P3 fabrication/abstention comparison
between original and replication judge results.

Fixes the empty dimension_comparisons bug in compare_scored_replication.py
by loading individual judge JSON files directly and comparing field-by-field.

Usage:
    python compare_p3_replication.py \
        --p3-original-dir ./results/p3_judged/individual \
        --p3-replication-dir ./results_replication/p3_judged/individual \
        --output p3_replication_comparison.json
"""

import argparse
import glob
import json
import os
import sys
from collections import defaultdict


def load_judge_results(directory, scenario_ids=None):
    """Load individual P3 judge JSON files from a directory.
    
    Returns dict keyed by (scenario_id, model) -> judge result dict.
    """
    results = {}
    pattern = os.path.join(directory, "P3_*.json")
    for filepath in sorted(glob.glob(pattern)):
        try:
            with open(filepath) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  WARNING: Could not read {filepath}: {e}", file=sys.stderr)
            continue

        sid = data.get("scenario_id", "")
        model = data.get("model", "")

        if scenario_ids and sid not in scenario_ids:
            continue

        results[(sid, model)] = data

    return results


def extract_fabrication_info(judge_result):
    """Extract fabrication and abstention details from a judge result."""
    gap_scores = judge_result.get("gap_scores", {})
    
    fabricated_any = False
    fabrication_details = []
    abstention_scores = []

    for gap_id, gap_data in sorted(gap_scores.items()):
        fab = gap_data.get("fabricated", False)
        abst = gap_data.get("abstained", 0.0)
        detail = gap_data.get("fabrication_detail", "")

        if fab:
            fabricated_any = True
            fabrication_details.append({"gap": gap_id, "detail": detail})
        abstention_scores.append({"gap": gap_id, "abstained": abst})

    return {
        "fabricated": fabricated_any,
        "fabrication_details": fabrication_details,
        "abstention_scores": abstention_scores,
        "mean_abstention": (
            sum(g["abstained"] for g in abstention_scores) / len(abstention_scores)
            if abstention_scores else 0.0
        ),
    }


def compare_p3(original_dir, replication_dir, scenario_ids=None):
    """Compare P3 judge results between original and replication."""
    orig = load_judge_results(original_dir, scenario_ids)
    repl = load_judge_results(replication_dir, scenario_ids)

    # Find common keys
    common_keys = sorted(set(orig.keys()) & set(repl.keys()))
    orig_only = sorted(set(orig.keys()) - set(repl.keys()))
    repl_only = sorted(set(repl.keys()) - set(orig.keys()))

    if orig_only:
        print(f"  WARNING: {len(orig_only)} entries only in original: {orig_only}",
              file=sys.stderr)
    if repl_only:
        print(f"  WARNING: {len(repl_only)} entries only in replication: {repl_only}",
              file=sys.stderr)

    comparisons = []
    fab_match_count = 0
    abst_match_count = 0
    total = len(common_keys)

    for key in common_keys:
        sid, model = key
        o_info = extract_fabrication_info(orig[key])
        r_info = extract_fabrication_info(repl[key])

        fab_match = o_info["fabricated"] == r_info["fabricated"]
        # Consider abstention "matching" if mean abstention is within 0.25
        abst_diff = abs(o_info["mean_abstention"] - r_info["mean_abstention"])
        abst_match = abst_diff <= 0.25

        if fab_match:
            fab_match_count += 1
        if abst_match:
            abst_match_count += 1

        comp = {
            "scenario_id": sid,
            "model": model,
            "original_fabricated": o_info["fabricated"],
            "replication_fabricated": r_info["fabricated"],
            "fabrication_match": fab_match,
            "original_mean_abstention": round(o_info["mean_abstention"], 3),
            "replication_mean_abstention": round(r_info["mean_abstention"], 3),
            "abstention_diff": round(abst_diff, 3),
            "abstention_match": abst_match,
        }

        # Add detail for any fabrication
        if o_info["fabricated"]:
            comp["original_fabrication_details"] = o_info["fabrication_details"]
        if r_info["fabricated"]:
            comp["replication_fabrication_details"] = r_info["fabrication_details"]

        comparisons.append(comp)

    # Per-model summary
    model_summary = defaultdict(lambda: {
        "total": 0, "orig_fab": 0, "repl_fab": 0, "fab_matches": 0
    })
    for c in comparisons:
        m = c["model"]
        model_summary[m]["total"] += 1
        if c["original_fabricated"]:
            model_summary[m]["orig_fab"] += 1
        if c["replication_fabricated"]:
            model_summary[m]["repl_fab"] += 1
        if c["fabrication_match"]:
            model_summary[m]["fab_matches"] += 1

    return {
        "description": "P3 replication comparison: fabrication and abstention agreement",
        "summary": {
            "total_compared": total,
            "fabrication_matches": fab_match_count,
            "fabrication_match_rate": round(fab_match_count / total, 3) if total else 0,
            "abstention_matches": abst_match_count,
            "abstention_match_rate": round(abst_match_count / total, 3) if total else 0,
        },
        "per_model": {
            model: {
                "scenarios": info["total"],
                "original_fabrication_count": info["orig_fab"],
                "replication_fabrication_count": info["repl_fab"],
                "fabrication_matches": info["fab_matches"],
            }
            for model, info in sorted(model_summary.items())
        },
        "fabrication_changes": [
            c for c in comparisons if not c["fabrication_match"]
        ],
        "all_comparisons": comparisons,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Compare P3 judge results between original and replication runs"
    )
    parser.add_argument("--p3-original-dir", required=True,
                        help="Directory with original P3 judge individual JSONs")
    parser.add_argument("--p3-replication-dir", required=True,
                        help="Directory with replication P3 judge individual JSONs")
    parser.add_argument("--scenarios", nargs="*", default=None,
                        help="Specific scenario IDs to compare (default: all common)")
    parser.add_argument("--output", default="p3_replication_comparison.json",
                        help="Output JSON path")
    args = parser.parse_args()

    scenario_ids = set(args.scenarios) if args.scenarios else None

    print("=" * 60)
    print("P3 REPLICATION COMPARISON")
    print("=" * 60)
    print(f"  Original dir:    {args.p3_original_dir}")
    print(f"  Replication dir: {args.p3_replication_dir}")
    if scenario_ids:
        print(f"  Scenarios:       {sorted(scenario_ids)}")
    print()

    result = compare_p3(args.p3_original_dir, args.p3_replication_dir, scenario_ids)

    s = result["summary"]
    print(f"  Pairs compared:         {s['total_compared']}")
    print(f"  Fabrication agreement:  {s['fabrication_matches']}/{s['total_compared']}"
          f" ({s['fabrication_match_rate']:.1%})")
    print(f"  Abstention agreement:   {s['abstention_matches']}/{s['total_compared']}"
          f" ({s['abstention_match_rate']:.1%})")
    print()

    # Per-model table
    print(f"  {'Model':<25} {'Orig Fab':>8} {'Repl Fab':>8} {'Matches':>8}")
    print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*8}")
    for model, info in sorted(result["per_model"].items()):
        print(f"  {model:<25} {info['original_fabrication_count']:>8}"
              f" {info['replication_fabrication_count']:>8}"
              f" {info['fabrication_matches']:>8}/{info['scenarios']}")
    print()

    # Changes
    changes = result["fabrication_changes"]
    if changes:
        print(f"  Fabrication changes ({len(changes)}):")
        for c in changes:
            direction = "fabricated→clean" if c["original_fabricated"] else "clean→fabricated"
            print(f"    {c['scenario_id']} / {c['model']}: {direction}")
    else:
        print("  No fabrication changes (perfect agreement)")

    print()

    # Write output — handle any serialization edge cases
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"  Saved to: {args.output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
