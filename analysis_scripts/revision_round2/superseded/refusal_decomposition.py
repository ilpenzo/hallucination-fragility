"""R3 comment 1 (mechanism): decompose post-conflict (T17) constraint satisfaction by the kind of output the
model produced: a full plan, a plan the rigid parser missed, a minimal plan, or a refusal to produce a plan."""
import glob, sys, collections
from common import *
sys.path.insert(0, ROOT); import p2_rescore as R
scen = R.load_scenarios(os.path.join(ROOT, 'p2_scenarios')); resp = {}
for f in glob.glob(os.path.join(ROOT, 'results', '*', 'P2_*.json')):
    d = load(f)
    for t in d['turns']: resp[(d['model'], d['scenario_id'], int(t['turn_number']))] = t.get('response', '') or ''
assign = load(ASSIGN); sat = {}; cls = {}
for a in assign:
    s = scen[a['scenario_id']]; turn = next(t for t in s['turns'] if int(t['turn_number']) == int(a['turn_number']))
    r = R.score_checkpoint(a['assignment_enhanced'] or {}, s, turn, resp[(a['model'], a['scenario_id'], int(a['turn_number']))], s.get('domain') or s.get('domain_key'))
    k = (a['model'], a['scenario_id'], int(a['turn_number'])); sat[k] = r['satisfaction_rate']; cls[k] = a['classification']
out = {}; md = '| Model | Turn | Refusals | Minimal | Format-miss | Full plan | Mean sat. (all) | Mean sat. excl. refusals | Mean sat. of full plans | Scenarios with sat<=0.1 (of which refusals) |\n|---|---|---|---|---|---|---|---|---|---|\n'
for m in MODELS:
    for t in (17, 20):
        keys = [(m, s, t) for s in scen]; byc = collections.defaultdict(list)
        for k in keys: byc[cls[k]].append(sat[k])
        allv = [sat[k] for k in keys]; non = [sat[k] for k in keys if cls[k] != 'REFUSAL']; full = byc.get('FULL_PARSE', [])
        low = [k for k in keys if sat[k] <= 0.1]; lowref = [k for k in low if cls[k] == 'REFUSAL']
        rec = {'refusal': len(byc.get('REFUSAL', [])), 'minimal': len(byc.get('MINIMAL', [])), 'format_miss': len(byc.get('FORMAT_MISS', [])), 'full': len(full), 'ambiguous': len(byc.get('AMBIGUOUS', [])),
               'mean_all': sum(allv) / len(allv), 'mean_excl_refusal': sum(non) / len(non), 'mean_full_plans': (sum(full) / len(full)) if full else None, 'mean_by_class': {c: sum(v) / len(v) for c, v in byc.items()}, 'n_low': len(low), 'n_low_refusal': len(lowref)}
        out[f'{m}|T{t}'] = rec
        full_txt = '-' if rec['mean_full_plans'] is None else f"{rec['mean_full_plans']:.3f}"
        md += f"| {LABELS[m]} | T{t} | {rec['refusal']} | {rec['minimal']} | {rec['format_miss']} | {rec['full']} | {rec['mean_all']:.3f} | {rec['mean_excl_refusal']:.3f} | {full_txt} | {rec['n_low']} ({rec['n_low_refusal']}) |\n"
print(md); save('refusal_decomposition', out, md)
