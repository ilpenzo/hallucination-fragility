"""Regenerate every auto-generated region of the manuscript from the analysis outputs, so that table cells and
the incompatibility-claim sentences are transcribed mechanically. Regions are delimited in the .tex source by
`% BEGIN AUTO:<name>` / `% END AUTO:<name>`. The generated LaTeX is always written to outputs/tex_regions.tex;
the manuscript is patched only when it is present next to the scripts (development tree).
Inputs: p2_v3_core.json, p2_v3_checkpoints_core.json, capacity_rule_sensitivity.json, cross_paradigm_v3.json,
incompatibility_llm_labels_core_feb2026.json, incompatibility_rates.json, p2_feasibility_classes.json."""
import re, collections
from common import *
rep = load(os.path.join(OUT, 'p2_v3_core.json')); rows = load(os.path.join(OUT, 'p2_v3_checkpoints_core.json')); cap = load(os.path.join(OUT, 'capacity_rule_sensitivity.json'))
xp = load(os.path.join(OUT, 'cross_paradigm_v3.json')); val = load(os.path.join(OUT, 'incompatibility_rates.json')); cls = load(os.path.join(OUT, 'p2_feasibility_classes.json'))
labs = load(os.path.join(OUT, 'incompatibility_llm_labels_core_feb2026.json'))['records']; lab = {(r['model'], r['scenario'], r['turn']): r for r in labs}
TEXNAME = {'deepseek-r1': 'DeepSeek-V3.2', 'claude-sonnet-4.5': 'Sonnet 4.5', 'gemini-2.5-pro': 'Gemini 2.5 Pro', 'minimax-m2.5': 'MiniMax M2.5', 'gpt-4o': 'GPT-4o'}
INTEXT = {k: v.replace(' ', '~') for k, v in TEXNAME.items()}
def f3(x): return ('%.3f' % x).lstrip('0') if x < 0.9995 else '1.00'
def f2(x): return ('%.2f' % x).lstrip('0') if x < 0.995 else '1.00'
def cell(t): return f'{f3(t[0])} [{f3(t[1])}, {f3(t[2])}]'
R = {}
# Table: feasible-plan success
order = ['deepseek-r1', 'claude-sonnet-4.5', 'gemini-2.5-pro', 'minimax-m2.5', 'gpt-4o']; best = max(order, key=lambda m: rep['A_feasible'][m]['post_revision_feasible']['valid_complete_count']); out = ''
for m in order:
    a = rep['A_feasible'][m]; pv = a['post_revision_feasible']; alt = cap['rules']['explicit_replaces_table']['models'][m]['post_valid']
    v = f"{pv['valid_complete_count']}/{pv['n']}"; v = f'\\textbf{{{v}}}' if m == best else v
    out += f"{TEXNAME[m]:<14} & {cell(a['T6']['sat_v3'])} & {cell(a['T11']['sat_v3'])} & {cell(a['T17']['sat_v3'])} & {cell(a['T20']['sat_v3'])} & {v} & {alt[0]}/{alt[1]} \\\\\n"
R['tab-p2'] = out
# Table: infeasible-request handling
def claim(m, tn, klass):
    ks = [k for k in lab if k[0] == m and k[2] == tn and cls.get(f'{k[1]}|T{tn}') == klass]; e = [lab[k].get('effective_label') for k in ks]
    return e.count('YES'), e.count('YES') + e.count('NO'), e.count('UNCLEAR'), [lab[k] for k in ks if lab[k].get('effective_label') == 'YES']
out = ''
def frac(t): return f'{t[0]}/{t[1]}'
for m in order:
    for tn in (15, 17, 20):
        if tn == 15: out += f"{TEXNAME[m]:<14} & T15 & --- & --- & --- & --- & {frac(claim(m, 15, 'genuine_conflict'))} & {frac(claim(m, 15, 'spurious_conflict'))} \\\\\n"; continue
        g = [r for r in rows if r['model'] == m and r['turn'] == tn and not r['feasible']]; c = collections.Counter(r['label'] for r in g)
        cl, fa_ = (frac(claim(m, 17, 'genuine_conflict')), frac(claim(m, 17, 'spurious_conflict'))) if tn == 17 else ('---', '---')
        out += f"{'':<14} & T{tn} & {c['no_plan'] + c['no_usable_plan']:>2} & {c['partial_plan']:>2} & {c['complete_plan']:>2} & {sum(1 for r in g if r['requests_resolution']):>2} & {cl} & {fa_} \\\\\n"
    if m != order[-1]: out += '\\addlinespace[2pt]\n'
