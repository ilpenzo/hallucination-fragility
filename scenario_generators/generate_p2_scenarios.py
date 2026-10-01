#!/usr/bin/env python3
"""
generate_p2_scenarios.py — Phase 0b: P2 Scenario Generator
Context-Dependent Hallucination in Frontier LLMs

Produces 40 self-contained scenarios for Paradigm 2 (Constraint Satisfaction
Under Load). Each scenario has 20 turns, checkpoints at T6/T11/T17/T20,
a constraint modification at T12, and one deliberate conflict at T15.

Architecture:
  - Abstract constraint engine (slot assignment) with 5 domain skins
  - Reverse generation: solution first, then constraints derived from it
  - Two solutions per scenario: base (checkpoints 1-2) and modified (3-4)
  - Conflict trap: constraint true in base but false in modified

Domains (8 items x 5 ordered slots each, 8 scenarios per domain):
  1. Conference: 8 sessions -> 5 time blocks
  2. Travel:     8 activities -> 5 days
  3. Product:    8 features -> 5 sprints
  4. Hiring:     8 candidates -> 5 interview weeks
  5. Relocation: 8 teams -> 5 floors

Output:
  p2_scenarios/P2_001.json ... P2_040.json
  p2_scenarios/p2_manifest.json
  p2_scenarios/p2_validation_report.txt

Usage:
  python3 generate_p2_scenarios.py
  python3 generate_p2_scenarios.py --output-dir ./my_scenarios --seed 12345
"""

import json, os, copy, random, argparse
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional, Set

# ================================================================
# CONSTANTS
# ================================================================

MASTER_SEED = 20260216
VERSION = "1.0.0"
N_ITEMS = 8
N_SLOTS = 5
N_SCENARIOS = 40
SCENARIOS_PER_DOMAIN = 8
CHECKPOINT_TURNS = {6, 11, 17, 20}
MODIFICATION_TURN = 12
CONFLICT_TURN = 15

SYSTEM_PROMPT = (
    "You are a planning assistant. Help the user build and maintain a plan "
    "by incorporating all constraints they introduce. Track every constraint "
    "carefully. When asked to produce a plan, use this exact format:\n\n"
    "Current Plan:\n"
    "[Slot Name]: [Item 1], [Item 2]\n"
    "[Slot Name]: [Item 3]\n"
    "...\n"
    "Unassigned: [Item 7], [Item 8] (if any)\n\n"
    "List ALL slots even if empty. If a new constraint conflicts with an "
    "earlier one, flag the conflict explicitly."
)

# ================================================================
# DOMAIN TEMPLATES
# ================================================================

DOMAINS = {
    "conference": {
        "display_name": "Conference Schedule",
        "item_label": "session", "items_label": "sessions",
        "slot_label": "time block", "slots_label": "time blocks",
        "verb_assign": "schedule", "verb_move": "reschedule",
        "in_verb": "scheduled in", "before_verb": "scheduled before",
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
        "agg_prop": "attendees", "agg_label": "total attendees", "agg_unit": "people",
        "slots": [
            {"id": "mon_am", "name": "Monday Morning", "order": 1, "capacity": 2},
            {"id": "mon_pm", "name": "Monday Afternoon", "order": 2, "capacity": 2},
            {"id": "tue_am", "name": "Tuesday Morning", "order": 3, "capacity": 2},
            {"id": "tue_pm", "name": "Tuesday Afternoon", "order": 4, "capacity": 1},
            {"id": "wed_am", "name": "Wednesday Morning", "order": 5, "capacity": 2},
        ],
        "intro": "We're organizing a 3-day tech conference with {ni} sessions across {ns} time blocks.",
    },
    "travel": {
        "display_name": "Travel Itinerary",
        "item_label": "activity", "items_label": "activities",
        "slot_label": "day", "slots_label": "days",
        "verb_assign": "plan", "verb_move": "move",
        "in_verb": "planned for", "before_verb": "planned before",
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
        "agg_prop": "cost_usd", "agg_label": "total cost", "agg_unit": "USD",
        "slots": [
            {"id": "day1", "name": "Day 1", "order": 1, "capacity": 2},
            {"id": "day2", "name": "Day 2", "order": 2, "capacity": 2},
            {"id": "day3", "name": "Day 3", "order": 3, "capacity": 2},
            {"id": "day4", "name": "Day 4", "order": 4, "capacity": 1},
            {"id": "day5", "name": "Day 5", "order": 5, "capacity": 2},
        ],
        "intro": "We're planning a 5-day trip with {ni} activities across {ns} days.",
    },
    "product": {
        "display_name": "Product Roadmap",
        "item_label": "feature", "items_label": "features",
        "slot_label": "sprint", "slots_label": "sprints",
        "verb_assign": "schedule", "verb_move": "move",
        "in_verb": "scheduled in", "before_verb": "scheduled before",
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
        "agg_prop": "story_pts", "agg_label": "total story points", "agg_unit": "points",
        "slots": [
            {"id": "sp1", "name": "Sprint 1", "order": 1, "capacity": 2},
            {"id": "sp2", "name": "Sprint 2", "order": 2, "capacity": 2},
            {"id": "sp3", "name": "Sprint 3", "order": 3, "capacity": 2},
            {"id": "sp4", "name": "Sprint 4", "order": 4, "capacity": 1},
            {"id": "sp5", "name": "Sprint 5", "order": 5, "capacity": 2},
        ],
        "intro": "We're planning a product roadmap with {ni} features across {ns} two-week sprints.",
    },
    "hiring": {
        "display_name": "Hiring Pipeline",
        "item_label": "candidate", "items_label": "candidates",
        "slot_label": "interview week", "slots_label": "interview weeks",
        "verb_assign": "schedule", "verb_move": "reschedule",
        "in_verb": "scheduled for", "before_verb": "interviewed before",
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
        "agg_prop": "salary_k", "agg_label": "total salary", "agg_unit": "K USD",
        "slots": [
            {"id": "wk1", "name": "Week 1", "order": 1, "capacity": 2},
            {"id": "wk2", "name": "Week 2", "order": 2, "capacity": 2},
            {"id": "wk3", "name": "Week 3", "order": 3, "capacity": 2},
            {"id": "wk4", "name": "Week 4", "order": 4, "capacity": 1},
            {"id": "wk5", "name": "Week 5", "order": 5, "capacity": 2},
        ],
        "intro": "We're organizing interviews for {ni} candidates across {ns} weeks.",
    },
    "relocation": {
        "display_name": "Office Relocation",
        "item_label": "team", "items_label": "teams",
        "slot_label": "floor", "slots_label": "floors",
        "verb_assign": "place", "verb_move": "move",
        "in_verb": "placed on", "before_verb": "placed on a lower floor than",
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
        "agg_prop": "headcount", "agg_label": "total headcount", "agg_unit": "people",
        "slots": [
            {"id": "fl1", "name": "Floor 1", "order": 1, "capacity": 2},
            {"id": "fl2", "name": "Floor 2", "order": 2, "capacity": 2},
            {"id": "fl3", "name": "Floor 3", "order": 3, "capacity": 2},
            {"id": "fl4", "name": "Floor 4", "order": 4, "capacity": 1},
            {"id": "fl5", "name": "Floor 5", "order": 5, "capacity": 2},
        ],
        "intro": "We're relocating to a new 5-floor office and need to assign {ni} teams across {ns} floors.",
    },
}

