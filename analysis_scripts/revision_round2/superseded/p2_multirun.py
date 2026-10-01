"""Multi-run P2 statistics (R3 comment 3 / R2 weakness 2).
Run 1 = the February 2026 run (assignments in p2_parser_analysis/); runs 2 and 3 = results_rerun2/ and
results_rerun3/ scored with the same enhanced parser (p2_parser_analysis_results_rerun{2,3}/).
Reports per-model average satisfaction, checkpoint satisfaction, and conflict detection for each run,
with mean, min-max range and SD across runs, plus per-scenario run-to-run SD. Robust to missing runs."""
import glob, sys, collections, statistics
from common import *
sys.path.insert(0, ROOT); import p2_rescore as R
MODEL_ALIAS = {'deepseek-v3.2': 'deepseek-r1'}
scen = R.load_scenarios(os.path.join(ROOT, 'p2_scenarios'))
RUNS = [('run1_feb2026', os.path.join(ROOT, 'results'), os.path.join(ROOT, 'p2_parser_analysis', 'p2_enhanced_assignments.json')),
        ('run2', os.path.join(ROOT, 'results_rerun2'), os.path.join(ROOT, 'p2_parser_analysis_results_rerun2', 'p2_enhanced_assignments.json')),
        ('run3', os.path.join(ROOT, 'results_rerun3'), os.path.join(ROOT, 'p2_parser_analysis_results_rerun3', 'p2_enhanced_assignments.json'))]
def scorer_conflicts(results_dir):
    """Conflict-detection scores from score_responses.py (results_dir/scored_full/scored_results.json), if present."""
    p = os.path.join(results_dir, 'scored_full', 'scored_results.json')
    if results_dir == os.path.join(ROOT, 'results'): p = FIXED
    if not os.path.exists(p): return None
    conf = collections.defaultdict(dict)
    for e in load(p):
        if e['paradigm'] == 'P2' and e.get('conflict_score') is not None:
            conf[MODEL_ALIAS.get(e['model'], e['model'])][e['scenario_id']] = e['conflict_score']
    return conf
def score_run(results_dir, assign_path):
    if not os.path.exists(assign_path): return None
    resp = {}
    for f in glob.glob(os.path.join(results_dir, '*', 'P2_*.json')):
        d = load(f); m = MODEL_ALIAS.get(d['model'], d['model'])
        for t in d['turns']: resp[(m, d['scenario_id'], int(t['turn_number']))] = t.get('response', '') or ''
    sat = collections.defaultdict(dict); conf = collections.defaultdict(dict)
    for a in load(assign_path):
        m = MODEL_ALIAS.get(a['model'], a['model']); s = scen[a['scenario_id']]; tn = int(a['turn_number'])
        turn = next(t for t in s['turns'] if int(t['turn_number']) == tn)
        r = R.score_checkpoint(a['assignment_enhanced'] or {}, s, turn, resp.get((m, a['scenario_id'], tn), ''), s.get('domain') or s.get('domain_key'))
        sat[(m, tn)][a['scenario_id']] = r['satisfaction_rate']
        if r['conflict_score'] is not None: conf[m][a['scenario_id']] = r['conflict_score']
    sc = scorer_conflicts(results_dir)
    if sc: conf = sc   # prefer the original scorer's conflict metric (the one reported in Table 2)
    return sat, conf
runs = {}
for name, rd, ap in RUNS:
    res = score_run(rd, ap)
    if res: runs[name] = res; print('loaded', name)
    else: print('missing', name)
out = {'runs': list(runs), 'per_model': {}}; md = f'Runs available: {list(runs)}\n\n'
metrics = ['avg', 'T6', 'T11', 'T17', 'T20', 'conflict']
md += '| Model | Metric | ' + ' | '.join(runs) + ' | Mean | Min-Max | SD |\n|---|---|' + '---|' * (len(runs) + 3) + '\n'
for m in MODELS:
    out['per_model'][m] = {}
    for met in metrics:
        vals = []
        for name, (sat, conf) in runs.items():
            if met == 'conflict': v = conf[m]; vals.append(sum(v.values()) / len(v) if v else float('nan'))
            elif met == 'avg':
                per_s = collections.defaultdict(list)
                for t in (6, 11, 17, 20):
                    for sid, x in sat[(m, t)].items(): per_s[sid].append(x)
                vals.append(sum(sum(v) / len(v) for v in per_s.values()) / len(per_s))
            else:
                v = sat[(m, int(met[1:]))]; vals.append(sum(v.values()) / len(v))
        rec = {'per_run': dict(zip(runs, vals)), 'mean': sum(vals) / len(vals), 'min': min(vals), 'max': max(vals), 'sd': (statistics.stdev(vals) if len(vals) > 1 else None)}
        out['per_model'][m][met] = rec
        sd_txt = '-' if rec['sd'] is None else f"{rec['sd']:.3f}"
        md += f"| {LABELS[m]} | {met} | " + ' | '.join(f'{v:.3f}' for v in vals) + f" | {rec['mean']:.3f} | {rec['min']:.3f}-{rec['max']:.3f} | {sd_txt} |\n"
# per-scenario run-to-run SD of average satisfaction (only if >= 2 runs)
if len(runs) >= 2:
    md += '\n| Model | Mean per-scenario SD of avg satisfaction across runs | Max |\n|---|---|---|\n'
    for m in MODELS:
        per_s = collections.defaultdict(list)
        for name, (sat, conf) in runs.items():
            tmp = collections.defaultdict(list)
            for t in (6, 11, 17, 20):
                for sid, x in sat[(m, t)].items(): tmp[sid].append(x)
            for sid, v in tmp.items(): per_s[sid].append(sum(v) / len(v))
        sds = [statistics.stdev(v) for v in per_s.values() if len(v) >= 2]
        out['per_model'][m]['per_scenario_sd_mean'] = sum(sds) / len(sds); out['per_model'][m]['per_scenario_sd_max'] = max(sds)
        md += f'| {LABELS[m]} | {sum(sds)/len(sds):.3f} | {max(sds):.3f} |\n'
print(md); save('p2_multirun', out, md)
