#!/usr/bin/env python3
"""Diagnose P1_009 and P1_021 ground truth to find list-valued targets."""
import json
import glob
import os

for scenario_id in ["P1_009", "P1_021"]:
    # Find the scenario file
    for pattern in [f"p1_scenarios/{scenario_id}.json", f"{scenario_id}.json"]:
        paths = glob.glob(pattern)
        if paths:
            break
    
    if not paths:
        print(f"{scenario_id}: FILE NOT FOUND")
        continue
    
    with open(paths[0]) as f:
        sc = json.load(f)
    
    print(f"\n{'='*60}")
    print(f"{scenario_id}")
    print(f"{'='*60}")
    
    for turn in sc["turns"]:
        gt = turn.get("ground_truth", {})
        if not gt:
            continue
        
        val = gt.get("value")
        stype = gt.get("scoring_type", "?")
        tn = turn["turn_number"]
        
        # Flag the problematic ones
        flag = " <<<< LIST VALUE" if isinstance(val, list) else ""
        print(f"  Turn {tn:2d} | scoring_type={stype:25s} | value type={type(val).__name__:6s} | value={val}{flag}")