# ================================================================
# HELPERS
# ================================================================

def get_item(d, item_id):
    return next(i for i in d["items"] if i["id"] == item_id)

def get_slot(d, slot_id):
    return next(s for s in d["slots"] if s["id"] == slot_id)

def slot_order(d, slot_id):
    return get_slot(d, slot_id)["order"]

def iname(d, item_id):
    return get_item(d, item_id)["name"]

def sname(d, slot_id):
    return get_slot(d, slot_id)["name"]


# ================================================================
# CONSTRAINT CHECKER
# ================================================================

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
        return slot_order(domain, sa) < slot_order(domain, sb)
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


# ================================================================
# SOLUTION GENERATION
# ================================================================

def generate_base_solution(rng, domain):
    """Random valid assignment of 8 items to 5 slots respecting capacity."""
    items = [i["id"] for i in domain["items"]]
    rng.shuffle(items)
    assignment = {}
    remaining = {s["id"]: s["capacity"] for s in domain["slots"]}
    for item in items:
        valid = [sid for sid, cap in remaining.items() if cap > 0]
        if not valid:
            raise RuntimeError("No valid slots (total capacity < N_ITEMS)")
        slot = rng.choice(valid)
        assignment[item] = slot
        remaining[slot] -= 1
    return assignment


# ================================================================
# CONSTRAINT DERIVATION (reverse generation)
# ================================================================

def _derive_fixed(rng, sol, dom, trk):
    avail = [i for i in sol if i not in trk["fixed"]]
    if not avail: return None
    item = rng.choice(avail)
    trk["fixed"].add(item)
    return {"type": "fixed_assignment", "item": item, "slot": sol[item]}

def _derive_exclusion(rng, sol, dom, trk):
    items = list(sol.keys()); rng.shuffle(items)
    slots = [s["id"] for s in dom["slots"]]
    for item in items:
        wrong = [s for s in slots if s != sol[item] and (item, s) not in trk["excl"]]
        if wrong:
            slot = rng.choice(wrong)
            trk["excl"].add((item, slot))
            return {"type": "exclusion", "item": item, "slot": slot}
    return None

def _derive_capacity(rng, sol, dom, trk):
    avail = [s["id"] for s in dom["slots"] if s["id"] not in trk["cap"]]
    if not avail: return None
    slot = rng.choice(avail)
    trk["cap"].add(slot)
    actual = sum(1 for v in sol.values() if v == slot)
    mx = actual + rng.choice([0, 1])
    return {"type": "capacity", "slot": slot, "max": max(mx, 1)}

def _derive_mutual_excl(rng, sol, dom, trk):
    items = list(sol.keys()); rng.shuffle(items)
    for i, a in enumerate(items):
        for b in items[i+1:]:
            if sol[a] != sol[b] and (a,b) not in trk["me"]:
                trk["me"].add((a,b)); trk["me"].add((b,a))
                return {"type": "mutual_exclusion", "item_a": a, "item_b": b}
    return None

