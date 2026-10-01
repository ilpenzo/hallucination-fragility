#!/usr/bin/env python3
"""
compare_scored_replication.py — Compare scored outcomes between original and replication.

Takes two scored_results_enhanced.json files (original and replication) and
reports whether the SCORES agree, regardless of text differences.

This is the critical analysis: text may differ at temperature 0 due to API
non-determinism, but what matters for the paper is whether the scored outcomes
(accuracy, satisfaction rates, probe scores) are stable.

For P3 (which uses a separate judge pipeline), this script compares P3 judged
results if --p3-original-dir and --p3-replication-dir are provided.

Usage:
  python compare_scored_replication.py \
      --original ./results/scored_full/scored_results_enhanced.json \
      --replication ./results_replication/scored_full/scored_results_enhanced.json \
      --p3-original-dir ./results/p3_judged/individual \
      --p3-replication-dir ./results_replication/p3_judged/individual \
      --output replication_score_comparison.json
"""

import json
import os
import argparse
import glob
from collections import defaultdict
from typing import Dict, List, Optional, Any


def load_scored(path):
    """Load scored results and index by (model, scenario_id)."""
    with open(path, "r") as f:
        data = json.load(f)
    index = {}
    for entry in data:
        key = (entry["model"], entry["scenario_id"])
        index[key] = entry
    return index


def compare_p1_entry(orig, repl):
    """Compare P1 scored entries. Returns per-turn comparison."""
    orig_turns = {t["turn_number"]: t for t in orig.get("turn_scores", [])}
    repl_turns = {t["turn_number"]: t for t in repl.get("turn_scores", [])}

    comparisons = []
    for tn in sorted(set(orig_turns.keys()) | set(repl_turns.keys())):
        ot = orig_turns.get(tn)
        rt = repl_turns.get(tn)

        if ot is None or rt is None:
            comparisons.append({
                "turn": tn,
                "status": "missing",
                "missing_in": "original" if ot is None else "replication",
            })
            continue

        orig_score = ot.get("score")
        repl_score = rt.get("score")

        # Handle None scores (unscorable turns)
        if orig_score is None and repl_score is None:
            comparisons.append({"turn": tn, "match": True, "both_unscorable": True})
            continue

        match = orig_score == repl_score
        comp = {
            "turn": tn,
            "match": match,
            "orig_score": orig_score,
            "repl_score": repl_score,
            "is_probe": ot.get("is_probe", False),
            "phase": ot.get("phase", ""),
        }

        if not match:
            # Include details about what changed
            orig_val = ot.get("details", {}).get("model_value")
            repl_val = rt.get("details", {}).get("model_value")
            target = ot.get("details", {}).get("target_value")
            comp["orig_model_value"] = orig_val
            comp["repl_model_value"] = repl_val
            comp["target_value"] = target
            comp["direction"] = ("0→1" if orig_score == 0 and repl_score == 1
                                 else "1→0" if orig_score == 1 and repl_score == 0
                                 else f"{orig_score}→{repl_score}")

        comparisons.append(comp)

    return comparisons


def compare_p2_entry(orig, repl):
    """Compare P2 scored entries. Returns satisfaction comparison."""
    orig_sat = orig.get("avg_satisfaction_rate", 0)
    repl_sat = repl.get("avg_satisfaction_rate", 0)

    orig_conflict = orig.get("conflict_score")
    repl_conflict = repl.get("conflict_score")

    # Compare checkpoint satisfaction if available
    orig_checks = orig.get("checkpoint_satisfaction", {})
    repl_checks = repl.get("checkpoint_satisfaction", {})

    checkpoint_comparisons = {}
    for cp in ["T6", "T11", "T17", "T20", "6", "11", "17", "20"]:
        if cp in orig_checks or cp in repl_checks:
            ov = orig_checks.get(cp)
            rv = repl_checks.get(cp)
            checkpoint_comparisons[cp] = {
                "orig": ov,
                "repl": rv,
                "match": ov == rv,
                "diff": abs((ov or 0) - (rv or 0)),
            }

    return {
        "orig_satisfaction": orig_sat,
        "repl_satisfaction": repl_sat,
        "satisfaction_diff": abs(orig_sat - repl_sat),
        "satisfaction_match": abs(orig_sat - repl_sat) < 0.001,
        "orig_conflict": orig_conflict,
        "repl_conflict": repl_conflict,
        "conflict_match": orig_conflict == repl_conflict,
        "checkpoints": checkpoint_comparisons,
    }


