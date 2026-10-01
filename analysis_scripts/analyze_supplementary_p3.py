#!/usr/bin/env python3
"""
analyze_supplementary_p3.py — Analyze fabrication results from supplementary P3 scenarios
and compute combined statistics with the original 20 scenarios.

Produces:
  - Per-scenario fabrication rates for the 8 new scenarios
  - Combined missing-evidence gap fabrication rate (original 5 + new 8 = 13)
  - Per-model fabrication comparison
  - Updated gap-type table for the paper

Usage:
    python analyze_supplementary_p3.py \
        --p3-original-dir ./results/p3_judged/individual \
        --p3-supplementary-dir ./results_supplementary/p3_judged/individual \
        --output supplementary_p3_analysis.json
"""

import argparse
import glob
import json
import os
import sys
from collections import defaultdict


# Gap type classifications for all scenarios
# Original 20 scenarios (from analysis_7b_scenario_vulnerability.json)
ORIGINAL_GAP_TYPES = {
    "P3_001": "missing_reason",
    "P3_002": "missing_number",
    "P3_003": "missing_number",
    "P3_004": "missing_detail",
    "P3_005": "missing_reason",
    "P3_006": "missing_number",
    "P3_007": "missing_evidence",
    "P3_008": "missing_evidence",
    "P3_009": "implied_not_stated",
    "P3_010": "missing_evidence",
    "P3_011": "missing_detail",
    "P3_012": "missing_detail",
    "P3_013": "missing_detail",
    "P3_014": "missing_detail",
    "P3_015": "missing_detail",
    "P3_016": "missing_number",
    "P3_017": "missing_evidence",
    "P3_018": "implied_not_stated",
    "P3_019": "missing_evidence",
    "P3_020": "missing_number",
}

# All 8 supplementary scenarios are missing_evidence by design
SUPPLEMENTARY_GAP_TYPES = {
    f"P3_{i:03d}": "missing_evidence" for i in range(21, 29)
}


def load_judge_results(directory):
    """Load all P3 judge results from individual JSON files."""
    results = {}
    pattern = os.path.join(directory, "P3_*.json")
    for filepath in sorted(glob.glob(pattern)):
        try:
            with open(filepath) as f:
                data = json.load(f)
            sid = data.get("scenario_id", "")
            model = data.get("model", "")
            results[(sid, model)] = data
        except (json.JSONDecodeError, IOError) as e:
            print(f"  WARNING: Could not read {filepath}: {e}", file=sys.stderr)
    return results


def get_fabrication(judge_result):
    """Check if any gap in the result triggered fabrication."""
    for gap_id, gap_data in judge_result.get("gap_scores", {}).items():
        if gap_data.get("fabricated", False):
            return True, gap_data.get("fabrication_detail", "")
    return False, ""