def _derive_co_location(rng, sol, dom, trk):
    groups = {}
    for it, sl in sol.items():
        groups.setdefault(sl, []).append(it)
    pairs = []
    for sl, g in groups.items():
        if len(g) >= 2:
            for i, a in enumerate(g):
                for b in g[i+1:]:
                    if (a,b) not in trk["cl"]:
                        pairs.append((a,b))
    if not pairs: return None
    a, b = rng.choice(pairs)
    trk["cl"].add((a,b)); trk["cl"].add((b,a))
    return {"type": "co_location", "item_a": a, "item_b": b}

def _derive_ordering(rng, sol, dom, trk):
    items = list(sol.keys()); rng.shuffle(items)
    for a in items:
        for b in items:
            if a != b and (a,b) not in trk["ord"]:
                if slot_order(dom, sol[a]) < slot_order(dom, sol[b]):
                    trk["ord"].add((a,b))
                    return {"type": "ordering", "item_a": a, "item_b": b}
    return None

def _derive_sum_limit(rng, sol, dom, trk):
    prop = dom["agg_prop"]
    ip = {i["id"]: i[prop] for i in dom["items"]}
    slot_totals = {}
    for s in dom["slots"]:
        slot_totals[s["id"]] = sum(ip[it] for it, sl in sol.items() if sl == s["id"])
    mx = max(slot_totals.values())
    if mx == 0: return None
    limit = mx + rng.choice([0, 5, 10])
    return {"type": "sum_limit", "property": prop, "max_per_slot": limit}

def _derive_conditional(rng, sol, dom, trk):
    items = list(sol.keys()); rng.shuffle(items)
    for a in items:
        for b in items:
            if a != b and (a,b) not in trk["cond"]:
                trk["cond"].add((a,b))
                return {"type": "conditional",
                        "if_item": a, "if_slot": sol[a],
                        "then_item": b, "then_slot": sol[b]}
    return None

_DERIVERS = {
    "fixed_assignment": _derive_fixed,
    "exclusion": _derive_exclusion,
    "capacity": _derive_capacity,
    "mutual_exclusion": _derive_mutual_excl,
    "co_location": _derive_co_location,
    "ordering": _derive_ordering,
    "sum_limit": _derive_sum_limit,
    "conditional": _derive_conditional,
}

_FALLBACKS = {
    "fixed_assignment": ["exclusion"],
    "exclusion": ["fixed_assignment"],
    "capacity": ["exclusion"],
    "mutual_exclusion": ["ordering", "co_location"],
    "co_location": ["mutual_exclusion", "ordering"],
    "ordering": ["mutual_exclusion"],
    "sum_limit": ["conditional"],
    "conditional": ["sum_limit"],
}

def derive_constraints(rng, sol, dom, type_seq, trk, id_start):
    """Derive constraints of given types from a known solution."""
    result = []
    for i, ct in enumerate(type_seq):
        c = _DERIVERS[ct](rng, sol, dom, trk)
        if c is None:
            for fb in _FALLBACKS.get(ct, []):
                c = _DERIVERS[fb](rng, sol, dom, trk)
                if c is not None: break
        if c is None:
            c = _derive_exclusion(rng, sol, dom, trk)
        if c is None:
            raise RuntimeError(f"Cannot derive constraint type={ct}")
        c["id"] = f"C{id_start + i:02d}"
        result.append(c)
    return result


# ================================================================
# MODIFICATION + REPAIR
# ================================================================

def generate_modification(rng, sol_base, constraints_early, domain):
    """
    Pick a fixed_assignment constraint, change the slot, repair.
    Returns (mod_info, solution_modified, replaced_constraint).

    Repair strategies (tried in order):
      1. Direct move (target slot has capacity)
      2. Bump one occupant to an open slot
      3. Swap with an occupant (both move)
    """
    fixed_cs = [c for c in constraints_early if c["type"] == "fixed_assignment"]
    rng.shuffle(fixed_cs)
    slots = [s["id"] for s in domain["slots"]]

    for fc in fixed_cs:
        item = fc["item"]
        old_slot = fc["slot"]
        new_slots = [s for s in slots if s != old_slot]
        rng.shuffle(new_slots)

        for new_slot in new_slots:
            mod = dict(sol_base)
            mod[item] = new_slot

            cap = get_slot(domain, new_slot)["capacity"]
            occupants = [it for it, sl in mod.items() if sl == new_slot and it != item]

            bumped = None
            bumped_to = None

            if len(occupants) + 1 > cap:
                # Strategy 2: bump one occupant
                bumpable = []
                for occ in occupants:
                    has_fix = any(c["type"] == "fixed_assignment" and
                                 c["item"] == occ and c["slot"] == new_slot
                                 for c in constraints_early if c["id"] != fc["id"])
                    if not has_fix:
                        bumpable.append(occ)

                placed = False
                for occ in bumpable:
                    for alt in slots:
                        if alt == new_slot:
                            continue
                        alt_cap = get_slot(domain, alt)["capacity"]
                        test_mod = dict(mod)
                        test_mod[occ] = alt
                        alt_n = sum(1 for it, sl in test_mod.items()
                                    if sl == alt and it != occ) + 1
                        if alt_n <= alt_cap:
                            mod[occ] = alt
                            bumped = occ
                            bumped_to = alt
                            placed = True
                            break
                    if placed:
                        break

                if not placed:
                    # Strategy 3: swap — move item to new_slot, move one
                    # occupant to old_slot (which just freed up)
                    for occ in bumpable:
                        test_mod = dict(sol_base)
                        test_mod[item] = new_slot
                        test_mod[occ] = old_slot
                        remaining = [c for c in constraints_early if c["id"] != fc["id"]]
                        if all(check_constraint(c, test_mod, domain) for c in remaining):
                            mod = test_mod
                            bumped = occ
                            bumped_to = old_slot
                            placed = True
                            break

                if not placed:
                    continue

            # Check remaining early constraints still hold
            remaining = [c for c in constraints_early if c["id"] != fc["id"]]
            if all(check_constraint(c, mod, domain) for c in remaining):
                info = {
                    "item": item, "old_slot": old_slot, "new_slot": new_slot,
                    "original_constraint_id": fc["id"],
                    "bumped_item": bumped, "bumped_to": bumped_to,
                }
                return info, mod, fc

    raise RuntimeError("Could not find valid modification")


