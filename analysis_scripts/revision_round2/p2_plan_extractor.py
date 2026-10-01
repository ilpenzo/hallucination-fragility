"""Block-scoped P2 plan extractor (round-2 protocol, decision 1; revision b, 2026-09-18).

Revision b fixes three verified false negatives of the first release: (1) code fences were counted as blank
lines and could end a block before its first slot line; (2) a plan heading followed by a short lead-in sentence
or carrying two adjectives / a parenthetical ("Updated Plan (with conflict flagged):") yielded an empty block;
(3) when every headed block was empty, un-headed plan listings were never considered; (4) the abbreviation
"HR" was not recognised as the item "Human Resources"; (5) slot names written without their space ("Week1")
were not recognised. Every extraction that
changed between the two releases is listed in outputs/plan_extraction_revision_b_changes.md.

Extracts assignments ONLY from the model's explicitly proposed current plan: a plan block introduced by a plan
heading (Current/Updated/Final/Revised/Proposed Plan, "Here is the ... plan", "Plan:") or, failing that, the last
contiguous run of slot-assignment lines. Within a block, a line assigns items to a slot if it is
"<slot> : <items>", "<slot> -> <items>", a table row "| <slot> | <items> |", or a bulleted item line directly
under a bare slot header. Items on an "Unassigned:" line are recorded as unassigned and never inferred.
Nothing is read from constraint recaps, verification lists, reasoning text, or superseded plans (the last
plan block wins). Reasoning tags (<think>...</think>) are removed first.

Outputs: assignment, unassigned set, label in {no_plan, partial_plan, complete_plan, no_usable_plan}, flags
(duplicate_placement, assigned_and_unassigned, unknown_slot_cell), the source span, and whether the model asks
the user to resolve conflicting requirements.
"""
import re, sys, os
from common import *
sys.path.insert(0, SCORING_DIR); import p2_rescore as R

PLAN_HEAD = re.compile(r'^\s*(?:#+\s*)?(?:\*{0,2})?\s*(?:here(?:\'s| is| are)\s+(?:the|my|an?|our)?\s*)?(?:(?:current|updated|final|revised|complete|proposed|new|corrected|resulting)\s+){0,2}(?:schedule|plan|assignment)s?\s*(?:\([^)]*\))?\s*(?:\*{0,2})?\s*:?\s*(?:\*{0,2})?\s*$', re.I)
PLAN_HEAD_INLINE = re.compile(r'^\s*(?:#+\s*)?\**\s*(?:current|updated|final|revised|complete|proposed|new)\s+plan\s*\**\s*:', re.I)
EMPTY_TOKENS = re.compile(r'^\s*(?:\[?\s*(?:empty|none|nothing|n/?a|tbd|-|—|–|\(none\)|\(empty\)|\(available\))\s*\]?\s*)+$', re.I)
RESOLVE_REQ = re.compile(r'(which (?:constraint|requirement|one)s? (?:should|would|do you want|to)|please (?:clarify|confirm|let me know|advise|specify)|let me know (?:which|how)|let me know if [^.!?\n]{0,80}(?:conflict|constraint|requirement|relax|priorit)|could you (?:clarify|confirm)|how would you like|which (?:should|would you like) (?:me )?to (?:relax|drop|prioriti|remove|override)|need (?:you|your) (?:to )?(?:decide|guidance|clarification|input)|which(?: \w+)? (?:would|should) (?:you|i|we|\w+ \w+ be)\b[^?\n]{0,80}\?|would you like (?:me )?to (?:resolve|remove|update|relax|drop|override|prioriti)|would you like (?:me )?to [^?\n]{0,120}(?:conflict|constraint|violation|requirement|capacit)[^?\n]{0,80}\?|how should (?:i|we|the|these|this)\b[^?\n]{0,80}(?:resolv|handl|proceed|prioriti)[^?\n]{0,40}\?|should i (?:update|remove|relax|drop|override|prioriti|treat)[^?\n]{0,100}\?)', re.I)   # revision b adds the question forms after "input))"

VERIFY_LABEL = re.compile(r'\b(verif\w*|checks?|checking|validat\w*|recap|summary|status|analysis|notes?|conflicts?|violations?|issues?|usage|utili[sz]ation|reasoning|explanation|options?|alternatives?|working|steps?|fixed assignments?)\b', re.I)
NO_PLAN_STATEMENT = re.compile(r"\b(cannot|can\s*not|can't|can’t|unable|impossible|not possible|no (?:valid|feasible|complete) (?:plan|solution|assignment|schedule))\b", re.I)
LEAD_IN_MAX = 3   # non-plan lines tolerated between a plan heading and its first slot line

def _is_markup_only(line):
    return bool(line.strip()) and not re.sub(r'[`*_#>\-=|:\s]', '', line)

