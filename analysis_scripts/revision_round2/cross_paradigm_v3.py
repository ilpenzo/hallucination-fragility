"""Cross-paradigm summary under scoring protocol v3.1 (manuscript Table "Cross-paradigm summary" and the
rank-stability paragraph).

Primary metric per paradigm:
  P1  phase-end accuracy (T5/T10/T15/T20) from the adjudicated score file (AI-review overrides applied);
  P2  complete-valid-plan rate on feasible post-revision checkpoints (feasible T17 and T20), with the fractional
      satisfaction on the same checkpoints for reference (both read from p2_v3_checkpoints_core.json);
  P3  gap abstention rate over the 20 core scenarios (judge output files).
Statistics: Spearman correlations with EXACT two-sided permutation p-values (5 models -> 120 permutations; the
t approximation is also printed for reference), Kendall's W with tie correction, its chi-square approximation and
an exact permutation reference (120 x 120 relabelings of two of the three rankings).
Rank stability: scenario-level bootstrap. Scenarios are resampled with replacement within each paradigm (the three
paradigms use different scenarios), the same draw is applied to all five models, and for P2 a scenario carries all
of its feasible post-revision checkpoints (cluster bootstrap), so T17/T20 of one scenario are never split."""
import glob, random, itertools, collections, math
from common import *
random.seed(20260917); B = 2000
adj = load(ADJUDICATED if os.path.exists(ADJUDICATED) else FIXED)
p1 = {m: {} for m in MODELS}
for e in adj:
    if e['paradigm'] == 'P1': p1[e['model']][e['scenario_id']] = e['probe_accuracy']
rows = load(os.path.join(OUT, 'p2_v3_checkpoints_core.json'))
p2 = {m: collections.defaultdict(list) for m in MODELS}     # scenario -> [(valid, sat)] over feasible post-revision checkpoints
for r in rows:
    if r['feasible'] and r['turn'] >= 17: p2[r['model']][r['scenario']].append((float(r['valid_complete_plan']), r['sat_v3']))
p3 = {m: {} for m in MODELS}
for f in glob.glob(os.path.join(JUDGED, '*.json')):
    j = load(f); g = j['gap_scores']; p3[j['model']][j['scenario_id']] = (sum(v['abstained'] for v in g.values()), len(g))
def p1_score(m, S): return sum(p1[m][s] for s in S) / len(S)
def p2_valid(m, S): c = [v for s in S for v, _ in p2[m][s]]; return sum(c) / len(c)
def p2_sat(m, S): c = [x for s in S for _, x in p2[m][s]]; return sum(c) / len(c)
def p3_score(m, S): return sum(p3[m][s][0] for s in S) / sum(p3[m][s][1] for s in S)
S1 = sorted(p1[MODELS[0]]); S2 = sorted(p2[MODELS[0]]); S3 = sorted(p3[MODELS[0]])
n2 = sum(len(p2[MODELS[0]][s]) for s in S2)
point = {m: {'P1': p1_score(m, S1), 'P2_valid': p2_valid(m, S2), 'P2_valid_n': [int(sum(v for s in S2 for v, _ in p2[m][s])), n2], 'P2_sat': p2_sat(m, S2), 'P3': p3_score(m, S3)} for m in MODELS}
R1 = ranks_desc([point[m]['P1'] for m in MODELS]); R2 = ranks_desc([point[m]['P2_valid'] for m in MODELS]); R3 = ranks_desc([point[m]['P3'] for m in MODELS])
def pearson(x, y):
    n = len(x); mx = sum(x) / n; my = sum(y) / n; sx = math.sqrt(sum((a - mx) ** 2 for a in x)); sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)
def spearman_exact(rx, ry):
    rho = pearson(rx, ry); perms = list(itertools.permutations(ry)); hits = sum(1 for p in perms if abs(pearson(rx, list(p))) >= abs(rho) - 1e-12)
    n = len(rx); t = rho * math.sqrt((n - 2) / max(1e-12, 1 - rho * rho))
    return {'rho': rho, 'p_exact_two_sided': hits / len(perms), 't_approx_statistic': t}
def kendall_w(rk):
    m = len(rk); n = len(rk[0]); Rj = [sum(r[j] for r in rk) for j in range(n)]; S = sum((x - sum(Rj) / n) ** 2 for x in Rj)
    T = sum(sum(c ** 3 - c for c in collections.Counter(r).values()) for r in rk)
    return 12 * S / (m * m * (n ** 3 - n) - m * T)
