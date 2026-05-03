#!/usr/bin/env python3
"""
p2_rescore.py — Re-score P2 with enhanced parser and compare results.

Reads enhanced parser assignments from p2_parser_fix2.py output,
re-evaluates constraint satisfaction, and compares old vs. new results.

Usage:
  python p2_rescore.py \
    --results-dir ./results \
    --scenarios-dir ./p2_scenarios \
    --enhanced-assignments ./p2_parser_analysis/p2_enhanced_assignments.json \
    --output-dir ./p2_rescore_results
"""

import json
import os
import re
import copy
import argparse
import glob
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Optional


# ==============================================================================
# P2 DOMAIN DEFINITIONS (from score_responses.py — must stay in sync)
# ==============================================================================

P2_DOMAINS = {
    "conference": {
        "display_name": "Conference Schedule",
        "items": [
            {"id": "keynote", "name": "Keynote Address", "attendees": 200, "duration_hrs": 2.0},
            {"id": "ai_panel", "name": "AI Ethics Panel", "attendees": 80, "duration_hrs": 1.5},
            {"id": "data_ws", "name": "Data Science Workshop", "attendees": 60, "duration_hrs": 2.0},
            {"id": "networking", "name": "Networking Session", "attendees": 120, "duration_hrs": 1.0},
            {"id": "product_demo", "name": "Product Demo", "attendees": 90, "duration_hrs": 1.5},
            {"id": "research", "name": "Research Talks", "attendees": 70, "duration_hrs": 2.0},
            {"id": "team_bldg", "name": "Team Building Activity", "attendees": 100, "duration_hrs": 1.5},
            {"id": "closing", "name": "Closing Remarks", "attendees": 180, "duration_hrs": 1.0},
        ],
        "agg_prop": "attendees",
        "slots": [
            {"id": "mon_am", "name": "Monday Morning", "order": 1, "capacity": 2},
            {"id": "mon_pm", "name": "Monday Afternoon", "order": 2, "capacity": 2},
            {"id": "tue_am", "name": "Tuesday Morning", "order": 3, "capacity": 2},
            {"id": "tue_pm", "name": "Tuesday Afternoon", "order": 4, "capacity": 1},
            {"id": "wed_am", "name": "Wednesday Morning", "order": 5, "capacity": 2},
        ],
    },
    "travel": {
        "display_name": "Travel Itinerary",
        "items": [
            {"id": "museum", "name": "Museum Visit", "cost_usd": 45, "energy": 2},
            {"id": "walking_tour", "name": "Walking Tour", "cost_usd": 30, "energy": 4},
            {"id": "beach", "name": "Beach Excursion", "cost_usd": 60, "energy": 3},
            {"id": "hike", "name": "Mountain Hike", "cost_usd": 25, "energy": 5},
            {"id": "market", "name": "Local Market", "cost_usd": 20, "energy": 2},
            {"id": "show", "name": "Cultural Show", "cost_usd": 80, "energy": 1},
            {"id": "food_tour", "name": "Food Tour", "cost_usd": 65, "energy": 3},
            {"id": "temple", "name": "Temple Visit", "cost_usd": 15, "energy": 2},
        ],
        "agg_prop": "cost_usd",
        "slots": [
            {"id": "day1", "name": "Day 1", "order": 1, "capacity": 2},
            {"id": "day2", "name": "Day 2", "order": 2, "capacity": 2},
            {"id": "day3", "name": "Day 3", "order": 3, "capacity": 2},
            {"id": "day4", "name": "Day 4", "order": 4, "capacity": 1},
            {"id": "day5", "name": "Day 5", "order": 5, "capacity": 2},
        ],
    },
    "product": {
        "display_name": "Product Roadmap",
        "items": [
            {"id": "auth", "name": "User Authentication", "story_pts": 8, "devs": 2},
            {"id": "dashboard", "name": "Dashboard UI", "story_pts": 13, "devs": 3},
            {"id": "payments", "name": "Payment System", "story_pts": 13, "devs": 3},
            {"id": "search", "name": "Search Engine", "story_pts": 5, "devs": 1},
            {"id": "notifs", "name": "Notification Service", "story_pts": 5, "devs": 1},
            {"id": "analytics", "name": "Analytics Module", "story_pts": 8, "devs": 2},
            {"id": "mobile", "name": "Mobile App", "story_pts": 13, "devs": 3},
            {"id": "api", "name": "API Gateway", "story_pts": 8, "devs": 2},
        ],
        "agg_prop": "story_pts",
        "slots": [
            {"id": "sp1", "name": "Sprint 1", "order": 1, "capacity": 2},
            {"id": "sp2", "name": "Sprint 2", "order": 2, "capacity": 2},
            {"id": "sp3", "name": "Sprint 3", "order": 3, "capacity": 2},
            {"id": "sp4", "name": "Sprint 4", "order": 4, "capacity": 1},
            {"id": "sp5", "name": "Sprint 5", "order": 5, "capacity": 2},
        ],
    },
    "hiring": {
        "display_name": "Hiring Pipeline",
        "items": [
            {"id": "alice", "name": "Alice Chen", "salary_k": 130, "experience_yrs": 8},
            {"id": "bob", "name": "Bob Kumar", "salary_k": 95, "experience_yrs": 4},
            {"id": "carol", "name": "Carol Santos", "salary_k": 110, "experience_yrs": 6},
            {"id": "david", "name": "David Park", "salary_k": 85, "experience_yrs": 3},
            {"id": "elena", "name": "Elena Volkov", "salary_k": 145, "experience_yrs": 12},
            {"id": "frank", "name": "Frank Osei", "salary_k": 100, "experience_yrs": 5},
            {"id": "grace", "name": "Grace Liu", "salary_k": 120, "experience_yrs": 7},
            {"id": "hasan", "name": "Hasan Ali", "salary_k": 90, "experience_yrs": 3},
        ],
        "agg_prop": "salary_k",
        "slots": [
            {"id": "wk1", "name": "Week 1", "order": 1, "capacity": 2},
            {"id": "wk2", "name": "Week 2", "order": 2, "capacity": 2},
            {"id": "wk3", "name": "Week 3", "order": 3, "capacity": 2},
            {"id": "wk4", "name": "Week 4", "order": 4, "capacity": 1},
            {"id": "wk5", "name": "Week 5", "order": 5, "capacity": 2},
        ],
    },
    "relocation": {
        "display_name": "Office Relocation",
        "items": [
            {"id": "eng", "name": "Engineering", "headcount": 28, "noise": 3},
            {"id": "mktg", "name": "Marketing", "headcount": 15, "noise": 4},
            {"id": "sales", "name": "Sales", "headcount": 20, "noise": 5},
            {"id": "hr", "name": "Human Resources", "headcount": 8, "noise": 2},
            {"id": "finance", "name": "Finance", "headcount": 10, "noise": 1},
            {"id": "legal", "name": "Legal", "headcount": 6, "noise": 1},
            {"id": "product", "name": "Product", "headcount": 12, "noise": 3},
            {"id": "design", "name": "Design", "headcount": 9, "noise": 2},
        ],
        "agg_prop": "headcount",
        "slots": [
            {"id": "fl1", "name": "Floor 1", "order": 1, "capacity": 2},
            {"id": "fl2", "name": "Floor 2", "order": 2, "capacity": 2},
            {"id": "fl3", "name": "Floor 3", "order": 3, "capacity": 2},
            {"id": "fl4", "name": "Floor 4", "order": 4, "capacity": 1},
            {"id": "fl5", "name": "Floor 5", "order": 5, "capacity": 2},
        ],
    },
}


