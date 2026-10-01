"""Fill the incompatibility-claim placeholders in tbench_submission_r2.tex from the LLM labels
(outputs/incompatibility_llm_labels_core_feb2026.json) and the validation output. T20 is not classified."""
import json, collections, re
from common import *
lab = {(r['model'], r['scenario'], r['turn']): r.get('effective_label') for r in load(os.path.join(OUT, 'incompatibility_llm_labels_core_feb2026.json'))['records']}
cls = load(os.path.join(OUT, 'p2_feasibility_classes.json')); val = load(os.path.join(OUT, 'incompatibility_rates.json'))
def rate(m, tn, klass):
    ks = [k for k in lab if k[0] == m and k[2] == tn and cls.get(f'{k[1]}|T{tn}') == klass]
    yes = sum(lab[k] == 'YES' for k in ks); dec = sum(lab[k] in ('YES', 'NO') for k in ks); unc = sum(lab[k] == 'UNCLEAR' for k in ks)
    return yes, dec, unc, len(ks)
tex_path = os.path.join(os.path.dirname(__file__), '..', 'tbench_submission_r2.tex'); s = open(tex_path).read()
tag = {'deepseek-r1': 'DEEPSEEK', 'claude-sonnet-4.5': 'SONNET', 'gemini-2.5-pro': 'GEMINI', 'minimax-m2.5': 'MINIMAX', 'gpt-4o': 'GPT'}
summary = {}
for m in MODELS:
    y, d, u, n = rate(m, 17, 'genuine_conflict'); s = s.replace(f'CLAIM17{tag[m]}', f'{y}/{d}' + (f' ({u} unclear)' if u else ''))
    s = s.replace(f'CLAIM20{tag[m]}', '---')
    y15, d15, u15, _ = rate(m, 15, 'genuine_conflict'); fa15 = rate(m, 15, 'spurious_conflict'); fa17 = rate(m, 17, 'spurious_conflict')
    summary[m] = {'claim_T17_infeasible': [y, d, u], 'claim_T15_infeasible': [y15, d15, u15], 'false_alarm_T15_feasible': list(fa15[:3]), 'false_alarm_T17_feasible': list(fa17[:3])}
def f(m, key): y, d, u = summary[m][key]; return f'{y}/{d}'
order = ['deepseek-r1', 'claude-sonnet-4.5', 'gemini-2.5-pro', 'minimax-m2.5', 'gpt-4o']
para = ("On the 23 infeasible scenarios, the share of turn-17 responses that state that the active requirements cannot all be satisfied is "
        + ', '.join(f"{f(m,'claim_T17_infeasible')} for {LABELS[m]}" for m in order)
        + " (Table~\\ref{tab:p2-infeasible}; responses labelled unclear are excluded from the denominators). At turn 15, when the requirement is introduced, the corresponding shares are "
        + ', '.join(f"{f(m,'claim_T15_infeasible')} ({LABELS[m]})" for m in order)
        + ". On the 17 feasible scenarios the same claim is a false alarm: at turn 15 it occurs in "
        + ', '.join(f"{f(m,'false_alarm_T15_feasible')} ({LABELS[m]})" for m in order)
        + " responses and at turn 17 in "
        + ', '.join(f"{f(m,'false_alarm_T17_feasible')} ({LABELS[m]})" for m in order)
        + ". Some false alarms follow the unit ambiguity in the historical capacity tables rather than a misreading of the requirements. The turn-20 responses were not classified, so no turn-20 claim rates are reported.")
s = s.replace('CLAIMSPARAGRAPH', para)
a = val['agreement']
vs = (f"Against an independently labelled selected sample of 90 responses (AI review, not human annotation), the classifier agreed on {a['agree']} of the {a['decided']} cases it decided"
      + (f" and labelled {a['unclear']} as unclear" if a['unclear'] else '') + "; the disagreements and all labels, quotes, and the rubric are released.")
s = s.replace('VALIDATIONSENTENCE', vs)
s = s.replace("The incompatibility-claim rate is the share of responses whose visible answer asserts that the active requirements cannot all be satisfied (rubric classification, Section~\\ref{sec:p2}); the corresponding false-alarm rate on feasible checkpoints is given in the text.",
              "Incompatibility claim: responses whose visible answer asserts that the active requirements cannot all be satisfied, over responses with a decided label (rubric classification, Section~\\ref{sec:p2}; turn 20 not classified). False alarms on feasible checkpoints are given in the text.")
open(tex_path, 'w').write(s); save('incompatibility_claim_summary', summary); print(json.dumps(summary, indent=1)); print('placeholders left:', len(re.findall(r'CLAIM17|CLAIM20|CLAIMSPARAGRAPH|VALIDATIONSENTENCE', s)))