def load_p3_judged(directory):
    """Load P3 judged results from individual files."""
    index = {}
    if not directory or not os.path.exists(directory):
        return index

    for fpath in sorted(glob.glob(os.path.join(directory, "*.json"))):
        try:
            with open(fpath, "r") as f:
                data = json.load(f)
            # Extract model and scenario from the data or filename
            model = data.get("model", "")
            scenario = data.get("scenario_id", "")
            if model and scenario:
                index[(model, scenario)] = data
        except (json.JSONDecodeError, KeyError):
            continue

    return index


def compare_p3_entry(orig, repl):
    """Compare P3 judged entries."""
    dims = ["contradiction_identified", "contradiction_resolved",
            "reasoning_quality", "gap_abstention", "fabrication_detected"]

    comparisons = {}
    for dim in dims:
        # Try multiple key patterns (different judge outputs may use different keys)
        ov = orig.get(dim, orig.get("scores", {}).get(dim))
        rv = repl.get(dim, repl.get("scores", {}).get(dim))

        if ov is not None and rv is not None:
            # For boolean dims (fabrication)
            if isinstance(ov, bool) and isinstance(rv, bool):
                comparisons[dim] = {
                    "orig": ov, "repl": rv, "match": ov == rv,
                }
            # For numeric dims
            elif isinstance(ov, (int, float)) and isinstance(rv, (int, float)):
                comparisons[dim] = {
                    "orig": ov, "repl": rv,
                    "diff": abs(ov - rv),
                    "match": abs(ov - rv) < 0.01,
                }
            else:
                comparisons[dim] = {"orig": ov, "repl": rv, "match": str(ov) == str(rv)}

    return comparisons


def safe_serialize(obj):
    """Handle non-serializable types for JSON output."""
    if isinstance(obj, float):
        if obj != obj:  # NaN
            return None
        if obj == float("inf") or obj == float("-inf"):
            return None
    if isinstance(obj, set):
        return sorted(list(obj))
    if hasattr(obj, "item"):
        return obj.item()
    return str(obj)


