"""Apply adjudicated P1 score corrections to the canonical post-fix scored file.

Provenance: the corrections in outputs/p1_adjudication_records.json originate from AI-assisted inspection of 22
selected extraction cases (2026-09-17). Each record carries `author_confirmed` (null until a human reviews it).
Mode is explicit:
  --mode ai_review   (default) apply all records; scores are labelled "AI-REVIEW OVERRIDE (provisional)".
  --mode author_confirmed  apply only records with author_confirmed == true; labelled "AUTHOR-CONFIRMED OVERRIDE".
Writes results/scored_full/scored_results_p1_adjudicated.json (P2 records are copied unchanged) and a Table 1
summary. The previous extraction is preserved under details.previous_extraction; the effective asserted answer,
absolute error and correctness fields are updated so the record is internally consistent. The original
`overall_accuracy` field is left untouched; a new `overall_accuracy_nonsynthesis` is added for every P1 record."""
import json, collections, argparse
from common import *
ap = argparse.ArgumentParser(); ap.add_argument('--mode', choices=['ai_review', 'author_confirmed'], default='ai_review'); args = ap.parse_args()
ovs = load(os.path.join(OUT, 'p1_adjudication_records.json'))['overrides']
if args.mode == 'author_confirmed': ovs = [o for o in ovs if o.get('author_confirmed') is True]
label = 'AI-REVIEW OVERRIDE (provisional): ' if args.mode == 'ai_review' else 'AUTHOR-CONFIRMED OVERRIDE: '
d = load(FIXED); key = {(o['model'], o['scenario'], int(o['turn'])): o for o in ovs}; applied = 0
for e in d:
    if e['paradigm'] != 'P1': continue
    for t in e['turn_scores']:
        k = (e['model'], e['scenario_id'], int(t['turn_number']))
        if k in key:
            o = key[k]; det = t.setdefault('details', {})
            det['previous_extraction'] = {'model_value': det.get('model_value'), 'is_close': det.get('is_close'), 'score': t.get('score'), 'reason': t.get('reason')}
            det['model_value'] = o['asserted_answer']; det['is_close'] = False
            det['abs_error'] = abs(float(o['asserted_answer']) - float(o['target'])) if o.get('asserted_answer') is not None else None
            t['score'] = o['new_score']; t['reason'] = label + o['reason'][:140]; t['adjudication'] = {'source': o['source'], 'author_confirmed': o.get('author_confirmed')}; applied += 1
    probes = [t['score'] for t in e['turn_scores'] if t.get('is_probe') and t.get('score') is not None and t['score'] >= 0]
    e['probe_accuracy'] = sum(probes) / len(probes) if probes else e['probe_accuracy']
    ph = collections.defaultdict(list)
    for t in e['turn_scores']:
        if t.get('score') is not None and t['score'] >= 0 and t.get('phase') != 'synthesis': ph[t['phase']].append(t['score'])
    for p, v in ph.items(): e['phase_accuracy'][p] = sum(v) / len(v)
    allv = [t['score'] for t in e['turn_scores'] if t.get('score') is not None and t['score'] >= 0 and t.get('phase') != 'synthesis']
    e['overall_accuracy_nonsynthesis'] = sum(allv) / len(allv)
out_path = ADJUDICATED
json.dump(d, open(out_path, 'w'), indent=1); print(f'mode={args.mode}: applied {applied} overrides ->', rel(out_path))
by = collections.defaultdict(list)
for e in d:
    if e['paradigm'] == 'P1': by[e['model']].append(e)
md = f'Mode: {args.mode}; overrides applied: {applied}\n\n| Model | Probe acc. | Lookup | Single | Multi | Corr. | Non-synthesis acc. |\n|---|---|---|---|---|---|---|\n'
for m in MODELS:
    L = by[m]; pa = sum(x['probe_accuracy'] for x in L) / len(L); ph = {p: sum(x['phase_accuracy'][p] for x in L) / len(L) for p in ('lookup', 'single_step', 'multi_step', 'correction')}
    md += f"| {LABELS[m]} | {pa:.3f} | {ph['lookup']:.3f} | {ph['single_step']:.3f} | {ph['multi_step']:.3f} | {ph['correction']:.3f} | {sum(x['overall_accuracy_nonsynthesis'] for x in L)/len(L):.3f} |\n"
print(md); save('p1_table1_after_overrides', {'mode': args.mode, 'applied': applied, 'table_md': md}, md)