# ==============================================================================
# HELPERS
# ==============================================================================

def _get_slot(d, slot_id):
    return next(s for s in d["slots"] if s["id"] == slot_id)

def _slot_order(d, slot_id):
    return _get_slot(d, slot_id)["order"]

def _iname(d, item_id):
    return next(i for i in d["items"] if i["id"] == item_id)["name"]


# ==============================================================================
# CONSTRAINT CHECKER (from score_responses.py — canonical)
# ==============================================================================

def check_constraint(c, assignment, domain):
    """Check if constraint c is satisfied by assignment. Returns bool."""
    ct = c["type"]
    if ct == "fixed_assignment":
        return assignment.get(c["item"]) == c["slot"]
    elif ct == "exclusion":
        return assignment.get(c["item"]) != c["slot"]
    elif ct == "capacity":
        count = sum(1 for v in assignment.values() if v == c["slot"])
        return count <= c["max"]
    elif ct == "mutual_exclusion":
        return assignment.get(c["item_a"]) != assignment.get(c["item_b"])
    elif ct == "co_location":
        return assignment.get(c["item_a"]) == assignment.get(c["item_b"])
    elif ct == "ordering":
        sa = assignment.get(c["item_a"])
        sb = assignment.get(c["item_b"])
        if sa is None or sb is None:
            return False
        return _slot_order(domain, sa) < _slot_order(domain, sb)
    elif ct == "sum_limit":
        prop = c["property"]
        ip = {i["id"]: i[prop] for i in domain["items"]}
        for s in domain["slots"]:
            total = sum(ip.get(it, 0) for it, sl in assignment.items() if sl == s["id"])
            if total > c["max_per_slot"]:
                return False
        return True
    elif ct == "conditional":
        if assignment.get(c["if_item"]) == c["if_slot"]:
            return assignment.get(c["then_item"]) == c["then_slot"]
        return True
    return True


