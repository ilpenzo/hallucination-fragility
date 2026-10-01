"""R3 comment 3 / R2 weakness 2: variance information for the main tables.
(1) scenario-bootstrap 95% CIs for P1 probe accuracy, P2 average and checkpoint satisfaction, P3 gap abstention
    and fabrication; (2) paired scenario-bootstrap stability of the rank inversions and of Kendall's W;
(3) run-to-run differences from the targeted replication (existing data)."""
import glob, random, sys, collections
from common import *
sys.path.insert(0, ROOT); import p2_rescore as R
random.seed(20260917); B = 2000
fixed = load(FIXED)
p1 = {m: {} for m in MODELS}; p2 = {m: {} for m in MODELS}
for e in fixed:
    if e['paradigm'] == 'P1': p1[e['model']][e['scenario_id']] = e['probe_accuracy']
    if e['paradigm'] == 'P2': p2[e['model']][e['scenario_id']] = e['avg_satisfaction_rate']
# per-checkpoint enhanced satisfaction, re-scored from the saved enhanced-parser assignments
scen = R.load_scenarios(os.path.join(ROOT, 'p2_scenarios')); resp = {}
for f in glob.glob(os.path.join(ROOT, 'results', '*', 'P2_*.json')):
    d = load(f)
    for t in d['turns']: resp[(d['model'], d['scenario_id'], int(t['turn_number']))] = t.get('response', '') or ''
cp = {m: collections.defaultdict(dict) for m in MODELS}
for a in load(ASSIGN):
    s = scen[a['scenario_id']]; turn = next(t for t in s['turns'] if int(t['turn_number']) == int(a['turn_number']))
    r = R.score_checkpoint(a['assignment_enhanced'] or {}, s, turn, resp[(a['model'], a['scenario_id'], int(a['turn_number']))], s.get('domain') or s.get('domain_key'))
    cp[a['model']][int(a['turn_number'])][a['scenario_id']] = r['satisfaction_rate']
p3 = {m: {} for m in MODELS}; p3f = {m: {} for m in MODELS}
for f in glob.glob(os.path.join(JUDGED, '*.json')):
    j = load(f); g = j['gap_scores']
    p3[j['model']][j['scenario_id']] = sum(v['abstained'] for v in g.values()) / len(g); p3f[j['model']][j['scenario_id']] = 1.0 if any(v['fabricated'] for v in g.values()) else 0.0
def ci(vals):
    n = len(vals); ms = sorted(sum(vals[random.randrange(n)] for _ in range(n)) / n for _ in range(B)); return sum(vals) / n, ms[int(.025 * B)], ms[int(.975 * B) - 1]
out = {'ci': {}}; md = '## Scenario-bootstrap 95% CIs\n| Metric | ' + ' | '.join(LABELS[m] for m in MODELS) + ' |\n|---|' + '---|' * len(MODELS) + '\n'
metrics = [('P1 probe accuracy', p1), ('P2 average satisfaction', p2), ('P2 T6 satisfaction', {m: cp[m][6] for m in MODELS}), ('P2 T11 satisfaction', {m: cp[m][11] for m in MODELS}),
           ('P2 T17 satisfaction', {m: cp[m][17] for m in MODELS}), ('P2 T20 satisfaction', {m: cp[m][20] for m in MODELS}), ('P3 gap abstention', p3), ('P3 fabrication rate', p3f)]
for name, data in metrics:
    out['ci'][name] = {}; cells = []
    for m in MODELS:
        mu, lo, hi = ci(list(data[m].values())); out['ci'][name][m] = {'mean': mu, 'lo': lo, 'hi': hi, 'n': len(data[m])}; cells.append(f'{mu:.3f} [{lo:.3f}, {hi:.3f}]')
    md += f'| {name} | ' + ' | '.join(cells) + ' |\n'
# paired rank stability
def kendall_w(rows):
    mm = len(rows); n = len(rows[0]); Rj = [sum(r[j] for r in rows) for j in range(n)]; Rm = sum(Rj) / n
    return 12 * sum((x - Rm) ** 2 for x in Rj) / (mm * mm * (n ** 3 - n))