# ================================================================
# CONFLICT GENERATION
# ================================================================

def generate_conflict(rng, sol_base, sol_mod, domain, existing_cs):
    """Generate constraint TRUE in base, FALSE in modified."""
    existing_pairs = set()
    for c in existing_cs:
        for k in ("item_a", "item_b"):
            pass  # just tracking pairs below
        if c["type"] in ("mutual_exclusion", "co_location"):
            existing_pairs.add((c.get("item_a"), c.get("item_b")))
            existing_pairs.add((c.get("item_b"), c.get("item_a")))

    # Strategy 1: co_location that held in base but broke in modified
    base_groups = {}
    for it, sl in sol_base.items():
        base_groups.setdefault(sl, []).append(it)
    for sl, group in base_groups.items():
        if len(group) >= 2:
            for i, a in enumerate(group):
                for b in group[i+1:]:
                    if sol_mod[a] != sol_mod[b] and (a,b) not in existing_pairs:
                        return {
                            "type": "co_location", "item_a": a, "item_b": b,
                            "conflict_reason": (
                                f"{iname(domain,a)} and {iname(domain,b)} were "
                                f"together in {sname(domain,sl)} before the "
                                f"modification but are now separated."
                            ),
                        }

    # Strategy 2: ordering that held in base but broke
    items = list(sol_base.keys()); rng.shuffle(items)
    for a in items:
        for b in items:
            if a == b: continue
            oa_b = slot_order(domain, sol_base[a])
            ob_b = slot_order(domain, sol_base[b])
            oa_m = slot_order(domain, sol_mod[a])
            ob_m = slot_order(domain, sol_mod[b])
            if oa_b < ob_b and oa_m >= ob_m:
                return {
                    "type": "ordering", "item_a": a, "item_b": b,
                    "conflict_reason": (
                        f"{iname(domain,a)} was before {iname(domain,b)} "
                        f"originally but after modification they are in the "
                        f"same slot or reversed."
                    ),
                }

    # Strategy 3: fixed_assignment to the old slot
    for it in items:
        if sol_base[it] != sol_mod[it]:
            return {
                "type": "fixed_assignment", "item": it, "slot": sol_base[it],
                "conflict_reason": (
                    f"{iname(domain,it)} was in {sname(domain,sol_base[it])} "
                    f"but was moved to {sname(domain,sol_mod[it])} by the "
                    f"modification."
                ),
            }

    raise RuntimeError("Could not generate conflict")


# ================================================================
# NATURAL LANGUAGE
# ================================================================

TRANSITIONS = {
    "easy": [
        "Also, {c}", "One more thing: {c}", "Additionally, {c}",
        "We also need: {c}", "Keep in mind: {c}", "Oh, and {cl}",
    ],
    "hard": [
        "This is important: {c}", "The team insists: {c}",
        "New requirement from stakeholders: {c}",
        "This came up in a meeting: {c}", "Firm requirement: {c}",
    ],
    "late": [
        "After discussion, we also need: {c}", "Another requirement: {c}",
        "The team added this: {c}", "Late addition: {c}",
    ],
    "stress": [
        "One more to factor in: {c}", "This is non-negotiable: {c}",
        "Final requirement: {c}",
    ],
}

def constraint_nl(c, dom):
    """Convert constraint dict to natural language."""
    ct = c["type"]
    iv = dom["in_verb"]
    bv = dom["before_verb"]
    if ct == "fixed_assignment":
        return f"{iname(dom,c['item'])} must be {iv} {sname(dom,c['slot'])}."
    elif ct == "exclusion":
        return f"{iname(dom,c['item'])} cannot be {iv} {sname(dom,c['slot'])}."
    elif ct == "capacity":
        return f"{sname(dom,c['slot'])} can hold at most {c['max']} {dom['items_label']}."
    elif ct == "mutual_exclusion":
        return f"{iname(dom,c['item_a'])} and {iname(dom,c['item_b'])} cannot be in the same {dom['slot_label']}."
    elif ct == "co_location":
        return f"{iname(dom,c['item_a'])} and {iname(dom,c['item_b'])} must be in the same {dom['slot_label']}."
    elif ct == "ordering":
        return f"{iname(dom,c['item_a'])} must be {bv} {iname(dom,c['item_b'])}."
    elif ct == "sum_limit":
        return (f"The {dom['agg_label']} in any single {dom['slot_label']} "
                f"must not exceed {c['max_per_slot']} {dom['agg_unit']}.")
    elif ct == "conditional":
        return (f"If {iname(dom,c['if_item'])} is {iv} {sname(dom,c['if_slot'])}, "
                f"then {iname(dom,c['then_item'])} must be {iv} {sname(dom,c['then_slot'])}.")
    return str(c)

