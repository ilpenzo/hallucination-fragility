#!/usr/bin/env python3
"""Rubric-based classification of incompatibility claims in P2 responses (round-2 protocol, decision 3).

Scope: the 400 T15 and T17 responses of the February 2026 core run (5 models x 40 scenarios x 2 turns).
The classifier sees ONLY the visible answer text (reasoning tags removed; model identity, scenario id, and verified
feasibility are hidden). Labels are keyed by batch tag + content hash of the response, so labels from one batch can
never be reused for another batch (replication or contemporary runs must be classified and validated separately).
Each label must carry a verbatim quote from the visible answer; quotes are verified and unverifiable quotes are
re-queried once, then marked quote_verified=false (treated as UNCLEAR downstream).
It labels the VISIBLE claim, not whether the claim is correct. Rubric (frozen 2026-09-17):

  Question: Does the final visible answer assert that the active requirements are incompatible, i.e. that they
  cannot all be satisfied together (equivalently: that no valid complete plan can satisfy every requirement)?
  Answer YES only for an explicit, unretracted assertion of joint incompatibility of requirements.
  Answer NO for: negated statements ("no conflicts"); statements that the current/previous arrangement must change;
  unassigned or unplaced items; promises to check for conflicts; hedged possibilities ("may", "potential") without a
  definite claim; warnings retracted by a later explicit all-satisfied conclusion; conflicts with an obsolete
  placement rather than with requirements.
  Answer UNCLEAR when the wording does not allow a confident YES or NO.
  Provide the single quote (verbatim, <= 200 chars) that best supports your label.

Output: outputs/incompatibility_llm_labels.json (resume-safe), one record per response with label, quote, and raw
JSON. Validation against the AI-review packets (60 + 30 cases) is reported separately by
validate_incompatibility_labels.py. Requires ANTHROPIC_API_KEY. Estimated cost with claude-opus-4-6:
~400 x (1.2K in + 0.1K out) => ~$3.5; use --model claude-sonnet-4-6 for ~ $0.7.
Usage: python classify_incompatibility_llm.py [--model claude-opus-4-6] [--dry-run] [--limit N]
"""
import argparse, glob, json, hashlib, random, sys, time, collections
from common import *
sys.path.insert(0, SCORING_DIR); import p2_rescore as R
RUBRIC = __doc__.split('Rubric (frozen 2026-09-17):')[1].split('Output:')[0].strip()
PROMPT = ("You are labelling a single assistant response from a multi-turn scheduling conversation. The user had been adding "
          "requirements over several turns. Read the response and apply the rubric exactly.\n\nRUBRIC\n" + RUBRIC +
          "\n\nRespond ONLY with JSON: {\"label\": \"YES\"|\"NO\"|\"UNCLEAR\", \"quote\": \"...\", \"rationale\": \"one sentence\"}\n\nRESPONSE TO LABEL:\n<<<\n{response}\n>>>")
ap = argparse.ArgumentParser(); ap.add_argument('--model', default='claude-opus-4-6'); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--limit', type=int, default=None); ap.add_argument('--results-dir', default=RESULTS); ap.add_argument('--batch', default='core_feb2026')
args = ap.parse_args()
import re
def visible(text):  # final visible answer: strip reasoning tags
    return re.sub(r'<think>.*?</think>', '', text or '', flags=re.S).strip()
def norm(t): return re.sub(r'\s+', ' ', re.sub(r'[*_`>#]', '', t or '')).strip().lower()
items = []
for f in sorted(glob.glob(os.path.join(args.results_dir, '*', 'P2_*.json'))):
    d = load(f)
    for t in d['turns']:
        if int(t['turn_number']) in (15, 17):
            text = visible(t.get('response', ''))
            chash = hashlib.sha256(text.encode()).hexdigest()[:16]
            items.append({'id': hashlib.sha1(f"{args.batch}|{d['model']}|{d['scenario_id']}|{t['turn_number']}|{chash}".encode()).hexdigest()[:16], 'batch': args.batch, 'content_hash': chash, 'model': d['model'], 'scenario': d['scenario_id'], 'turn': int(t['turn_number']), 'response': text})
random.Random(7).shuffle(items)           # hide model/scenario ordering from the classifier session
out_path = os.path.join(OUT, f'incompatibility_llm_labels_{args.batch}.json')
done = {r['id']: r for r in load(out_path)['records']} if os.path.exists(out_path) else {}
print(f'{len(items)} responses; {len(done)} already labelled; model={args.model}; dry_run={args.dry_run}')
if args.limit: items = items[:args.limit]
if not args.dry_run:
    import anthropic; client = anthropic.Anthropic()
n_new = 0
for it in items:
    if it['id'] in done: continue
    if args.dry_run: continue
    msg = PROMPT.replace('{response}', it['response'][:12000]); js = None; raw = None; verified = False
    for attempt in range(6):
        try:
            extra = '' if attempt < 2 else '\n\nYour previous quote could not be found verbatim in the response. Copy the quote exactly as it appears.'
            resp = client.messages.create(model=args.model, max_tokens=300, temperature=0, messages=[{'role': 'user', 'content': msg + extra}])
            raw = resp.content[0].text.strip(); cand = json.loads(raw[raw.find('{'): raw.rfind('}') + 1])
            if cand.get('label') not in ('YES', 'NO', 'UNCLEAR'): raise ValueError('bad label')
            q = cand.get('quote') or ''
            verified = bool(q) and (norm(q) in norm(it['response']))
            js = cand
            if verified or cand['label'] == 'UNCLEAR' or attempt >= 3: break
        except Exception as e:
            js = None; time.sleep(3 * (attempt + 1))
    label = (js or {}).get('label')
    rec = {'id': it['id'], 'batch': it['batch'], 'content_hash': it['content_hash'], 'model': it['model'], 'scenario': it['scenario'], 'turn': it['turn'],
           'label': label, 'quote': (js or {}).get('quote'), 'quote_verified': verified, 'effective_label': (label if (verified or label == 'UNCLEAR') else 'UNCLEAR'),
           'rationale': (js or {}).get('rationale'), 'classifier': args.model, 'raw': raw if js else None}
    done[it['id']] = rec; n_new += 1
    if n_new % 25 == 0:
        json.dump({'rubric': RUBRIC, 'classifier': args.model, 'batch': args.batch, 'records': list(done.values())}, open(out_path, 'w'), indent=1)
json.dump({'rubric': RUBRIC, 'classifier': args.model, 'batch': args.batch, 'visible_answer_only': True, 'hidden_fields': ['model', 'scenario', 'feasibility'], 'records': list(done.values())}, open(out_path, 'w'), indent=1)
recs = list(done.values()); print('labels:', collections.Counter(r['effective_label'] for r in recs), '| quotes verified:', sum(r['quote_verified'] for r in recs), '/', len(recs))
print('labelled new:', n_new, '-> ', out_path)
