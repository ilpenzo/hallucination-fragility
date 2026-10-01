#!/usr/bin/env python3
"""
compute_orthogonality_stats.py

Computes orthogonality statistics across all 5 models × 3 paradigms:
  1. Kendall's W (coefficient of concordance) across paradigm rankings
  2. Pairwise Spearman ρ between each paradigm pair
  3. Rank inversion analysis

Input:  three_paradigm_summary.json (updated with enhanced P2 + 5-model P3)
Output: orthogonality_stats_5model.json

Usage:
  python compute_orthogonality_stats.py \
    --three-paradigm ./analysis/three_paradigm_summary.json \
    --output-dir ./supplementary_analysis
"""

import argparse
import json
import os
import sys
import numpy as np
from scipy import stats


def load_data(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def rank_models(values: dict, reverse: bool = False) -> dict:
    """
    Rank models by value. Default: higher = rank 1.
    If reverse=True: lower = rank 1 (used for fabrication_rate).
    Returns dict of {model: rank} using scipy's rankdata with 'average' tie-breaking.
    """
    models = sorted(values.keys())
    vals = np.array([values[m] for m in models])
    if not reverse:
        vals = -vals  # negate so highest gets rank 1
    ranks = stats.rankdata(vals, method="average")
    return {m: float(r) for m, r in zip(models, ranks)}


def kendall_w(rank_matrix: np.ndarray) -> tuple:
    """
    Compute Kendall's W (coefficient of concordance).

    rank_matrix: shape (k, n) where k = number of rankers (paradigms),
                 n = number of items (models).

    Returns (W, chi2, p_value, df).
    """
    k, n = rank_matrix.shape
    # Sum of ranks per model (column sums)
    R_j = rank_matrix.sum(axis=0)
    R_bar = R_j.mean()
    S = np.sum((R_j - R_bar) ** 2)

    # Kendall's W
    W = (12 * S) / (k**2 * (n**3 - n))

    # Chi-squared approximation
    chi2 = k * (n - 1) * W
    df = n - 1
    p_value = 1 - stats.chi2.cdf(chi2, df)

    return float(W), float(chi2), float(p_value), int(df)


def pairwise_spearman(rankings: dict) -> list:
    """
    Compute pairwise Spearman ρ between all paradigm pairs.
    rankings: {paradigm_name: {model: rank}}
    Returns list of dicts with pair info and correlation.
    """
    paradigm_names = sorted(rankings.keys())
    models = sorted(next(iter(rankings.values())).keys())
    results = []

    for i in range(len(paradigm_names)):
        for j in range(i + 1, len(paradigm_names)):
            p_a = paradigm_names[i]
            p_b = paradigm_names[j]
            ranks_a = np.array([rankings[p_a][m] for m in models])
            ranks_b = np.array([rankings[p_b][m] for m in models])

            rho, p_val = stats.spearmanr(ranks_a, ranks_b)
            results.append({
                "pair": f"{p_a} × {p_b}",
                "paradigm_a": p_a,
                "paradigm_b": p_b,
                "spearman_rho": round(float(rho), 4),
                "p_value": round(float(p_val), 4),
                "n_models": len(models),
            })

    return results


def rank_inversion_analysis(rankings: dict) -> list:
    """
    Find models whose rank changes most across paradigms.
    """
    models = sorted(next(iter(rankings.values())).keys())
    paradigm_names = sorted(rankings.keys())
    inversions = []

    for model in models:
        model_ranks = {p: rankings[p][model] for p in paradigm_names}
        best_rank = min(model_ranks.values())
        worst_rank = max(model_ranks.values())
        spread = worst_rank - best_rank

        inversions.append({
            "model": model,
            "ranks": model_ranks,
            "best_rank": best_rank,
            "worst_rank": worst_rank,
            "rank_spread": spread,
        })

    inversions.sort(key=lambda x: x["rank_spread"], reverse=True)
    return inversions


def main():
    parser = argparse.ArgumentParser(description="Compute 5-model orthogonality statistics")
    parser.add_argument("--three-paradigm", required=True, help="Path to three_paradigm_summary.json")
    parser.add_argument("--output-dir", required=True, help="Directory for output files")
    args = parser.parse_args()

    # Load data
    tps = load_data(args.three_paradigm)

    # ── Extract per-model metrics ──────────────────────────────────────
    cross = tps["cross_paradigm"]
    models_with_p3 = [e for e in cross if e.get("P3_gap_abstained") is not None]

    if len(models_with_p3) < 5:
        print(f"WARNING: Only {len(models_with_p3)} models have P3 data. Expected 5.")
        print("Models missing P3:", [e["model"] for e in cross if e.get("P3_gap_abstained") is None])

    # Build metric dicts
    p1_probe = {}
    p2_satisfaction = {}
    p3_gap_abstention = {}
    p3_fabrication = {}

    for entry in models_with_p3:
        m = entry["model"]
        p1_probe[m] = entry["P1_probe"]
        p2_satisfaction[m] = entry["P2_satisfaction"]
        p3_gap_abstention[m] = entry["P3_gap_abstained"]
        p3_fabrication[m] = entry["P3_fabrication_rate"]

    n_models = len(models_with_p3)
    print(f"Models included: {n_models}")
    for m in sorted(p1_probe.keys()):
        print(f"  {m}: P1={p1_probe[m]:.3f}  P2={p2_satisfaction[m]:.4f}  "
              f"P3_gap={p3_gap_abstention[m]:.3f}  P3_fab={p3_fabrication[m]:.3f}")

    # ── Compute rankings ───────────────────────────────────────────────
    # Primary ranking set: P1 probe, P2 satisfaction, P3 gap abstention
    # (all "higher is better")
    rankings_primary = {
        "P1_probe": rank_models(p1_probe),
        "P2_satisfaction": rank_models(p2_satisfaction),
        "P3_gap_abstention": rank_models(p3_gap_abstention),
    }

    print("\n── Rankings (primary: higher = rank 1) ──")
    models_sorted = sorted(p1_probe.keys())
    header = f"{'Model':<22}" + "".join(f"{p:<20}" for p in sorted(rankings_primary.keys()))
    print(header)
    for m in models_sorted:
        row = f"{m:<22}" + "".join(f"{rankings_primary[p][m]:<20.1f}" for p in sorted(rankings_primary.keys()))
        print(row)

    # ── Kendall's W (primary: P1 probe, P2 satisfaction, P3 gap abstention) ──
    rank_matrix = np.array([
        [rankings_primary[p][m] for m in models_sorted]
        for p in sorted(rankings_primary.keys())
    ])

    W, chi2, p_val, df = kendall_w(rank_matrix)
    print(f"\n── Kendall's W (3 paradigms × {n_models} models) ──")
    print(f"  W = {W:.4f}")
    print(f"  χ² = {chi2:.4f}, df = {df}, p = {p_val:.4f}")
    print(f"  Interpretation: {'weak' if W < 0.3 else 'moderate' if W < 0.6 else 'strong'} concordance")

    # ── Sensitivity: also compute with P3 fabrication (lower=better) ──
    rankings_with_fab = {
        "P1_probe": rank_models(p1_probe),
        "P2_satisfaction": rank_models(p2_satisfaction),
        "P3_fabrication": rank_models(p3_fabrication, reverse=True),
    }

    rank_matrix_fab = np.array([
        [rankings_with_fab[p][m] for m in models_sorted]
        for p in sorted(rankings_with_fab.keys())
    ])

    W_fab, chi2_fab, p_fab, df_fab = kendall_w(rank_matrix_fab)
    print(f"\n── Kendall's W (sensitivity: P3 fabrication instead of gap abstention) ──")
    print(f"  W = {W_fab:.4f}")
    print(f"  χ² = {chi2_fab:.4f}, df = {df_fab}, p = {p_fab:.4f}")

    # ── Also compute with all 4 metrics as rankers ──
    rankings_all4 = {
        "P1_probe": rank_models(p1_probe),
        "P2_satisfaction": rank_models(p2_satisfaction),
        "P3_gap_abstention": rank_models(p3_gap_abstention),
        "P3_fabrication": rank_models(p3_fabrication, reverse=True),
    }

    rank_matrix_4 = np.array([
        [rankings_all4[p][m] for m in models_sorted]
        for p in sorted(rankings_all4.keys())
    ])

    W_4, chi2_4, p_4, df_4 = kendall_w(rank_matrix_4)
    print(f"\n── Kendall's W (4 metrics as rankers × {n_models} models) ──")
    print(f"  W = {W_4:.4f}")
    print(f"  χ² = {chi2_4:.4f}, df = {df_4}, p = {p_4:.4f}")

    # ── Pairwise Spearman ──────────────────────────────────────────────
    spearman_primary = pairwise_spearman(rankings_primary)
    print(f"\n── Pairwise Spearman ρ (primary rankings) ──")
    for r in spearman_primary:
        print(f"  {r['pair']}: ρ = {r['spearman_rho']:+.4f} (p = {r['p_value']:.4f})")

    spearman_all4 = pairwise_spearman(rankings_all4)
    print(f"\n── Pairwise Spearman ρ (all 4 metric rankings) ──")
    for r in spearman_all4:
        print(f"  {r['pair']}: ρ = {r['spearman_rho']:+.4f} (p = {r['p_value']:.4f})")

    # ── Rank inversion analysis ────────────────────────────────────────
    inversions = rank_inversion_analysis(rankings_primary)
    print(f"\n── Rank Inversion Analysis (primary) ──")
    for inv in inversions:
        print(f"  {inv['model']}: spread={inv['rank_spread']:.1f}  "
              f"best={inv['best_rank']:.1f}  worst={inv['worst_rank']:.1f}  "
              f"ranks={inv['ranks']}")

    # ── Save results ───────────────────────────────────────────────────
    os.makedirs(args.output_dir, exist_ok=True)

    output = {
        "n_models": n_models,
        "models": models_sorted,
        "metrics_used": {
            "P1": "probe_accuracy (higher = better)",
            "P2": "satisfaction_rate_enhanced (higher = better)",
            "P3_primary": "gap_abstention (higher = better)",
            "P3_sensitivity": "fabrication_rate (lower = better)",
        },
        "raw_values": {
            "P1_probe": {m: round(p1_probe[m], 4) for m in models_sorted},
            "P2_satisfaction": {m: round(p2_satisfaction[m], 4) for m in models_sorted},
            "P3_gap_abstention": {m: round(p3_gap_abstention[m], 4) for m in models_sorted},
            "P3_fabrication": {m: round(p3_fabrication[m], 4) for m in models_sorted},
        },
        "rankings": {
            "primary": {p: {m: rankings_primary[p][m] for m in models_sorted}
                        for p in sorted(rankings_primary.keys())},
            "with_fabrication": {p: {m: rankings_with_fab[p][m] for m in models_sorted}
                                 for p in sorted(rankings_with_fab.keys())},
            "all_4_metrics": {p: {m: rankings_all4[p][m] for m in models_sorted}
                              for p in sorted(rankings_all4.keys())},
        },
        "kendall_w": {
            "primary_3_paradigms": {
                "description": "P1 probe × P2 satisfaction × P3 gap abstention",
                "W": round(W, 4),
                "chi2": round(chi2, 4),
                "df": df,
                "p_value": round(p_val, 4),
                "k_rankers": 3,
                "n_items": n_models,
            },
            "sensitivity_p3_fabrication": {
                "description": "P1 probe × P2 satisfaction × P3 fabrication (lower=better)",
                "W": round(W_fab, 4),
                "chi2": round(chi2_fab, 4),
                "df": df_fab,
                "p_value": round(p_fab, 4),
                "k_rankers": 3,
                "n_items": n_models,
            },
            "all_4_metrics": {
                "description": "P1 probe × P2 satisfaction × P3 gap abstention × P3 fabrication",
                "W": round(W_4, 4),
                "chi2": round(chi2_4, 4),
                "df": df_4,
                "p_value": round(p_4, 4),
                "k_rankers": 4,
                "n_items": n_models,
            },
        },
        "pairwise_spearman": {
            "primary_3_paradigms": spearman_primary,
            "all_4_metrics": spearman_all4,
        },
        "rank_inversions": inversions,
    }

    output_path = os.path.join(args.output_dir, "orthogonality_stats_5model.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to: {output_path}")
    print("Done.")


if __name__ == "__main__":
    main()
