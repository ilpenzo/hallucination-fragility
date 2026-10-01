"""R2 comment 6: sensitivity of P1 accuracy to the numeric tolerance threshold.
Re-extracts every number from each raw P1 response (the any-number rule used by the final scorer)
and recomputes probe/overall accuracy at several relative tolerances, with and without the per-question
absolute tolerance. Non-numeric scoring types (quarter identification, top-k lists, correction
identification) keep their original scores. For the seven adjudicated responses (p1_adjudication_records.json,
AI review) the response's final asserted answer is used instead of the any-number rule, so the 1% row reproduces
Table 1. Also reports the distribution of relative errors over all single-valued numeric answers."""
import glob, re, collections, sys
from common import *
PRE = '--pre-adjudication' in sys.argv   # archive run: any-number rule for every response (the sweep before the seven adjudicated corrections)
resp = {}
for path in glob.glob(os.path.join(RESULTS, '*', 'P1_*.json')):
    d = load(path)
    for t in d.get('turns', []): resp[(d['model'], d['scenario_id'], int(t['turn_number']))] = t.get('response', '') or ''
def nums(text):
    clean = text.replace('$', '').replace(',', '').replace('%', '')
    return [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?', clean)]
fixed = load(FIXED); pcts = [0.001, 0.005, 0.01, 0.02, 0.05, 0.10]
adj_path = os.path.join(OUT, 'p1_adjudication_records.json')
ADJ = {(o['model'], o['scenario'], int(o['turn'])): o.get('asserted_answer') for o in load(adj_path)['overrides']} if (os.path.exists(adj_path) and not PRE) else {}
errs = []   # relative error of the scored answer, single-valued numeric questions
acc = {}
for e in fixed:
    if e['paradigm'] != 'P1': continue
    m = e['model']; sid = e['scenario_id']
    for t in e['turn_scores']:
        sc = t.get('score'); det = t.get('details') or {}
        if sc is None or sc < 0 or t.get('phase') == 'synthesis': continue
        numeric = ('is_close' in det) and (det.get('target_value') is not None)
        if numeric:
            tgt = float(det['target_value']); mm = re.search(r'±\s*([0-9.]+)', t.get('reason', '')); atol = float(mm.group(1)) if mm else 0.1
            ns = nums(resp[(m, sid, int(t['turn_number']))])
            k = (m, sid, int(t['turn_number']))
            if k in ADJ: ns = [float(ADJ[k])] if ADJ[k] is not None else []
            min_rel = min((abs(n - tgt) / abs(tgt) if tgt != 0 else float('inf')) for n in ns) if ns else float('inf')
            min_abs = min(abs(n - tgt) for n in ns) if ns else float('inf')
            errs.append(min_rel)
        for pct in pcts:
            for absmode in ('with_abs', 'no_abs'):
                ok = (1.0 if (min_rel <= pct or (absmode == 'with_abs' and min_abs <= atol)) else 0.0) if numeric else sc
                s = acc.setdefault((m, pct, absmode), [0, 0, 0, 0])
                if t.get('is_probe'): s[0] += ok; s[1] += 1
                s[2] += ok; s[3] += 1
out = {}; md = ''
for absmode in ('with_abs', 'no_abs'):
    md += f'\n### Probe accuracy ({absmode})\n| tolerance | ' + ' | '.join(LABELS[m] for m in MODELS) + ' | ranks |\n|---|' + '---|' * (len(MODELS) + 1) + '\n'
    for pct in pcts:
        probe = [acc[(m, pct, absmode)][0] / acc[(m, pct, absmode)][1] for m in MODELS]
        overall = [acc[(m, pct, absmode)][2] / acc[(m, pct, absmode)][3] for m in MODELS]
        out[f'{absmode}_{pct}'] = {'probe': dict(zip(MODELS, [round(v, 3) for v in probe])), 'overall': dict(zip(MODELS, [round(v, 3) for v in overall])), 'probe_ranks': dict(zip(MODELS, ranks_desc(probe)))}
        md += f'| {pct*100:g}% | ' + ' | '.join(f'{v:.3f}' for v in probe) + ' | ' + ','.join(f'{r:g}' for r in ranks_desc(probe)) + ' |\n'
n = len(errs); lt1 = sum(e < 0.01 for e in errs); mid = sum(0.01 <= e <= 0.5 for e in errs); gt50 = sum(e > 0.5 for e in errs)
out['relative_error_distribution'] = {'n_single_valued_numeric_answers': n, 'below_1pct': lt1, 'between_1_and_50pct': mid, 'above_50pct': gt50, 'adjudicated_answers_used': len(ADJ)}
md += f'\n### Relative error of the scored answer, {n} single-valued numeric answers\n- below 1%: {lt1} ({lt1/n:.1%}); 1% to 50%: {mid} ({mid/n:.1%}); above 50%: {gt50} ({gt50/n:.1%})\n'
print(md); save('tolerance_sweep_pre_adjudication' if PRE else 'tolerance_sweep', out, ('SUPERSEDED: sweep before the seven adjudicated corrections (archive).\n' if PRE else '') + md)
