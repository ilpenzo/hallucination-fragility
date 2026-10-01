#!/usr/bin/env python3
"""
recompute_cross_paradigm_stats.py
Reproduces the corrected cross-paradigm statistics for the JLCL paper.

WHY THIS EXISTS
---------------
The paper's printed cross-paradigm stats (W=0.089, P1xP3 rho=-0.895, p=0.040)
do NOT reproduce from the data in Table 4. They were computed on STALE,
pre-fix P1 probe values and are an artifact that does not match either the
pre-fix or post-fix data. This script recomputes everything from the
POST-FIX P1 probe values that appear in Table 1 / Table 4 (the values the
fix_p1_comprehensive.py correction produced, which are the correct ones).

Run:  python recompute_cross_paradigm_stats.py
Needs: numpy, scipy
"""

import numpy as np
from scipy import stats

models = ["Sonnet", "DeepSeek", "Gemini", "GPT-4o", "MiniMax"]

# ── POST-FIX P1 probe values (Table 1 / Table 4 — the CORRECT ones) ──
P1 = [0.995, 0.995, 0.965, 0.955, 0.890]
# P2 satisfaction (Table 2 / Table 4)
P2 = [0.832, 0.961, 0.782, 0.785, 0.862]
# P3 gap abstention (Table 3 / Table 4)
P3_gap = [0.885, 0.875, 0.930, 0.875, 0.975]
# P3 fabrication rate (Table 3)
P3_fab = [0.050, 0.100, 0.000, 0.100, 0.000]

# ── STALE pre-fix P1 (for reference only — do NOT use in the paper) ──
P1_stale = [0.690, 0.870, 0.925, 0.870, 0.485]


def kendalls_w(metric_vectors, tie_correction=False):
    """Kendall's W across m metric-rankings of n items (higher value = better)."""
    arr = np.array(metric_vectors, dtype=float)
    m, n = arr.shape
    ranks = np.vstack([stats.rankdata(row) for row in arr])
    Rj = ranks.sum(axis=0)
    S = np.sum((Rj - Rj.mean()) ** 2)
    if tie_correction:
        T = 0.0
        for row in arr:
            _, counts = np.unique(row, return_counts=True)
            T += np.sum(counts ** 3 - counts)
        denom = m ** 2 * (n ** 3 - n) - m * T
    else:
        denom = m ** 2 * (n ** 3 - n)
    W = 12 * S / denom
    chi2 = m * (n - 1) * W
    p = 1 - stats.chi2.cdf(chi2, n - 1)
    return W, chi2, n - 1, p


print("=" * 66)
print("CORRECTED CROSS-PARADIGM STATISTICS (post-fix P1, matches Table 4)")
print("=" * 66)

print("\nKendall's W (P1 probe, P2 sat, P3 gap abstention):")
W, chi2, df, p = kendalls_w([P1, P2, P3_gap], tie_correction=False)
print(f"  uncorrected : W = {W:.3f}, chi2 = {chi2:.3f}, df = {df}, p = {p:.3f}")
Wc, chi2c, dfc, pc = kendalls_w([P1, P2, P3_gap], tie_correction=True)
print(f"  tie-corrected: W = {Wc:.3f}, chi2 = {chi2c:.3f}, df = {dfc}, p = {pc:.3f}")
print("  -> paper reports the uncorrected value (matches the original pipeline).")

print("\nSpearman correlations (descriptive; n=5):")
for label, x, y in [
    ("P1 x P2     ", P1, P2),
    ("P1 x P3_gap ", P1, P3_gap),
    ("P2 x P3_gap ", P2, P3_gap),
    ("P3gap x P3fab", P3_gap, P3_fab),
]:
    rho, pp = stats.spearmanr(x, y)
    print(f"  {label}: rho = {rho:+.3f}, p = {pp:.3f}")

print("\n" + "=" * 66)
print("VALUES NOW IN THE PAPER (after correction)")
print("=" * 66)
print("""  Kendall's W = 0.228 (chi2 = 2.733, df = 4, p = 0.603)
  P1 x P2      rho = +0.205, p = 0.741
  P1 x P3      rho = -0.500, p = 0.391   (NOT significant)
  P2 x P3      rho = -0.154, p = 0.805
  P3gap x P3fab rho = -0.973, p = 0.005  (sign corrected; was +0.973)""")

print("\n" + "=" * 66)
print("FOR REFERENCE: what the stale pre-fix P1 would give (do NOT use)")
print("=" * 66)
Ws, chi2s, dfs, ps = kendalls_w([P1_stale, P2, P3_gap])
print(f"  Kendall's W = {Ws:.3f}, p = {ps:.3f}")
for label, x, y in [("P1 x P2", P1_stale, P2), ("P1 x P3", P1_stale, P3_gap)]:
    rho, pp = stats.spearmanr(x, y)
    print(f"  {label}: rho = {rho:+.3f}, p = {pp:.3f}")
print("  (Note: neither these nor the post-fix values reproduce the paper's")
print("   original -0.895 — that number was a stale artifact, now removed.)")