def _clean(line):
    line = re.sub(r'[\U0001F300-\U0001FAFF☀-➿✀-➿️‍]', '', line)
    line = re.sub(r'\*{1,3}|_{1,3}|`', '', line)
    return line.strip()

WORD_ALIASES = {'human resources': ['hr']}   # the one standard abbreviation among the 40 item names; whole-word match only

def _find_items(text, item_map):
    found = []
    low = text.lower()
    for name, iid in sorted(item_map.items(), key=lambda kv: -len(kv[0])):
        if name in low: found.append(iid); low = low.replace(name, ' '); continue
        for al in WORD_ALIASES.get(name, []):
            if re.search(r'\b' + re.escape(al) + r'\b', low): found.append(iid); low = re.sub(r'\b' + re.escape(al) + r'\b', ' ', low); break
    return found

def _match_slot(text, slot_map):
    t = re.sub(r'^(?:[\-\*\+•]\s+|\d+[\.\)]\s+)', '', _clean(text)).strip().lower()
    t = re.sub(r'\s*\(.*?\)\s*', ' ', t).strip()
    if t in slot_map: return slot_map[t]
    for name, sid in sorted(slot_map.items(), key=lambda kv: -len(kv[0])):
        if t.startswith(name) or t == name: return sid
    tn = t.replace(' ', '')                       # "Week1", "Day 1" written without the space
    for name, sid in sorted(slot_map.items(), key=lambda kv: -len(kv[0])):
        if tn.startswith(name.replace(' ', '')): return sid
    return None

def _name_maps(domain_key):
    dom = R.P2_DOMAINS[domain_key]
    return {i['name'].lower(): i['id'] for i in dom['items']}, {s['name'].lower(): s['id'] for s in dom['slots']}, [i['id'] for i in dom['items']]

def _parse_line(line, item_map, slot_map):
    """Return ('slot', slot_id, items_text) | ('unassigned', items_text) | ('table', slot_id, items_text) | None."""
    raw = line; c = _clean(line)
    if not c: return None
    if c.startswith('|'):
        cells = [x.strip() for x in c.strip('|').split('|')]
        if len(cells) >= 2 and not set(''.join(cells)) <= set('-: '):
            sid = _match_slot(cells[0], slot_map)
            if sid: return ('table', sid, ' '.join(cells[1:]))
            if cells[0].lower().startswith('unassigned'): return ('unassigned', ' '.join(cells[1:]))
        return None
    m = re.match(r'^(?:[\-\*\+•]\s+|\d+[\.\)]\s+|#+\s+)?(.+?)\s*(?::|→|➜|➡|=>|->)\s*(.*)$', c)
    if m:
        head, rest = m.group(1), m.group(2)
        if head.strip().lower().startswith('unassigned'): return ('unassigned', rest)
        sid = _match_slot(head, slot_map)
        if sid: return ('slot', sid, rest)
    return None