def chi2_sf(x, k):  # regularized upper incomplete gamma Q(k/2, x/2), series/continued fraction
    a = k / 2.0; x = x / 2.0
    if x <= 0: return 1.0
    if x < a + 1:
        ap = a; s = d = 1.0 / a
        for _ in range(500):
            ap += 1; d *= x / ap; s += d
            if abs(d) < abs(s) * 1e-14: break
        return 1.0 - s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    b = x + 1 - a; c = 1e300; d = 1.0 / b; h = d
    for i in range(1, 500):
        an = -i * (i - a); b += 2; d = an * d + b; d = 1e-300 if abs(d) < 1e-300 else d; c = b + an / c; c = 1e-300 if abs(c) < 1e-300 else c; d = 1.0 / d; de = d * c; h *= de
        if abs(de - 1) < 1e-14: break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
W = kendall_w([R1, R2, R3]); chi2 = 3 * (5 - 1) * W
perm_hits = perm_n = 0
for a in itertools.permutations(R2):
    for b in itertools.permutations(R3):
        perm_n += 1; perm_hits += kendall_w([R1, list(a), list(b)]) >= W - 1e-12
stats = {'spearman': {'P1-P2': spearman_exact(R1, R2), 'P1-P3': spearman_exact(R1, R3), 'P2-P3': spearman_exact(R2, R3)},
         'kendalls_w_tie_corrected': W, 'chi2': chi2, 'df': 4, 'p_chi2_approx': chi2_sf(chi2, 4), 'p_permutation_exact': perm_hits / perm_n}
cnt = collections.Counter(); mi, ds, gp, so, ge = (MODELS.index(x) for x in ('minimax-m2.5', 'deepseek-r1', 'gpt-4o', 'claude-sonnet-4.5', 'gemini-2.5-pro'))
for _ in range(B):
    b1 = [random.choice(S1) for _ in S1]; b2 = [random.choice(S2) for _ in S2]; b3 = [random.choice(S3) for _ in S3]
    r1 = ranks_desc([p1_score(m, b1) for m in MODELS]); r2 = ranks_desc([p2_valid(m, b2) for m in MODELS]); r3 = ranks_desc([p3_score(m, b3) for m in MODELS])
    cnt['MiniMax last on P1'] += r1[mi] == 5; cnt['MiniMax first on P3'] += r3[mi] == 1; cnt['MiniMax last on P1 and first on P3'] += (r1[mi] == 5 and r3[mi] == 1)
    cnt['DeepSeek first on P2 valid-plan rate'] += r2[ds] == 1; cnt['GPT-4o last on P2 valid-plan rate'] += r2[gp] == 5
    cnt['Sonnet second on P2 valid-plan rate'] += r2[so] == 2; cnt['DeepSeek top-2 on P1'] += r1[ds] <= 2
stab = {k: v / B for k, v in cnt.items()}
md = '| Model | P1 phase-end acc. (rank) | P2 valid plans, feasible post-revision (rank) | P2 sat. (same checkpoints) | P3 gap abstention (rank) |\n|---|---|---|---|---|\n'
for i, m in enumerate(MODELS):
    q = point[m]; md += f"| {LABELS[m]} | {q['P1']:.3f} ({R1[i]:g}) | {q['P2_valid_n'][0]}/{q['P2_valid_n'][1]} = {q['P2_valid']:.2f} ({R2[i]:g}) | {q['P2_sat']:.3f} | {q['P3']:.3f} ({R3[i]:g}) |\n"
md += '\n## Rank statistics (5 models; descriptive)\n' + ''.join(f"- Spearman {k}: rho = {v['rho']:+.2f}, exact two-sided permutation p = {v['p_exact_two_sided']:.3f}\n" for k, v in stats['spearman'].items())
md += f"- Kendall's W (tie-corrected) = {W:.3f}; chi2 = {chi2:.2f}, df = 4, p = {stats['p_chi2_approx']:.3f} (chi-square approx.); exact permutation p = {stats['p_permutation_exact']:.3f}\n"
md += f'\n## Scenario-level bootstrap rank stability ({B} resamples; P1 n={len(S1)} scenarios, P2 n={len(S2)} scenarios / {n2} checkpoints, P3 n={len(S3)} scenarios)\n' + ''.join(f'- {k}: {v:.3f}\n' for k, v in stab.items())
print(md); save('cross_paradigm_v3', {'p1_source': rel(ADJUDICATED if os.path.exists(ADJUDICATED) else FIXED), 'point': point, 'ranks': {'P1': R1, 'P2': R2, 'P3': R3}, 'stats': stats, 'bootstrap_resamples': B, 'rank_stability': stab}, md)