R['tab-p2-infeasible'] = out
# Table: cross-paradigm summary
xo = sorted(MODELS, key=lambda m: -xp['point'][m]['P1']); rk = {p: dict(zip(MODELS, xp['ranks'][p])) for p in ('P1', 'P2', 'P3')}; out = ''
def b(s, cond): return f'\\textbf{{{s}}}' if cond else s
for m in xo:
    q = xp['point'][m]; n, N = q['P2_valid_n']
    out += f"{TEXNAME[m]:<14} & {b(f3(q['P1']), rk['P1'][m] == 1)} ({rk['P1'][m]:g}) & {b(f'{n}/{N} = ' + f2(n / N), rk['P2'][m] == 1)} ({rk['P2'][m]:g}) & {f3(q['P2_sat'])} & {b(f3(q['P3']), rk['P3'][m] == 1)} ({rk['P3'][m]:g}) \\\\\n"
R['tab-cross'] = out
# Table: plan output types
out = ''
for m in ['deepseek-r1', 'claude-sonnet-4.5', 'minimax-m2.5', 'gemini-2.5-pro', 'gpt-4o']:
    c = collections.Counter(r['label'] for r in rows if r['model'] == m); out += f"{TEXNAME[m]:<14} & {c['complete_plan']:>3} & {c['partial_plan']:>3} & {c['no_usable_plan']} & {c['no_plan']:>2} & {rep['A_feasible'][m]['coverage_all']:.2f} \\\\\n"
R['tab-plan-types'] = out
# Table: capacity reading
out = ''; pr, al = cap['rules']['minimum']['models'], cap['rules']['explicit_replaces_table']['models']
for m in order:
    out += f"{TEXNAME[m]:<14} & {pr[m]['T6_valid']} / {al[m]['T6_valid']} & {pr[m]['T11_valid']} / {al[m]['T11_valid']} & {pr[m]['post_valid'][0]} / {al[m]['post_valid'][0]} & {pr[m]['capacity_violations'][0]} / {al[m]['capacity_violations'][0]} & {pr[m]['capacity_violations'][1]} \\\\\n"
