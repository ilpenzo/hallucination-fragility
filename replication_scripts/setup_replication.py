#!/usr/bin/env python3
"""
setup_replication.py — Targeted Replication Setup
Creates a staging directory with only the scenarios selected for replication.

Replication targets (20 scenarios × 5 models = 100 conversations):
  P1 (5):  Highest cross-model variance scenarios
  P2 (10): The 10 hardest post-conflict scenarios
  P3 (5):  All 3 fabrication scenarios + 2 zero-fabrication controls

Estimated cost: ~$12-15 across all 5 models.

Usage:
  python setup_replication.py \
      --scenarios-dir ./scenarios \
      --staging-dir ./replication_scenarios
"""

import os
import sys
import json
import argparse
from pathlib import Path


# ============================================================================
# TARGET SCENARIO IDS
# ============================================================================

# P1: 5 scenarios with highest cross-model variance
# These are where single-run instability would most affect the paper's claims
P1_TARGETS = ["P1_016", "P1_001", "P1_025", "P1_046", "P1_045"]

# P2: 10 hardest scenarios (lowest mean satisfaction, highest variance)
# These drive the post-conflict collapse finding central to the
# detection-integration dissociation
P2_TARGETS = [
    "P2_003", "P2_037", "P2_029", "P2_013", "P2_008",
    "P2_033", "P2_007", "P2_014", "P2_017", "P2_030",
]

# P3: all 3 scenarios with fabrication + 2 zero-fabrication controls
# P3_019 is the crown jewel (3/5 models fabricated)
P3_TARGETS = ["P3_019", "P3_008", "P3_014", "P3_016", "P3_001"]

ALL_TARGETS = P1_TARGETS + P2_TARGETS + P3_TARGETS

# Models and approximate per-conversation costs (from original runs)
MODELS = ["gpt-4o", "claude-sonnet-4.5", "deepseek-r1", "gemini-2.5-pro", "minimax-m2.5"]
COST_PER_CONV = {
    "gpt-4o": 0.19,
    "claude-sonnet-4.5": 0.28,
    "deepseek-r1": 0.07,
    "gemini-2.5-pro": 0.05,
    "minimax-m2.5": 0.03,
}


def main():
    parser = argparse.ArgumentParser(
        description="Set up targeted replication staging directory",
    )
    parser.add_argument("--scenarios-dir", required=True,
                        help="Path to original scenarios directory")
    parser.add_argument("--staging-dir", default="./replication_scenarios",
                        help="Where to create the staging directory")
    args = parser.parse_args()

    scenarios_dir = Path(args.scenarios_dir).resolve()
    staging_dir = Path(args.staging_dir).resolve()

    # Validate source directory
    p1_dir = scenarios_dir / "p1_scenarios"
    p2_dir = scenarios_dir / "p2_scenarios"
    p3_source = scenarios_dir / "p3_source_data.json"

    if not p1_dir.exists():
        print(f"ERROR: P1 scenarios directory not found: {p1_dir}")
        sys.exit(1)
    if not p2_dir.exists():
        print(f"ERROR: P2 scenarios directory not found: {p2_dir}")
        sys.exit(1)
    if not p3_source.exists():
        print(f"ERROR: P3 source data not found: {p3_source}")
        sys.exit(1)

    # Create staging directory structure
    staging_p1 = staging_dir / "p1_scenarios"
    staging_p2 = staging_dir / "p2_scenarios"

    staging_p1.mkdir(parents=True, exist_ok=True)
    staging_p2.mkdir(parents=True, exist_ok=True)

    print(f"Staging directory: {staging_dir}")
    print(f"Source directory:  {scenarios_dir}")
    print()

    # Link P1 scenarios
    linked = 0
    missing = []
    for sid in P1_TARGETS:
        src = p1_dir / f"{sid}.json"
        dst = staging_p1 / f"{sid}.json"
        if src.exists():
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            os.symlink(src, dst)
            linked += 1
        else:
            missing.append(str(src))
    print(f"P1: {linked}/{len(P1_TARGETS)} scenarios linked")

    # Link P2 scenarios
    linked = 0
    for sid in P2_TARGETS:
        src = p2_dir / f"{sid}.json"
        dst = staging_p2 / f"{sid}.json"
        if src.exists():
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            os.symlink(src, dst)
            linked += 1
        else:
            missing.append(str(src))
    print(f"P2: {linked}/{len(P2_TARGETS)} scenarios linked")

    # Filter P3 source data to only target scenarios
    with open(p3_source, "r") as f:
        p3_data = json.load(f)

    p3_target_set = set(P3_TARGETS)
    filtered_scenarios = [
        s for s in p3_data["scenarios"]
        if s["scenario_id"] in p3_target_set
    ]

    if len(filtered_scenarios) != len(P3_TARGETS):
        found_ids = {s["scenario_id"] for s in filtered_scenarios}
        for sid in P3_TARGETS:
            if sid not in found_ids:
                missing.append(f"P3 scenario {sid} in p3_source_data.json")

    filtered_p3 = {"scenarios": filtered_scenarios}
    p3_out = staging_dir / "p3_source_data.json"
    with open(p3_out, "w") as f:
        json.dump(filtered_p3, f, indent=2, ensure_ascii=False)
    print(f"P3: {len(filtered_scenarios)}/{len(P3_TARGETS)} scenarios written to filtered source")

    if missing:
        print(f"\nWARNING: {len(missing)} source files not found:")
        for m in missing:
            print(f"  {m}")

    # Print cost estimate
    total_convs = len(ALL_TARGETS) * len(MODELS)
    total_cost = sum(
        len(ALL_TARGETS) * COST_PER_CONV[m] for m in MODELS
    )

    print(f"\n{'='*60}")
    print(f"REPLICATION PLAN")
    print(f"{'='*60}")
    print(f"  Scenarios: {len(ALL_TARGETS)} ({len(P1_TARGETS)} P1 + {len(P2_TARGETS)} P2 + {len(P3_TARGETS)} P3)")
    print(f"  Models:    {len(MODELS)}")
    print(f"  Total conversations: {total_convs}")
    print(f"  Estimated cost:      ${total_cost:.2f}")
    print()
    print("  Per-model estimates:")
    for m in MODELS:
        mc = len(ALL_TARGETS) * COST_PER_CONV[m]
        print(f"    {m:25s}  {len(ALL_TARGETS)} convs × ${COST_PER_CONV[m]:.2f} = ${mc:.2f}")

    # Print run commands
    print(f"\n{'='*60}")
    print(f"RUN COMMANDS (execute one at a time)")
    print(f"{'='*60}")
    for m in MODELS:
        mc = len(ALL_TARGETS) * COST_PER_CONV[m]
        print(f"\n# {m} (~${mc:.2f})")
        print(f"python conversation_runner.py \\")
        print(f"    --scenarios-dir {staging_dir} \\")
        print(f"    --output-dir ./results_replication \\")
        print(f"    --model {m} \\")
        print(f"    --budget-limit {mc * 2:.2f}")

    print(f"\n{'='*60}")
    print(f"AFTER ALL RUNS COMPLETE")
    print(f"{'='*60}")
    print(f"python compare_replication.py \\")
    print(f"    --original-dir ./results \\")
    print(f"    --replication-dir ./results_replication \\")
    print(f"    --output compare_replication_results.json")
    print()


if __name__ == "__main__":
    main()