# ==============================================================================
# CONFLICT DETECTION (from score_responses.py)
# ==============================================================================

CONFLICT_KEYWORDS = [
    "conflict", "contradiction", "contradicts", "incompatible",
    "cannot satisfy", "can't satisfy", "cannot be satisfied",
    "violates", "violation", "impossible to satisfy",
    "mutually exclusive", "clashes with", "inconsistent",
    "at odds with", "irreconcilable", "cannot both",
    "trade-off", "tradeoff", "trade off",
]


def detect_conflict_flagged(response: str, conflict_constraint: Dict,
                            domain_key: str) -> bool:
    """Heuristically detects whether the model flagged a conflict."""
    response_lower = response.lower()
    has_keyword = any(kw in response_lower for kw in CONFLICT_KEYWORDS)
    if not has_keyword:
        return False

    dom = P2_DOMAINS[domain_key]
    involved_items = []
    for key in ("item", "item_a", "item_b", "if_item", "then_item"):
        if key in conflict_constraint:
            involved_items.append(_iname(dom, conflict_constraint[key]).lower())

    if not involved_items:
        return has_keyword

    item_mentioned = any(name in response_lower for name in involved_items)
    return item_mentioned


# ==============================================================================
# MAIN RESCORING
# ==============================================================================

CHECKPOINT_TURNS = {6, 11, 17, 20}


def load_scenarios(scenarios_dir: str) -> Dict[str, Dict]:
    """Load all P2 scenario files."""
    scenarios = {}
    for f in sorted(glob.glob(os.path.join(scenarios_dir, "P2_*.json"))):
        with open(f, 'r') as fp:
            scenario = json.load(fp)
        scenarios[scenario["scenario_id"]] = scenario
    return scenarios


def load_results(results_dir: str) -> Dict[Tuple[str, str, int], str]:
    """Load raw responses keyed by (scenario_id, model, turn_number)."""
    response_map = {}
    for model_dir in sorted(glob.glob(os.path.join(results_dir, "*"))):
        if not os.path.isdir(model_dir):
            continue
        model_name = os.path.basename(model_dir)
        if model_name.startswith('.') or model_name in ('scored', 'scored_full'):
            continue
        for f in sorted(glob.glob(os.path.join(model_dir, "P2_*.json"))):
            try:
                with open(f, 'r') as fp:
                    result = json.load(fp)
                if "turns" not in result:
                    continue
                sid = result["scenario_id"]
                for t in result["turns"]:
                    tn = t["turn_number"]
                    if tn in CHECKPOINT_TURNS and "response" in t:
                        response_map[(sid, model_name, tn)] = t["response"]
            except (json.JSONDecodeError, KeyError):
                pass
    return response_map


