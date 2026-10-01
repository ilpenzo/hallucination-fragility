"""Incompatibility-claim detector v3 (round-2 protocol, decision 3).

Rubric: a response is FLAGGED if its final visible answer asserts that active requirements are incompatible
(cannot all be satisfied / no valid plan exists / requirement X conflicts with requirement Y). It is NOT flagged
for: negated statements ("no conflicts"), statements that the current arrangement must change, unassigned items,
prospective promises to check for conflicts, hedged possibilities ("potential", "may", "might"), warnings that are
later retracted by an explicit all-satisfied conclusion, or reasoning-only text (<think> blocks; MiniMax-style
"The user wants me to..." preambles are handled by preferring statements after the last plan block).

Two scopes are returned: 'active_set' (any incompatibility assertion) and 'trap_specific' (the assertion sentence
names an item of the T15 requirement). The last verdict-bearing sentence wins when assertions and denials coexist.
"""
import re, sys
from common import *
sys.path.insert(0, SCORING_DIR); import p2_rescore as R

DENY = re.compile(r"\b(no|zero)\s+(?:new\s+|direct\s+|further\s+|remaining\s+|additional\s+|other\s+)?(?:conflict|contradiction|incompatibilit|violation)s?\b|\b(?:not|never|don't|doesn't|does not|do not)\s+(?:directly\s+|actually\s+)?(?:conflict|contradict)|\bconflict-?free\b|\ball(?: \d+)?(?: of the)? (?:constraints|requirements) (?:are|remain|have been|were) (?:now )?(?:fully |still )?(?:satisfied|met|compatible|mutually satisfiable|consistent)\b|\bwithout (?:any )?conflict|\bno (?:valid )?conflict|(?<!until )(?<!once )(?<!unless )(?<!after )(?<!when )(?<!if )\bconflict[s]? (?:is|are|has been|have been) (?:now )?resolved\b|\bmutually satisfiable\b|\bcan all be satisfied\b|\bthere (?:is|are) no (?:conflict|contradiction|incompatib)", re.I)
ASSERT = re.compile(r"\b(?:conflict detected|conflicts? (?:detected|identified|found|exists?|arises?)|(?:direct|genuine|fundamental|unresolvable|irreconcilable|hard|true|real|logical)\s+conflict|conflicts? with|in conflict|contradict(?:s|ion|ory)|incompatible|impossible to (?:satisfy|create|produce|build|construct|generate|schedule|place|meet|accommodate|assign|fit)|(?:is|are|becomes?|makes? (?:it|this|them))\s+(?:mathematically |logically |simply )?impossible|cannot (?:be )?(?:all |both |simultaneously )?(?:be )?(?:satisfied|met|accommodated|coexist|reconciled|fulfilled)|cannot (?:both|all) be|mutually exclusive|no (?:valid|feasible|possible) (?:plan|schedule|assignment|arrangement)|(?:no|not) (?:possible|feasible) to satisfy|(?:is|are) (?:not|un)satisfiable|violates?|violation of|cannot be (?:fully )?(?:honou?red|respected)|cannot satisfy (?:all|both|every))", re.I)
HEDGE = re.compile(r"\b(potential|possible|may|might|could|would|if|unless|check(?:ing)? for|watch for|flag any|will flag|were to)\b", re.I)
PLAN_RELATIVE = re.compile(r"\b(current (?:plan|arrangement|schedule|placement)|previous(?:ly)? (?:plan|placed|assigned|scheduled)|earlier (?:plan|placement)|needs? to (?:be )?(?:moved|changed|updated|rescheduled|relocated|reassigned)|must (?:now )?(?:be )?(?:moved|rescheduled|relocated)|no longer (?:valid|satisfied|holds)|conflicts? with the (?:available|remaining|current) (?:time blocks?|slots?|sprints?|weeks?|floors?|days?)|(?:remaining|unassigned) (?:items?|sessions?|features?|candidates?|teams?|activities) (?:cannot|can't) (?:be )?(?:fit|placed|assigned))\b", re.I)

def _sentences(text):
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.S)
    text = re.sub(r'\*{1,3}|_{1,3}|`', '', text)
    parts = re.split(r'(?<=[.!?])\s+|\n+', text)
    return [p.strip() for p in parts if p.strip()]

def classify(text, trap_constraint=None, domain_key=None):
    sents = _sentences(text)
    trap_names = []
    if trap_constraint and domain_key:
        dom = R.P2_DOMAINS[domain_key]
        for k in ('item', 'item_a', 'item_b'):
            if k in trap_constraint: trap_names.append(next(i['name'].lower() for i in dom['items'] if i['id'] == trap_constraint[k]))
    verdicts = []   # (index, kind, trap_specific)
    for i, s in enumerate(sents):
        low = s.lower()
        if DENY.search(s): verdicts.append((i, 'deny', any(n in low for n in trap_names))); continue
        if re.search(r"\b(?:cannot|can't|must not|should not|shouldn't|won't|will not) conflict\b", s, re.I) and not re.search(r"conflict detected|incompatible|impossible", low): continue
        if ASSERT.search(s):
            if HEDGE.search(s) and not re.search(r'conflict detected|cannot (?:be )?(?:all |both )?(?:be )?satisfied|impossible to', low): continue
            if PLAN_RELATIVE.search(s) and not re.search(r'incompatible|contradict|cannot (?:be )?(?:all|both)|impossible|mutually exclusive|no (?:valid|feasible)', low): continue
            verdicts.append((i, 'assert', any(n in low for n in trap_names)))
    if not verdicts: return {'active_set': False, 'trap_specific': False, 'evidence': None}
    # last verdict wins for the active-set scope
    last = verdicts[-1]
    active = last[1] == 'assert'
    trap_specific = active and any(k == 'assert' and ts for _, k, ts in verdicts if _ >= 0) and last[2]
    ev = sents[last[0]][:200]
    return {'active_set': active, 'trap_specific': trap_specific, 'evidence': ev}
