#!/usr/bin/env python3
"""
recompute_kendalls_w.py — Recompute Kendall's W and Spearman correlations
after Gemini P1 data fix.

Reads directly from three_paradigm_summary.json (which already contains
updated Gemini P1 numbers and enhanced P2 parser values).

All 5 models now have P3 data, so we compute W across all 5 models × 3 paradigms.

Usage:
  python recompute_kendalls_w.py \
    --three-paradigm ./analysis/three_paradigm_summary.json \
    --output ./supplementary_analysis/orthogonality_stats_5model.json
"""

import json
import math
import argparse
from itertools import combinations
from typing import List, Dict, Tuple


# ==============================================================================
# STATISTICAL HELPERS
# ==============================================================================

def _to_ranks(values: List[float], higher_is_better: bool = True) -> List[float]:
    """Convert values to ranks. Handles ties with average rank.
    If higher_is_better=True, highest value gets rank 1."""
    indexed = sorted(enumerate(values), key=lambda x: x[1],
                     reverse=higher_is_better)
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j + 1) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def kendalls_w(ranking_matrix: List[List[float]]) -> float:
    """Kendall's W (coefficient of concordance).
    ranking_matrix: k lists of length n (k raters, n objects)."""
    k = len(ranking_matrix)
    n = len(ranking_matrix[0])
    rank_sums = [0.0] * n
    for rater_ranks in ranking_matrix:
        for j in range(n):
            rank_sums[j] += rater_ranks[j]
    mean_sum = sum(rank_sums) / n
    S = sum((rs - mean_sum) ** 2 for rs in rank_sums)
    S_max = (k ** 2 * (n ** 3 - n)) / 12.0
    if S_max == 0:
        return 0.0
    return S / S_max


def spearman_rho(x: List[float], y: List[float]) -> float:
    """Spearman's rank correlation coefficient."""
    n = len(x)
    if n < 2:
        return 0.0
    rx = _to_ranks(x, higher_is_better=False)  # raw ranks for correlation
    ry = _to_ranks(y, higher_is_better=False)
    mean_rx = sum(rx) / n
    mean_ry = sum(ry) / n
    num = sum((rx[i] - mean_rx) * (ry[i] - mean_ry) for i in range(n))
    den_x = math.sqrt(sum((rx[i] - mean_rx) ** 2 for i in range(n)))
    den_y = math.sqrt(sum((ry[i] - mean_ry) ** 2 for i in range(n)))
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def spearman_p_value(rho: float, n: int) -> float:
    """Approximate p-value for Spearman correlation using t-distribution approx."""
    if n <= 2 or abs(rho) >= 1.0:
        return 0.0 if abs(rho) >= 1.0 else 1.0
    t_stat = rho * math.sqrt((n - 2) / (1 - rho ** 2))
    # Two-tailed p-value using normal approximation for small n
    # (t-distribution with n-2 df, but for n=5, df=3, normal is rough)
    df = n - 2
    # Use regularized incomplete beta function approximation
    # For simplicity, use the standard lookup for small df
    return _t_p_value(abs(t_stat), df)


def _t_p_value(t: float, df: int) -> float:
    """Two-tailed p-value for t-distribution (approximation)."""
    # Use the relationship: p = I_x(df/2, 1/2) where x = df/(df + t^2)
    x = df / (df + t * t)
    # Regularized incomplete beta via continued fraction
    p = _regularized_incomplete_beta(x, df / 2.0, 0.5)
    return p  # two-tailed


def _regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta function I_x(a, b) via continued fraction."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    # Use the continued fraction expansion (Lentz's method)
    # For numerical stability
    lnbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lnbeta) / a

    # Modified Lentz's method
    f = 1.0
    c = 1.0
    d = 1.0 - (a + b) * x / (a + 1.0)
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    f = d

    for m in range(1, 200):
        # Even step
        numerator = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
        d = 1.0 + numerator * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + numerator / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        f *= d * c

        # Odd step
        numerator = -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + numerator * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + numerator / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        f *= delta
        if abs(delta - 1.0) < 1e-10:
            break

    return front * f


def chi2_p_value(chi2: float, df: int) -> float:
    """Upper-tail p-value for chi-square (Wilson-Hilferty approx)."""
    if df <= 0 or chi2 <= 0:
        return 1.0
    z = ((chi2 / df) ** (1.0 / 3.0) - (1 - 2.0 / (9 * df))) / math.sqrt(2.0 / (9 * df))
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p_const = 0.3275911
    sign = 1 if z >= 0 else -1
    z_abs = abs(z)
    t = 1.0 / (1.0 + p_const * z_abs)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-z_abs * z_abs / 2.0)
    p_lower = 0.5 * (1.0 + sign * y)
    return max(0.0, 1.0 - p_lower)


