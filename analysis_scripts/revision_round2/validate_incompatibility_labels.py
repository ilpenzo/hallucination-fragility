"""Agreement of the LLM incompatibility labels with the AI-review packets (60 tuning cases + 30 fresh cases),
active-set scope, and derived flag/false-alarm rates by verified feasibility at T15 and T17."""
import json, collections
from common import *
import sys as _s
BATCH = _s.argv[1] if len(_s.argv) > 1 else 'core_feb2026'
lab = {(r['model'], r['scenario'], r['turn']): dict(r, label=r.get('effective_label', r.get('label'))) for r in load(os.path.join(OUT, f'incompatibility_llm_labels_{BATCH}.json'))['records']}
cls = load(os.path.join(OUT, 'p2_feasibility_classes.json'))
aud = json.load(open(os.path.join(AI_REVIEW, 'packet_verdicts_20260917.json')))
ref = {}; src = {}
for c in aud['conflict']:
    v = c.get('assistant_verdict_active_set_incompatibility_asserted')
    if v is not None: ref[(c['model'], c['scenario'], c['turn'])] = v; src[(c['model'], c['scenario'], c['turn'])] = 'first_packet'
AUD = AI_REVIEW
try:
    fresh = json.load(open(os.path.join(AUD, 'protocol_rebuild_ai_verdicts_20260917.json')))
    sample = load(os.path.join(OUT, 'conflict_detection_v3_fresh_sample.json'))     # packet case i == sample[i-1]
    for c in fresh.get('fresh_detector', []):
        v = c.get('ai_verdict_active_set_incompatibility_asserted'); i = c.get('packet_case')
        if v is not None and i and i <= len(sample):
            r = sample[i - 1]; ref[(r['model'], r['scenario'], r['turn'])] = v; src[(r['model'], r['scenario'], r['turn'])] = 'fresh_packet'
    for c in fresh.get('previously_ambiguous', []):
        v = c.get('ai_verdict_active_set_incompatibility_asserted')
        if v is not None: ref[(c['model'], c['scenario'], c['turn'])] = v; src[(c['model'], c['scenario'], c['turn'])] = 'first_packet'
except Exception as e:
    print('fresh verdicts not loaded:', e)
print('reference labels (AI review, active-set scope):', len(ref))
agree = n = unclear = 0; dis = []; by_src = collections.defaultdict(lambda: [0, 0, 0])   # agree, decided, unclear
for k, v in ref.items():
    r = lab.get(k)
    if not r: continue
    n += 1
    if r['label'] == 'UNCLEAR': unclear += 1; by_src[src[k]][2] += 1; continue
    by_src[src[k]][1] += 1; by_src[src[k]][0] += (r['label'] == 'YES') == v
    if (r['label'] == 'YES') == v: agree += 1
    else: dis.append({'case': k, 'llm': r['label'], 'ai_review': v, 'quote': r['quote']})
print(f'LLM labels vs AI-review reference: {agree}/{n - unclear} agree on decided cases; {unclear} UNCLEAR; {len(dis)} disagreements')
for k_, v_ in by_src.items(): print(f'  {k_}: {v_[0]}/{v_[1]} agree; {v_[2]} UNCLEAR')
rates = collections.defaultdict(lambda: [0, 0, 0])
for (m, sid, tn), r in lab.items():
    c = cls.get(f'{sid}|T{tn}') or cls.get(f'{sid}|T17'); k = (m, c, tn); rates[k][0] += 1; rates[k][1] += r['label'] == 'YES'; rates[k][2] += r['label'] == 'UNCLEAR'
md = '| Model | Feasibility at that turn | Turn | n | YES / decided | UNCLEAR (excluded) |\n|---|---|---|---|---|---|\n'
for (m, c, tn), (a, b, u) in sorted(rates.items()): md += f'| {LABELS.get(m, m)} | {c} | T{tn} | {a} | {b}/{a - u} = {b/(a - u):.2f} | {u} |\n'
print(md); save('incompatibility_rates', {'agreement': {'agree': agree, 'decided': n - unclear, 'unclear': unclear, 'by_reference_packet': {k_: {'agree': v_[0], 'decided': v_[1], 'unclear': v_[2]} for k_, v_ in by_src.items()}, 'reference_status': 'AI review (not human validation)', 'disagreements': dis}, 'rates': {f'{m}|{c}|T{tn}': {'n': a, 'yes': b, 'unclear': u} for (m, c, tn), (a, b, u) in rates.items()}}, md)