def extract_plan(text, domain_key):
    item_map, slot_map, all_items = _name_maps(domain_key)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.S)
    lines = text.split('\n')
    # candidate block starts: plan headings
    starts = [i for i, l in enumerate(lines) if PLAN_HEAD.match(_clean(l)) or PLAN_HEAD_INLINE.match(l)]
    blocks = []
    def collect(start, inline_rest=None, headed=False):
        assignment, unassigned, flags, order = {}, set(), set(), []
        i = start; last_slot = None; consumed = 0; blank_run = 0; seen_slots = set(); lead_in = 0
        if inline_rest is not None and inline_rest.strip() and not _is_markup_only(inline_rest):
            lines_iter = [inline_rest] + lines[start + 1:]
        else:
            lines_iter = lines[start + 1:]
        for k, l in enumerate(lines_iter):
            p = _parse_line(l, item_map, slot_map)
            if p is None:
                if _is_markup_only(l): continue   # code fences, rules, table separators: formatting, not blank lines
                c = _clean(l)
                if not c:
                    blank_run += 1
                    if blank_run > 2: break
                    continue
                if c in ('```', '---', '***') or re.fullmatch(r'[\-\|:\s=]+', c):
                    continue   # formatting / table separator lines never end a block
                if c.startswith('|') and not seen_slots:
                    continue   # table header row before the first slot row
                # bulleted item line under a bare slot header
                if last_slot and re.match(r'^(?:[\-\*\+•]\s+|\d+[\.\)]\s+)', c) and not re.search(r':|→|->|=>', c):
                    its = _find_items(c, item_map)
                    if its:
                        for it in its:
                            if it in assignment and assignment[it] != last_slot: flags.add('duplicate_placement')
                            assignment.setdefault(it, last_slot)
                        consumed = k; continue
                if headed and not seen_slots and not assignment and not unassigned and lead_in < LEAD_IN_MAX and not NO_PLAN_STATEMENT.search(c) and not (len(c.split()) <= 6 and VERIFY_LABEL.search(c)):
                    lead_in += 1; blank_run = 0; continue   # short lead-in between the heading and the plan ("Assuming ...:")
                break   # any other line ends the block
            blank_run = 0
            if p[0] == 'unassigned':
                for it in _find_items(p[1], item_map): unassigned.add(it)
                last_slot = None; consumed = k; continue
            sid, rest = p[1], p[2]
            if sid in seen_slots and p[0] == 'slot' and rest.strip() and not EMPTY_TOKENS.match(rest):
                # a second listing of the same slot in one block: treat as a new block (superseded plan)
                break
            seen_slots.add(sid); last_slot = sid; consumed = k
            rest_wo_paren = re.sub(r'\([^)]*\)', ' ', rest)
            if EMPTY_TOKENS.match(rest_wo_paren) or not rest_wo_paren.strip(): continue
            for it in _find_items(rest_wo_paren, item_map):
                if it in assignment and assignment[it] != sid: flags.add('duplicate_placement')
                assignment.setdefault(it, sid)
        return assignment, unassigned, flags, (start, start + 1 + consumed), seen_slots
    for s in starts:
        m = PLAN_HEAD_INLINE.match(lines[s]); rest = lines[s].split(':', 1)[1] if m else None
        a, u, f, span, seen = collect(s, rest, headed=True)
        blocks.append((a, u, f, span, seen))
    def label_above(i):
        for j in range(i - 1, max(-1, i - 7), -1):
            c = _clean(lines[j])
            if not c or _is_markup_only(lines[j]) or c.startswith('|'): continue
            if _parse_line(lines[j], item_map, slot_map): continue
            return c
        return ''
    if blocks and not any(b[0] or b[1] for b in blocks):
        # every headed block is empty (e.g. "# Current Plan" followed by sub-sections): use the last un-headed run of
        # >=3 distinct slot lines that assigns items and does not sit under a verification / options label
        i = 0; runs = []
        while i < len(lines):
            p = _parse_line(lines[i], item_map, slot_map)
            if p and p[0] in ('slot', 'table'):
                a, u, f, span, seen = collect(i - 1, None) if i > 0 else collect(-1, None)
                lab = label_above(i)
                if len(seen) >= 3 and a and not (len(lab.split()) <= 6 and VERIFY_LABEL.search(lab)) and not NO_PLAN_STATEMENT.search(lab): runs.append((a, u, f, span, seen))
                i = max(span[1], i + 1)
            else: i += 1
        blocks = blocks + runs
    if not blocks:
        # fallback: last maximal run of >=3 distinct slot lines without a heading
        i = 0; runs = []
        while i < len(lines):
            p = _parse_line(lines[i], item_map, slot_map)
            if p and p[0] in ('slot', 'table'):
                a, u, f, span, seen = collect(i - 1, None) if i > 0 else collect(-1, None)
                if len(seen) >= 3: runs.append((a, u, f, span, seen))
                i = max(span[1], i + 1)
            else: i += 1
        blocks = runs
    if not blocks:
        return {'assignment': {}, 'unassigned': [], 'label': 'no_plan', 'flags': [], 'span': None, 'span_coordinates': None, 'requests_resolution': bool(RESOLVE_REQ.search(text))}
    # the last (final, unretracted) plan wins; prefer blocks that actually assign or list items over
    # trailing slot-like lists (e.g. capacity checks) that name slots but no items
    with_items = [b for b in blocks if b[0] or b[1]]
    with_slots = [b for b in blocks if b[4]]
    a, u, f, span, seen = (with_items or with_slots or blocks)[-1]
    if not a and not u and not seen:
        return {'assignment': {}, 'unassigned': [], 'label': 'no_plan', 'flags': [], 'span': span, 'span_coordinates': 'lines of the response after removing <think>...</think> blocks', 'requests_resolution': bool(RESOLVE_REQ.search(text))}
    f = set(f)
    both = [it for it in a if it in u]
    if both:
        f.add('assigned_and_unassigned')
        for it in both: a.pop(it)
    n = len(a)
    if n == len(all_items): label = 'complete_plan'          # coverage of all items; validity is judged separately
    elif n > 0: label = 'partial_plan'
    else: label = 'no_usable_plan'                             # slots named or every item unassigned, but no assignment
    return {'assignment': a, 'unassigned': sorted(u), 'label': label, 'flags': sorted(f), 'span': span, 'span_coordinates': 'lines of the response after removing <think>...</think> blocks',
            'requests_resolution': bool(RESOLVE_REQ.search(text))}


def stripped_lines(text):
    """The line list that span indices refer to (reasoning tags removed)."""
    return re.sub(r'<think>.*?</think>', '', text, flags=re.S).split('\n')
