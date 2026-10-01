"""R2 comment 3: complete P2 ranking comparison under the three plan parsers.
v1 = original rigid regex parser (values recorded by p2_parser_fix2.py as 'original');
v2 = patched parser in score_responses.py (think-tag stripping, markdown tables, parentheticals);
v3 = enhanced format-tolerant parser (values used in the paper)."""
import collections
from common import *
cmp = load(RESCORE_CMP)['comparison']
v2 = load(V2); v3 = load(FIXED)
def avg(d):
    s = collections.defaultdict(list)
    for e in d:
        if e['paradigm'] == 'P2': s[e['model']].append(e['avg_satisfaction_rate'])
    return {m: sum(v) / len(v) for m, v in s.items()}
a1 = {m: cmp[m]['satisfaction_original'] for m in MODELS}; a2 = avg(v2); a3 = avg(v3)
r1 = dict(zip(MODELS, ranks_desc([a1[m] for m in MODELS]))); r2 = dict(zip(MODELS, ranks_desc([a2[m] for m in MODELS]))); r3 = dict(zip(MODELS, ranks_desc([a3[m] for m in MODELS])))
rows = [{'model': LABELS[m], 'v1_rigid': round(a1[m], 3), 'v1_rank': r1[m], 'v2_patched': round(a2[m], 3), 'v2_rank': r2[m], 'v3_enhanced': round(a3[m], 3), 'v3_rank': r3[m],
         'delta_v3_minus_v1': round(a3[m] - a1[m], 3), 'delta_v3_minus_v2': round(a3[m] - a2[m], 3),
         'per_turn_v1': {t: cmp[m]['per_turn'][t]['original'] for t in ('T6', 'T11', 'T17', 'T20')},
         'per_turn_v3': {t: cmp[m]['per_turn'][t]['enhanced'] for t in ('T6', 'T11', 'T17', 'T20')}} for m in MODELS]
md = '| Model | v1 rigid (rank) | v2 patched (rank) | v3 enhanced (rank) |\n|---|---|---|---|\n' + ''.join(
    f"| {r['model']} | {r['v1_rigid']:.3f} ({r['v1_rank']:g}) | {r['v2_patched']:.3f} ({r['v2_rank']:g}) | {r['v3_enhanced']:.3f} ({r['v3_rank']:g}) |\n" for r in sorted(rows, key=lambda r: -r['v3_enhanced']))
print(md); save('parser_comparison', rows, md)
