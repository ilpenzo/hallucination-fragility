"""Exact source of the provisional negation-aware conflict detector ("v2") whose predictions were saved in
outputs/conflict_detection_audit_sample.json on 2026-09-17. Kept unchanged as evidence; superseded by
conflict_detector_v3.py after the audit found 10 definite disagreements in 56 judged cases.

Rule: split the response into sentences; a response is "flagged" if any sentence matches POS and does not match NEG.
Known failure modes (from the audit): sentences such as "no conflicts" concluding statements when another sentence
mentions a conflict; "needs changing"/"cannot keep the current arrangement" treated as incompatibility; reasoning-text
inclusion; promises to check for conflicts.
"""
import re
NEG = re.compile(r"\b(no|not|doesn't|does not|don't|without|isn't|is not|aren't|are not|zero)\b[^.\n]{0,40}\b(conflict|contradict|incompatib|impossib|violat)", re.I)
POS = re.compile(r"\b(conflict|contradict|incompatible|impossible|cannot (?:be )?(?:satisf|accommodat|both)|mutually exclusive|violat)", re.I)

def flagged_v2(text):
    sents = re.split(r'(?<=[.!?\n])\s+', text)
    pos = [s for s in sents if POS.search(s) and not NEG.search(s)]
    return len(pos) > 0, pos[:2]
