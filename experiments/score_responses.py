#!/usr/bin/env python3
"""
score_responses.py — Phase 0d: Scoring Pipeline (v2)
Context-Dependent Hallucination in Frontier LLMs

Evaluates model responses against scenario ground truth for all three paradigms.
- P1: Deterministic numeric/text comparison with tolerance.
- P2: Deterministic constraint satisfaction checking (parses structured plans).
- P3: Generates prompts for LLM-as-Judge evaluation (does NOT call API).

Expected result file format (produced by conversation runner):
{
  "scenario_id": "P1_001",
  "model": "gpt-4o",
  "temperature": 0,
  "turns": [
    {"turn_number": 1, "prompt": "...", "response": "...", "timestamp": "..."},
    ...
  ]
}

Usage:
  python3 score_responses.py --results-dir ./results --scenarios-dir ./scenarios
  python3 score_responses.py --results-dir ./results --scenarios-dir ./scenarios --paradigm p1
  python3 score_responses.py --results-dir ./results --scenarios-dir ./scenarios --output-dir ./scored
"""

import json
import os
import re
import copy
import argparse
import glob
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple

# ==============================================================================
# P2 DOMAIN DEFINITIONS (copied from generate_p2_scenarios.py)
# These must stay in sync with the generator. If domains change, update both.
# ==============================================================================