R['tab-capacity'] = out
# Claims paragraph
S = {m: {'T17_inf': claim(m, 17, 'genuine_conflict'), 'T15_inf': claim(m, 15, 'genuine_conflict'), 'T15_fa': claim(m, 15, 'spurious_conflict'), 'T17_fa': claim(m, 17, 'spurious_conflict')} for m in MODELS}
def lst(key): return ', '.join(f"{S[m][key][0]}/{S[m][key][1]} ({INTEXT[m]})" for m in order)
fa = [r for m in MODELS for k in ('T15_fa', 'T17_fa') for r in S[m][k][3]]; fa_cap = sum(1 for r in fa if re.search(r'capacit|can (?:only )?hold|at most|slots?\b|room for|over-?capacity|exceed', r.get('quote') or '', re.I))
unc = sum(1 for r in labs if r.get('effective_label') == 'UNCLEAR'); unc_own = sum(1 for r in labs if r.get('label') == 'UNCLEAR'); unc_quote = unc - unc_own
NUMW = {0: 'none', 1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven'}
def rng(key):
    v = sorted(((S[m][key][0] / S[m][key][1], m) for m in MODELS)); lo, hi = v[0][1], v[-1][1]
    return f"from {S[lo][key][0]}/{S[lo][key][1]} ({INTEXT[lo]}) to {S[hi][key][0]}/{S[hi][key][1]} ({INTEXT[hi]})"
ds = S['deepseek-r1']; fa_ds = ds['T15_fa'][0] + ds['T17_fa'][0]; n_ds = ds['T15_fa'][1] + ds['T17_fa'][1]
R['claims'] = ("The last two columns of Table~\\ref{tab:p2-infeasible} give the rubric classification of the turn-15 and turn-17 responses. On the infeasible scenarios, the number of responses stating that the active requirements cannot all be satisfied ranges "
    + rng('T15_inf') + " at turn 15, when the requirement is introduced, and " + rng('T17_inf') + " at turn 17. On the 17 feasible scenarios the same statement is a false alarm; these range " + rng('T15_fa') + " at turn 15 and " + rng('T17_fa')
    + f" at turn 17, and DeepSeek-V3.2 makes {fa_ds} in its {n_ds} feasible responses. Denominators exclude {unc} of the 400 responses: {NUMW.get(unc_own, unc_own)} that the classifier labelled unclear and {NUMW.get(unc_quote, unc_quote)} whose supporting quote could not be verified. In at least {fa_cap} of the {len(fa)} false alarms the quoted sentence attributes the conflict to slot capacity (developer counts, hours, or story points read as the capacity unit), where the historical prompts are ambiguous (Section~\\ref{{sec:p2}}); these are not simple misreadings of the requirements. The turn-20 responses were not classified.\n")
a = val['agreement']; bp = a['by_reference_packet']
R['validation'] = (f"Two samples (60 selected cases, then 30 further cases) had been labelled beforehand in a separate AI-assisted review, not by human annotators. "
    f"The classifier agreed with that review on {bp['first_packet']['agree']} of {bp['first_packet']['decided']} and on {bp['fresh_packet']['agree']} of {bp['fresh_packet']['decided']} decided cases"
    + (f" ({a['unclear']} labelled unclear)" if a['unclear'] else '') + "; all labels, quotes, disagreements, and the rubric are released.\n")
# P1 tolerance sweep: table rows, the ordering sentence, and the relative-error sentence
ts = load(os.path.join(OUT, 'tolerance_sweep.json')); TOLS = [('0.001', '0.1\\%'), ('0.005', '0.5\\%'), ('0.01', '1\\% (used)'), ('0.02', '2\\%'), ('0.05', '5\\%'), ('0.1', '10\\%')]
TORDER = ['claude-sonnet-4.5', 'deepseek-r1', 'gemini-2.5-pro', 'gpt-4o', 'minimax-m2.5']
R['tab-tolerance'] = ''.join(f"{lab:<20} & " + ' & '.join(f"{ts['with_abs_' + k]['probe'][m]:.3f}" for m in TORDER) + ' \\\\\n' for k, lab in TOLS)
rk = {k: tuple(ts['with_abs_' + k]['probe_ranks'][m] for m in TORDER) for k, _ in TOLS}; same = [lab.split(' ')[0] for k, lab in TOLS if rk[k] == rk['0.01'] and k != '0.01']
exp5 = (1.5, 1.5, 3.0, 4.0, 5.0); exp10 = (1.5, 1.5, 4.0, 3.0, 5.0)
if rk['0.05'] == exp5 and rk['0.1'] == exp10 and len(same) == 3:
    R['tolsentence'] = f"The model order at the 1\\% rule is also obtained at {', '.join(same[:-1])} and {same[-1]}; Sonnet~4.5 ties DeepSeek-V3.2 for first at 5\\% and 10\\%, and GPT-4o passes Gemini~2.5~Pro only at 10\\%.\n"
else:
    R['tolsentence'] = 'Ranks (Sonnet, DeepSeek, Gemini, GPT-4o, MiniMax) by tolerance: ' + '; '.join(f"{lab.split(' ')[0]}: " + ', '.join(f'{x:g}' for x in rk[k]) for k, lab in TOLS) + '.\n'
ed = ts['relative_error_distribution']; n_ = ed['n_single_valued_numeric_answers']
R['errdist'] = (f"Of the {n_:,} single-valued numeric answers, {ed['below_1pct']/n_:.1%} are within 1\\% of the target, {ed['between_1_and_50pct']/n_:.1%} err by between 1\\% and 50\\%, and {ed['above_50pct']/n_:.1%} by more than 50\\%, so moderate changes of the threshold move few scores.\n").replace('%', '\\%').replace('\\\\%', '\\%').replace(',', '{,}', 1)
# Contemporary P3 supplement (Step A): one paragraph, written from gap_types_batched.json; batches are never pooled
gp = os.path.join(OUT, 'gap_types_batched.json'); R['stepA'] = ''
if os.path.exists(gp):
    cb = load(gp)['batches'].get('contemporary', {}); ca = load(gp).get('control_agreement', {})
    NAMES = {'missing_evidence': 'missing-evidence comparison', 'missing_reason': 'missing-reason', 'implied_not_stated': 'implied-not-stated'}
    if cb.get('n_scenarios'):
        intro = ("\\paragraph{Contemporary supplement.} Because the two least-sampled gap types had two scenarios each, we collected a supplement in September 2026 under a plan fixed before collection (released with the artifact): four new scenarios of each of those types, plus the eight supplementary missing-evidence scenarios re-collected in the same batch for comparison. The batches are never pooled. ")
        if cb.get('n_scenarios_complete_panel', 0) == cb['n_scenarios']:
            pt = cb['per_type']; parts = ', '.join(f"{pt[k]['scenarios_any_fab']} of {pt[k]['scenarios']} {NAMES[k]} scenarios" for k in ('missing_evidence', 'missing_reason', 'implied_not_stated') if k in pt)
            pc = cb.get('prespecified_contrasts', {}); tests = '; '.join(f"{'missing reason' if 'reason' in k else 'implied not stated'}: $p = {v['fisher_p']:.2f}$, Holm-adjusted ${v['holm_adjusted_p']:.2f}$" for k, v in pc.items())
            agree = ', '.join(f"{v['agree']}/{v['n']} ({INTEXT.get(m, 'DeepSeek-V3.2, third-party host')})" for m, v in ca.items())
            R['stepA'] = (intro + f"At least one of the five models fabricated in {parts}. The two prespecified scenario-level contrasts against the comparison scenarios (Fisher exact, two-sided) give {tests}; with four scenarios per new type these tests have little power and bound the pattern rather than confirm it. "
                          + (f"On the eight comparison scenarios, the fabrication label agreed between the February and September collections in {agree}. " if agree else '')
                          + "DeepSeek-V3.2 was served by a pinned third-party host in this batch, because the original endpoint no longer serves that model, so its contemporary responses are a cross-provider replication rather than a rerun.\n")
        else:
            d = cb.get('incomplete_panel_descriptive', {}); hist = load(gp)['batches'].get('historical', {}).get('per_scenario', {})
            pl = [f"{d[k]['pair_events']} of {d[k]['pairs']} {NAMES[k]} pairs" for k in ('missing_reason', 'implied_not_stated', 'missing_evidence') if k in d]; parts = ', '.join(pl[:-1]) + ', and ' + pl[-1] if len(pl) > 1 else ''.join(pl)
            flagged = [(sid, m) for sid, dd in cb['per_scenario'].items() for m, v in dd.items() if v]
            notes = []
            for sid, m in flagged:
                hm = [x for x, v in hist.get(sid, {}).items() if v]
                notes.append(f"{INTEXT.get(m, m)}, on a scenario that was flagged for {' and '.join(INTEXT.get(x, x) for x in hm)} in February" if hm and m not in hm else INTEXT.get(m, m))
            pk = os.path.join(OUT, 'stepA_fabrication_flag_audit_packet.md'); audited = None
            if os.path.exists(pk):
                mm = re.search(r'Fabrication confirmed\?[^\n]*:\s*\*\*(yes|no|borderline)\*\*', open(pk).read(), re.I); audited = mm.group(1).lower() if mm else None
            if len(flagged) == 1 and audited == 'yes': notes = [notes[0] + "; confirmed in the author's unblinded audit"]
            ag = sum(v['agree'] for v in ca.values()); an = sum(v['n'] for v in ca.values()); missing = [INTEXT.get(m, 'DeepSeek-V3.2') for m in ('claude-sonnet-4.5', 'deepseek-v3.2', 'gemini-2.5-pro', 'gpt-4o', 'minimax-m2.5') if m not in cb['panel_models']]
            R['stepA'] = (intro + f"{NUMW.get(len(cb['panel_models']), len(cb['panel_models'])).capitalize()} of the five models were collected. The endpoint that served {' and '.join(missing)} in February no longer serves that model, and the planned third-party-hosted session had not been run at the time of writing, so the prespecified scenario-level endpoint, which requires all five models, is not reported. "
                          + f"Descriptively, the judge labelled a fabrication in {parts}" + (f" ({'; '.join(notes)})" if notes else '') + f". On the comparison scenarios, per-model fabrication labels agreed between the two collections in {ag} of {an} cases. These counts are too small to confirm or refute a gap-type effect.\n")
with open(os.path.join(OUT, 'tex_regions.tex'), 'w') as fh:
    for k, v in R.items(): fh.write(f'% BEGIN AUTO:{k}\n{v}% END AUTO:{k}\n\n')
save('incompatibility_claim_summary', {m: {k: list(v[:3]) for k, v in S[m].items()} for m in MODELS} | {'unclear_by_classifier': unc_own, 'unclear_unverified_quote': unc_quote, 'false_alarms_total': len(fa), 'false_alarms_quote_concerns_capacity': fa_cap, 'unclear_total': unc})
tex = os.path.join(HERE, '..', 'tbench_submission_r2.tex')
if LAYOUT == 'dev' and os.path.exists(tex):
    s = open(tex).read(); missing = []
    for k, v in R.items():
        pat = re.compile(r'(% BEGIN AUTO:' + re.escape(k) + r'\n).*?(% END AUTO:' + re.escape(k) + r'\n)', re.S)
        if not pat.search(s): missing.append(k); continue
        s = pat.sub(lambda mm: mm.group(1) + v + mm.group(2), s)
    open(tex, 'w').write(s); print('patched manuscript; regions not present in the .tex:', missing)
for k in ('claims', 'validation'): print(f'--- {k}\n{R[k]}')
