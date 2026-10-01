"""R2 comment 5 / R3 comment 2: confidence intervals and exact tests for gap-type fabrication rates."""
import math
from math import comb
from common import *
def wilson(k, n, z=1.96):
    ph = k / n; den = 1 + z * z / n; c = (ph + z * z / (2 * n)) / den; h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)
def fisher(a, b, c, d):
    n = a + b + c + d; r1 = a + b; c1 = a + c
    p = lambda x: comb(r1, x) * comb(n - r1, c1 - x) / comb(n, c1); p0 = p(a)
    return sum(p(x) for x in range(max(0, c1 - (n - r1)), min(r1, c1) + 1) if p(x) <= p0 + 1e-12)
sup = load(os.path.join(ROOT, 'supplementary_p3_analysis.json'))['updated_gap_type_table']
types = {t: (v['n_fabrication_events'], v['n_model_scenario_pairs'], v['n_gaps']) for t, v in sup.items()}
out = {'per_type': {}}; md = '| Gap type | Gaps | Model-scenario pairs | Fabrication events | Rate | Wilson 95% CI |\n|---|---|---|---|---|---|\n'
for t, (k, n, g) in types.items():
    lo, hi = wilson(k, n); out['per_type'][t] = {'events': k, 'pairs': n, 'gaps': g, 'rate': k / n, 'ci95': [lo, hi]}
    md += f'| {t} | {g} | {n} | {k} | {k/n:.3f} | [{lo:.3f}, {hi:.3f}] |\n'
me_k, me_n, _ = types['missing_evidence']
ok = sum(k for t, (k, n, g) in types.items() if t != 'missing_evidence'); on = sum(n for t, (k, n, g) in types.items() if t != 'missing_evidence')
out['fisher'] = {'missing_evidence_vs_all_other': fisher(me_k, me_n - me_k, ok, on - ok),
                 'missing_evidence_vs_missing_detail': fisher(me_k, me_n - me_k, types['missing_detail'][0], types['missing_detail'][1] - types['missing_detail'][0]),
                 'missing_evidence_vs_zero_rate_types_pooled': fisher(me_k, me_n - me_k, 0, types['missing_number'][1] + types['missing_reason'][1] + types['implied_not_stated'][1])}
# scenario-level (events cluster in scenarios): scenarios with >=1 fabrication among 13 ME vs 15 other scenarios
out['fisher']['scenario_level_any_fabrication'] = fisher(3, 10, 1, 14)
md += '\nFisher exact (two-sided): ' + '; '.join(f'{k}: p={v:.3f}' for k, v in out['fisher'].items()) + '\n'
print(md); save('gap_type_stats', out, md)