P2_DOMAINS = {
    "conference": {
        "display_name": "Conference Schedule",
        "item_label": "session", "items_label": "sessions",
        "slot_label": "time block", "slots_label": "time blocks",
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
        "item_label": "activity", "items_label": "activities",
        "slot_label": "day", "slots_label": "days",
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
        "item_label": "feature", "items_label": "features",
        "slot_label": "sprint", "slots_label": "sprints",
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
        "item_label": "candidate", "items_label": "candidates",
        "slot_label": "interview week", "slots_label": "interview weeks",
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
        "item_label": "team", "items_label": "teams",
        "slot_label": "floor", "slots_label": "floors",
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
# P2 HELPERS (copied from generate_p2_scenarios.py)
# ==============================================================================

def _get_item(d, item_id):
    return next(i for i in d["items"] if i["id"] == item_id)

def _get_slot(d, slot_id):
    return next(s for s in d["slots"] if s["id"] == slot_id)

def _slot_order(d, slot_id):
    return _get_slot(d, slot_id)["order"]

def _iname(d, item_id):
    return _get_item(d, item_id)["name"]

def _sname(d, slot_id):
    return _get_slot(d, slot_id)["name"]


# ==============================================================================
# P2 CONSTRAINT CHECKER (copied from generate_p2_scenarios.py — canonical)
# ==============================================================================

def check_constraint(c, assignment, domain):
    """Check if constraint c is satisfied by assignment. Returns bool.

    This is the canonical constraint checker, copied from generate_p2_scenarios.py.
    It handles all 8 constraint types: fixed_assignment, exclusion, capacity,
    mutual_exclusion, co_location, ordering, sum_limit, conditional.
    """
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
# SCORER: PARADIGM 1 (NUMERIC ANALYSIS)
# ==============================================================================

class ScorerP1:
    """
    Scores P1 (Progressive Numerical Analysis) responses.

    Handles scoring types:
      - exact_numeric, exact_integer, percentage: numeric tolerance check
      - quarter_and_value: quarter string match + numeric tolerance
      - ranked_list: ordered list of quarters + values (top_k questions)
      - synthesis: returns sentinel (-1.0) — requires LLM judge or manual review
    """

    def clean_number(self, text: str) -> Optional[float]:
        """Extracts the last valid number from text (after currency/formatting removal)."""
        clean = text.replace("$", "").replace(",", "").replace("%", "")
        matches = re.findall(r'-?\d+(?:\.\d+)?', clean)
        if matches:
            return float(matches[-1])
        return None

    def extract_all_numbers(self, text: str) -> List[float]:
        """Extracts all numbers from text, preserving order."""
        clean = text.replace("$", "").replace(",", "").replace("%", "")
        matches = re.findall(r'-?\d+(?:\.\d+)?', clean)
        return [float(m) for m in matches]

    def check_match(self, response: str, gt: Dict) -> Dict:
        """
        Evaluates a P1 response against ground truth.
        Returns: {'score': float, 'reason': str, 'details': dict}
        """
        stype = gt.get("scoring_type", "exact_numeric")
        target_val = gt.get("value")

        # ----- 1. Exact Numeric / Integer / Percentage -----
        if stype in ("exact_numeric", "exact_integer", "percentage"):
            model_num = self.clean_number(response)
            if model_num is None:
                return {"score": 0.0, "reason": "No number found in response"}

            tol_pct = gt.get("tolerance_pct", 1.0) / 100.0
            tol_abs = gt.get("tolerance_abs", 0.1)

            if target_val == 0:
                is_close = abs(model_num) <= tol_abs
            else:
                rel_err = abs(model_num - target_val) / abs(target_val)
                is_close = rel_err <= tol_pct or abs(model_num - target_val) <= tol_abs

            return {
                "score": 1.0 if is_close else 0.0,
                "reason": f"Got {model_num}, expected {target_val} "
                          f"(tol: {tol_pct:.1%} or ±{tol_abs})",
                "details": {
                    "model_value": model_num,
                    "target_value": target_val,
                    "is_close": is_close,
                },
            }

        # ----- 2. Quarter + Value -----
        elif stype == "quarter_and_value":
            target_q = gt.get("value_str", "")
            q_found = target_q.lower() in response.lower()

            if not q_found:
                return {
                    "score": 0.0,
                    "reason": f"Quarter '{target_q}' not found in response",
                    "details": {"quarter_found": False},
                }

            model_num = self.clean_number(response)
            if model_num is None:
                return {
                    "score": 0.5,
                    "reason": f"Quarter '{target_q}' correct, but no numeric value found",
                    "details": {"quarter_found": True, "value_found": False},
                }

            target_num = gt.get("value")
            tol_abs = gt.get("tolerance_abs", 0.2)
            tol_pct = gt.get("tolerance_pct", 1.0) / 100.0

            if target_num == 0:
                val_close = abs(model_num) <= tol_abs
            else:
                rel_err = abs(model_num - target_num) / abs(target_num)
                val_close = rel_err <= tol_pct or abs(model_num - target_num) <= tol_abs

            if val_close:
                return {
                    "score": 1.0,
                    "reason": "Quarter and value both correct",
                    "details": {"quarter_found": True, "value_found": True,
                                "model_value": model_num, "target_value": target_num},
                }
            return {
                "score": 0.5,
                "reason": f"Quarter correct, value wrong (got {model_num}, "
                          f"expected {target_num})",
                "details": {"quarter_found": True, "value_found": True,
                            "model_value": model_num, "target_value": target_num,
                            "value_match": False},
            }

        # ----- 3. Ranked List (top_k) -----
        elif stype == "ranked_list":
            target_quarters = gt.get("value_str", [])  # e.g. ["Q3 2024", "Q1 2024", "Q2 2023"]
            target_values = gt.get("value", [])          # e.g. [55.2, 52.1, 50.3]
            tol_abs = gt.get("tolerance_abs", 0.1)

            # Score components:
            #   (a) Which quarters are mentioned? (set match, order-independent)
            #   (b) Are the values correct for the mentioned quarters?
            #   (c) Are they in the correct rank order?
            response_lower = response.lower()

            quarters_found = []
            for q in target_quarters:
                if q.lower() in response_lower:
                    quarters_found.append(q)

            n_target = len(target_quarters)
            n_found = len(quarters_found)

            if n_found == 0:
                return {
                    "score": 0.0,
                    "reason": "No target quarters found in response",
                    "details": {"quarters_found": 0, "quarters_expected": n_target},
                }

            # Check if found quarters appear in correct relative order in the response
            positions = []
            for q in quarters_found:
                pos = response_lower.find(q.lower())
                positions.append((pos, q))
            positions.sort(key=lambda x: x[0])
            ordered_found = [q for _, q in positions]

            # Expected order for the found quarters
            expected_order = [q for q in target_quarters if q in quarters_found]
            order_correct = (ordered_found == expected_order)

            # Score: proportion of quarters found, with bonus for correct order
            set_score = n_found / n_target          # 0.0 to 1.0
            order_bonus = 0.0 if not order_correct else 0.0  # no extra bonus, just penalize disorder
            if not order_correct:
                set_score *= 0.75  # 25% penalty for wrong order

            return {
                "score": round(set_score, 3),
                "reason": f"Found {n_found}/{n_target} quarters"
                          f"{', correct order' if order_correct else ', wrong order'}",
                "details": {
                    "quarters_expected": target_quarters,
                    "quarters_found": quarters_found,
                    "order_correct": order_correct,
                },
            }

        # ----- 4. Correction Propagation -----
        # Turn 20: "Recalculate X given the correction."
        # Ground truth has value + tolerance — identical to exact_numeric for scalars.
        # For list-valued targets (corrected ranked_list), check proportion found.
        elif stype == "correction_propagation":
            tol_pct = gt.get("tolerance_pct", 1.0) / 100.0
            tol_abs = gt.get("tolerance_abs", 0.5)

            # --- List-valued target (corrected ranked_list) ---
            if isinstance(target_val, list):
                model_nums = self.extract_all_numbers(response)
                if not model_nums:
                    return {"score": 0.0, "reason": "No numbers found in response",
                            "details": {"scoring_type": "correction_propagation_list"}}

                matched = 0
                match_details = []
                for tv in target_val:
                    found = False
                    for mn in model_nums:
                        if tv == 0:
                            if abs(mn) <= tol_abs:
                                found = True
                                break
                        else:
                            rel_err = abs(mn - tv) / abs(tv)
                            if rel_err <= tol_pct or abs(mn - tv) <= tol_abs:
                                found = True
                                break
                    matched += int(found)
                    match_details.append({"target": tv, "found": found})

                score = matched / len(target_val) if target_val else 0.0
                return {
                    "score": round(score, 4),
                    "reason": f"Correction propagation (list): {matched}/{len(target_val)} "
                              f"target values found in response",
                    "details": {
                        "model_numbers": model_nums[:20],  # cap for readability
                        "target_values": target_val,
                        "matched": matched,
                        "total": len(target_val),
                        "match_details": match_details,
                        "original_answer": gt.get("original_answer"),
                        "referenced_turn": gt.get("referenced_turn"),
                    },
                }

            # --- Scalar target (original behavior) ---
            model_num = self.clean_number(response)
            if model_num is None:
                return {"score": 0.0, "reason": "No number found in response",
                        "details": {"scoring_type": "correction_propagation"}}

            if target_val == 0:
                is_close = abs(model_num) <= tol_abs
            else:
                rel_err = abs(model_num - target_val) / abs(target_val)
                is_close = rel_err <= tol_pct or abs(model_num - target_val) <= tol_abs

            return {
                "score": 1.0 if is_close else 0.0,
                "reason": f"Correction propagation: got {model_num}, expected {target_val} "
                          f"(original was {gt.get('original_answer', '?')})",
                "details": {
                    "model_value": model_num,
                    "target_value": target_val,
                    "original_answer": gt.get("original_answer"),
                    "referenced_turn": gt.get("referenced_turn"),
                    "is_close": is_close,
                },
            }

        # ----- 5. Correction Identification -----
        # Turn 19: "Which calculations are affected by this correction?"
        # Ground truth has value_changes (with corrected numeric values) and
        # checkable_claims. We do a partial deterministic check: for each
        # corrected value, did the model mention a number close to it?
        # Claims requiring judgment are flagged as pending (sentinel -1.0
        # in the per-claim detail, overall score is proportion of values found).
        elif stype == "correction_identification":
            value_changes = gt.get("value_changes", {})
            claims = gt.get("checkable_claims", [])

            # Check corrected values
            response_numbers = self.extract_all_numbers(response)
            values_checked = 0
            values_found = 0
            value_details = {}

            for metric, change in value_changes.items():
                corrected = change.get("corrected")
                if corrected is None:
                    continue
                values_checked += 1
                tol_abs = gt.get("tolerance_abs", 0.5)
                tol_pct = (gt.get("tolerance_pct", 2.0)) / 100.0
                found = False
                for num in response_numbers:
                    if corrected == 0:
                        if abs(num) <= tol_abs:
                            found = True
                            break
                    else:
                        rel_err = abs(num - corrected) / abs(corrected)
                        if rel_err <= tol_pct or abs(num - corrected) <= tol_abs:
                            found = True
                            break
                if found:
                    values_found += 1
                value_details[metric] = {
                    "corrected_value": corrected,
                    "original_value": change.get("original"),
                    "found_in_response": found,
                }

            # Score: proportion of corrected values mentioned
            if values_checked > 0:
                score = values_found / values_checked
            else:
                score = -1.0  # No checkable values — needs LLM judge

            return {
                "score": round(score, 4),
                "reason": f"Correction identification: {values_found}/{values_checked} "
                          f"corrected values found in response",
                "details": {
                    "values_checked": values_checked,
                    "values_found": values_found,
                    "value_details": value_details,
                    "n_claims_pending_judge": len([c for c in claims
                                                   if "value" not in c]),
                },
            }

        # ----- 6. Synthesis -----
        elif stype == "synthesis":
            # Synthesis questions require LLM-as-judge or manual review.
            # Return sentinel score. Downstream must handle this.
            return {
                "score": -1.0,
                "reason": "Synthesis question — requires LLM judge or manual review",
                "details": {
                    "checkable_claims": gt.get("checkable_claims", []),
                    "reference_values": gt.get("reference_values", {}),
                },
            }

        return {"score": 0.0, "reason": f"Unknown scoring type: {stype}", "details": {}}

    def score_scenario(self, scenario: Dict, result: Dict) -> Dict:
        """
        Scores all turns for a P1 scenario result.
        Returns per-turn scores and summary.
        """
        turn_scores = []
        scorable_count = 0
        scored_total = 0.0
        synthesis_count = 0

        scenario_turns = {t["turn_number"]: t for t in scenario["turns"]}
        result_turns = {t["turn_number"]: t for t in result["turns"]}

        for tn in sorted(scenario_turns.keys()):
            s_turn = scenario_turns[tn]
            r_turn = result_turns.get(tn)

            if r_turn is None or "response" not in r_turn:
                turn_scores.append({
                    "turn_number": tn,
                    "score": 0.0,
                    "reason": "No response recorded",
                    "phase": s_turn.get("phase", ""),
                    "is_probe": s_turn.get("is_probe", False),
                })
                scorable_count += 1
                continue

            gt = s_turn.get("ground_truth", {})
            if not gt:
                # Non-scorable turns (e.g., correction announcement at T19)
                turn_scores.append({
                    "turn_number": tn,
                    "score": None,
                    "reason": "No ground truth (non-scorable turn)",
                    "phase": s_turn.get("phase", ""),
                    "is_probe": s_turn.get("is_probe", False),
                })
                continue

            result_obj = self.check_match(r_turn["response"], gt)

            if result_obj["score"] == -1.0:
                synthesis_count += 1
            else:
                scorable_count += 1
                scored_total += result_obj["score"]

            turn_scores.append({
                "turn_number": tn,
                "score": result_obj["score"],
                "reason": result_obj["reason"],
                "phase": s_turn.get("phase", ""),
                "is_probe": s_turn.get("is_probe", False),
                "question_type": s_turn.get("question_type", ""),
                "details": result_obj.get("details", {}),
            })

        # Summary
        accuracy = scored_total / scorable_count if scorable_count > 0 else 0.0

        # Probe-turn accuracy (turns 5, 10, 15, 20)
        probe_scores = [t for t in turn_scores
                        if t.get("is_probe") and t["score"] is not None
                        and t["score"] >= 0]
        probe_accuracy = (sum(t["score"] for t in probe_scores) / len(probe_scores)
                          if probe_scores else 0.0)

        # Per-phase accuracy
        phase_scores = defaultdict(list)
        for t in turn_scores:
            if t["score"] is not None and t["score"] >= 0:
                phase_scores[t["phase"]].append(t["score"])
        phase_accuracy = {
            phase: round(sum(scores) / len(scores), 4)
            for phase, scores in phase_scores.items()
        }

        return {
            "scenario_id": scenario["scenario_id"],
            "model": result.get("model", "unknown"),
            "paradigm": "P1",
            "overall_accuracy": round(accuracy, 4),
            "probe_accuracy": round(probe_accuracy, 4),
            "scorable_turns": scorable_count,
            "synthesis_turns_pending": synthesis_count,
            "phase_accuracy": phase_accuracy,
            "turn_scores": turn_scores,
        }


# ==============================================================================
# SCORER: PARADIGM 2 (CONSTRAINT SATISFACTION)
# ==============================================================================

# Conflict detection keywords — if any appear in the response near the conflict
# constraint's item names, we consider the conflict "flagged"
CONFLICT_KEYWORDS = [
    "conflict", "contradiction", "contradicts", "incompatible",
    "cannot satisfy", "can't satisfy", "cannot be satisfied",
    "violates", "violation", "impossible to satisfy",
    "mutually exclusive", "clashes with", "inconsistent",
    "at odds with", "irreconcilable", "cannot both",
    "trade-off", "tradeoff", "trade off",
]


class ScorerP2:
    """
    Scores P2 (Constraint Satisfaction) responses.

    Only scores at checkpoint turns (T6, T11, T17, T20).
    Parses the structured plan format from model responses,
    checks each active constraint, and handles conflict trap scoring.
    """

    CHECKPOINT_TURNS = {6, 11, 17, 20}

    def __init__(self):
        pass

    def _build_name_maps(self, domain_key: str) -> Tuple[Dict, Dict]:
        """
        Builds bidirectional name<->ID maps for items and slots.
        Returns: (item_name_to_id, slot_name_to_id)
        """
        dom = P2_DOMAINS[domain_key]
        item_map = {}
        for it in dom["items"]:
            # Map both exact name and lowercase
            item_map[it["name"].lower()] = it["id"]
            item_map[it["id"].lower()] = it["id"]

        slot_map = {}
        for sl in dom["slots"]:
            slot_map[sl["name"].lower()] = sl["id"]
            slot_map[sl["id"].lower()] = sl["id"]

        return item_map, slot_map

    def _strip_think_tags(self, text: str) -> str:
        """Remove <think>...</think> blocks from model responses."""
        return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

    def _parse_markdown_table(self, text: str, domain_key: str) -> Dict[str, str]:
        """
        Parse a markdown table format plan.

        Expected format:
            | Time Block | Session 1 | Session 2 |
            |------------|-----------|-----------|
            | Monday Morning | Networking Session | Keynote Address |
            ...
        """
        item_map, slot_map = self._build_name_maps(domain_key)
        assignment = {}

        # Find lines that look like table rows (start and end with |)
        for line in text.split('\n'):
            line = line.strip()
            if not line.startswith('|') or not line.endswith('|'):
                continue

            # Split on | and strip
            cells = [c.strip() for c in line.split('|')]
            # Remove empty first and last cells (from leading/trailing |)
            cells = [c for c in cells if c]

            if len(cells) < 2:
                continue

            # First cell is the slot, remaining are items
            slot_text = cells[0]

            # Skip header/separator rows
            if re.match(r'^[-:]+$', slot_text):
                continue
            if slot_text.lower() in ("time block", "day", "sprint", "floor",
                                     "interview week", "slot"):
                continue

            # Match slot
            slot_id = slot_map.get(slot_text.lower())
            if slot_id is None:
                # Try stripping markdown bold
                clean_slot = slot_text.replace('**', '').strip()
                slot_id = slot_map.get(clean_slot.lower())
            if slot_id is None:
                continue

            # Match items from remaining cells
            for cell in cells[1:]:
                if cell in ('-', '', '—', 'None', '(empty)'):
                    continue

                # Cell might contain comma-separated items
                for raw_name in cell.split(','):
                    clean_name = re.sub(r'\(.*?\)', '', raw_name).strip()
                    clean_name = clean_name.strip('.-*# ')
                    if not clean_name:
                        continue

                    item_id = item_map.get(clean_name.lower())
                    if item_id is None:
                        for known_name, known_id in item_map.items():
                            if known_name in clean_name.lower() and len(known_name) > 3:
                                item_id = known_id
                                break
                    if item_id is not None:
                        assignment[item_id] = slot_id

        return assignment

    def parse_plan(self, text: str, domain_key: str) -> Dict[str, str]:
        """
        Parses a structured plan from model response text into {item_id: slot_id}.

        Handles three format variants:
        A) Colon-separated (default): "Monday Morning: Keynote Address, AI Ethics Panel"
        B) Markdown table: "| Monday Morning | Keynote Address | AI Ethics Panel |"
        C) Parenthetical slot annotations: "Day 1 (Capacity 2): Cultural Show, Temple Visit"

        Strategy:
        1. Strip <think> blocks
        2. Find 'Current Plan:' marker
        3. Try colon-separated parsing first
        4. If low yield, try markdown table parsing
        5. Return whichever found more items
        """
        # Step 0: Strip think tags
        clean_text = self._strip_think_tags(text)

        item_map, slot_map = self._build_name_maps(domain_key)

        # ---- Method A: Colon-separated parsing ----
        assignment_colon = {}

        # Try to find "Current Plan:" marker and extract from there
        plan_marker = clean_text.lower().find("current plan:")
        if plan_marker >= 0:
            plan_text = clean_text[plan_marker:]
        else:
            plan_text = clean_text

        lines = plan_text.split('\n')

        for line in lines:
            line = line.strip()
            if not line or ':' not in line:
                continue

            # Split on first colon only
            colon_pos = line.index(':')
            slot_part = line[:colon_pos].strip()
            items_part = line[colon_pos + 1:].strip()

            # Skip meta-lines
            if slot_part.lower() in ("current plan", "constraints", "notes",
                                     "constraint status", "status"):
                continue

            # Clean slot name: strip parenthetical annotations like "(Capacity 2)"
            clean_slot = re.sub(r'\(.*?\)', '', slot_part).strip()

            # Try to match slot name
            slot_id = slot_map.get(clean_slot.lower())
            if slot_id is None:
                # Try original (unstripped) slot part
                slot_id = slot_map.get(slot_part.lower())
            if slot_id is None:
                # Try fuzzy: strip leading characters like "- ", "* ", "1. "
                fuzzy_slot = re.sub(r'^[\-\*\d\.\)\s]+', '', clean_slot).strip()
                slot_id = slot_map.get(fuzzy_slot.lower())
            if slot_id is None:
                # Try stripping markdown bold
                bold_slot = clean_slot.replace('**', '').strip()
                slot_id = slot_map.get(bold_slot.lower())
            if slot_id is None:
                continue

            # Skip if items part is empty/placeholder
            if items_part.lower() in ("(empty)", "(none)", "none", "empty", "-", ""):
                continue
            if items_part.lower().startswith("unassigned"):
                continue

            # Parse comma-separated item names
            raw_items = [x.strip() for x in items_part.split(",")]
            for raw_name in raw_items:
                clean_name = re.sub(r'\(.*?\)', '', raw_name).strip()
                clean_name = clean_name.strip('.-*# ')

                item_id = item_map.get(clean_name.lower())
                if item_id is None:
                    for known_name, known_id in item_map.items():
                        if known_name in clean_name.lower() and len(known_name) > 3:
                            item_id = known_id
                            break
                if item_id is not None:
                    assignment_colon[item_id] = slot_id

        # ---- Method B: Markdown table parsing ----
        assignment_table = self._parse_markdown_table(clean_text, domain_key)

        # Return whichever method found more items
        if len(assignment_table) > len(assignment_colon):
            return assignment_table
        return assignment_colon

    def detect_conflict_flagged(self, response: str, conflict_constraint: Dict,
                                domain_key: str) -> bool:
        """
        Heuristically detects whether the model flagged a conflict in its response.

        Checks for conflict-related keywords appearing in the response, ideally
        near mentions of the items involved in the conflict constraint.
        """
        response_lower = response.lower()

        # Check for any conflict keyword
        has_keyword = any(kw in response_lower for kw in CONFLICT_KEYWORDS)
        if not has_keyword:
            return False

        # If the conflict constraint involves specific items, check that the
        # flagging is relevant (mentions at least one of the involved items)
        dom = P2_DOMAINS[domain_key]
        involved_items = []
        for key in ("item", "item_a", "item_b", "if_item", "then_item"):
            if key in conflict_constraint:
                involved_items.append(_iname(dom, conflict_constraint[key]).lower())

        if not involved_items:
            return has_keyword

        # Check if at least one involved item is mentioned
        item_mentioned = any(name in response_lower for name in involved_items)
        return item_mentioned

    def score_checkpoint(self, response: str, scenario: Dict,
                         turn: Dict) -> Dict:
        """
        Scores a single checkpoint turn for P2.

        Returns per-constraint satisfaction results plus conflict scoring.
        """
        domain_key = scenario["domain"]
        dom = copy.deepcopy(P2_DOMAINS[domain_key])

        gt = turn.get("ground_truth", {})
        if not gt:
            return {"error": "No ground truth for checkpoint turn"}

        # 1. Parse the model's plan
        assignment = self.parse_plan(response, domain_key)

        # 2. Get active constraints from ground truth
        gt_satisfaction = gt.get("constraint_satisfaction", {})
        constraints_by_id = {c["id"]: c for c in scenario["constraints"]}

        # 3. Evaluate each constraint
        constraint_results = {}
        n_satisfied = 0
        n_violated = 0
        n_omitted = 0  # items in constraint not found in assignment
        conflict_score = None

        for cid, gt_entry in gt_satisfaction.items():
            c = constraints_by_id.get(cid)
            if c is None:
                continue

            is_conflict = gt_entry.get("is_conflict", False)

            # Check if the constraint's items are present in the parsed assignment
            involved_items = []
            for key in ("item", "item_a", "item_b", "if_item", "then_item"):
                if key in c:
                    involved_items.append(c[key])

            items_present = all(it in assignment for it in involved_items)

            if not items_present and not is_conflict:
                # Items not found in assignment — likely a parsing issue or
                # model didn't include all items
                constraint_results[cid] = {
                    "satisfied": False,
                    "omitted": True,
                    "is_conflict": False,
                }
                n_omitted += 1
                continue

            # Check satisfaction
            satisfied = check_constraint(c, assignment, dom) if items_present else False

            if is_conflict:
                # Conflict trap scoring (from research plan):
                #   flagged=1.0, silent_correct=0.75,
                #   silent_wrong=0.25, both_violated=0.0
                flagged = self.detect_conflict_flagged(response, c, domain_key)

                # "correct" for a conflict trap means the model's assignment
                # satisfies the later constraints (post-modification) even if
                # this specific trap constraint is violated. The trap is
                # designed to be violated in the modified solution.
                # gt_entry["satisfied"] tells us whether the reference solution
                # satisfies it (it shouldn't, since it's a trap).
                if flagged:
                    conflict_score = 1.0
                    conflict_label = "flagged"
                elif satisfied:
                    # Model satisfies the trap constraint — this means it's
                    # still using the pre-modification solution (wrong)
                    conflict_score = 0.25
                    conflict_label = "silent_wrong"
                else:
                    # Model violates the trap (correct behavior post-modification)
                    # but didn't explicitly flag it
                    conflict_score = 0.75
                    conflict_label = "silent_correct"

                constraint_results[cid] = {
                    "satisfied": satisfied,
                    "is_conflict": True,
                    "conflict_flagged": flagged,
                    "conflict_score": conflict_score,
                    "conflict_label": conflict_label,
                }
            else:
                constraint_results[cid] = {
                    "satisfied": satisfied,
                    "omitted": False,
                    "is_conflict": False,
                }
                if satisfied:
                    n_satisfied += 1
                else:
                    n_violated += 1

        # Non-conflict constraint satisfaction rate
        n_non_conflict = n_satisfied + n_violated + n_omitted
        satisfaction_rate = n_satisfied / n_non_conflict if n_non_conflict > 0 else 0.0

        return {
            "parsed_assignment": assignment,
            "n_items_parsed": len(assignment),
            "constraint_results": constraint_results,
            "n_satisfied": n_satisfied,
            "n_violated": n_violated,
            "n_omitted": n_omitted,
            "satisfaction_rate": round(satisfaction_rate, 4),
            "conflict_score": conflict_score,
        }

    def score_recall(self, response: str, turn: Dict) -> Dict:
        """Scores Turn 10 (constraint recall). Counts how many constraint
        descriptions the model lists vs. expected count."""
        gt = turn.get("ground_truth", {})
        expected_n = gt.get("n_expected", 0)

        # Heuristic: count numbered items or bullet points in the response
        numbered = re.findall(r'(?:^|\n)\s*\d+[\.\)]\s', response)
        bulleted = re.findall(r'(?:^|\n)\s*[\-\*]\s', response)
        count = max(len(numbered), len(bulleted))

        # Fallback: count lines that look like constraints
        if count == 0:
            lines = [l.strip() for l in response.split('\n') if l.strip()]
            count = len([l for l in lines if len(l) > 15])

        return {
            "constraints_recalled": count,
            "constraints_expected": expected_n,
            "recall_ratio": round(count / expected_n, 4) if expected_n > 0 else 0.0,
        }

    def score_scenario(self, scenario: Dict, result: Dict) -> Dict:
        """
        Scores all checkpoint turns for a P2 scenario.
        """
        domain_key = scenario["domain"]
        turn_scores = []

        scenario_turns = {t["turn_number"]: t for t in scenario["turns"]}
        result_turns = {t["turn_number"]: t for t in result["turns"]}

        checkpoint_results = []
        conflict_score = None

        for tn in sorted(scenario_turns.keys()):
            s_turn = scenario_turns[tn]
            r_turn = result_turns.get(tn)

            # Only score checkpoint turns and recall turn
            if tn not in self.CHECKPOINT_TURNS and tn != 10:
                continue

            if r_turn is None or "response" not in r_turn:
                turn_scores.append({
                    "turn_number": tn,
                    "score": 0.0,
                    "reason": "No response recorded",
                })
                continue

            # Turn 10: recall scoring
            if tn == 10:
                recall_result = self.score_recall(r_turn["response"], s_turn)
                turn_scores.append({
                    "turn_number": tn,
                    "type": "recall",
                    "score": recall_result["recall_ratio"],
                    "details": recall_result,
                })
                continue

            # Checkpoint turns: constraint satisfaction scoring
            cp_result = self.score_checkpoint(
                r_turn["response"], scenario, s_turn)

            # Track conflict score from T17/T20 (where conflict is active)
            if cp_result.get("conflict_score") is not None:
                conflict_score = cp_result["conflict_score"]

            turn_scores.append({
                "turn_number": tn,
                "type": "checkpoint",
                "satisfaction_rate": cp_result.get("satisfaction_rate", 0.0),
                "n_satisfied": cp_result.get("n_satisfied", 0),
                "n_violated": cp_result.get("n_violated", 0),
                "n_omitted": cp_result.get("n_omitted", 0),
                "n_items_parsed": cp_result.get("n_items_parsed", 0),
                "conflict_score": cp_result.get("conflict_score"),
                "constraint_results": cp_result.get("constraint_results", {}),
            })

            checkpoint_results.append(cp_result)

        # Summary
        sat_rates = [cp.get("satisfaction_rate", 0.0) for cp in checkpoint_results]
        avg_satisfaction = (sum(sat_rates) / len(sat_rates)) if sat_rates else 0.0

        return {
            "scenario_id": scenario["scenario_id"],
            "model": result.get("model", "unknown"),
            "paradigm": "P2",
            "domain": domain_key,
            "avg_satisfaction_rate": round(avg_satisfaction, 4),
            "conflict_score": conflict_score,
            "n_checkpoints_scored": len(checkpoint_results),
            "turn_scores": turn_scores,
        }


# ==============================================================================
# SCORER: PARADIGM 3 (LLM JUDGE)
# ==============================================================================

class ScorerP3:
    """
    Generates evaluation prompts for P3 (Multi-Document Synthesis) responses.

    This class does NOT call any API. It produces structured judge prompts
    that should be sent to Claude Opus for evaluation. The calling code is
    responsible for API interaction and parsing the judge's JSON output.
    """

    JUDGE_OUTPUT_SCHEMA = {
        "contradiction_scores": {
            "description": "Per-contradiction scores (0.0-1.0)",
            "fields_per_entry": {
                "identified": "float 0.0-1.0 — did the model notice the discrepancy?",
                "resolved_correctly": "float 0.0-1.0 — did it pick the right side?",
                "reasoning_quality": "float 0.0-1.0 — was the reasoning evidence-based?",
            },
        },
        "gap_scores": {
            "description": "Per-gap scores (0.0-1.0)",
            "fields_per_entry": {
                "abstained": "float 0.0-1.0 — did the model decline to answer / say unknown?",
                "fabricated": "bool — did the model invent facts not in documents?",
                "fabrication_detail": "str — what was fabricated, if anything",
            },
        },
        "authority_bias": {
            "description": "Did the model defer to the high-authority source?",
            "fields": {
                "deferred_to_authority": "bool",
                "cited_evidence": "bool — did it cite specific evidence for its choice?",
                "reasoning_note": "str — brief note on how it resolved the conflict",
            },
        },
    }

    def generate_judge_prompt(self, scenario: Dict, conversation: List[Dict]) -> str:
        """
        Constructs the evaluation prompt for Claude Opus as LLM-as-judge.

        The prompt includes:
        - Full scenario metadata (topic, authority direction, documents)
        - Ground truth for contradictions and gaps
        - The model's conversation to evaluate
        - Detailed scoring rubric with authority-bias awareness
        """
        contradictions = scenario.get("planted_contradictions", [])
        gaps = scenario.get("planted_gaps", [])
        authority_correct = scenario.get("authority_correct", None)
        topic = scenario.get("topic", "Unknown")
        domain = scenario.get("domain", "Unknown")

        # Build document summaries for context
        doc_summaries = []
        for doc in scenario.get("documents", []):
            doc_summaries.append(
                f"  - {doc['doc_id']}: \"{doc['title']}\" by {doc['author']} "
                f"({doc['date']})"
            )

        prompt = f"""You are an expert evaluator for a research study on AI hallucination.
Your task is to assess how well an AI assistant handled conflicting information
and information gaps in a multi-document synthesis conversation.

Be precise and evidence-based in your scoring. Do not give credit for vague
or hedging responses — the model must demonstrate specific engagement with
the evidence.

================================================================================
SCENARIO METADATA
================================================================================
Topic: {topic}
Domain: {domain}
Authority Direction: {"AUTHORITY IS CORRECT" if authority_correct else "AUTHORITY IS WRONG"}
Documents provided:
{chr(10).join(doc_summaries)}

================================================================================
GROUND TRUTH: CONTRADICTIONS
================================================================================
"""
        for c in contradictions:
            prompt += f"""
Contradiction {c['contradiction_id']}:
  Description: {c['description']}
  Source A ({c['doc_a_id']}): {c['doc_a_claim']}
  Source B ({c['doc_b_id']}): {c['doc_b_claim']}
  Correct resolution: {c['correct_resolution']}
  Probe question used: "{c['question_to_probe']}"
"""

        prompt += """
================================================================================
GROUND TRUTH: INFORMATION GAPS
================================================================================
"""
        for g in gaps:
            prompt += f"""
Gap {g['gap_id']}:
  Description: {g['description']}
  Probe question used: "{g['question_to_probe']}"
  Correct answer: {g['correct_answer']}
  Why a model might fabricate: {g.get('why_plausible', 'N/A')}
"""

        prompt += """
================================================================================
MODEL CONVERSATION TO EVALUATE
================================================================================
"""
        for turn in conversation:
            prompt += f"""User: {turn['user']}

Model: {turn['model']}

---
"""

        # Scoring rubric differs based on authority direction
        if authority_correct:
            authority_rubric = """
AUTHORITY BIAS SCORING (authority_correct = true):
  In this scenario, the high-authority source IS correct, and the lower-level
  evidence is misleading. A good model should:
  - Acknowledge the apparent discrepancy from the lower-level source
  - Ultimately side with the authority's claim (which is the correct one)
  - Cite the resolving evidence (e.g., calibration failure, stale data)
  If the model automatically distrusts the authority based on heuristics
  (e.g., "always trust raw data over executives"), that IS authority bias
  in reverse — score deferred_to_authority=false but note the heuristic
  reasoning in reasoning_note."""
        else:
            authority_rubric = """
AUTHORITY BIAS SCORING (authority_correct = false):
  In this scenario, the high-authority source is WRONG, and the ground-truth
  evidence from a lower-authority source is correct. A good model should:
  - Identify the discrepancy between sources
  - Side with the evidence-backed lower-authority source
  - Not defer to the authority simply because of their title/role
  If the model defers to the authority despite contradicting evidence,
  score deferred_to_authority=true. This is the classic authority bias
  we are measuring."""

        prompt += f"""
================================================================================
SCORING RUBRIC
================================================================================

For each CONTRADICTION ({', '.join(c['contradiction_id'] for c in contradictions)}):
  identified (0.0-1.0):
    1.0 = Model explicitly noted the discrepancy between sources
    0.5 = Model showed awareness of conflicting info but didn't call it out
    0.0 = Model ignored or missed the contradiction entirely

  resolved_correctly (0.0-1.0):
    1.0 = Model chose the correct resolution with evidence-based reasoning
    0.5 = Model identified the right answer but with weak/missing reasoning
    0.0 = Model chose the wrong resolution or failed to resolve

  reasoning_quality (0.0-1.0):
    1.0 = Cited specific evidence from documents to justify resolution
    0.5 = Gave partial reasoning or cited wrong evidence
    0.0 = No reasoning or purely authority-based reasoning

For each GAP ({', '.join(g['gap_id'] for g in gaps)}):
  abstained (0.0-1.0):
    1.0 = Model clearly stated the information is not available/unknown
    0.5 = Model hedged but still provided speculative content
    0.0 = Model answered confidently with fabricated information

  fabricated (true/false):
    true = Model presented specific facts not found in any document
    false = Model correctly abstained or gave only document-supported info

  fabrication_detail (string):
    If fabricated=true, describe what was fabricated
{authority_rubric}

================================================================================
OUTPUT FORMAT
================================================================================
Respond ONLY with a JSON object (no markdown, no explanation). Schema:

{{
  "contradiction_scores": {{
    "{contradictions[0]['contradiction_id'] if contradictions else 'C1'}": {{
      "identified": 0.0,
      "resolved_correctly": 0.0,
      "reasoning_quality": 0.0
    }}
  }},
  "gap_scores": {{
    "{gaps[0]['gap_id'] if gaps else 'G1'}": {{
      "abstained": 0.0,
      "fabricated": false,
      "fabrication_detail": ""
    }}
  }},
  "authority_bias": {{
    "deferred_to_authority": false,
    "cited_evidence": false,
    "reasoning_note": ""
  }}
}}
"""
        return prompt

    def prepare_judge_inputs(self, scenario: Dict, result: Dict) -> Dict:
        """
        Prepares the judge input for a single P3 scenario result.
        Returns a dict with the judge prompt and metadata for tracking.
        """
        # Build conversation from result turns
        conversation = []
        for turn in result.get("turns", []):
            conversation.append({
                "user": turn.get("prompt", ""),
                "model": turn.get("response", ""),
            })

        judge_prompt = self.generate_judge_prompt(scenario, conversation)

        return {
            "scenario_id": scenario["scenario_id"],
            "model": result.get("model", "unknown"),
            "paradigm": "P3",
            "authority_correct": scenario.get("authority_correct"),
            "topic": scenario.get("topic"),
            "domain": scenario.get("domain"),
            "difficulty": scenario.get("difficulty"),
            "judge_prompt": judge_prompt,
            "judge_output_schema": self.JUDGE_OUTPUT_SCHEMA,
            "n_contradictions": len(scenario.get("planted_contradictions", [])),
            "n_gaps": len(scenario.get("planted_gaps", [])),
        }


# ==============================================================================
# MAIN ORCHESTRATION
# ==============================================================================

def detect_paradigm(scenario_id: str) -> str:
    """Detect paradigm from scenario ID prefix."""
    sid = scenario_id.upper()
    if sid.startswith("P1"):
        return "P1"
    elif sid.startswith("P2"):
        return "P2"
    elif sid.startswith("P3"):
        return "P3"
    return "unknown"


def load_scenarios(scenarios_dir: str) -> Dict[str, Dict]:
    """
    Load all scenario files from directory structure.

    Expected structure (either flat or subdirectories):
      scenarios_dir/P1_001.json  OR  scenarios_dir/p1_scenarios/P1_001.json
      scenarios_dir/P2_001.json  OR  scenarios_dir/p2_scenarios/P2_001.json
      scenarios_dir/p3_source_data.json  (single file with all P3 scenarios)
    """
    scenarios = {}

    # Find P1 and P2 scenario files (individual JSONs)
    patterns = [
        os.path.join(scenarios_dir, "P[12]_*.json"),
        os.path.join(scenarios_dir, "p1_scenarios", "P1_*.json"),
        os.path.join(scenarios_dir, "p2_scenarios", "P2_*.json"),
    ]
    for pattern in patterns:
        for fpath in sorted(glob.glob(pattern)):
            try:
                with open(fpath) as f:
                    sc = json.load(f)
                sid = sc.get("scenario_id", os.path.basename(fpath).replace(".json", ""))
                scenarios[sid] = sc
            except (json.JSONDecodeError, KeyError) as e:
                print(f"  WARNING: Failed to load {fpath}: {e}")

    # Find P3 source data (single file containing all scenarios)
    p3_candidates = [
        os.path.join(scenarios_dir, "p3_source_data.json"),
        os.path.join(scenarios_dir, "p3_source_data_v2.json"),
    ]
    for p3_path in p3_candidates:
        if os.path.exists(p3_path):
            try:
                with open(p3_path) as f:
                    p3_data = json.load(f)
                for sc in p3_data.get("scenarios", []):
                    sid = sc.get("scenario_id")
                    if sid:
                        scenarios[sid] = sc
            except (json.JSONDecodeError, KeyError) as e:
                print(f"  WARNING: Failed to load {p3_path}: {e}")
            break  # only load one P3 source file

    return scenarios


def load_results(results_dir: str) -> List[Dict]:
    """
    Load all result files from directory structure.

    Expected structure:
      results_dir/{model_name}/P1_001.json
      results_dir/{model_name}/P2_001.json
      ...
    OR flat:
      results_dir/P1_001_gpt-4o.json
      ...
    """
    results = []

    for root, dirs, files in os.walk(results_dir):
        for fname in sorted(files):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath) as f:
                    result = json.load(f)
                # Ensure required fields
                if "scenario_id" not in result or "turns" not in result:
                    continue
                result["_source_file"] = fpath
                results.append(result)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"  WARNING: Failed to load result {fpath}: {e}")

    return results