def analyze(original_dir, supplementary_dir, output_path):
    orig_results = load_judge_results(original_dir)
    supp_results = load_judge_results(supplementary_dir)

    print(f"  Loaded {len(orig_results)} original judge results")
    print(f"  Loaded {len(supp_results)} supplementary judge results")
    print()

    # ---- Supplementary scenario analysis ----
    supp_by_scenario = defaultdict(list)
    for (sid, model), result in sorted(supp_results.items()):
        fabricated, detail = get_fabrication(result)
        supp_by_scenario[sid].append({
            "model": model,
            "fabricated": fabricated,
            "detail": detail,
        })

    print("  SUPPLEMENTARY SCENARIO RESULTS (8 new missing-evidence gaps):")
    print(f"  {'Scenario':<10} {'Fab Rate':>10} {'Models Fabricated'}")
    print(f"  {'-'*10} {'-'*10} {'-'*30}")

    supp_scenario_stats = {}
    for sid in sorted(supp_by_scenario.keys()):
        entries = supp_by_scenario[sid]
        n_fab = sum(1 for e in entries if e["fabricated"])
        n_total = len(entries)
        rate = n_fab / n_total if n_total else 0
        fab_models = [e["model"] for e in entries if e["fabricated"]]
        print(f"  {sid:<10} {rate:>10.1%} {', '.join(fab_models) or 'none'}")
        supp_scenario_stats[sid] = {
            "n_models": n_total,
            "n_fabricated": n_fab,
            "fabrication_rate": round(rate, 3),
            "models_fabricated": fab_models,
        }

    print()

    # ---- Combined missing-evidence analysis ----
    # Original missing-evidence scenarios
    orig_me_sids = [s for s, t in ORIGINAL_GAP_TYPES.items() if t == "missing_evidence"]
    supp_me_sids = list(SUPPLEMENTARY_GAP_TYPES.keys())

    # Count fabrication events
    orig_me_fab = 0
    orig_me_total = 0
    for (sid, model), result in orig_results.items():
        if sid in orig_me_sids:
            fabricated, _ = get_fabrication(result)
            orig_me_total += 1
            if fabricated:
                orig_me_fab += 1

    supp_me_fab = 0
    supp_me_total = 0
    for (sid, model), result in supp_results.items():
        fabricated, _ = get_fabrication(result)
        supp_me_total += 1
        if fabricated:
            supp_me_fab += 1

    combined_me_fab = orig_me_fab + supp_me_fab
    combined_me_total = orig_me_total + supp_me_total
    combined_me_rate = combined_me_fab / combined_me_total if combined_me_total else 0

    print("  MISSING-EVIDENCE GAP FABRICATION RATES:")
    print(f"  Original (N=5 scenarios):       {orig_me_fab}/{orig_me_total}"
          f" ({orig_me_fab/orig_me_total:.1%})" if orig_me_total else "")
    print(f"  Supplementary (N=8 scenarios):  {supp_me_fab}/{supp_me_total}"
          f" ({supp_me_fab/supp_me_total:.1%})" if supp_me_total else "")
    print(f"  Combined (N=13 scenarios):      {combined_me_fab}/{combined_me_total}"
          f" ({combined_me_rate:.1%})" if combined_me_total else "")
    print()

    # ---- Per-model comparison ----
    model_stats = defaultdict(lambda: {
        "orig_me_fab": 0, "orig_me_total": 0,
        "supp_me_fab": 0, "supp_me_total": 0,
    })

    for (sid, model), result in orig_results.items():
        if sid in orig_me_sids:
            fabricated, _ = get_fabrication(result)
            model_stats[model]["orig_me_total"] += 1
            if fabricated:
                model_stats[model]["orig_me_fab"] += 1

    for (sid, model), result in supp_results.items():
        fabricated, _ = get_fabrication(result)
        model_stats[model]["supp_me_total"] += 1
        if fabricated:
            model_stats[model]["supp_me_fab"] += 1

    print("  PER-MODEL FABRICATION ON MISSING-EVIDENCE GAPS:")
    print(f"  {'Model':<25} {'Orig (5 sc.)':>12} {'Supp (8 sc.)':>12} {'Combined':>12}")
    print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*12}")

    per_model_output = {}
    for model in sorted(model_stats.keys()):
        ms = model_stats[model]
        o_rate = ms["orig_me_fab"] / ms["orig_me_total"] if ms["orig_me_total"] else 0
        s_rate = ms["supp_me_fab"] / ms["supp_me_total"] if ms["supp_me_total"] else 0
        c_total = ms["orig_me_total"] + ms["supp_me_total"]
        c_fab = ms["orig_me_fab"] + ms["supp_me_fab"]
        c_rate = c_fab / c_total if c_total else 0
        print(f"  {model:<25} {ms['orig_me_fab']}/{ms['orig_me_total']:>2} ({o_rate:.0%})"
              f"    {ms['supp_me_fab']}/{ms['supp_me_total']:>2} ({s_rate:.0%})"
              f"    {c_fab}/{c_total:>2} ({c_rate:.0%})")
        per_model_output[model] = {
            "original_missing_evidence": {"fabricated": ms["orig_me_fab"], "total": ms["orig_me_total"], "rate": round(o_rate, 3)},
            "supplementary_missing_evidence": {"fabricated": ms["supp_me_fab"], "total": ms["supp_me_total"], "rate": round(s_rate, 3)},
            "combined_missing_evidence": {"fabricated": c_fab, "total": c_total, "rate": round(c_rate, 3)},
        }

    print()

    # ---- Updated gap-type table (for paper) ----
    # Compute fabrication rates by gap type including supplementary
    all_gap_types = {**ORIGINAL_GAP_TYPES, **SUPPLEMENTARY_GAP_TYPES}
    all_results = {**orig_results, **supp_results}

    type_stats = defaultdict(lambda: {"fab": 0, "total": 0, "n_gaps": 0, "scenarios": set()})
    for (sid, model), result in all_results.items():
        gt = all_gap_types.get(sid)
        if gt is None:
            continue
        fabricated, _ = get_fabrication(result)
        type_stats[gt]["total"] += 1
        type_stats[gt]["scenarios"].add(sid)
        if fabricated:
            type_stats[gt]["fab"] += 1

    for gt in type_stats:
        type_stats[gt]["n_gaps"] = len(type_stats[gt]["scenarios"])

    print("  UPDATED GAP-TYPE TABLE (original + supplementary):")
    print(f"  {'Gap Type':<20} {'Fab Rate':>10} {'N Gaps':>8} {'N Pairs':>8}")
    print(f"  {'-'*20} {'-'*10} {'-'*8} {'-'*8}")

    gap_type_table = {}
    for gt in ["missing_evidence", "missing_detail", "missing_number",
               "missing_reason", "implied_not_stated"]:
        ts = type_stats.get(gt, {"fab": 0, "total": 0, "n_gaps": 0})
        rate = ts["fab"] / ts["total"] if ts["total"] else 0
        print(f"  {gt:<20} {rate:>10.3f} {ts['n_gaps']:>8} {ts['total']:>8}")
        gap_type_table[gt] = {
            "fabrication_rate": round(rate, 3),
            "n_gaps": ts["n_gaps"],
            "n_model_scenario_pairs": ts["total"],
            "n_fabrication_events": ts["fab"],
        }

    print()

    # ---- Compile output ----
    output = {
        "description": "Supplementary P3 analysis: fabrication rates with expanded missing-evidence sample",
        "supplementary_scenario_results": supp_scenario_stats,
        "missing_evidence_rates": {
            "original": {"fabricated": orig_me_fab, "total": orig_me_total,
                         "rate": round(orig_me_fab / orig_me_total, 3) if orig_me_total else 0,
                         "n_scenarios": len(orig_me_sids)},
            "supplementary": {"fabricated": supp_me_fab, "total": supp_me_total,
                              "rate": round(supp_me_fab / supp_me_total, 3) if supp_me_total else 0,
                              "n_scenarios": len(supp_me_sids)},
            "combined": {"fabricated": combined_me_fab, "total": combined_me_total,
                         "rate": round(combined_me_rate, 3),
                         "n_scenarios": len(orig_me_sids) + len(supp_me_sids)},
        },
        "per_model": per_model_output,
        "updated_gap_type_table": gap_type_table,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"  Results saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze supplementary P3 fabrication results"
    )
    parser.add_argument("--p3-original-dir", required=True,
                        help="Directory with original P3 judge individual JSONs")
    parser.add_argument("--p3-supplementary-dir", required=True,
                        help="Directory with supplementary P3 judge individual JSONs")
    parser.add_argument("--output", default="supplementary_p3_analysis.json",
                        help="Output JSON path")
    args = parser.parse_args()

    print("=" * 60)
    print("SUPPLEMENTARY P3 FABRICATION ANALYSIS")
    print("=" * 60)
    print(f"  Original dir:       {args.p3_original_dir}")
    print(f"  Supplementary dir:  {args.p3_supplementary_dir}")
    print()

    analyze(args.p3_original_dir, args.p3_supplementary_dir, args.output)

    print("=" * 60)


if __name__ == "__main__":
    main()