def wrap_nl(rng, nl_text, phase):
    pool = TRANSITIONS.get(phase, TRANSITIONS["easy"])
    t = rng.choice(pool)
    return t.format(c=nl_text, cl=nl_text[0].lower() + nl_text[1:])


# ================================================================
# FORMAT HELPERS
# ================================================================

def format_items_table(dom):
    items = dom["items"]
    props = [k for k in items[0] if k not in ("id", "name")]
    LABELS = {
        "attendees": "Attendees", "duration_hrs": "Duration(hrs)",
        "cost_usd": "Cost($)", "energy": "Energy(1-5)",
        "story_pts": "Story Pts", "devs": "Devs",
        "salary_k": "Salary(K$)", "experience_yrs": "Exp(yrs)",
        "headcount": "Headcount", "noise": "Noise(1-5)",
    }
    hdrs = [dom["item_label"].title()] + [LABELS.get(p, p) for p in props]
    rows = [[it["name"]] + [str(it[p]) for p in props] for it in items]
    widths = [max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(hdrs)]
    lines = ["| " + " | ".join(h.ljust(w) for h, w in zip(hdrs, widths)) + " |"]
    lines.append("| " + " | ".join("-"*w for w in widths) + " |")
    for r in rows:
        lines.append("| " + " | ".join(v.ljust(w) for v, w in zip(r, widths)) + " |")
    return "\n".join(lines)

def format_slots_table(dom):
    hdrs = [dom["slot_label"].title(), "Capacity"]
    rows = [(s["name"], str(s["capacity"])) for s in dom["slots"]]
    widths = [max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(hdrs)]
    lines = ["| " + " | ".join(h.ljust(w) for h, w in zip(hdrs, widths)) + " |"]
    lines.append("| " + " | ".join("-"*w for w in widths) + " |")
    for r in rows:
        lines.append("| " + " | ".join(v.ljust(w) for v, w in zip(r, widths)) + " |")
    return "\n".join(lines)

def format_plan(assignment, dom):
    slot_items = {s["id"]: [] for s in dom["slots"]}
    for it_id, sl_id in assignment.items():
        slot_items.setdefault(sl_id, []).append(iname(dom, it_id))
    lines = ["Current Plan:"]
    for s in dom["slots"]:
        its = slot_items.get(s["id"], [])
        lines.append(f"{s['name']}: {', '.join(its)}" if its
                     else f"{s['name']}: (empty)")
    return "\n".join(lines)


# ================================================================
# CHECKPOINT GROUND TRUTH
# ================================================================

def checkpoint_gt(assignment, active_cs, domain, conflict_id=None):
    """Build ground truth for a checkpoint turn."""
    sat = {}
    for c in active_cs:
        ok = check_constraint(c, assignment, domain)
        entry = {"satisfied": ok}
        if c["id"] == conflict_id:
            entry["is_conflict"] = True
            entry["expected_behavior"] = "flag_conflict"
            entry["scoring"] = {
                "flagged": 1.0, "silent_correct": 0.75,
                "silent_wrong": 0.25, "both_violated": 0.0,
            }
            if "conflict_reason" in c:
                entry["conflict_reason"] = c["conflict_reason"]
        sat[c["id"]] = entry

    return {
        "reference_assignment": dict(assignment),
        "reference_plan_text": format_plan(assignment, domain),
        "constraint_satisfaction": sat,
        "n_satisfied": sum(1 for e in sat.values()
                          if e["satisfied"] and not e.get("is_conflict")),
        "n_total": len(sat),
        "n_conflicts": sum(1 for e in sat.values() if e.get("is_conflict")),
    }


# ================================================================
# TURN BUILDER
# ================================================================

