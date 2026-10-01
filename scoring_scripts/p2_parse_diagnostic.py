#!/usr/bin/env python3
"""
p2_parse_diagnostic.py — Investigate P2 parser failures.

For each model, samples raw responses from 0-parse and low-parse checkpoint
entries to determine whether the issue is:
  (a) Parser failure: model outputs a structured plan but in an unrecognized format
  (b) Genuine behavior: model doesn't assign all items (e.g., leaves items "Unassigned")

Run from ContextRot/ directory:
    python p2_parse_diagnostic.py --results-dir ./results --scored-results ./results/scored_full/scored_results.json

Output: Prints sampled responses with parse counts for manual inspection,
        plus writes a summary to ./analysis/p2_parse_diagnostic.txt
"""

import json
import os
import argparse
import glob
from collections import defaultdict


def load_result_file(results_dir, model, scenario_id):
    """Load a single raw result file."""
    path = os.path.join(results_dir, model, f"{scenario_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def get_response_at_turn(result, turn_number):
    """Extract the model's response at a specific turn."""
    for t in result.get("turns", []):
        if t["turn_number"] == turn_number:
            return t.get("response", "")
    return None


def main():
    parser = argparse.ArgumentParser(description="P2 parser failure diagnostic")
    parser.add_argument("--results-dir", required=True, help="Directory containing model results")
    parser.add_argument("--scored-results", required=True, help="Path to scored_results.json")
    parser.add_argument("--output-dir", default="./analysis", help="Output directory")
    parser.add_argument("--samples-per-model", type=int, default=3,
                        help="Number of 0-parse responses to show per model")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Load scored results
    with open(args.scored_results) as f:
        scored = json.load(f)

    # Collect P2 checkpoint data with parse counts
    checkpoint_data = []  # (model, scenario_id, turn, n_parsed, sat_rate)
    for entry in scored:
        if entry["paradigm"] != "P2":
            continue
        model = entry["model"]
        sid = entry["scenario_id"]
        for t in entry["turn_scores"]:
            if t.get("type") != "checkpoint":
                continue
            checkpoint_data.append({
                "model": model,
                "scenario_id": sid,
                "turn": t["turn_number"],
                "n_items_parsed": t.get("n_items_parsed", 0),
                "satisfaction_rate": t.get("satisfaction_rate", 0),
                "n_satisfied": t.get("n_satisfied", 0),
                "n_violated": t.get("n_violated", 0),
                "n_omitted": t.get("n_omitted", 0),
            })

    output_lines = []

    def log(msg=""):
        print(msg)
        output_lines.append(msg)

    log("=" * 80)
    log("P2 PARSER FAILURE DIAGNOSTIC")
    log("=" * 80)

    # ---- PART 1: Summary of parse counts by model ----
    log("\n--- PART 1: Parse Count Distribution by Model ---\n")

    models = sorted(set(c["model"] for c in checkpoint_data))
    for model in models:
        mc = [c for c in checkpoint_data if c["model"] == model]
        n_total = len(mc)
        n_zero = sum(1 for c in mc if c["n_items_parsed"] == 0)
        n_low = sum(1 for c in mc if 0 < c["n_items_parsed"] <= 3)
        n_ok = sum(1 for c in mc if c["n_items_parsed"] >= 4)
        n_full = sum(1 for c in mc if c["n_items_parsed"] == 8)

        log(f"  {model}:")
        log(f"    Total checkpoints: {n_total}")
        log(f"    0 items parsed:    {n_zero} ({n_zero/n_total:.0%})")
        log(f"    1-3 items parsed:  {n_low} ({n_low/n_total:.0%})")
        log(f"    4-7 items parsed:  {n_ok - n_full} ({(n_ok-n_full)/n_total:.0%})")
        log(f"    8 items parsed:    {n_full} ({n_full/n_total:.0%})")
        log()

    # ---- PART 2: Sample zero-parse responses ----
    log("\n--- PART 2: Sample ZERO-PARSE Responses (raw text) ---\n")

    zero_parse = [c for c in checkpoint_data if c["n_items_parsed"] == 0]

    # Group by model
    zero_by_model = defaultdict(list)
    for c in zero_parse:
        zero_by_model[c["model"]].append(c)

    for model in models:
        zeros = zero_by_model.get(model, [])
        if not zeros:
            log(f"  {model}: No zero-parse entries ✓")
            log()
            continue

        log(f"  {model}: {len(zeros)} zero-parse entries. Sampling {min(args.samples_per_model, len(zeros))}:")
        log()

        for i, entry in enumerate(zeros[:args.samples_per_model]):
            sid = entry["scenario_id"]
            turn = entry["turn"]

            # Load raw response
            result = load_result_file(args.results_dir, model, sid)
            if result is None:
                log(f"    [{sid} T{turn}] Raw file not found")
                continue

            response = get_response_at_turn(result, turn)
            if response is None:
                log(f"    [{sid} T{turn}] No response at this turn")
                continue

            # Truncate for display
            display = response[:1500]
            if len(response) > 1500:
                display += f"\n    ... [truncated, total {len(response)} chars]"

            log(f"    ---- {sid} T{turn} ({len(response)} chars) ----")
            # Indent the response
            for line in display.split("\n"):
                log(f"    | {line}")
            log()

        log("-" * 70)
        log()

    # ---- PART 3: Sample GPT-4o LOW-PARSE (2-3 items) at T6 ----
    log("\n--- PART 3: GPT-4o Early Checkpoint Responses (low parse count) ---\n")

    gpt4o_t6 = [c for c in checkpoint_data
                if c["model"] == "gpt-4o" and c["turn"] == 6 and c["n_items_parsed"] <= 3]

    log(f"  GPT-4o T6 entries with ≤3 items parsed: {len(gpt4o_t6)}")
    log()

    for entry in gpt4o_t6[:3]:
        sid = entry["scenario_id"]
        result = load_result_file(args.results_dir, "gpt-4o", sid)
        if result is None:
            continue
        response = get_response_at_turn(result, 6)
        if response is None:
            continue

        display = response[:2000]
        if len(response) > 2000:
            display += f"\n    ... [truncated, total {len(response)} chars]"

        log(f"    ---- {sid} T6 (parsed {entry['n_items_parsed']}/8 items) ----")
        for line in display.split("\n"):
            log(f"    | {line}")
        log()

    # ---- PART 4: Sample DeepSeek-R1 HIGH-PARSE for comparison ----
    log("\n--- PART 4: DeepSeek-R1 T6 Response (high parse, for comparison) ---\n")

    ds_t6 = [c for c in checkpoint_data
             if c["model"] == "deepseek-r1" and c["turn"] == 6 and c["n_items_parsed"] >= 7]

    if ds_t6:
        entry = ds_t6[0]
        sid = entry["scenario_id"]
        result = load_result_file(args.results_dir, "deepseek-r1", sid)
        if result:
            response = get_response_at_turn(result, 6)
            if response:
                display = response[:2000]
                if len(response) > 2000:
                    display += f"\n    ... [truncated, total {len(response)} chars]"
                log(f"    ---- {sid} T6 (parsed {entry['n_items_parsed']}/8 items) ----")
                for line in display.split("\n"):
                    log(f"    | {line}")

    # ---- PART 5: Which scenarios are problematic across models? ----
    log("\n\n--- PART 5: Scenarios with Parsing Problems Across Multiple Models ---\n")

    # For each scenario+turn, count how many models had 0 parse
    from collections import Counter
    scenario_turn_zeros = Counter()
    for c in zero_parse:
        scenario_turn_zeros[(c["scenario_id"], c["turn"])] += 1

    # Show scenario+turns where 2+ models had 0 parse (likely scenario-specific issue)
    multi_model_zeros = {k: v for k, v in scenario_turn_zeros.items() if v >= 2}
    if multi_model_zeros:
        log(f"  Scenario+turn combos where 2+ models parsed 0 items:")
        for (sid, turn), count in sorted(multi_model_zeros.items()):
            log(f"    {sid} T{turn}: {count} models had 0 items parsed")
    else:
        log(f"  No scenario+turn combos where 2+ models both parsed 0 items.")

    # Also check: scenarios where ALL models parse low
    log(f"\n  Per-scenario mean parse count (averaged across all models and checkpoints):")
    scenario_parse = defaultdict(list)
    for c in checkpoint_data:
        scenario_parse[c["scenario_id"]].append(c["n_items_parsed"])

    low_scenarios = []
    for sid in sorted(scenario_parse.keys()):
        mean_parse = sum(scenario_parse[sid]) / len(scenario_parse[sid])
        if mean_parse < 4.0:
            low_scenarios.append((sid, mean_parse, len(scenario_parse[sid])))

    if low_scenarios:
        log(f"\n  Scenarios with mean parse < 4.0 (likely problematic):")
        for sid, mp, n in low_scenarios:
            log(f"    {sid}: mean_parsed={mp:.1f} (n={n} checkpoints)")
    else:
        log(f"  All scenarios have mean parse ≥ 4.0")

    # Write output
    output_path = os.path.join(args.output_dir, "p2_parse_diagnostic.txt")
    with open(output_path, "w") as f:
        f.write("\n".join(output_lines))
    print(f"\n  Full diagnostic saved to: {output_path}")


if __name__ == "__main__":
    main()
