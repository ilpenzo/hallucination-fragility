"""Gap-type fabrication analysis with batch separation and scenario-level inference (Step A protocol, frozen
before collection). Batches:
  historical  = core 20 scenarios (Feb 2026) + supplementary P3_021-P3_028 (Feb 2026), official endpoints;
  contemporary = P3_029-P3_036 (new) + P3_021-P3_028 re-collected as controls, collected together (Sep 2026),
                 DeepSeek served by a third-party host and kept as its own serving condition (key 'deepseek-v3.2').
Never pooled across batches. Primary endpoint: scenario-level "any fabrication among the five-model panel"
(one observation per scenario). Pair-level counts are descriptive only. Prespecified contrasts (contemporary batch):
  (C1) missing_evidence controls (8) vs missing_reason (4); (C2) missing_evidence controls (8) vs implied_not_stated (4);
two-sided Fisher exact tests at scenario level, Holm-adjusted over the two contrasts. Robust to missing batches."""
import glob, collections
from math import comb
from common import *
ORIG = {"P3_001": "missing_reason", "P3_002": "missing_number", "P3_003": "missing_number", "P3_004": "missing_detail", "P3_005": "missing_reason", "P3_006": "missing_number", "P3_007": "missing_evidence", "P3_008": "missing_evidence", "P3_009": "implied_not_stated", "P3_010": "missing_evidence", "P3_011": "missing_detail", "P3_012": "missing_detail", "P3_013": "missing_detail", "P3_014": "missing_detail", "P3_015": "missing_detail", "P3_016": "missing_number", "P3_017": "missing_evidence", "P3_018": "implied_not_stated", "P3_019": "missing_evidence", "P3_020": "missing_number"}
GAP = dict(ORIG); GAP.update({f"P3_{i:03d}": "missing_evidence" for i in range(21, 29)})
r2 = P3_R2_SRC
if os.path.exists(r2):
    for s in load(r2)['scenarios']: GAP[s['scenario_id']] = s['gap_type']
BATCHES = {'historical': [JUDGED, JUDGED_SUPP],
           'contemporary': [JUDGED_R2, JUDGED_R2_CTRL]}
def fisher(a, b, c, d):
    n = a + b + c + d; r1 = a + b; c1 = a + c
    p = lambda x: comb(r1, x) * comb(n - r1, c1 - x) / comb(n, c1); p0 = p(a)
    return sum(p(x) for x in range(max(0, c1 - (n - r1)), min(r1, c1) + 1) if p(x) <= p0 + 1e-12)
def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i]); adj = [0] * len(ps); m = len(ps); running = 0
    for rank, i in enumerate(order): running = max(running, (m - rank) * ps[i]); adj[i] = min(1.0, running)
    return adj