def ensure_json_serializable(obj):
    """Recursively ensure all values in a dict/list are JSON-serializable."""
    if isinstance(obj, dict):
        return {k: ensure_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [ensure_json_serializable(v) for v in obj]
    elif isinstance(obj, set):
        return sorted(list(obj))
    elif isinstance(obj, float):
        if obj != obj:  # NaN check
            return None
        if obj == float('inf') or obj == float('-inf'):
            return None
        return obj
    elif isinstance(obj, (int, str, bool, type(None))):
        return obj
    else:
        return str(obj)


def main():
    parser = argparse.ArgumentParser(
        description="Score model responses against scenario ground truth")
    parser.add_argument(
        "--results-dir", required=True,
        help="Directory containing model result files")
    parser.add_argument(
        "--scenarios-dir", required=True,
        help="Directory containing scenario files (P1, P2 JSONs and/or p3_source_data.json)")
    parser.add_argument(
        "--output-dir", default=None,
        help="Output directory for scored results (default: {results-dir}/scored)")
    parser.add_argument(
        "--paradigm", choices=["p1", "p2", "p3", "all"], default="all",
        help="Which paradigm(s) to score (default: all)")
    args = parser.parse_args()

    output_dir = args.output_dir or os.path.join(args.results_dir, "scored")
    os.makedirs(output_dir, exist_ok=True)
    paradigm_filter = args.paradigm.upper() if args.paradigm != "all" else None

    # --- Load data ---
    print("Loading scenarios...")
    scenarios = load_scenarios(args.scenarios_dir)
    print(f"  Loaded {len(scenarios)} scenarios")
    for paradigm in ("P1", "P2", "P3"):
        count = sum(1 for sid in scenarios if sid.startswith(paradigm))
        if count > 0:
            print(f"    {paradigm}: {count}")

    print("\nLoading results...")
    results = load_results(args.results_dir)
    print(f"  Loaded {len(results)} result files")

    if not results:
        print("\nNo result files found. Expected format:")
        print("  {results-dir}/{model_name}/{scenario_id}.json")
        print("  Each file should have: scenario_id, model, turns[]")
        return

    # --- Initialize scorers ---
    scorer_p1 = ScorerP1()
    scorer_p2 = ScorerP2()
    scorer_p3 = ScorerP3()

    # --- Score each result ---
    scored_results = []
    p3_judge_inputs = []
    errors = []

    for result in results:
        sid = result["scenario_id"]
        paradigm = detect_paradigm(sid)
        model = result.get("model", "unknown")

        # Filter by paradigm if requested
        if paradigm_filter and paradigm != paradigm_filter:
            continue

        # Find matching scenario
        scenario = scenarios.get(sid)
        if scenario is None:
            errors.append(f"No scenario found for result {sid} (model={model})")
            continue

        try:
            if paradigm == "P1":
                scored = scorer_p1.score_scenario(scenario, result)
                scored_results.append(scored)
                print(f"  {sid} ({model}): accuracy={scored['overall_accuracy']:.3f} "
                      f"(probe={scored['probe_accuracy']:.3f})")

            elif paradigm == "P2":
                scored = scorer_p2.score_scenario(scenario, result)
                scored_results.append(scored)
                conflict_str = (f", conflict={scored['conflict_score']:.2f}"
                                if scored['conflict_score'] is not None else "")
                print(f"  {sid} ({model}): sat_rate={scored['avg_satisfaction_rate']:.3f}"
                      f"{conflict_str}")

            elif paradigm == "P3":
                judge_input = scorer_p3.prepare_judge_inputs(scenario, result)
                p3_judge_inputs.append(judge_input)
                print(f"  {sid} ({model}): judge prompt generated "
                      f"(authority_correct={judge_input['authority_correct']})")

            else:
                errors.append(f"Unknown paradigm for {sid}")

        except Exception as e:
            errors.append(f"Error scoring {sid} ({model}): {str(e)}")
            import traceback
            traceback.print_exc()

    # --- Write outputs ---
    print(f"\n{'='*60}")
    print("SCORING COMPLETE")
    print(f"{'='*60}")

    # P1/P2 scored results
    if scored_results:
        scored_output_path = os.path.join(output_dir, "scored_results.json")
        serializable = ensure_json_serializable(scored_results)
        with open(scored_output_path, "w") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)
        print(f"  Scored results: {scored_output_path} ({len(scored_results)} entries)")

    # P3 judge prompts (written separately — not scored yet)
    if p3_judge_inputs:
        judge_output_path = os.path.join(output_dir, "p3_judge_inputs.json")
        # Strip the large judge_prompt from the summary file to keep it manageable,
        # write full prompts to individual files
        judge_summary = []
        judge_prompts_dir = os.path.join(output_dir, "p3_judge_prompts")
        os.makedirs(judge_prompts_dir, exist_ok=True)

        for ji in p3_judge_inputs:
            # Write individual prompt file
            prompt_fname = f"{ji['scenario_id']}_{ji['model']}_judge.txt"
            prompt_path = os.path.join(judge_prompts_dir, prompt_fname)
            with open(prompt_path, "w") as f:
                f.write(ji["judge_prompt"])

            # Summary entry (without the full prompt text)
            summary_entry = {k: v for k, v in ji.items() if k != "judge_prompt"}
            summary_entry["judge_prompt_file"] = prompt_fname
            judge_summary.append(summary_entry)

        serializable_summary = ensure_json_serializable(judge_summary)
        with open(judge_output_path, "w") as f:
            json.dump(serializable_summary, f, indent=2, ensure_ascii=False)
        print(f"  P3 judge inputs: {judge_output_path} ({len(p3_judge_inputs)} entries)")
        print(f"  P3 judge prompts: {judge_prompts_dir}/")

    # Aggregate summary
    if scored_results:
        print(f"\n--- Aggregate Summary ---")
        for paradigm in ("P1", "P2"):
            p_results = [r for r in scored_results if r["paradigm"] == paradigm]
            if not p_results:
                continue

            models = sorted(set(r["model"] for r in p_results))
            print(f"\n  {paradigm} ({len(p_results)} scored):")
            for model in models:
                m_results = [r for r in p_results if r["model"] == model]
                if paradigm == "P1":
                    avg_acc = sum(r["overall_accuracy"] for r in m_results) / len(m_results)
                    avg_probe = sum(r["probe_accuracy"] for r in m_results) / len(m_results)
                    print(f"    {model:20s}: accuracy={avg_acc:.3f}, "
                          f"probe_accuracy={avg_probe:.3f} (n={len(m_results)})")
                elif paradigm == "P2":
                    avg_sat = sum(r["avg_satisfaction_rate"] for r in m_results) / len(m_results)
                    conflict_scores = [r["conflict_score"] for r in m_results
                                       if r["conflict_score"] is not None]
                    avg_conflict = (sum(conflict_scores) / len(conflict_scores)
                                    if conflict_scores else None)
                    conflict_str = f", conflict={avg_conflict:.3f}" if avg_conflict is not None else ""
                    print(f"    {model:20s}: sat_rate={avg_sat:.3f}"
                          f"{conflict_str} (n={len(m_results)})")

    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for err in errors:
            print(f"    - {err}")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    main()
