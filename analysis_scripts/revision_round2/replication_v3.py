"""Run-to-run comparison for the targeted replication (manuscript Appendix "Replication"), protocol v3.1.

P1: phase-end answers (T5/T10/T15/T20) of the five replicated scenarios, both runs scored with the final
    extraction rule (post-fix score files); agreement = same correct/incorrect outcome.
P2: checkpoints matched on (model, scenario, turn) between p2_v3_checkpoints_core.json and
    p2_v3_checkpoints_replication.json (run p2_v3_report.py for both tags first). Reported on feasible
    checkpoints (primary) and, as a diagnostic, on all matched checkpoints.
Batches are compared, never pooled."""
import collections
from common import *
core = load(FIXED); rep = load(FIXED_REPL)
def probes(d):
    o = {}
    for e in d:
        if e['paradigm'] != 'P1': continue
        for t in e['turn_scores']:
            if t.get('is_probe') and t.get('score') is not None and t['score'] >= 0: o[(e['model'], e['scenario_id'], int(t['turn_number']))] = t['score']
    return o
pc, pr = probes(core), probes(rep); keys = sorted(k for k in pr if k in pc)
agree = sum(1 for k in keys if (pc[k] >= 0.5) == (pr[k] >= 0.5))
out = {'P1': {'matched_phase_end_answers': len(keys), 'agree': agree, 'per_model': {}}, 'P2': {}}
md = f'## P1 phase-end answers: {agree}/{len(keys)} agree between runs\n| Model | acc. original | acc. replication |\n|---|---|---|\n'
for m in MODELS:
    k = [x for x in keys if x[0] == m]; a = sum(pc[x] for x in k) / len(k); b = sum(pr[x] for x in k) / len(k)
    out['P1']['per_model'][m] = {'n': len(k), 'original': a, 'replication': b}; md += f'| {LABELS[m]} | {a:.2f} | {b:.2f} |\n'
c = {(r['model'], r['scenario'], r['turn']): r for r in load(os.path.join(OUT, 'p2_v3_checkpoints_core.json'))}
r_ = {(r['model'], r['scenario'], r['turn']): r for r in load(os.path.join(OUT, 'p2_v3_checkpoints_replication.json'))}
mk = sorted(k for k in r_ if k in c); scen = sorted({k[1] for k in mk})
post_feasible = sorted({(k[1], k[2]) for k in mk if k[2] >= 17 and c[k]['feasible']})
md += f'\n## P2 (protocol v3.1): {len(scen)} replicated scenarios; feasible post-revision checkpoints among them: {len(post_feasible)} {post_feasible}\n'
md += '| Model | feasible n | sat original | sat replication | change | max per-checkpoint change | all-checkpoint sat original | replication | valid plans (feasible) original | replication |\n|---|---|---|---|---|---|---|---|---|---|\n'
def mean(v): return sum(v) / len(v)
for m in MODELS:
    k = [x for x in mk if x[0] == m]; f = [x for x in k if c[x]['feasible']]
    rec = {'n_feasible': len(f), 'sat_core': mean([c[x]['sat_v3'] for x in f]), 'sat_repl': mean([r_[x]['sat_v3'] for x in f]), 'max_abs_change_feasible': max(abs(c[x]['sat_v3'] - r_[x]['sat_v3']) for x in f),
           'sat_all_core': mean([c[x]['sat_v3'] for x in k]), 'sat_all_repl': mean([r_[x]['sat_v3'] for x in k]), 'max_abs_change_all': max(abs(c[x]['sat_v3'] - r_[x]['sat_v3']) for x in k),
           'valid_core': sum(c[x]['valid_complete_plan'] for x in f), 'valid_repl': sum(r_[x]['valid_complete_plan'] for x in f)}
    out['P2'][m] = rec
    md += f"| {LABELS[m]} | {rec['n_feasible']} | {rec['sat_core']:.3f} | {rec['sat_repl']:.3f} | {rec['sat_repl']-rec['sat_core']:+.3f} | {rec['max_abs_change_feasible']:.2f} | {rec['sat_all_core']:.3f} | {rec['sat_all_repl']:.3f} | {rec['valid_core']}/{rec['n_feasible']} | {rec['valid_repl']}/{rec['n_feasible']} |\n"
for run, key in (('original', 'core'), ('replication', 'repl')):
    first = {metric: max(MODELS, key=lambda m: out['P2'][m][f'{metric}_{key}']) for metric in ('sat', 'sat_all', 'valid')}; out[f'first_{run}'] = first
    md += f"- first in the {run} run: " + ', '.join(f'{k}: {LABELS[v]}' for k, v in first.items()) + '\n'
print(md); save('replication_v3', out, md)
