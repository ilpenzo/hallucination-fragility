#!/usr/bin/env python3
"""
p2_parser_fix.py — P2 Parser Diagnostic & Enhanced Parser

Phase 1: Diagnose WHY parse counts are low for each model.
  Classifies each low-parse checkpoint response into:
    REFUSAL      — model explicitly refused to produce a plan
    MINIMAL      — model produced a plan but left items unassigned intentionally
    FORMAT_MISS  — model assigned items but current parser couldn't extract them
    AMBIGUOUS    — couldn't clearly classify

Phase 2: Build an enhanced parser that handles format variations.
  - Markdown bold/italic slot names
  - Bullet/numbered list prefixes
  - Pipe-delimited tables
  - Additional plan markers ("Updated Plan", "Final Plan", "Revised Plan", etc.)
  - Items on sub-lines under slot headers
  - Arrow syntax: "Slot → Item" or "Item → Slot"
  - Natural language lists ("Item A and Item B")

Phase 3: Re-score with enhanced parser and compare results.

Usage:
  python p2_parser_fix.py \
    --results-dir ./results \
    --scenarios-dir ./p2_scenarios \
    --output-dir ./p2_parser_analysis

Expects:
  results/{model_name}/P2_*.json — raw conversation results
  p2_scenarios/P2_*.json — scenario files with ground truth
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
        "item_label": "session", "items_label": "sessions",
        "slot_label": "time block", "slots_label": "time blocks",
        "items": [
            {"id": "keynote", "name": "Keynote Address"},
            {"id": "ai_panel", "name": "AI Ethics Panel"},
            {"id": "data_ws", "name": "Data Science Workshop"},
            {"id": "networking", "name": "Networking Session"},
            {"id": "product_demo", "name": "Product Demo"},
            {"id": "research", "name": "Research Talks"},
            {"id": "team_bldg", "name": "Team Building Activity"},
            {"id": "closing", "name": "Closing Remarks"},
        ],
        "slots": [
            {"id": "mon_am", "name": "Monday Morning"},
            {"id": "mon_pm", "name": "Monday Afternoon"},
            {"id": "tue_am", "name": "Tuesday Morning"},
            {"id": "tue_pm", "name": "Tuesday Afternoon"},
            {"id": "wed_am", "name": "Wednesday Morning"},
        ],
    },
    "travel": {
        "display_name": "Travel Itinerary",
        "item_label": "activity", "items_label": "activities",
        "slot_label": "day", "slots_label": "days",
        "items": [
            {"id": "museum", "name": "Museum Visit"},
            {"id": "walking_tour", "name": "Walking Tour"},
            {"id": "beach", "name": "Beach Excursion"},
            {"id": "hike", "name": "Mountain Hike"},
            {"id": "market", "name": "Local Market"},
            {"id": "show", "name": "Cultural Show"},
            {"id": "food_tour", "name": "Food Tour"},
            {"id": "temple", "name": "Temple Visit"},
        ],
        "slots": [
            {"id": "day1", "name": "Day 1"},
            {"id": "day2", "name": "Day 2"},
            {"id": "day3", "name": "Day 3"},
            {"id": "day4", "name": "Day 4"},
            {"id": "day5", "name": "Day 5"},
        ],
    },
    "product": {
        "display_name": "Product Roadmap",
        "item_label": "feature", "items_label": "features",
        "slot_label": "sprint", "slots_label": "sprints",
        "items": [
            {"id": "auth", "name": "User Authentication"},
            {"id": "dashboard", "name": "Dashboard UI"},
            {"id": "payments", "name": "Payment System"},
            {"id": "search", "name": "Search Engine"},
            {"id": "notifs", "name": "Notification Service"},
            {"id": "analytics", "name": "Analytics Module"},
            {"id": "mobile", "name": "Mobile App"},
            {"id": "api", "name": "API Gateway"},
        ],
        "slots": [
            {"id": "sp1", "name": "Sprint 1"},
            {"id": "sp2", "name": "Sprint 2"},
            {"id": "sp3", "name": "Sprint 3"},
            {"id": "sp4", "name": "Sprint 4"},
            {"id": "sp5", "name": "Sprint 5"},
        ],
    },
    "hiring": {
        "display_name": "Hiring Pipeline",
        "item_label": "candidate", "items_label": "candidates",
        "slot_label": "interview week", "slots_label": "interview weeks",
        "items": [
            {"id": "alice", "name": "Alice Chen"},
            {"id": "bob", "name": "Bob Kumar"},
            {"id": "carol", "name": "Carol Santos"},
            {"id": "david", "name": "David Park"},
            {"id": "elena", "name": "Elena Volkov"},
            {"id": "frank", "name": "Frank Osei"},
            {"id": "grace", "name": "Grace Liu"},
            {"id": "hasan", "name": "Hasan Ali"},
        ],
        "slots": [
            {"id": "wk1", "name": "Week 1"},
            {"id": "wk2", "name": "Week 2"},
            {"id": "wk3", "name": "Week 3"},
            {"id": "wk4", "name": "Week 4"},
            {"id": "wk5", "name": "Week 5"},
        ],
    },
    "relocation": {
        "display_name": "Office Relocation",
        "item_label": "team", "items_label": "teams",
        "slot_label": "floor", "slots_label": "floors",
        "items": [
            {"id": "eng", "name": "Engineering"},
            {"id": "mktg", "name": "Marketing"},
            {"id": "sales", "name": "Sales"},
            {"id": "hr", "name": "Human Resources"},
            {"id": "finance", "name": "Finance"},
            {"id": "legal", "name": "Legal"},
            {"id": "product", "name": "Product"},
            {"id": "design", "name": "Design"},
        ],
        "slots": [
            {"id": "fl1", "name": "Floor 1"},
            {"id": "fl2", "name": "Floor 2"},
            {"id": "fl3", "name": "Floor 3"},
            {"id": "fl4", "name": "Floor 4"},
            {"id": "fl5", "name": "Floor 5"},
        ],
    },
}


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def _build_name_maps(domain_key: str) -> Tuple[Dict, Dict]:
    """Build item_name->id and slot_name->id maps."""
    dom = P2_DOMAINS[domain_key]
    item_map = {}
    for it in dom["items"]:
        item_map[it["name"].lower()] = it["id"]
        item_map[it["id"].lower()] = it["id"]
    slot_map = {}
    for sl in dom["slots"]:
        slot_map[sl["name"].lower()] = sl["id"]
        slot_map[sl["id"].lower()] = sl["id"]
    return item_map, slot_map


def _all_item_names(domain_key: str) -> List[str]:
    """Return all item display names for a domain."""
    return [it["name"] for it in P2_DOMAINS[domain_key]["items"]]


def _all_slot_names(domain_key: str) -> List[str]:
    """Return all slot display names for a domain."""
    return [sl["name"] for sl in P2_DOMAINS[domain_key]["slots"]]


# ==============================================================================
# ORIGINAL PARSER (exact copy from score_responses.py for comparison)
# ==============================================================================

def parse_plan_original(text: str, domain_key: str) -> Dict[str, str]:
    """Original parser from score_responses.py (unchanged)."""
    item_map, slot_map = _build_name_maps(domain_key)
    assignment = {}

    plan_marker = text.lower().find("current plan:")
    if plan_marker >= 0:
        plan_text = text[plan_marker:]
    else:
        plan_text = text

    lines = plan_text.split('\n')

    for line in lines:
        line = line.strip()
        if not line or ':' not in line:
            continue

        colon_pos = line.index(':')
        slot_part = line[:colon_pos].strip()
        items_part = line[colon_pos + 1:].strip()

        if slot_part.lower() in ("current plan", "constraints", "notes",
                                 "constraint status", "status"):
            continue

        slot_id = slot_map.get(slot_part.lower())
        if slot_id is None:
            clean_slot = re.sub(r'^[\-\*\d\.\)\s]+', '', slot_part).strip()
            slot_id = slot_map.get(clean_slot.lower())
        if slot_id is None:
            continue

        if items_part.lower() in ("(empty)", "(none)", "none", "empty", "-", ""):
            continue
        if items_part.lower().startswith("unassigned"):
            continue

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
                assignment[item_id] = slot_id

    return assignment


# ==============================================================================
# ENHANCED PARSER (Phase 2)
# ==============================================================================

def parse_plan_enhanced(text: str, domain_key: str) -> Dict[str, str]:
    """
    Enhanced parser that handles common format variations:
    1. Multiple plan markers (Updated Plan, Final Plan, Revised Plan, etc.)
    2. Markdown bold/italic around slot names: **Monday Morning**: ...
    3. Bullet/numbered prefixes: - Monday Morning: ... or 1. Monday Morning: ...
    4. Hash headers: ### Monday Morning or ## Monday Morning: ...
    5. Pipe-delimited tables: | Monday Morning | Item1, Item2 |
    6. Arrow syntax: Item → Slot or Slot → Item
    7. Sub-line items under slot headers
    8. Parenthetical notes and emoji stripping
    """
    item_map, slot_map = _build_name_maps(domain_key)
    all_items = _all_item_names(domain_key)
    all_slots = _all_slot_names(domain_key)

    assignment = {}

    # --- Step 0: Strip <think>...</think> blocks (DeepSeek-R1) ---
    text_clean = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

    # --- Step 1: Find best plan section ---
    # Try multiple plan markers, prefer the LAST one (most up-to-date)
    plan_markers = [
        r'(?:^|\n)\s*(?:#+\s*)?(?:\*{0,2})?\s*(?:current|updated|final|revised|complete|proposed|new)\s+plan\s*(?:\*{0,2})?\s*:?',
        r'(?:^|\n)\s*(?:#+\s*)?(?:\*{0,2})?\s*plan\s*(?:\*{0,2})?\s*:',
        r'(?:^|\n)\s*(?:#+\s*)here\s+is\s+(?:the|my|an?)\s+(?:updated|revised|current|final|complete)?\s*plan',
    ]

    plan_start = -1
    for pattern in plan_markers:
        for m in re.finditer(pattern, text_clean, re.IGNORECASE):
            plan_start = max(plan_start, m.start())

    if plan_start >= 0:
        plan_text = text_clean[plan_start:]
    else:
        plan_text = text_clean

    # --- Step 2: Try pipe-delimited table parsing ---
    table_assignment = _parse_table_format(plan_text, item_map, slot_map, all_slots)
    if len(table_assignment) >= 3:  # Table seems to have worked
        assignment.update(table_assignment)

    # --- Step 3: Line-by-line parsing with enhanced matching ---
    lines = plan_text.split('\n')
    current_slot_id = None  # for sub-line items

    for line_raw in lines:
        line = line_raw.strip()
        if not line:
            current_slot_id = None  # blank line resets sub-line context
            continue

        # Strip emoji
        line_stripped = re.sub(
            r'[\U0001F600-\U0001F9FF\U00002702-\U000027B0'
            r'\U0001F1E0-\U0001F1FF\U0000FE00-\U0000FE0F'
            r'\U0001FA00-\U0001FAFF\u2600-\u26FF\u2700-\u27BF'
            r'\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
            r'\U0001F900-\U0001F9FF\U0000200D]+', '', line).strip()

        # Strip markdown bold/italic
        line_clean = re.sub(r'\*{1,3}', '', line_stripped)
        # Strip leading bullets, numbers, hash headers
        line_clean = re.sub(r'^(?:#{1,4}\s+|[\-\*\+]\s+|\d+[\.\)]\s+)', '', line_clean).strip()

        # --- Try slot: items format ---
        if ':' in line_clean:
            parts = line_clean.split(':', 1)
            slot_part = parts[0].strip()
            items_part = parts[1].strip()

            slot_id = _match_slot(slot_part, slot_map)

            if slot_id is not None:
                current_slot_id = slot_id  # set context for sub-lines

                # Skip meta-lines and empty assignments
                if _is_empty_or_meta(items_part):
                    continue

                # Parse items from the right side
                _extract_items(items_part, item_map, slot_id, assignment)
                continue

        # --- Try "Item → Slot" or "Slot → Item" arrow syntax ---
        arrow_match = re.search(r'(.+?)\s*[→➜➡>]\s*(.+)', line_clean)
        if arrow_match:
            left, right = arrow_match.group(1).strip(), arrow_match.group(2).strip()
            # Try both orientations
            slot_id_l = _match_slot(left, slot_map)
            slot_id_r = _match_slot(right, slot_map)
            if slot_id_r:
                # "Item → Slot" format
                _extract_items(left, item_map, slot_id_r, assignment)
                continue
            elif slot_id_l:
                # "Slot → Item" format
                _extract_items(right, item_map, slot_id_l, assignment)
                continue

        # --- Try sub-line items (indented or bulleted under a slot header) ---
        if current_slot_id is not None:
            # Check if this line contains any item names
            found_any = False
            for item_name_lower, item_id in item_map.items():
                if len(item_name_lower) > 3 and item_name_lower in line_clean.lower():
                    if item_id not in assignment:
                        assignment[item_id] = current_slot_id
                        found_any = True
            if found_any:
                continue

        # If no slot-related parsing happened, reset sub-line context
        # (but only if the line doesn't look like a continuation)
        if not re.match(r'^[\-\*\+]\s', line_stripped) and not re.match(r'^\d+[\.\)]', line_stripped):
            # Non-list line that didn't match anything => break sub-line context
            # But be lenient — break if line is substantial or looks like a new unmapped header
            if line_clean.endswith(':') or len(line_stripped) > 30:
                current_slot_id = None

    return assignment


def _match_slot(text: str, slot_map: Dict[str, str]) -> Optional[str]:
    """Try to match text to a slot name, with fuzzy cleaning."""
    clean = text.strip()

    # Direct match
    slot_id = slot_map.get(clean.lower())
    if slot_id:
        return slot_id

    # Strip markdown/formatting residue
    clean = re.sub(r'^[\-\*\+\d\.\)\s#]+', '', clean).strip()
    clean = re.sub(r'[\*_`]+', '', clean).strip()
    slot_id = slot_map.get(clean.lower())
    if slot_id:
        return slot_id

    # Try substring match against known slot names
    for sname, sid in slot_map.items():
        if len(sname) > 3 and sname in clean.lower():
            return sid

    return None


def _is_empty_or_meta(text: str) -> bool:
    """Check if items_part is empty or a meta label."""
    t = text.strip().lower()
    if t in ("(empty)", "(none)", "none", "empty", "-", "", "n/a", "—", "–",
             "tbd", "to be determined", "(tbd)"):
        return True
    if t.startswith("unassigned") or t.startswith("(unassigned"):
        return True
    # Skip lines that are clearly metadata
    meta_prefixes = ("current plan", "constraints", "notes", "constraint status",
                     "status", "conflict", "analysis", "summary", "reasoning")
    for mp in meta_prefixes:
        if t.startswith(mp):
            return True
    return False


def _extract_items(text: str, item_map: Dict, slot_id: str,
                   assignment: Dict) -> None:
    """Extract item names from a text chunk and add to assignment."""
    # Pre-process: replace ' and ' and ' & ' with commas to handle natural language lists
    text = re.sub(r'\b(?:and|&)\b', ',', text, flags=re.IGNORECASE)

    # Try comma-separated first
    raw_items = [x.strip() for x in text.split(",")]

    for raw_name in raw_items:
        # Clean: remove parenthetical notes, formatting
        clean_name = re.sub(r'\(.*?\)', '', raw_name).strip()
        clean_name = re.sub(r'[\*_`]+', '', clean_name).strip()
        clean_name = clean_name.strip('.-*# →>')

        item_id = item_map.get(clean_name.lower())
        if item_id is None:
            # Substring match
            for known_name, known_id in item_map.items():
                if known_name in clean_name.lower() and len(known_name) > 3:
                    item_id = known_id
                    break
        if item_id is not None and item_id not in assignment:
            assignment[item_id] = slot_id


def _parse_table_format(text: str, item_map: Dict, slot_map: Dict,
                        all_slots: List[str]) -> Dict[str, str]:
    """Parse pipe-delimited markdown table format."""
    assignment = {}
    lines = text.split('\n')

    for line in lines:
        line = line.strip()
        if '|' not in line:
            continue

        # Split on pipes, strip each cell
        cells = [c.strip() for c in line.split('|')]
        cells = [c for c in cells if c and c != '---' and not re.match(r'^[\-:]+$', c)]

        if len(cells) < 2:
            continue

        # Try first cell as slot, second as items
        slot_id = _match_slot(cells[0], slot_map)
        if slot_id and len(cells) >= 2:
            _extract_items(cells[1], item_map, slot_id, assignment)

    return assignment


# ==============================================================================
# RESPONSE CLASSIFICATION (Phase 1)
# ==============================================================================

REFUSAL_PATTERNS = [
    r'cannot\s+produce\s+(?:a\s+)?(?:valid\s+)?plan',
    r'impossible\s+to\s+satisfy',
    r'mathematically\s+impossible',
    r'cannot\s+(?:be\s+)?(?:built|created|produced)',
    r'logically\s+impossible',
    r'please\s+(?:clarify|confirm|specify|advise)',
    r'which\s+constraint\s+should\s+be\s+(?:relaxed|removed|modified)',
    r'need\s+(?:you\s+to\s+)?clarif',
    r'how\s+(?:would\s+you\s+like|should\s+I)\s+(?:to\s+)?proceed',
    r'(?:a\s+)?final\s+plan\s+cannot\s+be\s+produced',
    r'unresolvable?\s+conflict',
    r'unsolvable\s+conflict',
    r'mutually\s+exclusive.*?(?:which|please)',
    r'(?:direct|clear)\s+(?:and\s+)?(?:unresolved|unresolvable)\s+conflict',
    r'must\s+(?:decide|choose|modify|change)\s+(?:which|at\s+least)',
]

MINIMAL_PATTERNS = [
    r'unassigned\s*:\s*\w',  # "Unassigned: ItemA, ItemB, ..."
]


def classify_response(response: str, n_parsed_original: int,
                      n_parsed_enhanced: int, domain_key: str) -> str:
    """
    Classify a low-parse checkpoint response.

    Returns one of:
      REFUSAL      — model refused to produce a plan
      MINIMAL      — model produced a plan but intentionally left items unassigned
      FORMAT_MISS  — model assigned items but parser missed (enhanced parser finds more)
      FULL_PARSE   — both parsers got >=7 items (not a problem)
      AMBIGUOUS    — can't clearly classify
    """
    resp_lower = response.lower()

    # If enhanced parser recovered significantly more items, it's a format issue
    if n_parsed_enhanced >= 7:
        if n_parsed_original < 7:
            return "FORMAT_MISS"
        else:
            return "FULL_PARSE"

    # Check for explicit refusal patterns
    for pattern in REFUSAL_PATTERNS:
        if re.search(pattern, resp_lower):
            return "REFUSAL"

    # Check for intentional minimal commitment (has Unassigned with items)
    for pattern in MINIMAL_PATTERNS:
        if re.search(pattern, resp_lower):
            return "MINIMAL"

    # Count how many domain items appear anywhere in the response
    all_items = _all_item_names(domain_key)
    items_mentioned = sum(1 for item in all_items
                         if item.lower() in resp_lower)

    # If most items are mentioned but few parsed, likely format issue
    if items_mentioned >= 6 and n_parsed_enhanced < 5:
        return "FORMAT_MISS"

    # If very few items mentioned at all, likely refusal or very short response
    if items_mentioned < 3:
        return "REFUSAL"

    # If many items mentioned and some parsed, model was trying but partial
    if items_mentioned >= 4 and n_parsed_enhanced >= 2:
        return "MINIMAL"

    return "AMBIGUOUS"


# ==============================================================================
# MAIN ANALYSIS
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


def load_results(results_dir: str) -> List[Dict]:
    """Load all P2 result files from results/{model}/P2_*.json."""
    results = []
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
                    print(f"  Warning: {f} is missing 'turns' data. Skipping.")
                    continue
                result.setdefault("model", model_name)
                results.append(result)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"  Warning: Could not load {f}: {e}")
    return results


def analyze_checkpoint(response: str, domain_key: str) -> Dict:
    """Run both parsers on a response and classify."""
    orig = parse_plan_original(response, domain_key)
    enhanced = parse_plan_enhanced(response, domain_key)

    classification = classify_response(
        response, len(orig), len(enhanced), domain_key
    )

    return {
        "n_parsed_original": len(orig),
        "n_parsed_enhanced": len(enhanced),
        "parse_gain": len(enhanced) - len(orig),
        "classification": classification,
        "assignment_original": orig,
        "assignment_enhanced": enhanced,
    }


def run_analysis(results_dir: str, scenarios_dir: str, output_dir: str):
    """Main analysis pipeline."""
    os.makedirs(output_dir, exist_ok=True)

    print("Loading P2 scenarios...")
    scenarios = load_scenarios(scenarios_dir)
    print(f"  Loaded {len(scenarios)} scenarios")

    print("Loading P2 results...")
    results = load_results(results_dir)
    print(f"  Loaded {len(results)} result files")

    # --- Analyze every checkpoint ---
    all_checkpoints = []
    model_stats = defaultdict(lambda: {
        "total_checkpoints": 0,
        "original_zero": 0, "original_low": 0, "original_full": 0,
        "enhanced_zero": 0, "enhanced_low": 0, "enhanced_full": 0,
        "classifications": defaultdict(int),
        "original_parse_total": 0,
        "enhanced_parse_total": 0,
        "format_miss_gains": [],  # gains from enhanced parser for FORMAT_MISS cases
    })

    for result in results:
        sid = result["scenario_id"]
        model = result.get("model", "unknown")
        scenario = scenarios.get(sid)
        if not scenario:
            continue

        domain_key = scenario["domain"]
        result_turns = {t["turn_number"]: t for t in result["turns"]}

        for tn in CHECKPOINT_TURNS:
            r_turn = result_turns.get(tn)
            if r_turn is None or "response" not in r_turn:
                continue

            response = r_turn["response"]
            analysis = analyze_checkpoint(response, domain_key)
            analysis["scenario_id"] = sid
            analysis["model"] = model
            analysis["turn_number"] = tn
            analysis["domain"] = domain_key
            analysis["response_length"] = len(response)
            all_checkpoints.append(analysis)

            # Accumulate stats
            ms = model_stats[model]
            ms["total_checkpoints"] += 1
            ms["original_parse_total"] += analysis["n_parsed_original"]
            ms["enhanced_parse_total"] += analysis["n_parsed_enhanced"]

            n_orig = analysis["n_parsed_original"]
            n_enh = analysis["n_parsed_enhanced"]

            if n_orig == 0:
                ms["original_zero"] += 1
            elif n_orig < 7:
                ms["original_low"] += 1
            else:
                ms["original_full"] += 1

            if n_enh == 0:
                ms["enhanced_zero"] += 1
            elif n_enh < 7:
                ms["enhanced_low"] += 1
            else:
                ms["enhanced_full"] += 1

            ms["classifications"][analysis["classification"]] += 1

            if analysis["classification"] == "FORMAT_MISS":
                ms["format_miss_gains"].append(analysis["parse_gain"])

    # --- Print Phase 1 Report ---
    print(f"\n{'='*70}")
    print("PHASE 1: DIAGNOSTIC REPORT")
    print(f"{'='*70}")

    for model in sorted(model_stats.keys()):
        ms = model_stats[model]
        total = ms["total_checkpoints"]
        if total == 0:
            continue

        print(f"\n  {model}:")
        print(f"    Total checkpoints: {total}")
        print(f"    --- Original Parser ---")
        print(f"      0 items:   {ms['original_zero']:3d} ({ms['original_zero']/total*100:.0f}%)")
        print(f"      1-6 items: {ms['original_low']:3d} ({ms['original_low']/total*100:.0f}%)")
        print(f"      7-8 items: {ms['original_full']:3d} ({ms['original_full']/total*100:.0f}%)")
        avg_orig = ms["original_parse_total"] / total
        print(f"      Mean items parsed: {avg_orig:.2f}")

        print(f"    --- Enhanced Parser ---")
        print(f"      0 items:   {ms['enhanced_zero']:3d} ({ms['enhanced_zero']/total*100:.0f}%)")
        print(f"      1-6 items: {ms['enhanced_low']:3d} ({ms['enhanced_low']/total*100:.0f}%)")
        print(f"      7-8 items: {ms['enhanced_full']:3d} ({ms['enhanced_full']/total*100:.0f}%)")
        avg_enh = ms["enhanced_parse_total"] / total
        print(f"      Mean items parsed: {avg_enh:.2f}")

        improvement = avg_enh - avg_orig
        print(f"    --- Improvement ---")
        print(f"      Mean gain: +{improvement:.2f} items/checkpoint")
        full_pct_orig = ms["original_full"] / total * 100
        full_pct_enh = ms["enhanced_full"] / total * 100
        print(f"      Full-parse rate: {full_pct_orig:.0f}% → {full_pct_enh:.0f}%")

        print(f"    --- Response Classifications ---")
        for cls, cnt in sorted(ms["classifications"].items()):
            print(f"      {cls:15s}: {cnt:3d} ({cnt/total*100:.0f}%)")

        if ms["format_miss_gains"]:
            avg_gain = sum(ms["format_miss_gains"]) / len(ms["format_miss_gains"])
            print(f"    --- FORMAT_MISS Details ---")
            print(f"      Count: {len(ms['format_miss_gains'])}")
            print(f"      Avg gain when fixed: +{avg_gain:.1f} items")

    # --- Print Phase 2 Report: Per-turn comparison ---
    print(f"\n{'='*70}")
    print("PHASE 2: PER-CHECKPOINT-TURN COMPARISON")
    print(f"{'='*70}")

    for tn in sorted(CHECKPOINT_TURNS):
        print(f"\n  Turn {tn}:")
        for model in sorted(model_stats.keys()):
            tn_checks = [c for c in all_checkpoints
                         if c["model"] == model and c["turn_number"] == tn]
            if not tn_checks:
                continue
            n = len(tn_checks)
            avg_orig = sum(c["n_parsed_original"] for c in tn_checks) / n
            avg_enh = sum(c["n_parsed_enhanced"] for c in tn_checks) / n
            gain = avg_enh - avg_orig
            print(f"    {model:25s}: orig={avg_orig:.1f} → enh={avg_enh:.1f}  "
                  f"(Δ={gain:+.1f})")

    # --- Phase 3: Sample responses where enhanced parser recovered items ---
    print(f"\n{'='*70}")
    print("PHASE 3: SAMPLE FORMAT_MISS RECOVERIES")
    print(f"{'='*70}")

    format_misses = [c for c in all_checkpoints
                     if c["classification"] == "FORMAT_MISS"]
    # Sample up to 3 per model
    by_model = defaultdict(list)
    for c in format_misses:
        by_model[c["model"]].append(c)

    for model in sorted(by_model.keys()):
        samples = by_model[model][:3]
        print(f"\n  {model}: ({len(by_model[model])} total FORMAT_MISS)")
        for s in samples:
            print(f"    {s['scenario_id']} T{s['turn_number']}: "
                  f"orig={s['n_parsed_original']} → enh={s['n_parsed_enhanced']}")
            # Show what was gained
            gained_items = set(s["assignment_enhanced"].keys()) - set(s["assignment_original"].keys())
            if gained_items:
                dom = P2_DOMAINS[s["domain"]]
                item_names = {it["id"]: it["name"] for it in dom["items"]}
                gained_names = [item_names.get(iid, iid) for iid in gained_items]
                print(f"      Recovered: {', '.join(gained_names)}")

    # --- Phase 3b: Sample REFUSAL responses (for manual verification) ---
    print(f"\n{'='*70}")
    print("PHASE 3b: SAMPLE REFUSAL RESPONSES (first 200 chars)")
    print(f"{'='*70}")

    refusals = [c for c in all_checkpoints if c["classification"] == "REFUSAL"]
    by_model_ref = defaultdict(list)
    for c in refusals:
        by_model_ref[c["model"]].append(c)

    for model in sorted(by_model_ref.keys()):
        samples = by_model_ref[model][:2]
        print(f"\n  {model}: ({len(by_model_ref[model])} total REFUSAL)")
        for s in samples:
            # We need to get the actual response text — find it in results
            print(f"    {s['scenario_id']} T{s['turn_number']}: "
                  f"orig={s['n_parsed_original']}, enh={s['n_parsed_enhanced']}")

    # --- Write detailed output ---
    # Summary JSON
    summary = {
        "total_checkpoints_analyzed": len(all_checkpoints),
        "models": {},
    }
    for model in sorted(model_stats.keys()):
        ms = model_stats[model]
        total = ms["total_checkpoints"]
        if total == 0:
            continue
        summary["models"][model] = {
            "total_checkpoints": total,
            "original_parser": {
                "zero_parse": ms["original_zero"],
                "low_parse": ms["original_low"],
                "full_parse": ms["original_full"],
                "mean_items": round(ms["original_parse_total"] / total, 3),
            },
            "enhanced_parser": {
                "zero_parse": ms["enhanced_zero"],
                "low_parse": ms["enhanced_low"],
                "full_parse": ms["enhanced_full"],
                "mean_items": round(ms["enhanced_parse_total"] / total, 3),
            },
            "classifications": dict(ms["classifications"]),
            "format_miss_count": len(ms["format_miss_gains"]),
            "format_miss_avg_gain": (
                round(sum(ms["format_miss_gains"]) / len(ms["format_miss_gains"]), 2)
                if ms["format_miss_gains"] else 0
            ),
        }

    summary_path = os.path.join(output_dir, "p2_parser_diagnostic_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n\nSummary written to: {summary_path}")

    # Detailed per-checkpoint JSON (for further analysis)
    # Exclude actual response text (too large), keep assignments
    detail_records = []
    for c in all_checkpoints:
        record = {
            "scenario_id": c["scenario_id"],
            "model": c["model"],
            "turn_number": c["turn_number"],
            "domain": c["domain"],
            "n_parsed_original": c["n_parsed_original"],
            "n_parsed_enhanced": c["n_parsed_enhanced"],
            "parse_gain": c["parse_gain"],
            "classification": c["classification"],
            "response_length": c["response_length"],
        }
        detail_records.append(record)

    detail_path = os.path.join(output_dir, "p2_parser_checkpoint_details.json")
    with open(detail_path, "w") as f:
        json.dump(detail_records, f, indent=2)
    print(f"Details written to: {detail_path}")

    # Save enhanced assignments for re-scoring
    enhanced_assignments_path = os.path.join(output_dir, "p2_enhanced_assignments.json")
    enhanced_data = []
    for c in all_checkpoints:
        enhanced_data.append({
            "scenario_id": c["scenario_id"],
            "model": c["model"],
            "turn_number": c["turn_number"],
            "assignment_original": c["assignment_original"],
            "assignment_enhanced": c["assignment_enhanced"],
            "classification": c["classification"],
        })
    with open(enhanced_assignments_path, "w") as f:
        json.dump(enhanced_data, f, indent=2)
    print(f"Enhanced assignments written to: {enhanced_assignments_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="P2 Parser Diagnostic & Enhanced Parser")
    parser.add_argument(
        "--results-dir", required=True,
        help="Directory containing model results (results/{model}/P2_*.json)")
    parser.add_argument(
        "--scenarios-dir", required=True,
        help="Directory containing P2 scenario files (P2_*.json)")
    parser.add_argument(
        "--output-dir", default="./p2_parser_analysis",
        help="Output directory for diagnostic results")
    args = parser.parse_args()

    run_analysis(args.results_dir, args.scenarios_dir, args.output_dir)