def main():
    parser = argparse.ArgumentParser(
        description="Compare scored outcomes: original vs replication",
    )
    parser.add_argument("--original", required=True,
                        help="Path to original scored_results_enhanced.json")
    parser.add_argument("--replication", required=True,
                        help="Path to replication scored_results_enhanced.json")
    parser.add_argument("--p3-original-dir", default=None,
                        help="Path to original P3 judged individual files")
    parser.add_argument("--p3-replication-dir", default=None,
                        help="Path to replication P3 judged individual files")
    parser.add_argument("--output", default="replication_score_comparison.json",
                        help="Output path")
    args = parser.parse_args()

    # Load data
    orig_index = load_scored(args.original)
    repl_index = load_scored(args.replication)

    p3_orig = load_p3_judged(args.p3_original_dir)
    p3_repl = load_p3_judged(args.p3_replication_dir)

    # Aggregate stats
    p1_stats = {
        "total_turns": 0, "matching_turns": 0,
        "total_probes": 0, "matching_probes": 0,
        "total_scenarios": 0, "identical_scenarios": 0,
        "flips_0_to_1": 0, "flips_1_to_0": 0,
    }
    p2_stats = {
        "total_scenarios": 0, "satisfaction_identical": 0,
        "conflict_identical": 0,
        "satisfaction_diffs": [],
    }
    p3_stats = {
        "total_scenarios": 0, "fabrication_match": 0,
        "abstention_match": 0,
    }

    all_results = []
    score_disagreements = []

    # Compare P1 and P2
    for key, repl_entry in repl_index.items():
        model, scenario_id = key
        paradigm = scenario_id.split("_")[0]

        if key not in orig_index:
            all_results.append({
                "model": model, "scenario_id": scenario_id,
                "paradigm": paradigm, "status": "no_original",
            })
            continue

        orig_entry = orig_index[key]

        if paradigm == "P1":
            comparisons = compare_p1_entry(orig_entry, repl_entry)

            scored_turns = [c for c in comparisons
                           if "match" in c and c.get("both_unscorable") is not True]
            matching = [c for c in scored_turns if c["match"]]
            probes = [c for c in scored_turns if c.get("is_probe")]
            probe_matching = [c for c in probes if c["match"]]

            p1_stats["total_turns"] += len(scored_turns)
            p1_stats["matching_turns"] += len(matching)
            p1_stats["total_probes"] += len(probes)
            p1_stats["matching_probes"] += len(probe_matching)
            p1_stats["total_scenarios"] += 1
            if len(matching) == len(scored_turns):
                p1_stats["identical_scenarios"] += 1

            for c in scored_turns:
                if not c["match"]:
                    direction = c.get("direction", "?")
                    if direction == "0→1":
                        p1_stats["flips_0_to_1"] += 1
                    elif direction == "1→0":
                        p1_stats["flips_1_to_0"] += 1
                    score_disagreements.append({
                        "paradigm": "P1", "model": model,
                        "scenario_id": scenario_id,
                        "turn": c["turn"],
                        "direction": direction,
                        "is_probe": c.get("is_probe", False),
                        "target": c.get("target_value"),
                        "orig_value": c.get("orig_model_value"),
                        "repl_value": c.get("repl_model_value"),
                    })

            result = {
                "model": model, "scenario_id": scenario_id,
                "paradigm": "P1",
                "orig_accuracy": orig_entry.get("overall_accuracy"),
                "repl_accuracy": repl_entry.get("overall_accuracy"),
                "orig_probe": orig_entry.get("probe_accuracy"),
                "repl_probe": repl_entry.get("probe_accuracy"),
                "n_scored": len(scored_turns),
                "n_matching": len(matching),
                "all_match": len(matching) == len(scored_turns),
                "turn_details": comparisons,
            }
            all_results.append(result)

        elif paradigm == "P2":
            comp = compare_p2_entry(orig_entry, repl_entry)

            p2_stats["total_scenarios"] += 1
            if comp["satisfaction_match"]:
                p2_stats["satisfaction_identical"] += 1
            if comp["conflict_match"]:
                p2_stats["conflict_identical"] += 1
            p2_stats["satisfaction_diffs"].append(comp["satisfaction_diff"])

            if not comp["satisfaction_match"]:
                score_disagreements.append({
                    "paradigm": "P2", "model": model,
                    "scenario_id": scenario_id,
                    "orig_satisfaction": comp["orig_satisfaction"],
                    "repl_satisfaction": comp["repl_satisfaction"],
                    "diff": comp["satisfaction_diff"],
                })

            result = {
                "model": model, "scenario_id": scenario_id,
                "paradigm": "P2",
                **comp,
            }
            all_results.append(result)

    # Compare P3 (if judged files provided)
    if p3_orig and p3_repl:
        for key, repl_j in p3_repl.items():
            if key not in p3_orig:
                continue
            orig_j = p3_orig[key]
            model, scenario_id = key

            comp = compare_p3_entry(orig_j, repl_j)

            p3_stats["total_scenarios"] += 1
            if "fabrication_detected" in comp:
                if comp["fabrication_detected"]["match"]:
                    p3_stats["fabrication_match"] += 1
            if "gap_abstention" in comp:
                if comp["gap_abstention"]["match"]:
                    p3_stats["abstention_match"] += 1

            result = {
                "model": model, "scenario_id": scenario_id,
                "paradigm": "P3",
                "dimension_comparisons": comp,
            }
            all_results.append(result)

    # Compute summary
    summary = {}

    if p1_stats["total_turns"] > 0:
        summary["P1"] = {
            "scenarios_compared": p1_stats["total_scenarios"],
            "scenarios_all_turns_match": p1_stats["identical_scenarios"],
            "scenario_match_rate": round(
                p1_stats["identical_scenarios"] / p1_stats["total_scenarios"], 4
            ),
            "turn_score_match_rate": round(
                p1_stats["matching_turns"] / p1_stats["total_turns"], 4
            ),
            "probe_score_match_rate": round(
                p1_stats["matching_probes"] / p1_stats["total_probes"], 4
            ) if p1_stats["total_probes"] > 0 else None,
            "total_scored_turns": p1_stats["total_turns"],
            "matching_scored_turns": p1_stats["matching_turns"],
            "total_probes": p1_stats["total_probes"],
            "matching_probes": p1_stats["matching_probes"],
            "flips_wrong_to_right": p1_stats["flips_0_to_1"],
            "flips_right_to_wrong": p1_stats["flips_1_to_0"],
        }

    if p2_stats["total_scenarios"] > 0:
        diffs = p2_stats["satisfaction_diffs"]
        mean_diff = sum(diffs) / len(diffs) if diffs else 0
        max_diff = max(diffs) if diffs else 0
        summary["P2"] = {
            "scenarios_compared": p2_stats["total_scenarios"],
            "satisfaction_identical": p2_stats["satisfaction_identical"],
            "satisfaction_match_rate": round(
                p2_stats["satisfaction_identical"] / p2_stats["total_scenarios"], 4
            ),
            "conflict_identical": p2_stats["conflict_identical"],
            "mean_satisfaction_diff": round(mean_diff, 4),
            "max_satisfaction_diff": round(max_diff, 4),
        }

    if p3_stats["total_scenarios"] > 0:
        summary["P3"] = {
            "scenarios_compared": p3_stats["total_scenarios"],
            "fabrication_match": p3_stats["fabrication_match"],
            "abstention_match": p3_stats["abstention_match"],
        }
    else:
        summary["P3"] = {
            "note": "P3 requires LLM judge. Run score_replication_pipeline.sh "
                    "step 1 to generate judge prompts, then run_p3_judge.py "
                    "on replication results (~$2-3 for 25 entries).",
        }

    # Write output
    output = {
        "description": "Replication score comparison: do scored outcomes agree "
                       "despite text-level differences?",
        "summary": summary,
        "score_disagreements": score_disagreements,
        "scenario_details": all_results,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=safe_serialize)
    print(f"\nResults saved to: {args.output}")

    # Human-readable summary
    print(f"\n{'='*60}")
    print(f"REPLICATION SCORE COMPARISON")
    print(f"{'='*60}")

    if "P1" in summary:
        s = summary["P1"]
        print(f"\n  P1 Numeric Fidelity ({s['scenarios_compared']} scenarios):")
        print(f"    Turn-level score agreement: "
              f"{s['matching_scored_turns']}/{s['total_scored_turns']} "
              f"({s['turn_score_match_rate']:.1%})")
        print(f"    Probe score agreement:      "
              f"{s['matching_probes']}/{s['total_probes']} "
              f"({s['probe_score_match_rate']:.1%})" if s['probe_score_match_rate'] else "")
        print(f"    Scenarios fully identical:   "
              f"{s['scenarios_all_turns_match']}/{s['scenarios_compared']} "
              f"({s['scenario_match_rate']:.1%})")
        if s['flips_right_to_wrong'] > 0 or s['flips_wrong_to_right'] > 0:
            print(f"    Score flips: {s['flips_wrong_to_right']} wrong→right, "
                  f"{s['flips_right_to_wrong']} right→wrong")

    if "P2" in summary:
        s = summary["P2"]
        print(f"\n  P2 Constraint Satisfaction ({s['scenarios_compared']} scenarios):")
        print(f"    Satisfaction identical:  "
              f"{s['satisfaction_identical']}/{s['scenarios_compared']} "
              f"({s['satisfaction_match_rate']:.1%})")
        print(f"    Conflict score identical: "
              f"{s['conflict_identical']}/{s['scenarios_compared']}")
        print(f"    Mean satisfaction diff:  {s['mean_satisfaction_diff']:.4f}")
        print(f"    Max satisfaction diff:   {s['max_satisfaction_diff']:.4f}")

    if "P3" in summary:
        if "note" in summary["P3"]:
            print(f"\n  P3 Source Fidelity: {summary['P3']['note']}")
        else:
            s = summary["P3"]
            print(f"\n  P3 Source Fidelity ({s['scenarios_compared']} scenarios):")
            print(f"    Fabrication agreement: {s['fabrication_match']}/{s['scenarios_compared']}")
            print(f"    Abstention agreement:  {s['abstention_match']}/{s['scenarios_compared']}")

    if score_disagreements:
        print(f"\n  Score disagreements ({len(score_disagreements)} total):")
        for d in score_disagreements[:15]:
            if d["paradigm"] == "P1":
                print(f"    P1 {d['model']}/{d['scenario_id']} T{d['turn']}: "
                      f"{d['direction']}"
                      f"{' (PROBE)' if d.get('is_probe') else ''}"
                      f" target={d.get('target')}")
            elif d["paradigm"] == "P2":
                print(f"    P2 {d['model']}/{d['scenario_id']}: "
                      f"sat {d['orig_satisfaction']:.3f} → {d['repl_satisfaction']:.3f} "
                      f"(Δ={d['diff']:.3f})")
        if len(score_disagreements) > 15:
            print(f"    ... and {len(score_disagreements) - 15} more")
    else:
        print(f"\n  No score disagreements found across any paradigm.")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    main()