out = {'batches': {}}; md = ''
for batch, dirs in BATCHES.items():
    recs = []
    for d in dirs:
        for f in glob.glob(os.path.join(d, '*.json')):
            j = load(f)
            if not j.get('success', True) or j['scenario_id'] not in GAP: continue
            recs.append({'scenario': j['scenario_id'], 'model': j['model'], 'gap_type': GAP[j['scenario_id']], 'fabricated': any(v.get('fabricated') for v in j['gap_scores'].values()),
                         'host': j.get('serving_provider') or j.get('host') or ('third-party' if j['model'] == 'deepseek-v3.2' else 'official')})
    if not recs: out['batches'][batch] = {'status': 'no data'}; md += f'## {batch}: no data\n\n'; continue
    by_scen = collections.defaultdict(dict)
    for r in recs: by_scen[r['scenario']][r['model']] = r['fabricated']
    PANEL = 5; incomplete = {sid: sorted(d) for sid, d in by_scen.items() if len(d) < PANEL}
    types = collections.defaultdict(lambda: {'scenarios': 0, 'scenarios_any_fab': 0, 'pairs': 0, 'pair_events': 0, 'models': set()})
    for sid, d in by_scen.items():
        if sid in incomplete: continue   # primary endpoint requires the complete five-model panel
        t = types[GAP[sid]]; t['scenarios'] += 1; t['scenarios_any_fab'] += any(d.values()); t['pairs'] += len(d); t['pair_events'] += sum(d.values()); t['models'] |= set(d)
    rec = {'n_scenarios': len(by_scen), 'n_scenarios_complete_panel': len(by_scen) - len(incomplete), 'excluded_incomplete_panel': incomplete, 'panel_models': sorted({r['model'] for r in recs}), 'per_type': {k: {kk: (sorted(vv) if isinstance(vv, set) else vv) for kk, vv in v.items()} for k, v in types.items()},
           'per_scenario': {sid: d for sid, d in sorted(by_scen.items())}}
    md += f"## {batch} batch: {len(by_scen)} scenarios ({len(incomplete)} excluded for incomplete panel: {sorted(incomplete)}); panel {rec['panel_models']}\n\n| Gap type | Scenarios | Scenarios with any fabrication (primary) | Pairs (descriptive) | Pair events (descriptive) |\n|---|---|---|---|---|\n"
    for k, v in sorted(types.items()): md += f"| {k} | {v['scenarios']} | {v['scenarios_any_fab']} | {v['pairs']} | {v['pair_events']} |\n"
    if incomplete:
        dt = collections.defaultdict(lambda: [0, 0, 0, 0])   # scenarios, scenarios with any fabrication so far, pairs, pair events
        for sid in incomplete:
            d = by_scen[sid]; x = dt[GAP[sid]]; x[0] += 1; x[1] += any(d.values()); x[2] += len(d); x[3] += sum(d.values())
        rec['incomplete_panel_descriptive'] = {k: {'scenarios': v[0], 'scenarios_any_fab_among_collected_models': v[1], 'pairs': v[2], 'pair_events': v[3]} for k, v in dt.items()}
        md += '\nINCOMPLETE PANEL (descriptive only; NOT the primary endpoint, which requires all five models):\n| Gap type | Scenarios | Any fabrication among collected models | Pairs | Pair events |\n|---|---|---|---|---|\n' + ''.join(f"| {k} | {v[0]} | {v[1]} | {v[2]} | {v[3]} |\n" for k, v in sorted(dt.items()))
    if batch == 'contemporary':
        me = types.get('missing_evidence'); ps = {}
        for name, other in (('C1_ME_vs_missing_reason', 'missing_reason'), ('C2_ME_vs_implied_not_stated', 'implied_not_stated')):
            o = types.get(other)
            if me and o and me['scenarios'] and o['scenarios']: ps[name] = fisher(me['scenarios_any_fab'], me['scenarios'] - me['scenarios_any_fab'], o['scenarios_any_fab'], o['scenarios'] - o['scenarios_any_fab'])
        if ps:
            adj = holm(list(ps.values())); rec['prespecified_contrasts'] = {k: {'fisher_p': p, 'holm_adjusted_p': a} for (k, p), a in zip(ps.items(), adj)}
            md += '\nPrespecified scenario-level contrasts (Fisher exact, two-sided; Holm over two contrasts): ' + '; '.join(f"{k}: p={v['fisher_p']:.3f} (adj {v['holm_adjusted_p']:.3f})" for k, v in rec['prespecified_contrasts'].items()) + '\n'
    md += '\n'; out['batches'][batch] = rec
# control drift check (same documents, two batches) per model, excluding the DeepSeek host change from "drift"
h = out['batches'].get('historical', {}).get('per_scenario', {}); c = out['batches'].get('contemporary', {}).get('per_scenario', {})
ctrl = [f"P3_{i:03d}" for i in range(21, 29)]
if h and c and any(s in c for s in ctrl):
    agree = collections.Counter(); n = collections.Counter()
    for s in ctrl:
        if s in h and s in c:
            for m, v in c[s].items():
                hm = 'deepseek-r1' if m == 'deepseek-v3.2' else m
                if hm in h[s]: n[m] += 1; agree[m] += (h[s][hm] == v)
    out['control_agreement'] = {m: {'agree': agree[m], 'n': n[m], 'note': 'host change, not drift' if m == 'deepseek-v3.2' else 'same endpoint'} for m in n}
    md += '## Control scenarios (P3_021-P3_028): historical vs contemporary fabrication agreement per model\n' + ''.join(f"- {m}: {agree[m]}/{n[m]}{' (third-party host; serving condition differs)' if m=='deepseek-v3.2' else ''}\n" for m in n)
save('gap_types_batched', out, md); print(md)
