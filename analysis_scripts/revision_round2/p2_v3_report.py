"""P2 results under scoring v3.1, reported as two separate tasks (2026-09-17 review, section 4):
  A. Feasible planning success: checkpoints whose active requirement set is satisfiable (T6 and T11 for all
     40 scenarios; T17 and T20 for the verified-feasible scenarios). Metrics: fractional satisfaction sat_v3
     (explicit non-capacity constraints + one capacity condition per slot + the T15 requirement when feasible),
     complete valid plan rate, coverage. Scenario-bootstrap 95% intervals (resamples recorded in metadata).
  B. Infeasible-request handling: checkpoints whose active set is unsatisfiable (T17: 23 scenarios; T20: 28).
     Reported: incompatibility-claim rate (PROVISIONAL heuristic v3 unless LLM labels exist), output type
     (no plan / partial / complete coverage), requests for resolution, and the reduced-set diagnostic
     (satisfaction/validity with the T15 requirement dropped), which is NOT a task-success measure.
  C. T15 incompatibility claims by T15 feasibility; capacity violations with numerator/denominator.
No pooled all-checkpoint average is used as a primary ranking. Usage: --results-dir, --tag, --boot."""
import glob, sys, random, collections, argparse
from common import *
sys.path.insert(0, SCORING_DIR); import p2_rescore as R
import p2_scoring_v3 as S
ap = argparse.ArgumentParser(); ap.add_argument('--results-dir', default=RESULTS); ap.add_argument('--tag', default='core'); ap.add_argument('--boot', type=int, default=2000)
args = ap.parse_args(); random.seed(20260917)
scen = R.load_scenarios(P2_SCEN); cls = load(os.path.join(OUT, 'p2_feasibility_classes.json'))
BATCH_OF = {'core': 'core_feb2026', 'replication': 'replication_feb2026'}
llm_path = os.path.join(OUT, f"incompatibility_llm_labels_{BATCH_OF.get(args.tag, args.tag)}.json"); llm = {}
if os.path.exists(llm_path):   # labels are batch-specific; never reused across batches
    llm = {(r['model'], r['scenario'], r['turn']): r.get('effective_label', r.get('label')) for r in load(llm_path)['records'] if r.get('label')}
ALIAS = {'deepseek-v3.2': 'deepseek-r1'}; resp = {}
for f in glob.glob(os.path.join(args.results_dir, '*', 'P2_*.json')):
    d = load(f); m = ALIAS.get(d['model'], d['model'])
    for t in d['turns']: resp[(m, d['scenario_id'], int(t['turn_number']))] = t.get('response', '') or ''
models = [m for m in MODELS if any(k[0] == m for k in resp)]
rows = []
for m in models:
    for sid, s in scen.items():
        if (m, sid, 17) not in resp: continue
        for t in s['turns']:
            if not t.get('is_checkpoint'): continue
            tn = int(t['turn_number']); c = cls.get(f'{sid}|T{tn}', 'no_trap')
            r = S.score(s, t, resp[(m, sid, tn)], c, resp.get((m, sid, 15)) if tn >= 17 else None)
            r.update({'model': m, 'scenario': sid, 'turn': tn, 'class_T15': cls.get(f'{sid}|T15', 'no_trap')})
            if llm:
                r['flag_here_llm'] = llm.get((m, sid, tn)); r['flag_t15_llm'] = llm.get((m, sid, 15))
            rows.append(r)
json.dump(rows, open(os.path.join(OUT, f'p2_v3_checkpoints_{args.tag}.json'), 'w'), indent=1)
def mean(v): return sum(v) / len(v) if v else float('nan')
SEED = 20260917
def ci(vals, key, B=args.boot):
    """Percentile bootstrap over scenarios (one value per scenario). Each interval has its own generator, seeded
    from `key`, so an interval does not depend on the order in which the others are computed."""
    n = len(vals)
    if n == 0: return (float('nan'),) * 3
    rng = random.Random(f'{SEED}|{key}')
    ms = sorted(sum(vals[rng.randrange(n)] for _ in range(n)) / n for _ in range(B)); return mean(vals), ms[int(.025 * B)], ms[int(.975 * B) - 1]
