"""R2 comment 4: raw-score (unbinned) agreement between the two P3 judges."""
import csv, math
from common import *
rows = list(csv.DictReader(open(IRR_CSV)))
dims = [('contradiction_identified', 'opus_contr_id', 'gpt52_contr_id'), ('contradiction_resolved', 'opus_contr_res', 'gpt52_contr_res'),
        ('reasoning_quality', 'opus_reasoning', 'gpt52_reasoning'), ('gap_abstention', 'opus_gap_abst', 'gpt52_gap_abst')]
def pearson(x, y):
    n = len(x); mx = sum(x) / n; my = sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y)); sxx = sum((a - mx) ** 2 for a in x); syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else None
out = {}; md = '| Dimension | Exact agreement | Within 0.1 | Mean abs. diff. | Max abs. diff. | Pearson r (raw) |\n|---|---|---|---|---|---|\n'
for name, a, b in dims:
    x = [float(r[a]) for r in rows]; y = [float(r[b]) for r in rows]; d = [abs(p - q) for p, q in zip(x, y)]
    rec = {'exact_agreement': sum(1 for v in d if v < 1e-9) / len(d), 'within_0.1': sum(1 for v in d if v <= 0.1 + 1e-9) / len(d), 'mean_abs_diff': sum(d) / len(d), 'max_abs_diff': max(d), 'pearson_r': pearson(x, y)}
    out[name] = rec
    r_txt = 'undefined (no variance)' if rec['pearson_r'] is None else f"{rec['pearson_r']:.3f}"
    md += f"| {name} | {rec['exact_agreement']:.2f} | {rec['within_0.1']:.2f} | {rec['mean_abs_diff']:.3f} | {rec['max_abs_diff']:.2f} | {r_txt} |\n"
fa = [r['opus_fab'] == 'True' for r in rows]; fb = [r['gpt52_fab'] == 'True' for r in rows]
out['fabrication'] = {'exact_agreement': sum(1 for p, q in zip(fa, fb) if p == q) / len(fa), 'opus_true': sum(fa), 'gpt52_true': sum(fb)}
md += f"| fabrication (boolean) | {out['fabrication']['exact_agreement']:.2f} | – | – | – | – |\n"
print(md); save('irr_raw_agreement', out, md)