def score_checkpoint(assignment: Dict[str, str], scenario: Dict,
                     turn: Dict, response: str, domain_key: str) -> Dict:
    """
    Score a single checkpoint using a given assignment dict.
    Returns satisfaction rate and conflict score.
    """
    dom = copy.deepcopy(P2_DOMAINS[domain_key])
    gt = turn.get("ground_truth", {})
    if not gt:
        return {"satisfaction_rate": 0.0, "conflict_score": None,
                "n_satisfied": 0, "n_violated": 0, "n_omitted": 0}

    gt_satisfaction = gt.get("constraint_satisfaction", {})
    constraints_by_id = {c["id"]: c for c in scenario["constraints"]}

    n_satisfied = 0
    n_violated = 0
    n_omitted = 0
    conflict_score = None

    for cid, gt_entry in gt_satisfaction.items():
        c = constraints_by_id.get(cid)
        if c is None:
            continue

        is_conflict = gt_entry.get("is_conflict", False)

        # Check if constraint's items are present in assignment
        involved_items = []
        for key in ("item", "item_a", "item_b", "if_item", "then_item"):
            if key in c:
                involved_items.append(c[key])

        items_present = all(it in assignment for it in involved_items)

        if not items_present and not is_conflict:
            n_omitted += 1
            continue

        satisfied = check_constraint(c, assignment, dom) if items_present else False

        if is_conflict:
            flagged = detect_conflict_flagged(response, c, domain_key)
            if flagged:
                conflict_score = 1.0
            elif satisfied:
                conflict_score = 0.25
            else:
                conflict_score = 0.75
        else:
            if satisfied:
                n_satisfied += 1
            else:
                n_violated += 1

    n_non_conflict = n_satisfied + n_violated + n_omitted
    satisfaction_rate = n_satisfied / n_non_conflict if n_non_conflict > 0 else 0.0

    return {
        "satisfaction_rate": round(satisfaction_rate, 4),
        "conflict_score": conflict_score,
        "n_satisfied": n_satisfied,
        "n_violated": n_violated,
        "n_omitted": n_omitted,
    }