def ci_cluster(groups, key, B=args.boot):
    """Scenario-cluster bootstrap for pooled T17+T20 values: a resampled scenario carries all of its checkpoints."""
    ks = sorted(groups); allv = [v for k in ks for v in groups[k]]
    if not allv: return (float('nan'),) * 3
    rng = random.Random(f'{SEED}|{key}'); ms = []
    for _ in range(B):
        c = [v for k in (ks[rng.randrange(len(ks))] for _ in ks) for v in groups[k]]; ms.append(sum(c) / len(c))
    ms.sort(); return mean(allv), ms[int(.025 * B)], ms[int(.975 * B) - 1]
def by_scen(rs, f):
    g = collections.defaultdict(list)
    for r in rs: g[r['scenario']].append(f(r))
    return g
def fmt(t): return f'{t[0]:.3f} [{t[1]:.3f}, {t[2]:.3f}]' if t[0] == t[0] else 'n/a'
flag_src = 'LLM rubric labels' if llm else 'heuristic v3 (PROVISIONAL; not for publication)'
out = {'results_dir': rel(args.results_dir), 'tag': args.tag, 'bootstrap_resamples': args.boot, 'scoring': 'v3.1', 'flag_source': flag_src, 'n_checkpoints': len(rows), 'A_feasible': {}, 'B_infeasible': {}, 'C_T15_and_capacity': {}}
md = f'# P2 report ({args.tag}); scoring v3.1; {len(rows)} checkpoints; bootstrap resamples = {args.boot}; flag source = {flag_src}\n\n'
md += '## A. Feasible planning success\n| Model | T6 sat_v3 | T11 sat_v3 | Feasible T17 sat_v3 (n) | Feasible T20 sat_v3 (n) | Valid complete plan: T6 | T11 | feasible T17 | feasible T20 | post-revision feasible valid (count) | Coverage |\n|---|---|---|---|---|---|---|---|---|---|---|\n'
for m in models:
    rm = [r for r in rows if r['model'] == m]; F = {t: [r for r in rm if r['turn'] == t and r['feasible']] for t in (6, 11, 17, 20)}
    post = F[17] + F[20]
    rec = {f'T{t}': {'n': len(F[t]), 'sat_v3': ci([r['sat_v3'] for r in F[t]], f'{m}|T{t}|sat'), 'valid_complete': ci([float(r['valid_complete_plan']) for r in F[t]], f'{m}|T{t}|valid')} for t in (6, 11, 17, 20)}
    rec['post_revision_feasible'] = {'n': len(post), 'valid_complete_count': sum(r['valid_complete_plan'] for r in post), 'valid_complete_rate': ci_cluster(by_scen(post, lambda r: float(r['valid_complete_plan'])), f'{m}|post|valid'), 'sat_v3': ci_cluster(by_scen(post, lambda r: r['sat_v3']), f'{m}|post|sat')}
    rec['coverage_all'] = mean([r['coverage'] for r in rm]); out['A_feasible'][m] = rec
    md += f"| {LABELS[m]} | {fmt(rec['T6']['sat_v3'])} | {fmt(rec['T11']['sat_v3'])} | {fmt(rec['T17']['sat_v3'])} ({rec['T17']['n']}) | {fmt(rec['T20']['sat_v3'])} ({rec['T20']['n']}) | {rec['T6']['valid_complete'][0]:.2f} | {rec['T11']['valid_complete'][0]:.2f} | {rec['T17']['valid_complete'][0]:.2f} | {rec['T20']['valid_complete'][0]:.2f} | {rec['post_revision_feasible']['valid_complete_count']}/{rec['post_revision_feasible']['n']} | {rec['coverage_all']:.2f} |\n"
