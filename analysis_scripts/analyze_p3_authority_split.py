#!/usr/bin/env python3
"""
analyze_p3_authority_split.py — P3 Authority Bias Split Analysis
Context-Dependent Hallucination in Frontier LLMs

Breaks down P3 judge results by authority_correct (true/false) to determine
whether authority deference is appropriate (correct scenarios) or biased
(wrong scenarios). Also analyzes fabrication and gap handling by split.

Usage:
  python analyze_p3_authority_split.py --input-dir ./results/p3_judged

Output:
  - Console summary with per-model, per-authority-direction breakdowns
  - authority_split_analysis.json (full results)
  - authority_split_summary.csv (flat table)
"""

import os
import sys
import json
import csv
import argparse
from collections import defaultdict
from typing import Dict, List, Any, Optional


def load_individual_results(input_dir: str) -> List[Dict]:
    """Load all individual judge result files."""
    individual_dir = os.path.join(input_dir, "individual")
    if not os.path.isdir(individual_dir):
        print(f"ERROR: {individual_dir} not found")
        sys.exit(1)

    results = []
    for fname in sorted(os.listdir(individual_dir)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(individual_dir, fname)
        try:
            with open(fpath, "r") as f:
                data = json.load(f)
            if data.get("success"):
                results.append(data)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  Warning: skipping {fname}: {e}")

    return results


def safe_mean(values: List[float]) -> Optional[float]:
    """Compute mean, returning None for empty lists."""
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def analyze_split(results: List[Dict]) -> Dict[str, Any]:
    """
    Core analysis: break down all metrics by model × authority_correct.
    """
    # Group by model and authority direction
    groups = defaultdict(lambda: defaultdict(list))
    for r in results:
        model = r["model"]
        auth = "authority_correct" if r.get("authority_correct") else "authority_wrong"
        groups[model][auth].append(r)

    # Also track per-scenario patterns
    scenario_deference = defaultdict(dict)  # scenario_id -> {model: deferred}

    model_splits = {}
    for model in sorted(groups.keys()):
        model_splits[model] = {}
        for split in ["authority_correct", "authority_wrong"]:
            entries = groups[model][split]
            if not entries:
                model_splits[model][split] = {"n": 0}
                continue

            # Contradiction scores
            all_identified = []
            all_resolved = []
            all_reasoning = []
            for e in entries:
                for cid, cs in e.get("contradiction_scores", {}).items():
                    all_identified.append(cs.get("identified", 0.0))
                    all_resolved.append(cs.get("resolved_correctly", 0.0))
                    all_reasoning.append(cs.get("reasoning_quality", 0.0))

            # Gap scores
            all_abstained = []
            all_fabricated = []
            fabrication_details = []
            for e in entries:
                for gid, gs in e.get("gap_scores", {}).items():
                    all_abstained.append(gs.get("abstained", 0.0))
                    fab = gs.get("fabricated", False)
                    all_fabricated.append(1.0 if fab else 0.0)
                    if fab and gs.get("fabrication_detail"):
                        fabrication_details.append({
                            "scenario_id": e["scenario_id"],
                            "model": model,
                            "detail": gs["fabrication_detail"][:200],
                        })

            # Authority bias
            deferred_count = 0
            cited_count = 0
            for e in entries:
                ab = e.get("authority_bias", {})
                if ab.get("deferred_to_authority"):
                    deferred_count += 1
                    scenario_deference[e["scenario_id"]][model] = True
                else:
                    scenario_deference[e["scenario_id"]][model] = False
                if ab.get("cited_evidence"):
                    cited_count += 1

            model_splits[model][split] = {
                "n": len(entries),
                "contradiction_identified": safe_mean(all_identified),
                "contradiction_resolved": safe_mean(all_resolved),
                "contradiction_reasoning": safe_mean(all_reasoning),
                "gap_abstained": safe_mean(all_abstained),
                "fabrication_rate": safe_mean(all_fabricated),
                "authority_deferred_count": deferred_count,
                "authority_deferred_rate": round(deferred_count / len(entries), 4),
                "authority_cited_rate": round(cited_count / len(entries), 4),
                "fabrication_details": fabrication_details,
            }

    # Scenario-level analysis: which scenarios have unanimous deference?
    scenario_analysis = {}
    for sid, model_map in sorted(scenario_deference.items()):
        n_deferred = sum(1 for v in model_map.values() if v)
        n_total = len(model_map)
        # Find the authority direction from any result
        auth_correct = None
        for r in results:
            if r["scenario_id"] == sid:
                auth_correct = r.get("authority_correct")
                break
        scenario_analysis[sid] = {
            "authority_correct": auth_correct,
            "n_models_deferred": n_deferred,
            "n_models_total": n_total,
            "unanimous_deference": n_deferred == n_total,
            "per_model": model_map,
        }

    return {
        "model_splits": model_splits,
        "scenario_analysis": scenario_analysis,
    }


def print_results(analysis: Dict):
    """Print formatted results to console."""
    model_splits = analysis["model_splits"]
    scenario_analysis = analysis["scenario_analysis"]

    print(f"\n{'='*70}")
    print("P3 AUTHORITY BIAS SPLIT ANALYSIS")
    print(f"{'='*70}")

    # Per-model split table
    print(f"\n--- Per-Model Breakdown ---\n")
    header = (f"  {'Model':<22} {'Split':<18} {'n':>3} "
              f"{'C.Res':>5} {'G.Abst':>6} {'Fabr%':>5} "
              f"{'Defer%':>6} {'Cited%':>6}")
    print(header)
    print(f"  {'-'*22} {'-'*18} {'-'*3} {'-'*5} {'-'*6} {'-'*5} {'-'*6} {'-'*6}")

    for model in sorted(model_splits.keys()):
        for split in ["authority_correct", "authority_wrong"]:
            s = model_splits[model].get(split, {})
            if s.get("n", 0) == 0:
                continue

            def _fmt(v):
                return f"{v:.3f}" if v is not None else "  N/A"

            fab_pct = f"{s['fabrication_rate']*100:.0f}%" if s.get('fabrication_rate') is not None else "N/A"
            def_pct = f"{s['authority_deferred_rate']*100:.0f}%" if s.get('authority_deferred_rate') is not None else "N/A"
            cit_pct = f"{s['authority_cited_rate']*100:.0f}%" if s.get('authority_cited_rate') is not None else "N/A"

            label = "auth_correct" if split == "authority_correct" else "auth_WRONG"
            print(f"  {model:<22} {label:<18} {s['n']:>3} "
                  f"{_fmt(s.get('contradiction_resolved')):>5} "
                  f"{_fmt(s.get('gap_abstained')):>6} "
                  f"{fab_pct:>5} {def_pct:>6} {cit_pct:>6}")
        print()  # blank line between models

    # Key finding: inappropriate deference
    print(f"\n--- Key Finding: Inappropriate Authority Deference ---\n")
    for model in sorted(model_splits.keys()):
        wrong_split = model_splits[model].get("authority_wrong", {})
        correct_split = model_splits[model].get("authority_correct", {})
        wrong_defer = wrong_split.get("authority_deferred_count", 0)
        wrong_n = wrong_split.get("n", 0)
        correct_defer = correct_split.get("authority_deferred_count", 0)
        correct_n = correct_split.get("n", 0)

        print(f"  {model:<22}: "
              f"Appropriate deference: {correct_defer}/{correct_n} "
              f"({correct_defer/correct_n*100:.0f}% of auth_correct) | "
              f"Inappropriate deference: {wrong_defer}/{wrong_n} "
              f"({wrong_defer/wrong_n*100:.0f}% of auth_WRONG)")

    # Scenario-level deference patterns
    print(f"\n--- Scenario-Level Deference Patterns ---\n")
    auth_correct_scenarios = {sid: sa for sid, sa in scenario_analysis.items()
                              if sa.get("authority_correct") is True}
    auth_wrong_scenarios = {sid: sa for sid, sa in scenario_analysis.items()
                            if sa.get("authority_correct") is False}

    print(f"  Authority-CORRECT scenarios ({len(auth_correct_scenarios)}):")
    for sid, sa in sorted(auth_correct_scenarios.items()):
        models_deferred = [m for m, d in sa["per_model"].items() if d]
        models_resisted = [m for m, d in sa["per_model"].items() if not d]
        status = "ALL deferred" if sa["unanimous_deference"] else f"{sa['n_models_deferred']}/{sa['n_models_total']} deferred"
        print(f"    {sid}: {status}")
        if models_resisted:
            print(f"           Resisted (incorrect): {', '.join(models_resisted)}")

    print(f"\n  Authority-WRONG scenarios ({len(auth_wrong_scenarios)}):")
    for sid, sa in sorted(auth_wrong_scenarios.items()):
        models_deferred = [m for m, d in sa["per_model"].items() if d]
        if sa["n_models_deferred"] > 0:
            print(f"    {sid}: {sa['n_models_deferred']}/{sa['n_models_total']} deferred (BAD)")
            print(f"           Deferred (incorrect): {', '.join(models_deferred)}")
        else:
            print(f"    {sid}: None deferred (good)")

    # Fabrication details
    all_fabrications = []
    for model in sorted(model_splits.keys()):
        for split in ["authority_correct", "authority_wrong"]:
            s = model_splits[model].get(split, {})
            all_fabrications.extend(s.get("fabrication_details", []))

    if all_fabrications:
        print(f"\n--- Fabrication Details ({len(all_fabrications)} instances) ---\n")
        for fab in all_fabrications:
            print(f"  [{fab['scenario_id']}] {fab['model']}:")
            print(f"    {fab['detail']}")
            print()


def save_results(analysis: Dict, output_dir: str):
    """Save analysis results to files."""
    # Strip fabrication_details from JSON (they're long strings)
    clean_analysis = json.loads(json.dumps(analysis, default=str))

    json_path = os.path.join(output_dir, "authority_split_analysis.json")
    with open(json_path, "w") as f:
        json.dump(clean_analysis, f, indent=2, ensure_ascii=False)

    # Flat CSV summary
    csv_rows = []
    for model, splits in sorted(analysis["model_splits"].items()):
        for split in ["authority_correct", "authority_wrong"]:
            s = splits.get(split, {})
            if s.get("n", 0) == 0:
                continue
            row = {
                "model": model,
                "authority_direction": split,
                "n": s["n"],
                "contradiction_identified": s.get("contradiction_identified"),
                "contradiction_resolved": s.get("contradiction_resolved"),
                "contradiction_reasoning": s.get("contradiction_reasoning"),
                "gap_abstained": s.get("gap_abstained"),
                "fabrication_rate": s.get("fabrication_rate"),
                "authority_deferred_rate": s.get("authority_deferred_rate"),
                "authority_cited_rate": s.get("authority_cited_rate"),
            }
            csv_rows.append(row)

    if csv_rows:
        csv_path = os.path.join(output_dir, "authority_split_summary.csv")
        fieldnames = list(csv_rows[0].keys())
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"\n  Saved: {json_path}")
        print(f"  Saved: {csv_path}")


def main():
    parser = argparse.ArgumentParser(
        description="P3 Authority Bias Split Analysis"
    )
    parser.add_argument(
        "--input-dir", required=True,
        help="Directory containing p3_judged/individual/*.json results"
    )
    args = parser.parse_args()

    results = load_individual_results(args.input_dir)
    print(f"Loaded {len(results)} successful judge results")

    analysis = analyze_split(results)
    print_results(analysis)
    save_results(analysis, args.input_dir)


if __name__ == "__main__":
    main()