def build_turns(rng, dom, sol_base, sol_mod,
                cs_early, cs_late, cs_stress, c_conflict, mod_info, replaced_c):
    """
    Build all 20 turns.

    Constraint schedule:
      T1:  setup + C01, C02       T2:  C03        T3:  C04
      T4:  C05                    T5:  C06        T6:  CHECKPOINT 1
      T7:  C07                    T8:  C08        T9:  C09
      T10: recall prompt          T11: CHECKPOINT 2
      T12: MODIFICATION           T13: C10        T14: C11
      T15: C_trap (conflict)      T16: C12        T17: CHECKPOINT 3
      T18: C13 (stress)           T19: C14 (stress)   T20: FINAL CHECKPOINT
    """
    sched = {
        1: [cs_early[0], cs_early[1]],
        2: [cs_early[2]], 3: [cs_early[3]], 4: [cs_early[4]], 5: [cs_early[5]],
        7: [cs_early[6]], 8: [cs_early[7]], 9: [cs_early[8]],
        13: [cs_late[0]], 14: [cs_late[1]], 15: [c_conflict], 16: [cs_late[2]],
        18: [cs_stress[0]], 19: [cs_stress[1]],
    }

    active = []  # running list of active constraints
    turns = []

    for tn in range(1, 21):
        turn = {"turn_number": tn, "is_checkpoint": tn in CHECKPOINT_TURNS}

        # ---- Turn 1: Problem setup ----
        if tn == 1:
            intro = dom["intro"].format(ni=N_ITEMS, ns=N_SLOTS)
            itbl = format_items_table(dom)
            stbl = format_slots_table(dom)
            c1 = constraint_nl(sched[1][0], dom)
            c2 = constraint_nl(sched[1][1], dom)
            turn["prompt"] = (
                f"{intro}\n\n"
                f"Here are the {dom['items_label']}:\n\n{itbl}\n\n"
                f"Available {dom['slots_label']} (in order):\n\n{stbl}\n\n"
                f"First two requirements:\n1. {c1}\n2. {c2}\n\n"
                f"What's your initial thinking?"
            )
            active.extend(sched[1])
            turn["phase"] = "setup"
            turn["constraints_introduced"] = [c["id"] for c in sched[1]]

        # ---- Checkpoints ----
        elif tn == 6:
            turn["prompt"] = (
                f"Let's see where we are. Produce a complete plan satisfying "
                f"all constraints so far. Use the format:\n\n"
                f"Current Plan:\n"
                f"[{dom['slot_label'].title()}]: [{dom['item_label'].title()} 1], ...\n"
                f"...\nUnassigned: (if any)"
            )
            turn["phase"] = "checkpoint"
            turn["constraints_introduced"] = []
            turn["ground_truth"] = checkpoint_gt(sol_base, active, dom)

        elif tn == 11:
            turn["prompt"] = (
                "Produce an updated plan incorporating all constraints. "
                "Same format as before."
            )
            turn["phase"] = "checkpoint"
            turn["constraints_introduced"] = []
            turn["ground_truth"] = checkpoint_gt(sol_base, active, dom)

        elif tn == 17:
            turn["prompt"] = (
                "With all changes and new requirements, produce an updated "
                "plan. If any constraints conflict, flag them explicitly."
            )
            turn["phase"] = "checkpoint"
            turn["constraints_introduced"] = []
            turn["ground_truth"] = checkpoint_gt(
                sol_mod, active, dom, conflict_id=c_conflict["id"])

        elif tn == 20:
            turn["prompt"] = (
                "Produce your final plan. Then list every constraint we've "
                "discussed and state whether it is satisfied, violated, or "
                "in conflict with another constraint."
            )
            turn["phase"] = "final_checkpoint"
            turn["constraints_introduced"] = []
            turn["ground_truth"] = checkpoint_gt(
                sol_mod, active, dom, conflict_id=c_conflict["id"])

        # ---- Turn 10: recall ----
        elif tn == 10:
            turn["prompt"] = (
                "Before we finalize, can you list all the constraints "
                "we've established so far?"
            )
            turn["phase"] = "recall"
            turn["constraints_introduced"] = []
            turn["ground_truth"] = {
                "scoring_type": "constraint_recall",
                "expected_constraints": [c["id"] for c in active],
                "n_expected": len(active),
            }

        # ---- Turn 12: modification ----
        elif tn == MODIFICATION_TURN:
            it_nm = iname(dom, mod_info["item"])
            old_sn = sname(dom, mod_info["old_slot"])
            new_sn = sname(dom, mod_info["new_slot"])
            turn["prompt"] = (
                f"There's been a change. {it_nm} needs to be "
                f"{dom['in_verb']} {new_sn} instead of {old_sn}. "
                f"Please note this — we'll update the full plan soon."
            )
            # Replace constraint in active list
            new_fix = {
                "type": "fixed_assignment", "id": replaced_c["id"],
                "item": mod_info["item"], "slot": mod_info["new_slot"],
            }
            active = [new_fix if c["id"] == replaced_c["id"] else c
                      for c in active]
            turn["phase"] = "modification"
            turn["constraints_introduced"] = []
            turn["modification"] = {
                "replaces": replaced_c["id"],
                "item": mod_info["item"],
                "old_slot": mod_info["old_slot"],
                "new_slot": mod_info["new_slot"],
            }

        # ---- Constraint introduction turns ----
        elif tn in sched:
            new_cs = sched[tn]
            if tn <= 5:
                phase = "easy"
            elif tn <= 9:
                phase = "hard"
            elif tn <= 16:
                phase = "late"
            else:
                phase = "stress"

            parts = [wrap_nl(rng, constraint_nl(c, dom), phase) for c in new_cs]
            turn["prompt"] = " ".join(parts)
            turn["phase"] = phase
            turn["constraints_introduced"] = [c["id"] for c in new_cs]
            active.extend(new_cs)

        else:
            turn["prompt"] = ""
            turn["phase"] = "gap"
            turn["constraints_introduced"] = []

        turn["active_constraint_ids"] = [c["id"] for c in active]
        turn["n_active_constraints"] = len(active)
        turns.append(turn)

    return turns


# ================================================================
# SCENARIO ASSEMBLY
# ================================================================

