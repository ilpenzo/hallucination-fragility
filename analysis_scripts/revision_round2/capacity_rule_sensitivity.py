"""Sensitivity of the P2 results to the reading of slot capacity (existing outputs only; no new model calls).

Every historical scenario states slot capacities in its opening table and later adds one explicit capacity
sentence ("X can hold at most k ..."). In 19 of 40 scenarios the explicit k is LARGER than the table value, in 17
it is equal and in 4 it is smaller. Protocol v3.1 (primary) enforces the MINIMUM of the two statements, i.e. both
must hold. The alternative reading treats the later explicit sentence as replacing the table value for that slot.
This script recomputes, under the alternative reading, (a) the verified feasibility of every T15/T17/T20 request,
(b) complete-valid-plan counts and satisfaction on feasible checkpoints, (c) capacity violations, and reports
both readings side by side, plus how often a model's no-plan output at T6/T11 occurs in a scenario whose two
capacity statements differ."""
import sys, glob, copy, collections
from common import *
sys.path.insert(0, SCORING_DIR); import p2_rescore as R
import p2_corrected_scoring as C, p2_scoring_v3 as S
scen = R.load_scenarios(P2_SCEN); resp = {}
for f in glob.glob(os.path.join(RESULTS, '*', 'P2_*.json')):
    d = load(f)
    for t in d['turns']: resp[(d['model'], d['scenario_id'], int(t['turn_number']))] = t.get('response', '') or ''
_orig_domain_of = C.domain_of
def relation(s):
    dom = _orig_domain_of(s); cap = {x['id']: x['capacity'] for x in dom['slots']}
    c = next(c for c in s['constraints'] if c['type'] == 'capacity')
    return 'looser' if c['max'] > cap[c['slot']] else 'tighter' if c['max'] < cap[c['slot']] else 'equal'
def domain_override(s):
    dom = _orig_domain_of(s)
    for c in s['constraints']:
        if c['type'] == 'capacity':
            for sl in dom['slots']:
                if sl['id'] == c['slot']: sl['capacity'] = c['max']
    return dom
def run(rule):
    C.domain_of = _orig_domain_of if rule == 'minimum' else domain_override
    cls = {}; rows = []
    for sid, s in scen.items():
        for t in s['turns']:
            if int(t['turn_number']) in (15, 17, 20): cls[(sid, int(t['turn_number']))] = C.classify_checkpoint(s, t)[0]
    for m in MODELS:
        for sid, s in scen.items():
            for t in s['turns']:
                if not t.get('is_checkpoint'): continue
                tn = int(t['turn_number']); r = S.score(s, t, resp[(m, sid, tn)], cls.get((sid, tn), 'no_trap'))
                rows.append(dict(model=m, scenario=sid, turn=tn, feasible=r['feasible'], valid=r['valid_complete_plan'], sat=r['sat_v3'], capviol=r['capacity_violation'], label=r['label']))
    C.domain_of = _orig_domain_of
    return cls, rows
rel_of = {sid: relation(s) for sid, s in scen.items()}; out = {'capacity_statement_relation': dict(collections.Counter(rel_of.values())), 'rules': {}}
md = f"Explicit capacity sentence vs opening table (40 scenarios): {dict(collections.Counter(rel_of.values()))}\n\n"
for rule in ('minimum', 'explicit_replaces_table'):
    cls, rows = run(rule); nf = {t: sum(1 for (sid, tn), c in cls.items() if tn == t and c == 'spurious_conflict') for t in (15, 17, 20)}
    rec = {'feasible_requests': nf, 'models': {}}
    md += f"## Capacity rule: {rule}. Feasible requests: T15 {nf[15]}/40, T17 {nf[17]}/40, T20 {nf[20]}/40\n| Model | T6 valid | T11 valid | post-revision feasible valid | post-revision feasible sat | capacity violations (plans with items) |\n|---|---|---|---|---|---|\n"
    for m in MODELS:
        rm = [r for r in rows if r['model'] == m]; post = [r for r in rm if r['turn'] >= 17 and r['feasible']]; cv = [r['capviol'] for r in rm if r['capviol'] is not None]
        q = {'T6_valid': sum(r['valid'] for r in rm if r['turn'] == 6), 'T11_valid': sum(r['valid'] for r in rm if r['turn'] == 11), 'post_valid': [sum(r['valid'] for r in post), len(post)],
             'post_sat': sum(r['sat'] for r in post) / len(post), 'capacity_violations': [sum(cv), len(cv)]}
        rec['models'][m] = q
        md += f"| {LABELS[m]} | {q['T6_valid']}/40 | {q['T11_valid']}/40 | {q['post_valid'][0]}/{q['post_valid'][1]} = {q['post_valid'][0]/q['post_valid'][1]:.2f} | {q['post_sat']:.3f} | {q['capacity_violations'][0]}/{q['capacity_violations'][1]} |\n"
    out['rules'][rule] = rec; md += '\n'
    if rule == 'minimum': base_rows = rows; base_cls = cls
    else:
        out['feasibility_labels_identical_under_both_rules'] = (cls == base_cls)
        md += f"Feasibility labels identical under both rules: {cls == base_cls}\n"
        xp = os.path.join(OUT, 'cross_paradigm_v3.json')
        if os.path.exists(xp):
            import itertools, math
            P1 = [load(xp)['point'][m]['P1'] for m in MODELS]; P2a = [rec['models'][m]['post_valid'][0] / rec['models'][m]['post_valid'][1] for m in MODELS]; r1 = ranks_desc(P1); r2 = ranks_desc(P2a)
            def pear(x, y):
                mx = sum(x) / len(x); my = sum(y) / len(y); return sum((u - mx) * (v - my) for u, v in zip(x, y)) / math.sqrt(sum((u - mx) ** 2 for u in x) * sum((v - my) ** 2 for v in y))
            rho = pear(r1, r2); pe = sum(1 for q in itertools.permutations(r2) if abs(pear(r1, list(q))) >= abs(rho) - 1e-12) / 120
            out['spearman_P1_P2_alternative_rule'] = {'rho': rho, 'p_exact_two_sided': pe, 'P2_ranks': r2}; md += f"Spearman P1-P2 under the alternative rule: rho = {rho:+.2f} (exact permutation p = {pe:.3f}); P2 ranks {r2}\n\n"
md += '## No-plan outputs at the feasible checkpoints T6 and T11, by relation of the two capacity statements\n| Model | no plan: looser (of 38) | equal (of 34) | tighter (of 8) |\n|---|---|---|---|\n'; out['no_plan_T6_T11'] = {}
for m in MODELS:
    c = collections.Counter(rel_of[r['scenario']] for r in base_rows if r['model'] == m and r['turn'] in (6, 11) and r['label'] in ('no_plan', 'no_usable_plan'))
    out['no_plan_T6_T11'][m] = dict(c); md += f"| {LABELS[m]} | {c['looser']} | {c['equal']} | {c['tighter']} |\n"
print(md); save('capacity_rule_sensitivity', out, md)