def run_rescore(results_dir: str, scenarios_dir: str,
                enhanced_path: str, output_dir: str):
    """Main re-scoring pipeline."""
    os.makedirs(output_dir, exist_ok=True)

    print("Loading P2 scenarios...")
    scenarios = load_scenarios(scenarios_dir)
    print(f"  Loaded {len(scenarios)} scenarios")

    print("Loading raw responses for conflict detection...")
    response_map = load_results(results_dir)
    print(f"  Loaded {len(response_map)} checkpoint responses")

    print("Loading enhanced assignments...")
    with open(enhanced_path, 'r') as f:
        enhanced_data = json.load(f)
    print(f"  Loaded {len(enhanced_data)} checkpoint records")

    # --- Re-score each checkpoint with both parsers ---
    results_orig = defaultdict(list)   # model -> list of per-scenario results
    results_enh = defaultdict(list)

    # Group enhanced data by (scenario_id, model)
    by_scenario_model = defaultdict(dict)  # (sid, model) -> {turn: record}
    for rec in enhanced_data:
        key = (rec["scenario_id"], rec["model"])
        by_scenario_model[key][rec["turn_number"]] = rec

    for (sid, model), turn_records in sorted(by_scenario_model.items()):
        scenario = scenarios.get(sid)
        if not scenario:
            continue

        domain_key = scenario["domain"]
        scenario_turns = {t["turn_number"]: t for t in scenario["turns"]}

        cp_results_orig = []
        cp_results_enh = []
        conflict_orig = None
        conflict_enh = None

        for tn in sorted(CHECKPOINT_TURNS):
            rec = turn_records.get(tn)
            s_turn = scenario_turns.get(tn)
            if rec is None or s_turn is None:
                continue

            response = response_map.get((sid, model, tn), "")

            # Score with original assignments
            orig_result = score_checkpoint(
                rec["assignment_original"], scenario, s_turn,
                response, domain_key)
            cp_results_orig.append(orig_result)
            if orig_result["conflict_score"] is not None:
                conflict_orig = orig_result["conflict_score"]

            # Score with enhanced assignments
            enh_result = score_checkpoint(
                rec["assignment_enhanced"], scenario, s_turn,
                response, domain_key)
            cp_results_enh.append(enh_result)
            if enh_result["conflict_score"] is not None:
                conflict_enh = enh_result["conflict_score"]

        if cp_results_orig:
            avg_sat_orig = sum(r["satisfaction_rate"] for r in cp_results_orig) / len(cp_results_orig)
            results_orig[model].append({
                "scenario_id": sid,
                "avg_satisfaction": round(avg_sat_orig, 4),
                "conflict_score": conflict_orig,
                "per_checkpoint": cp_results_orig,
            })

        if cp_results_enh:
            avg_sat_enh = sum(r["satisfaction_rate"] for r in cp_results_enh) / len(cp_results_enh)
            results_enh[model].append({
                "scenario_id": sid,
                "avg_satisfaction": round(avg_sat_enh, 4),
                "conflict_score": conflict_enh,
                "per_checkpoint": cp_results_enh,
            })

    # --- Compute aggregate comparisons ---
    print(f"\n{'='*70}")
    print("P2 RE-SCORING RESULTS: ORIGINAL vs ENHANCED PARSER")
    print(f"{'='*70}")

    comparison = {}
    all_models = sorted(set(list(results_orig.keys()) + list(results_enh.keys())))

    for model in all_models:
        orig_scenarios = results_orig.get(model, [])
        enh_scenarios = results_enh.get(model, [])

        if not orig_scenarios or not enh_scenarios:
            continue

        n = len(orig_scenarios)
        avg_sat_orig = sum(r["avg_satisfaction"] for r in orig_scenarios) / n
        avg_sat_enh = sum(r["avg_satisfaction"] for r in enh_scenarios) / n

        # Conflict scores
        conflict_orig_scores = [r["conflict_score"] for r in orig_scenarios
                                if r["conflict_score"] is not None]
        conflict_enh_scores = [r["conflict_score"] for r in enh_scenarios
                               if r["conflict_score"] is not None]
        avg_conflict_orig = (sum(conflict_orig_scores) / len(conflict_orig_scores)
                             if conflict_orig_scores else None)
        avg_conflict_enh = (sum(conflict_enh_scores) / len(conflict_enh_scores)
                            if conflict_enh_scores else None)

        # Per-checkpoint-turn averages
        per_turn_orig = defaultdict(list)
        per_turn_enh = defaultdict(list)
        for scen_orig, scen_enh in zip(orig_scenarios, enh_scenarios):
            for i, tn in enumerate(sorted(CHECKPOINT_TURNS)):
                if i < len(scen_orig["per_checkpoint"]):
                    per_turn_orig[tn].append(scen_orig["per_checkpoint"][i]["satisfaction_rate"])
                if i < len(scen_enh["per_checkpoint"]):
                    per_turn_enh[tn].append(scen_enh["per_checkpoint"][i]["satisfaction_rate"])

        turn_comparison = {}
        for tn in sorted(CHECKPOINT_TURNS):
            if per_turn_orig[tn] and per_turn_enh[tn]:
                orig_avg = sum(per_turn_orig[tn]) / len(per_turn_orig[tn])
                enh_avg = sum(per_turn_enh[tn]) / len(per_turn_enh[tn])
                turn_comparison[f"T{tn}"] = {
                    "original": round(orig_avg, 4),
                    "enhanced": round(enh_avg, 4),
                    "delta": round(enh_avg - orig_avg, 4),
                }

        delta = avg_sat_enh - avg_sat_orig

        comparison[model] = {
            "n_scenarios": n,
            "satisfaction_original": round(avg_sat_orig, 4),
            "satisfaction_enhanced": round(avg_sat_enh, 4),
            "delta": round(delta, 4),
            "conflict_original": round(avg_conflict_orig, 4) if avg_conflict_orig is not None else None,
            "conflict_enhanced": round(avg_conflict_enh, 4) if avg_conflict_enh is not None else None,
            "per_turn": turn_comparison,
        }

        print(f"\n  {model}:")
        print(f"    Satisfaction: {avg_sat_orig:.3f} → {avg_sat_enh:.3f}  (Δ={delta:+.3f})")
        if avg_conflict_orig is not None:
            c_delta = (avg_conflict_enh or 0) - (avg_conflict_orig or 0)
            print(f"    Conflict:    {avg_conflict_orig:.3f} → {avg_conflict_enh:.3f}  (Δ={c_delta:+.3f})")
        for tn_label, tc in sorted(turn_comparison.items()):
            print(f"    {tn_label}:  {tc['original']:.3f} → {tc['enhanced']:.3f}  (Δ={tc['delta']:+.3f})")

    # --- Print ranking comparison ---
    print(f"\n{'='*70}")
    print("MODEL RANKING COMPARISON")
    print(f"{'='*70}")

    rank_orig = sorted(comparison.items(), key=lambda x: x[1]["satisfaction_original"], reverse=True)
    rank_enh = sorted(comparison.items(), key=lambda x: x[1]["satisfaction_enhanced"], reverse=True)

    print(f"\n  Original parser ranking (by satisfaction rate):")
    for i, (model, data) in enumerate(rank_orig, 1):
        print(f"    {i}. {model:25s}  {data['satisfaction_original']:.3f}")

    print(f"\n  Enhanced parser ranking (by satisfaction rate):")
    for i, (model, data) in enumerate(rank_enh, 1):
        print(f"    {i}. {model:25s}  {data['satisfaction_enhanced']:.3f}")

    # --- Highlight biggest movers ---
    print(f"\n  Biggest changes:")
    sorted_by_delta = sorted(comparison.items(), key=lambda x: abs(x[1]["delta"]), reverse=True)
    for model, data in sorted_by_delta:
        direction = "↑" if data["delta"] > 0 else "↓"
        print(f"    {model:25s}  {direction} {abs(data['delta']):.3f}")

    # --- Write output ---
    output = {
        "comparison": comparison,
        "ranking_original": [m for m, _ in rank_orig],
        "ranking_enhanced": [m for m, _ in rank_enh],
    }

    output_path = os.path.join(output_dir, "p2_rescore_comparison.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n\nResults written to: {output_path}")

    # Per-scenario detail for further analysis
    detail = {}
    for model in all_models:
        detail[model] = {
            "original": results_orig.get(model, []),
            "enhanced": results_enh.get(model, []),
        }

    # Strip per_checkpoint sub-detail to keep file manageable
    detail_slim = {}
    for model in all_models:
        orig_list = []
        enh_list = []
        for r in results_orig.get(model, []):
            orig_list.append({
                "scenario_id": r["scenario_id"],
                "avg_satisfaction": r["avg_satisfaction"],
                "conflict_score": r["conflict_score"],
            })
        for r in results_enh.get(model, []):
            enh_list.append({
                "scenario_id": r["scenario_id"],
                "avg_satisfaction": r["avg_satisfaction"],
                "conflict_score": r["conflict_score"],
            })
        detail_slim[model] = {"original": orig_list, "enhanced": enh_list}

    detail_path = os.path.join(output_dir, "p2_rescore_per_scenario.json")
    with open(detail_path, "w") as f:
        json.dump(detail_slim, f, indent=2)
    print(f"Per-scenario detail written to: {detail_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Re-score P2 with enhanced parser and compare")
    parser.add_argument(
        "--results-dir", required=True,
        help="Directory containing raw model results")
    parser.add_argument(
        "--scenarios-dir", required=True,
        help="Directory containing P2 scenario files")
    parser.add_argument(
        "--enhanced-assignments", required=True,
        help="Path to p2_enhanced_assignments.json from p2_parser_fix2.py")
    parser.add_argument(
        "--output-dir", default="./p2_rescore_results",
        help="Output directory")
    args = parser.parse_args()

    run_rescore(args.results_dir, args.scenarios_dir,
                args.enhanced_assignments, args.output_dir)