def generate_scenario(scenario_num, domain_key, seed=MASTER_SEED, max_retries=5):
    """Generate one complete P2 scenario. Retries with seed jitter on failure."""
    for attempt in range(max_retries):
        s = seed * 100 + scenario_num + 5000 + attempt * 7919  # prime offset
        rng = random.Random(s)
        try:
            dom = copy.deepcopy(DOMAINS[domain_key])
            dom["_domain_key"] = domain_key

            # 1. Base solution
            sol_base = generate_base_solution(rng, dom)

            # 2. Derive early constraints (C01-C09)
            trk = {"fixed": set(), "excl": set(), "cap": set(),
                   "me": set(), "cl": set(), "ord": set(), "cond": set()}
            easy_types = ["fixed_assignment", "fixed_assignment",
                          "exclusion", "exclusion", "capacity", "exclusion"]
            hard_types = ["mutual_exclusion", "ordering", "mutual_exclusion"]
            rng.shuffle(easy_types)
            rng.shuffle(hard_types)
            cs_early = derive_constraints(rng, sol_base, dom, easy_types + hard_types, trk, 1)

            # 3. Modification + repair
            mod_info, sol_mod, replaced_c = generate_modification(rng, sol_base, cs_early, dom)

            # 4. Late constraints (C10-C12) from modified solution
            late_types = ["exclusion", "mutual_exclusion", "ordering"]
            rng.shuffle(late_types)
            cs_late = derive_constraints(rng, sol_mod, dom, late_types, trk, 10)

            # 5. Conflict
            c_conflict = generate_conflict(rng, sol_base, sol_mod, dom, cs_early + cs_late)
            c_conflict["id"] = "C_trap"

            # 6. Stress constraints (C13-C14) from modified solution
            cs_stress = derive_constraints(rng, sol_mod, dom, ["sum_limit", "conditional"], trk, 13)

            # 7. Build turns
            turns = build_turns(rng, dom, sol_base, sol_mod,
                                cs_early, cs_late, cs_stress, c_conflict,
                                mod_info, replaced_c)

            # Assemble all constraints for metadata
            all_cs = cs_early + cs_late + [c_conflict] + cs_stress
            all_cs_clean = []
            for c in all_cs:
                cc = {k: v for k, v in c.items() if k != "conflict_reason"}
                all_cs_clean.append(cc)

            sid = f"P2_{scenario_num:03d}"
            return {
                "scenario_id": sid,
                "generator_version": VERSION,
                "seed": s,
                "domain": domain_key,
                "domain_display": dom["display_name"],
                "n_items": N_ITEMS,
                "n_slots": N_SLOTS,
                "system_prompt": SYSTEM_PROMPT,
                "solution_base": sol_base,
                "solution_modified": sol_mod,
                "modification": mod_info,
                "conflict": {
                    "id": c_conflict["id"],
                    "type": c_conflict["type"],
                    "introduced_at_turn": CONFLICT_TURN,
                    "reason": c_conflict.get("conflict_reason", ""),
                },
                "constraints": all_cs_clean,
                "turns": turns,
            }
        except RuntimeError:
            if attempt == max_retries - 1:
                raise
            continue  # retry with different seed


# ================================================================
# VALIDATION
# ================================================================

def validate_scenario(sc):
    """Validate a single scenario. Returns list of issue strings."""
    issues = []
    sid = sc["scenario_id"]
    dom_key = sc["domain"]
    dom = copy.deepcopy(DOMAINS[dom_key])
    dom["_domain_key"] = dom_key

    # Check turn count
    if len(sc["turns"]) != 20:
        issues.append(f"{sid}: Expected 20 turns, got {len(sc['turns'])}")

    # Check checkpoints exist
    checkpoint_nums = {t["turn_number"] for t in sc["turns"] if t.get("is_checkpoint")}
    if checkpoint_nums != CHECKPOINT_TURNS:
        issues.append(f"{sid}: Checkpoints at {checkpoint_nums}, expected {CHECKPOINT_TURNS}")

    # Check all turns have prompts
    for t in sc["turns"]:
        if not t.get("prompt"):
            issues.append(f"{sid} T{t['turn_number']}: Empty prompt")

    # Check base solution satisfies early constraints
    cs_by_id = {c["id"]: c for c in sc["constraints"]}
    early_ids = set()
    for t in sc["turns"]:
        if t["turn_number"] <= 9:
            early_ids.update(t.get("constraints_introduced", []))

    for cid in early_ids:
        if cid in cs_by_id:
            c = cs_by_id[cid]
            if not check_constraint(c, sc["solution_base"], dom):
                issues.append(f"{sid}: Base solution violates early constraint {cid}")

    # Check modified solution satisfies non-replaced early + late constraints
    replaced_id = sc["modification"]["original_constraint_id"]
    for cid in early_ids:
        if cid == replaced_id:
            continue
        if cid in cs_by_id:
            c = cs_by_id[cid]
            if not check_constraint(c, sc["solution_modified"], dom):
                issues.append(f"{sid}: Modified solution violates constraint {cid}")

    # Check the replacement constraint (modified version) is satisfied
    mod = sc["modification"]
    new_fix = {"type": "fixed_assignment", "item": mod["item"], "slot": mod["new_slot"]}
    if not check_constraint(new_fix, sc["solution_modified"], dom):
        issues.append(f"{sid}: Modified solution doesn't satisfy replacement constraint")

    # Check late constraints satisfied by modified solution
    late_ids = set()
    for t in sc["turns"]:
        if 13 <= t["turn_number"] <= 16 and t["turn_number"] != CONFLICT_TURN:
            late_ids.update(t.get("constraints_introduced", []))
    for cid in late_ids:
        if cid in cs_by_id:
            c = cs_by_id[cid]
            if not check_constraint(c, sc["solution_modified"], dom):
                issues.append(f"{sid}: Modified solution violates late constraint {cid}")

    # Check stress constraints satisfied by modified solution
    stress_ids = set()
    for t in sc["turns"]:
        if t["turn_number"] in (18, 19):
            stress_ids.update(t.get("constraints_introduced", []))
    for cid in stress_ids:
        if cid in cs_by_id:
            c = cs_by_id[cid]
            if not check_constraint(c, sc["solution_modified"], dom):
                issues.append(f"{sid}: Modified solution violates stress constraint {cid}")

    # Check conflict IS violated by modified solution
    trap = cs_by_id.get("C_trap")
    if trap:
        if check_constraint(trap, sc["solution_modified"], dom):
            issues.append(f"{sid}: Conflict C_trap is NOT violated by modified solution (should be)")
        if not check_constraint(trap, sc["solution_base"], dom):
            issues.append(f"{sid}: Conflict C_trap is NOT satisfied by base solution (should be)")

    # Check checkpoint ground truths have content
    for t in sc["turns"]:
        if t.get("is_checkpoint") and "ground_truth" not in t:
            issues.append(f"{sid} T{t['turn_number']}: Checkpoint missing ground_truth")

    # Check constraint accumulation
    total_introduced = sum(
        len(t.get("constraints_introduced", []))
        for t in sc["turns"]
    )
    expected = 9 + 3 + 1 + 2  # early + late + conflict + stress = 15
    if total_introduced != expected:
        issues.append(f"{sid}: {total_introduced} constraints introduced, expected {expected}")

    return issues