md += '\n## B. Infeasible-request handling (T15 requirement makes the active set unsatisfiable)\n| Model | Turn | n | Incompatibility claim at this turn | No plan | Partial | Complete coverage | Requests resolution | Reduced-set sat (diagnostic) | Reduced-set valid (diagnostic) |\n|---|---|---|---|---|---|---|---|---|---|\n'
for m in models:
    out['B_infeasible'][m] = {}
    for tn in (17, 20):
        g = [r for r in rows if r['model'] == m and r['turn'] == tn and not r['feasible']]
        fl = [r['flag_here_llm'] == 'YES' for r in g if r.get('flag_here_llm') in ('YES', 'NO')] if llm else [bool(r['flag_here']) for r in g]
        rec = {'n': len(g), 'claim_rate': mean(fl), 'claim_n': len(fl), 'no_plan': sum(r['label'] == 'no_plan' for r in g), 'no_usable_plan': sum(r['label'] == 'no_usable_plan' for r in g), 'partial': sum(r['label'] == 'partial_plan' for r in g), 'complete': sum(r['label'] == 'complete_plan' for r in g),
               'requests_resolution': sum(r['requests_resolution'] for r in g), 'reduced_sat': mean([r['sat_v3'] for r in g]), 'reduced_valid': sum(r['reduced_set_valid_plan'] for r in g)}
        out['B_infeasible'][m][f'T{tn}'] = rec
        md += f"| {LABELS[m]} | T{tn} | {rec['n']} | {rec['claim_rate']:.2f} ({rec['claim_n']}) | {rec['no_plan']+rec['no_usable_plan']} | {rec['partial']} | {rec['complete']} | {rec['requests_resolution']} | {rec['reduced_sat']:.3f} | {rec['reduced_valid']} |\n"
md += '\n## C. Incompatibility claims at T15 by T15 feasibility, false alarms on feasible T17/T20, capacity violations\n| Model | T15 claim, infeasible (n) | T15 claim, feasible = false alarm (n) | False alarm feasible T17 (n) | False alarm feasible T20 (n) | Capacity violations (plans with >=1 assignment) |\n|---|---|---|---|---|---|\n'
for m in models:
    rm = [r for r in rows if r['model'] == m]
    def claims(rs, key):
        v = [r[key + '_llm'] == 'YES' for r in rs if r.get(key + '_llm') in ('YES', 'NO')] if llm else [bool(r[key]) for r in rs]; return mean(v), len(v)
    t15_inf = claims([r for r in rm if r['turn'] == 17 and r['class_T15'] == 'genuine_conflict'], 'flag_t15'); t15_fea = claims([r for r in rm if r['turn'] == 17 and r['class_T15'] == 'spurious_conflict'], 'flag_t15')
    fa17 = claims([r for r in rm if r['turn'] == 17 and r['feasible']], 'flag_here'); fa20 = claims([r for r in rm if r['turn'] == 20 and r['feasible']], 'flag_here')
    cv = [r['capacity_violation'] for r in rm if r['capacity_violation'] is not None]
    out['C_T15_and_capacity'][m] = {'t15_claim_infeasible': t15_inf, 't15_claim_feasible': t15_fea, 'false_alarm_T17': fa17, 'false_alarm_T20': fa20, 'capacity_violations': [sum(cv), len(cv)]}
    md += f"| {LABELS[m]} | {t15_inf[0]:.2f} ({t15_inf[1]}) | {t15_fea[0]:.2f} ({t15_fea[1]}) | {fa17[0]:.2f} ({fa17[1]}) | {fa20[0]:.2f} ({fa20[1]}) | {sum(cv)}/{len(cv)} = {mean(cv):.2f} |\n"
md += '\nNotes: sat_explicit (explicit non-capacity, non-trap constraints only; block-scoped extraction) is kept in the per-checkpoint file as a continuity diagnostic; it is not identical to the original rigid-parser metric. Capacity is interpreted as a maximum item count per slot (minimum of the stated table and any explicit active bound); the historical prompts left the unit ambiguous.\n'
md += '\nRank stability of the post-revision valid-plan rate is computed by cross_paradigm_v3.py (scenario-cluster bootstrap).\n'
save(f'p2_v3_{args.tag}', out, md); print(md)