# ==============================================================================
# MAIN COMPUTATION
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Recompute Kendall's W after Gemini fix")
    parser.add_argument("--three-paradigm", required=True,
                        help="Path to three_paradigm_summary.json")
    parser.add_argument("--output", required=True,
                        help="Output JSON path")
    args = parser.parse_args()

    with open(args.three_paradigm) as f:
        tp = json.load(f)

    # Extract model data from cross_paradigm table
    models = []
    for entry in tp["cross_paradigm"]:
        models.append({
            "model": entry["model"],
            "display_name": entry["display_name"],
            "P1_probe": entry["P1_probe"],
            "P2_satisfaction": entry["P2_satisfaction"],
            "P3_gap_abstained": entry["P3_gap_abstained"],
            "P3_fabrication_rate": entry["P3_fabrication_rate"],
        })

    model_names = [m["model"] for m in models]
    n = len(model_names)

    print(f"\n{'='*70}")
    print("KENDALL'S W RECOMPUTATION (post-Gemini fix)")
    print(f"{'='*70}")
    print(f"\nModels: {n}")
    print(f"\n{'Model':25s} {'P1 Probe':>10s} {'P2 Sat':>10s} {'P3 Gap':>10s} {'P3 Fab':>10s}")
    print("-" * 70)
    for m in models:
        print(f"{m['display_name']:25s} {m['P1_probe']:10.3f} {m['P2_satisfaction']:10.3f} "
              f"{m['P3_gap_abstained']:10.3f} {m['P3_fabrication_rate']:10.3f}")

    # --- Compute ranks (higher = rank 1) ---
    p1_values = [m["P1_probe"] for m in models]
    p2_values = [m["P2_satisfaction"] for m in models]
    p3_gap_values = [m["P3_gap_abstained"] for m in models]
    p3_fab_values = [m["P3_fabrication_rate"] for m in models]

    p1_ranks = _to_ranks(p1_values, higher_is_better=True)
    p2_ranks = _to_ranks(p2_values, higher_is_better=True)
    p3_gap_ranks = _to_ranks(p3_gap_values, higher_is_better=True)
    p3_fab_ranks = _to_ranks(p3_fab_values, higher_is_better=False)  # lower is better

    print(f"\n{'Model':25s} {'P1 Rank':>8s} {'P2 Rank':>8s} {'P3Gap Rank':>10s} {'P3Fab Rank':>10s} {'Spread':>8s}")
    print("-" * 76)
    for i, m in enumerate(models):
        spread = max(p1_ranks[i], p2_ranks[i], p3_gap_ranks[i]) - min(p1_ranks[i], p2_ranks[i], p3_gap_ranks[i])
        print(f"{m['display_name']:25s} {p1_ranks[i]:8.1f} {p2_ranks[i]:8.1f} "
              f"{p3_gap_ranks[i]:10.1f} {p3_fab_ranks[i]:10.1f} {spread:8.1f}")

    # === PRIMARY: W across P1 probe × P2 satisfaction × P3 gap_abstained ===
    print(f"\n--- Kendall's W: P1 probe × P2 satisfaction × P3 gap_abstained ({n} models) ---")
    ranking_matrix_primary = [p1_ranks, p2_ranks, p3_gap_ranks]
    k_primary = 3
    W_primary = kendalls_w(ranking_matrix_primary)
    chi2_primary = k_primary * (n - 1) * W_primary
    p_primary = chi2_p_value(chi2_primary, n - 1)
    print(f"  W = {W_primary:.4f}")
    print(f"  χ²({n-1}) = {chi2_primary:.3f}, p = {p_primary:.4f}")

    # === SENSITIVITY 1: P3 fabrication instead of gap_abstained ===
    print(f"\n--- Sensitivity: P1 × P2 × P3 fabrication ({n} models) ---")
    ranking_matrix_fab = [p1_ranks, p2_ranks, p3_fab_ranks]
    W_fab = kendalls_w(ranking_matrix_fab)
    chi2_fab = 3 * (n - 1) * W_fab
    p_fab = chi2_p_value(chi2_fab, n - 1)
    print(f"  W = {W_fab:.4f}")
    print(f"  χ²({n-1}) = {chi2_fab:.3f}, p = {p_fab:.4f}")

    # === SENSITIVITY 2: All 4 metrics ===
    print(f"\n--- Sensitivity: All 4 metrics ({n} models) ---")
    ranking_matrix_all4 = [p1_ranks, p2_ranks, p3_gap_ranks, p3_fab_ranks]
    W_all4 = kendalls_w(ranking_matrix_all4)
    chi2_all4 = 4 * (n - 1) * W_all4
    p_all4 = chi2_p_value(chi2_all4, n - 1)
    print(f"  W = {W_all4:.4f}")
    print(f"  χ²({n-1}) = {chi2_all4:.3f}, p = {p_all4:.4f}")

    # === PAIRWISE SPEARMAN ===
    print(f"\n--- Pairwise Spearman Correlations ({n} models) ---")
    metric_pairs = {
        "P1_probe": p1_values,
        "P2_satisfaction": p2_values,
        "P3_gap_abstained": p3_gap_values,
        "P3_fabrication_rate": [-v for v in p3_fab_values],  # negate so higher = better
    }

    spearman_results = {}
    for (name_a, vals_a), (name_b, vals_b) in combinations(metric_pairs.items(), 2):
        rho = spearman_rho(vals_a, vals_b)
        p_val = spearman_p_value(rho, n)
        pair_key = f"{name_a} × {name_b}"
        spearman_results[pair_key] = {"rho": round(rho, 4), "p_value": round(p_val, 4)}
        sig = "*" if p_val < 0.05 else ""
        print(f"  {pair_key:50s}  ρ = {rho:+.4f}  (p = {p_val:.4f}){sig}")

    # === BUILD RANK TABLE FOR PAPER ===
    rank_table = []
    for i, m in enumerate(models):
        spread = max(p1_ranks[i], p2_ranks[i], p3_gap_ranks[i]) - \
                 min(p1_ranks[i], p2_ranks[i], p3_gap_ranks[i])
        rank_table.append({
            "model": m["display_name"],
            "P1_rank": p1_ranks[i],
            "P2_rank": p2_ranks[i],
            "P3_rank": p3_gap_ranks[i],
            "spread": spread,
        })
    rank_table.sort(key=lambda x: -x["spread"])

    print(f"\n--- Rank Table (sorted by spread, for paper) ---")
    print(f"{'Model':25s} {'P1':>5s} {'P2':>5s} {'P3':>5s} {'Spread':>7s}")
    print("-" * 50)
    for r in rank_table:
        print(f"{r['model']:25s} {r['P1_rank']:5.1f} {r['P2_rank']:5.1f} "
              f"{r['P3_rank']:5.1f} {r['spread']:7.1f}")

    # === COMPARISON WITH OLD VALUES ===
    print(f"\n--- Comparison with pre-fix values ---")
    print(f"  Old W (3 metrics): 0.089  → New W: {W_primary:.4f}")
    print(f"  Old P1×P2 ρ: -0.051      → New: {spearman_results.get('P1_probe × P2_satisfaction', {}).get('rho', 'N/A')}")
    print(f"  Old P1×P3 ρ: -0.895      → New: {spearman_results.get('P1_probe × P3_gap_abstained', {}).get('rho', 'N/A')}")
    print(f"  Old P2×P3 ρ: -0.154      → New: {spearman_results.get('P2_satisfaction × P3_gap_abstained', {}).get('rho', 'N/A')}")

    # === SAVE ===
    output = {
        "description": "Kendall's W and Spearman correlations — post Gemini P1 fix",
        "n_models": n,
        "models": model_names,
        "metrics_used": {
            m["model"]: {
                "P1_probe": m["P1_probe"],
                "P2_satisfaction": m["P2_satisfaction"],
                "P3_gap_abstained": m["P3_gap_abstained"],
                "P3_fabrication_rate": m["P3_fabrication_rate"],
            } for m in models
        },
        "rankings": {
            m["model"]: {
                "P1_rank": p1_ranks[i],
                "P2_rank": p2_ranks[i],
                "P3_gap_rank": p3_gap_ranks[i],
                "P3_fab_rank": p3_fab_ranks[i],
            } for i, m in enumerate(models)
        },
        "rank_table": rank_table,
        "kendalls_w": {
            "primary_3metrics": {
                "metrics": ["P1_probe", "P2_satisfaction", "P3_gap_abstained"],
                "W": round(W_primary, 4),
                "chi2": round(chi2_primary, 3),
                "df": n - 1,
                "p_value": round(p_primary, 4),
            },
            "sensitivity_fabrication": {
                "metrics": ["P1_probe", "P2_satisfaction", "P3_fabrication_rate"],
                "W": round(W_fab, 4),
                "chi2": round(chi2_fab, 3),
                "df": n - 1,
                "p_value": round(p_fab, 4),
            },
            "sensitivity_all4": {
                "metrics": ["P1_probe", "P2_satisfaction", "P3_gap_abstained", "P3_fabrication_rate"],
                "W": round(W_all4, 4),
                "chi2": round(chi2_all4, 3),
                "df": n - 1,
                "p_value": round(p_all4, 4),
            },
        },
        "spearman_correlations": spearman_results,
        "comparison_with_old": {
            "old_W_primary": 0.089,
            "old_P1xP2_rho": -0.051,
            "old_P1xP3_rho": -0.895,
            "old_P2xP3_rho": -0.154,
        },
    }

    import os
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults written to: {args.output}")


if __name__ == "__main__":
    main()