# ================================================================
# MAIN
# ================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate P2 scenarios")
    parser.add_argument("--output-dir", default="p2_scenarios")
    parser.add_argument("--seed", type=int, default=MASTER_SEED)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    seed = args.seed

    # Domain allocation: 8 scenarios each, 5 domains = 40
    domain_keys = list(DOMAINS.keys())
    allocation = []
    for dk in domain_keys:
        for i in range(SCENARIOS_PER_DOMAIN):
            allocation.append(dk)
    # Total = 40

    print(f"Generating {N_SCENARIOS} P2 scenarios (seed={seed})...")
    domain_counts = {dk: 0 for dk in domain_keys}
    for dk in allocation:
        domain_counts[dk] += 1
    print(f"  Domains: {', '.join(f'{dk}={n}' for dk, n in domain_counts.items())}")
    print(f"  Items: {N_ITEMS}, Slots: {N_SLOTS}, Constraints: 15 per scenario")
    print()

    all_issues = []
    manifest_scenarios = []

    for i, dk in enumerate(allocation):
        num = i + 1
        try:
            sc = generate_scenario(num, dk, seed)
        except RuntimeError as e:
            print(f"  P2_{num:03d} ({dk:12s}): FAIL [{e}]")
            all_issues.append(f"P2_{num:03d}: Generation failed: {e}")
            continue

        # Validate
        issues = validate_scenario(sc)
        all_issues.extend(issues)
        status = "OK" if not issues else f"ISSUES({len(issues)})"

        # Save
        path = os.path.join(args.output_dir, f"P2_{num:03d}.json")
        with open(path, "w") as f:
            json.dump(sc, f, indent=2)

        print(f"  P2_{num:03d} ({dk:12s}): {status}  [{sc['domain_display']}]")

        manifest_scenarios.append({
            "scenario_id": sc["scenario_id"],
            "domain": dk,
            "domain_display": sc["domain_display"],
            "modification_item": sc["modification"]["item"],
            "conflict_type": sc["conflict"]["type"],
        })

    # Write manifest
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "generator_version": VERSION,
        "master_seed": seed,
        "total_scenarios": len(manifest_scenarios),
        "n_items": N_ITEMS,
        "n_slots": N_SLOTS,
        "domain_distribution": domain_counts,
        "system_prompt": SYSTEM_PROMPT,
        "scenarios": manifest_scenarios,
    }
    mpath = os.path.join(args.output_dir, "p2_manifest.json")
    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=2)

    # Write validation report
    rpath = os.path.join(args.output_dir, "p2_validation_report.txt")
    with open(rpath, "w") as f:
        f.write(f"P2 Scenario Validation Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Master seed: {seed}\n")
        f.write(f"Generator version: {VERSION}\n")
        f.write(f"Total scenarios: {len(manifest_scenarios)}\n")
        f.write(f"Total issues: {len(all_issues)}\n\n")
        if not all_issues:
            f.write("All scenarios passed validation.\n")
        else:
            f.write("Issues:\n")
            for issue in all_issues:
                f.write(f"  - {issue}\n")
        f.write(f"\nDomain distribution:\n")
        for dk, n in domain_counts.items():
            f.write(f"  {dk}: {n}\n")

    # Summary
    print(f"\n{'='*60}")
    if not all_issues:
        print(f"DONE: {len(manifest_scenarios)} scenarios generated")
        print(f"  Output: {args.output_dir}/")
        print(f"  Manifest: {mpath}")
        print(f"  Validation: {rpath}")
        print(f"  All scenarios passed validation")
    else:
        print(f"DONE with {len(all_issues)} issues:")
        for issue in all_issues:
            print(f"  - {issue}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