s1 = sorted(p1[MODELS[0]]); s2 = sorted(p2[MODELS[0]]); s3 = sorted(p3[MODELS[0]]); cnt = collections.Counter(); Ws = []
mi, ds, ge, gp, so = (MODELS.index(x) for x in ('minimax-m2.5', 'deepseek-r1', 'gemini-2.5-pro', 'gpt-4o', 'claude-sonnet-4.5'))
for _ in range(B):
    b1 = [s1[random.randrange(len(s1))] for _ in s1]; b2 = [s2[random.randrange(len(s2))] for _ in s2]; b3 = [s3[random.randrange(len(s3))] for _ in s3]
    r1 = ranks_desc([sum(p1[m][s] for s in b1) / len(b1) for m in MODELS]); r2 = ranks_desc([sum(p2[m][s] for s in b2) / len(b2) for m in MODELS]); r3 = ranks_desc([sum(p3[m][s] for s in b3) / len(b3) for m in MODELS])
    cnt['MiniMax last on P1'] += r1[mi] == 5; cnt['MiniMax first on P3'] += r3[mi] == 1; cnt['MiniMax last on P1 AND first on P3'] += (r1[mi] == 5 and r3[mi] == 1)
    cnt['DeepSeek first on P2'] += r2[ds] == 1; cnt['DeepSeek top-2 on P1'] += r1[ds] <= 2; cnt['Gemini last on P2'] += r2[ge] == 5; cnt['Gemini or GPT-4o last on P2'] += (r2[ge] == 5 or r2[gp] == 5)
    cnt['Gemini top-3 on P1'] += r1[ge] <= 3; cnt['Sonnet top-2 on P1'] += r1[so] <= 2; Ws.append(kendall_w([r1, r2, r3]))
Ws.sort(); out['rank_stability'] = {k: v / B for k, v in cnt.items()}; out['kendalls_w_bootstrap'] = {'mean': sum(Ws) / B, 'ci95': [Ws[int(.025 * B)], Ws[int(.975 * B) - 1]], 'P(W>0.5)': sum(1 for w in Ws if w > 0.5) / B}
md += '\n## Paired scenario-bootstrap rank stability (fraction of 2000 resamples)\n' + ''.join(f'- {k}: {v/B:.3f}\n' for k, v in cnt.items()) + f"- Kendall's W: mean {sum(Ws)/B:.3f}, 95% interval [{Ws[int(.025*B)]:.3f}, {Ws[int(.975*B)-1]:.3f}], P(W>0.5) = {sum(1 for w in Ws if w>0.5)/B:.3f}\n"
# replication deltas
rep = load(REPL); pre = load(PREFIX)
repP2 = {(e['model'], e['scenario_id']): e['avg_satisfaction_rate'] for e in rep if e['paradigm'] == 'P2'}; repP1 = {(e['model'], e['scenario_id']): e['probe_accuracy'] for e in rep if e['paradigm'] == 'P1'}
preP1 = {(e['model'], e['scenario_id']): e['probe_accuracy'] for e in pre if e['paradigm'] == 'P1'}
out['replication'] = {}; md += '\n## Targeted replication: aggregate over replicated scenarios\n| Model | P2 orig | P2 repl | delta | per-scenario MAD | max | P1 probe orig (pre-fix) | P1 repl (pre-fix) |\n|---|---|---|---|---|---|---|---|\n'
for m in MODELS:
    s2r = [s for (mm, s) in repP2 if mm == m]; o = [p2[m][s] for s in s2r]; r = [repP2[(m, s)] for s in s2r]
    s1r = [s for (mm, s) in repP1 if mm == m]; o1 = [preP1[(m, s)] for s in s1r]; r1_ = [repP1[(m, s)] for s in s1r]
    rec = {'p2_orig': sum(o) / len(o), 'p2_repl': sum(r) / len(r), 'p2_mad': sum(abs(a - b) for a, b in zip(o, r)) / len(o), 'p2_max': max(abs(a - b) for a, b in zip(o, r)), 'p1_probe_orig_prefix': sum(o1) / len(o1), 'p1_probe_repl_prefix': sum(r1_) / len(r1_), 'n_p2': len(o), 'n_p1': len(o1)}
    out['replication'][m] = rec
    md += f"| {LABELS[m]} | {rec['p2_orig']:.3f} | {rec['p2_repl']:.3f} | {rec['p2_repl']-rec['p2_orig']:+.3f} | {rec['p2_mad']:.3f} | {rec['p2_max']:.3f} | {rec['p1_probe_orig_prefix']:.3f} | {rec['p1_probe_repl_prefix']:.3f} |\n"
print(md); save('bootstrap_robustness', out, md)
