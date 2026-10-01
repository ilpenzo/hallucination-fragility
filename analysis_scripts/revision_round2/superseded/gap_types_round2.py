"""Gap-type fabrication analysis including the round-2 scenarios (P3_029-P3_036).
Combines judge outputs from the core 20, the first supplementary 8, and the round-2 8 scenarios;
recomputes per-type rates with Wilson CIs and Fisher exact tests. Robust to missing round-2 data."""
import glob, math, collections
from math import comb
from common import *
CORE = load(os.path.join(ROOT, 'analyze_supplementary_p3.py')) if False else None
ORIGINAL_GAP_TYPES = {"P3_001": "missing_reason", "P3_002": "missing_number", "P3_003": "missing_number", "P3_004": "missing_detail", "P3_005": "missing_reason",
    "P3_006": "missing_number", "P3_007": "missing_evidence", "P3_008": "missing_evidence", "P3_009": "implied_not_stated", "P3_010": "missing_evidence",
    "P3_011": "missing_detail", "P3_012": "missing_detail", "P3_013": "missing_detail", "P3_014": "missing_detail", "P3_015": "missing_detail",
    "P3_016": "missing_number", "P3_017": "missing_evidence", "P3_018": "implied_not_stated", "P3_019": "missing_evidence", "P3_020": "missing_number"}
GAP_TYPES = dict(ORIGINAL_GAP_TYPES); GAP_TYPES.update({f"P3_{i:03d}": "missing_evidence" for i in range(21, 29)})
r2_src = os.path.join(ROOT, 'p3_supplementary_r2', 'p3_source_data.json')
if os.path.exists(r2_src):
    for s in load(r2_src)['scenarios']: GAP_TYPES[s['scenario_id']] = s['gap_type']
MODEL_ALIAS = {'deepseek-v3.2': 'deepseek-r1'}   # same weights family label used in the paper
def wilson(k, n, z=1.96):
    if n == 0: return (float('nan'), float('nan'))
    ph = k / n; den = 1 + z * z / n; c = (ph + z * z / (2 * n)) / den; h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)
def fisher(a, b, c, d):
    n = a + b + c + d; r1 = a + b; c1 = a + c
    p = lambda x: comb(r1, x) * comb(n - r1, c1 - x) / comb(n, c1); p0 = p(a)
    return sum(p(x) for x in range(max(0, c1 - (n - r1)), min(r1, c1) + 1) if p(x) <= p0 + 1e-12)
dirs = [os.path.join(ROOT, 'results', 'p3_judged', 'individual'), os.path.join(ROOT, 'results_supplementary', 'p3_judged', 'individual'), os.path.join(ROOT, 'results_supplementary_r2', 'p3_judged', 'individual')]
events = collections.defaultdict(list); per_scenario = collections.defaultdict(dict)
for d in dirs:
    for f in glob.glob(os.path.join(d, '*.json')):
        j = load(f)
        if not j.get('success', True): continue
        sid = j['scenario_id']; m = MODEL_ALIAS.get(j['model'], j['model']); fab = any(v.get('fabricated') for v in j['gap_scores'].values())
        gt = GAP_TYPES.get(sid)
        if gt is None: continue
        events[gt].append((sid, m, fab)); per_scenario[sid][m] = fab
out = {'per_type': {}, 'per_scenario': {}}; md = '| Gap type | Gaps | Pairs | Events | Rate | Wilson 95% CI |\n|---|---|---|---|---|---|\n'
for gt in ['missing_evidence', 'missing_detail', 'missing_number', 'missing_reason', 'implied_not_stated']:
    ev = events.get(gt, []); k = sum(1 for _, _, f in ev if f); n = len(ev); gaps = len({s for s, _, _ in ev}); lo, hi = wilson(k, n)
    out['per_type'][gt] = {'gaps': gaps, 'pairs': n, 'events': k, 'rate': (k / n if n else None), 'ci95': [lo, hi], 'scenarios_with_event': sorted({s for s, _, f in ev if f})}
    md += f'| {gt} | {gaps} | {n} | {k} | {(k/n if n else float("nan")):.3f} | [{lo:.3f}, {hi:.3f}] |\n'
me = out['per_type']['missing_evidence']; ok = sum(v['events'] for t, v in out['per_type'].items() if t != 'missing_evidence'); on = sum(v['pairs'] for t, v in out['per_type'].items() if t != 'missing_evidence')
out['fisher'] = {'missing_evidence_vs_all_other': fisher(me['events'], me['pairs'] - me['events'], ok, on - ok)}
zt = [t for t in ('missing_number', 'missing_reason', 'implied_not_stated')]; zk = sum(out['per_type'][t]['events'] for t in zt); zn = sum(out['per_type'][t]['pairs'] for t in zt)
out['fisher']['missing_evidence_vs_number_reason_implied'] = fisher(me['events'], me['pairs'] - me['events'], zk, zn - zk)
md += '\nFisher exact (two-sided): ' + '; '.join(f'{k}: p = {v:.3f}' for k, v in out['fisher'].items()) + '\n'
for sid in sorted(per_scenario):
    if int(sid[3:]) >= 29: out['per_scenario'][sid] = per_scenario[sid]; md += f"- {sid} ({GAP_TYPES[sid]}): fabricated by {[m for m, f in per_scenario[sid].items() if f] or 'none'}\n"
n_r2 = sum(1 for sid in per_scenario if int(sid[3:]) >= 29)
md = f'Round-2 scenarios with judge outputs: {n_r2} of 8\n\n' + md
print(md); save('gap_types_round2', out, md)
