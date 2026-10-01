#!/usr/bin/env python3
"""
compare_replication.py — Targeted Replication Comparison

Compares original and replication conversation results to establish
test-retest reliability. For temperature 0 runs, identical API inputs
should produce identical outputs; any differences indicate API
non-determinism or provider-side model updates.

Reports:
  - Per-turn exact text match rates
  - Key-turn match rates (scored turns only)
  - Per-paradigm and per-model breakdowns
  - Any substantive differences flagged for review

Usage:
  python compare_replication.py \
      --original-dir ./results \
      --replication-dir ./results_replication \
      --output compare_replication_results.json
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path
from difflib import SequenceMatcher
from collections import defaultdict

# Model directory name mapping (runner output uses CLI model names)
MODEL_DIR_NAMES = [
    "gpt-4o",
    "claude-sonnet-4.5",
    "deepseek-r1",
    "gemini-2.5-pro",
    "minimax-m2.5",
]

# Key turns per paradigm (where scores are computed)
P1_KEY_TURNS = [5, 10, 15, 19, 20]
P2_KEY_TURNS = [6, 11, 17, 20]
P3_KEY_TURNS = list(range(1, 13))  # all turns matter for P3


def load_result(directory, model_name, scenario_id):
    """Load a single result JSON from directory/model_name/scenario_id.json."""
    path = Path(directory) / model_name / f"{scenario_id}.json"
    if not path.exists():
        return None
    with open(path, "r") as f:
        return json.load(f)


def extract_numbers(text):
    """Extract all numbers from text for numeric comparison."""
    # Match integers, decimals, percentages, and dollar amounts
    pattern = r'[-+]?\$?[\d,]+\.?\d*%?'
    matches = re.findall(pattern, text)
    # Clean and convert
    cleaned = []
    for m in matches:
        m = m.replace(",", "").replace("$", "").replace("%", "")
        try:
            cleaned.append(float(m))
        except ValueError:
            pass
    return cleaned


def text_similarity(a, b):
    """Compute similarity ratio between two strings (0.0 to 1.0)."""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def compare_turns(orig_turns, repl_turns, paradigm):
    """Compare two lists of turns, return per-turn comparison data."""
    comparisons = []

    # Build turn-number lookup
    orig_by_turn = {t["turn_number"]: t for t in orig_turns}
    repl_by_turn = {t["turn_number"]: t for t in repl_turns}

    if paradigm == "P1":
        key_turns = P1_KEY_TURNS
    elif paradigm == "P2":
        key_turns = P2_KEY_TURNS
    else:
        key_turns = P3_KEY_TURNS

    all_turn_nums = sorted(set(orig_by_turn.keys()) | set(repl_by_turn.keys()))

    for tn in all_turn_nums:
        orig_t = orig_by_turn.get(tn)
        repl_t = repl_by_turn.get(tn)

        if orig_t is None or repl_t is None:
            comparisons.append({
                "turn_number": tn,
                "is_key_turn": tn in key_turns,
                "status": "missing",
                "missing_in": "original" if orig_t is None else "replication",
            })
            continue

        orig_text = orig_t.get("response", "")
        repl_text = repl_t.get("response", "")

        exact_match = orig_text == repl_text
        similarity = text_similarity(orig_text, repl_text) if not exact_match else 1.0

        comp = {
            "turn_number": tn,
            "is_key_turn": tn in key_turns,
            "exact_match": exact_match,
            "similarity": round(similarity, 4),
        }

        # For P1 key turns, also compare extracted numbers
        if paradigm == "P1" and tn in key_turns and not exact_match:
            orig_nums = extract_numbers(orig_text)
            repl_nums = extract_numbers(repl_text)
            comp["orig_numbers"] = orig_nums[:5]  # cap for readability
            comp["repl_numbers"] = repl_nums[:5]
            comp["numbers_match"] = orig_nums == repl_nums

        # For non-matching key turns, store a short diff preview
        if not exact_match and tn in key_turns:
            orig_preview = orig_text[:200].replace("\n", " ")
            repl_preview = repl_text[:200].replace("\n", " ")
            comp["orig_preview"] = orig_preview
            comp["repl_preview"] = repl_preview

        comparisons.append(comp)

    return comparisons


def main():
    parser = argparse.ArgumentParser(
        description="Compare original vs replication results",
    )
    parser.add_argument("--original-dir", required=True,
                        help="Path to original results directory")
    parser.add_argument("--replication-dir", required=True,
                        help="Path to replication results directory")
    parser.add_argument("--output", default="compare_replication_results.json",
                        help="Output JSON path")
    args = parser.parse_args()

    orig_dir = Path(args.original_dir)
    repl_dir = Path(args.replication_dir)

    if not orig_dir.exists():
        print(f"ERROR: Original directory not found: {orig_dir}")
        sys.exit(1)
    if not repl_dir.exists():
        print(f"ERROR: Replication directory not found: {repl_dir}")
        sys.exit(1)

    # Discover which scenario/model pairs exist in the replication
    pairs_found = 0
    pairs_missing = 0
    all_comparisons = []

    # Aggregate statistics
    stats = {
        "by_paradigm": defaultdict(lambda: {
            "total_key_turns": 0,
            "exact_key_turns": 0,
            "total_all_turns": 0,
            "exact_all_turns": 0,
            "scenarios_compared": 0,
            "scenarios_identical": 0,
        }),
        "by_model": defaultdict(lambda: {
            "total_key_turns": 0,
            "exact_key_turns": 0,
            "total_all_turns": 0,
            "exact_all_turns": 0,
            "scenarios_compared": 0,
            "scenarios_identical": 0,
        }),
    }

    # Collect all differences at key turns for the report
    key_turn_differences = []

    for model_name in MODEL_DIR_NAMES:
        repl_model_dir = repl_dir / model_name
        if not repl_model_dir.exists():
            print(f"  [SKIP] No replication data for {model_name}")
            continue

        # Find all replication result files for this model
        for repl_file in sorted(repl_model_dir.glob("P*.json")):
            scenario_id = repl_file.stem
            if scenario_id.startswith("_"):
                continue  # skip manifests

            paradigm = scenario_id.split("_")[0]

            # Load both
            orig = load_result(orig_dir, model_name, scenario_id)
            repl = load_result(repl_dir, model_name, scenario_id)

            if orig is None:
                print(f"  [WARN] Original not found: {model_name}/{scenario_id}")
                pairs_missing += 1
                continue

            pairs_found += 1

            # Compare turns
            comparisons = compare_turns(
                orig.get("turns", []),
                repl.get("turns", []),
                paradigm,
            )

            # Compute scenario-level stats
            key_comps = [c for c in comparisons if c.get("is_key_turn")]
            all_exact = all(c.get("exact_match", False) for c in comparisons
                           if c.get("status") != "missing")
            key_exact = all(c.get("exact_match", False) for c in key_comps
                           if c.get("status") != "missing")

            n_key = len([c for c in key_comps if c.get("status") != "missing"])
            n_key_exact = len([c for c in key_comps
                               if c.get("exact_match", False)])
            n_all = len([c for c in comparisons if c.get("status") != "missing"])
            n_all_exact = len([c for c in comparisons
                               if c.get("exact_match", False)])

            # Update aggregates
            for bucket_key, bucket_name in [("by_paradigm", paradigm),
                                            ("by_model", model_name)]:
                s = stats[bucket_key][bucket_name]
                s["total_key_turns"] += n_key
                s["exact_key_turns"] += n_key_exact
                s["total_all_turns"] += n_all
                s["exact_all_turns"] += n_all_exact
                s["scenarios_compared"] += 1
                if all_exact:
                    s["scenarios_identical"] += 1

            # Collect key-turn differences
            for c in key_comps:
                if not c.get("exact_match", True) and c.get("status") != "missing":
                    key_turn_differences.append({
                        "model": model_name,
                        "scenario_id": scenario_id,
                        "paradigm": paradigm,
                        "turn": c["turn_number"],
                        "similarity": c.get("similarity", 0),
                        "orig_preview": c.get("orig_preview", ""),
                        "repl_preview": c.get("repl_preview", ""),
                    })

            scenario_result = {
                "model": model_name,
                "scenario_id": scenario_id,
                "paradigm": paradigm,
                "all_turns_identical": all_exact,
                "key_turns_identical": key_exact,
                "n_turns": n_all,
                "n_exact": n_all_exact,
                "n_key_turns": n_key,
                "n_key_exact": n_key_exact,
                "turn_details": comparisons,
            }
            all_comparisons.append(scenario_result)

    # Compute summary rates
    summary = {
        "pairs_compared": pairs_found,
        "pairs_missing_original": pairs_missing,
    }

    # Paradigm summary
    paradigm_summary = {}
    for p_name, s in stats["by_paradigm"].items():
        n_key = s["total_key_turns"]
        n_all = s["total_all_turns"]
        paradigm_summary[p_name] = {
            "scenarios_compared": s["scenarios_compared"],
            "scenarios_fully_identical": s["scenarios_identical"],
            "scenario_identity_rate": round(
                s["scenarios_identical"] / s["scenarios_compared"], 4
            ) if s["scenarios_compared"] > 0 else None,
            "key_turn_exact_match_rate": round(
                s["exact_key_turns"] / n_key, 4
            ) if n_key > 0 else None,
            "all_turn_exact_match_rate": round(
                s["exact_all_turns"] / n_all, 4
            ) if n_all > 0 else None,
        }
    summary["by_paradigm"] = paradigm_summary

    # Model summary
    model_summary = {}
    for m_name, s in stats["by_model"].items():
        n_key = s["total_key_turns"]
        n_all = s["total_all_turns"]
        model_summary[m_name] = {
            "scenarios_compared": s["scenarios_compared"],
            "scenarios_fully_identical": s["scenarios_identical"],
            "scenario_identity_rate": round(
                s["scenarios_identical"] / s["scenarios_compared"], 4
            ) if s["scenarios_compared"] > 0 else None,
            "key_turn_exact_match_rate": round(
                s["exact_key_turns"] / n_key, 4
            ) if n_key > 0 else None,
            "all_turn_exact_match_rate": round(
                s["exact_all_turns"] / n_all, 4
            ) if n_all > 0 else None,
        }
    summary["by_model"] = model_summary

    # Overall
    total_key = sum(s["total_key_turns"] for s in stats["by_paradigm"].values())
    exact_key = sum(s["exact_key_turns"] for s in stats["by_paradigm"].values())
    total_all = sum(s["total_all_turns"] for s in stats["by_paradigm"].values())
    exact_all = sum(s["exact_all_turns"] for s in stats["by_paradigm"].values())
    total_scenarios = sum(s["scenarios_compared"] for s in stats["by_paradigm"].values())
    identical_scenarios = sum(s["scenarios_identical"] for s in stats["by_paradigm"].values())

    summary["overall"] = {
        "total_scenarios": total_scenarios,
        "identical_scenarios": identical_scenarios,
        "scenario_identity_rate": round(
            identical_scenarios / total_scenarios, 4
        ) if total_scenarios > 0 else None,
        "key_turn_exact_match_rate": round(
            exact_key / total_key, 4
        ) if total_key > 0 else None,
        "all_turn_exact_match_rate": round(
            exact_all / total_all, 4
        ) if total_all > 0 else None,
    }

    summary["key_turn_differences"] = key_turn_differences

    # Save full results
    output = {
        "description": "Targeted replication comparison: original vs replication at temperature 0",
        "summary": summary,
        "scenario_comparisons": all_comparisons,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nFull results saved to: {args.output}")

    # Print human-readable summary
    print(f"\n{'='*60}")
    print(f"REPLICATION COMPARISON SUMMARY")
    print(f"{'='*60}")

    print(f"\n  Scenario pairs compared: {pairs_found}")
    if pairs_missing > 0:
        print(f"  Missing originals:       {pairs_missing}")

    if total_scenarios > 0:
        print(f"\n  Overall:")
        print(f"    Scenarios fully identical:  "
              f"{identical_scenarios}/{total_scenarios} "
              f"({identical_scenarios/total_scenarios:.1%})")
        print(f"    Key-turn exact match rate:  "
              f"{exact_key}/{total_key} "
              f"({exact_key/total_key:.1%})" if total_key > 0 else "    Key turns: N/A")
        print(f"    All-turn exact match rate:  "
              f"{exact_all}/{total_all} "
              f"({exact_all/total_all:.1%})" if total_all > 0 else "    All turns: N/A")

    print(f"\n  By paradigm:")
    for p_name in sorted(paradigm_summary.keys()):
        ps = paradigm_summary[p_name]
        rate = ps["key_turn_exact_match_rate"]
        ident = ps["scenarios_fully_identical"]
        total = ps["scenarios_compared"]
        print(f"    {p_name}: {ident}/{total} scenarios identical, "
              f"key-turn match: {rate:.1%}" if rate is not None else
              f"    {p_name}: no data")

    print(f"\n  By model:")
    for m_name in MODEL_DIR_NAMES:
        if m_name in model_summary:
            ms = model_summary[m_name]
            rate = ms["key_turn_exact_match_rate"]
            ident = ms["scenarios_fully_identical"]
            total = ms["scenarios_compared"]
            print(f"    {m_name:25s} {ident}/{total} identical, "
                  f"key-turn match: {rate:.1%}" if rate is not None else
                  f"    {m_name:25s} no data")

    if key_turn_differences:
        print(f"\n  Key-turn differences ({len(key_turn_differences)} total):")
        for d in key_turn_differences[:10]:
            print(f"    {d['model']}/{d['scenario_id']} T{d['turn']}: "
                  f"similarity={d['similarity']:.3f}")
        if len(key_turn_differences) > 10:
            print(f"    ... and {len(key_turn_differences) - 10} more "
                  f"(see full output)")
    else:
        print(f"\n  No key-turn differences found. All scored turns are identical.")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    main()
