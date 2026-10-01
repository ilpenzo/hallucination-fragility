#!/usr/bin/env python3
"""
compute_irr_metrics.py — Compute all inter-rater reliability metrics for paper

Reads the GPT-5.2 vs Opus IRR comparison CSV and produces paper-ready metrics:
  - Cohen's κ (unweighted, linear-weighted, quadratic-weighted) per dimension
  - PABAK (prevalence-adjusted, bias-adjusted kappa) for ceiling dimensions
  - Gwet's AC1 (prevalence-robust alternative to κ)
  - Raw/binned agreement percentages
  - Confusion matrices (ordinal + binary)
  - Disagreement direction analysis
  - Bootstrap 95% confidence intervals for all κ values
  - Per-model agreement breakdown
  - Comparison table: old human IRR vs new GPT-5.2 IRR

Usage:
  python compute_irr_metrics.py \
    --csv ./gpt52_irr_results/irr_comparison.csv \
    --output ./gpt52_irr_results/irr_paper_metrics.json

Dependencies:
  None beyond Python 3.8+ standard library (no numpy/scipy required)
"""

import json
import csv
import os
import sys
import argparse
import random
import math
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple


# ===========================================================================
# BINNING (matches paper: low [0,0.25), mid [0.25,0.75), high [0.75,1.0])
# ===========================================================================

def bin_score(score: float) -> int:
    """Bin continuous score: 0=low, 1=mid, 2=high."""
    if score < 0.25:
        return 0
    elif score < 0.75:
        return 1
    else:
        return 2

BIN_LABELS = {0: "low [0, 0.25)", 1: "mid [0.25, 0.75)", 2: "high [0.75, 1.0]"}
N_BINS = 3


# ===========================================================================
# COHEN'S KAPPA (weighted and unweighted)
# ===========================================================================

def build_confusion_matrix(r1: List[int], r2: List[int], n_cat: int) -> List[List[int]]:
    """Build n_cat × n_cat confusion matrix."""
    matrix = [[0] * n_cat for _ in range(n_cat)]
    for a, b in zip(r1, r2):
        matrix[a][b] += 1
    return matrix


def cohens_kappa(r1: List[int], r2: List[int], n_cat: int = 3,
                 weight: str = "unweighted") -> Optional[float]:
    """
    Compute Cohen's κ with optional weighting.
    weight: "unweighted", "linear", "quadratic"
    Returns None if undefined (zero expected disagreement).
    """
    n = len(r1)
    if n == 0:
        return None

    matrix = build_confusion_matrix(r1, r2, n_cat)

    # Weight matrix
    w = [[0.0] * n_cat for _ in range(n_cat)]
    for i in range(n_cat):
        for j in range(n_cat):
            if weight == "linear":
                w[i][j] = abs(i - j) / (n_cat - 1) if n_cat > 1 else 0
            elif weight == "quadratic":
                w[i][j] = ((i - j) ** 2) / ((n_cat - 1) ** 2) if n_cat > 1 else 0
            else:
                w[i][j] = 0.0 if i == j else 1.0

    row_marg = [sum(matrix[i]) for i in range(n_cat)]
    col_marg = [sum(matrix[i][j] for i in range(n_cat)) for j in range(n_cat)]

    p_o = sum(w[i][j] * matrix[i][j] / n for i in range(n_cat) for j in range(n_cat))
    p_e = sum(w[i][j] * row_marg[i] * col_marg[j] / (n * n)
              for i in range(n_cat) for j in range(n_cat))

    if p_e == 0:
        return None
    return 1.0 - (p_o / p_e)


def cohens_kappa_binary(r1: List[int], r2: List[int]) -> Optional[float]:
    """Binary Cohen's κ."""
    n = len(r1)
    if n == 0:
        return None
    a = sum(1 for x, y in zip(r1, r2) if x == 1 and y == 1)
    b = sum(1 for x, y in zip(r1, r2) if x == 1 and y == 0)
    c = sum(1 for x, y in zip(r1, r2) if x == 0 and y == 1)
    d = sum(1 for x, y in zip(r1, r2) if x == 0 and y == 0)
    p_o = (a + d) / n
    p_e = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
    if p_e == 1.0:
        return None
    return (p_o - p_e) / (1 - p_e)


# ===========================================================================
# PREVALENCE-ADJUSTED METRICS
# ===========================================================================

def pabak(r1: List[int], r2: List[int], n_cat: int = 3) -> float:
    """
    Prevalence-Adjusted Bias-Adjusted Kappa (PABAK).
    For ordinal data, uses the observed binned agreement.
    PABAK = (n_cat * p_o - 1) / (n_cat - 1)
    where p_o is observed agreement proportion.

    Byrt, Bishop & Carlin (1993). Bias, prevalence and kappa.
    J Clin Epidemiol 46(5):423-429.
    """
    n = len(r1)
    if n == 0:
        return 0.0
    p_o = sum(1 for a, b in zip(r1, r2) if a == b) / n
    return (n_cat * p_o - 1) / (n_cat - 1) if n_cat > 1 else p_o


def gwets_ac1(r1: List[int], r2: List[int], n_cat: int = 3) -> Optional[float]:
    """
    Gwet's AC1 — prevalence-robust alternative to Cohen's κ.

    Unlike κ, AC1 does not become unstable when prevalence is extreme.
    It estimates chance agreement from the marginal distribution rather
    than assuming rater independence.

    Gwet (2008). Computing inter-rater reliability and its variance
    in the presence of high agreement. British J Math Stat Psych 61:29-48.
    """
    n = len(r1)
    if n == 0:
        return None

    # Observed agreement
    p_o = sum(1 for a, b in zip(r1, r2) if a == b) / n

    # Category probabilities (pooled across both raters)
    counts = [0] * n_cat
    for a, b in zip(r1, r2):
        counts[a] += 1
        counts[b] += 1
    pi = [c / (2 * n) for c in counts]

    # Chance agreement under AC1
    p_e = sum(pk * (1 - pk) for pk in pi) / (n_cat - 1) if n_cat > 1 else 0

    if p_e == 1.0:
        return None
    return (p_o - p_e) / (1 - p_e)


def gwets_ac1_binary(r1: List[int], r2: List[int]) -> Optional[float]:
    """Gwet's AC1 for binary data."""
    return gwets_ac1(r1, r2, n_cat=2)


# ===========================================================================
# BOOTSTRAP CONFIDENCE INTERVALS
# ===========================================================================

def bootstrap_ci(r1: List[int], r2: List[int], stat_fn, n_boot: int = 2000,
                 alpha: float = 0.05, seed: int = 42, **kwargs) -> Dict:
    """
    Compute bootstrap percentile confidence interval for a statistic.
    stat_fn should accept (r1, r2, **kwargs) and return a float or None.
    """
    rng = random.Random(seed)
    n = len(r1)
    observed = stat_fn(r1, r2, **kwargs)

    boot_vals = []
    for _ in range(n_boot):
        indices = [rng.randint(0, n - 1) for _ in range(n)]
        b1 = [r1[i] for i in indices]
        b2 = [r2[i] for i in indices]
        val = stat_fn(b1, b2, **kwargs)
        if val is not None:
            boot_vals.append(val)

    if len(boot_vals) < 100:
        return {"point": observed, "ci_lower": None, "ci_upper": None,
                "n_valid_boots": len(boot_vals)}

    boot_vals.sort()
    lo_idx = int(len(boot_vals) * (alpha / 2))
    hi_idx = int(len(boot_vals) * (1 - alpha / 2)) - 1
    lo_idx = max(0, lo_idx)
    hi_idx = min(len(boot_vals) - 1, hi_idx)

    return {
        "point": round(observed, 4) if observed is not None else None,
        "ci_lower": round(boot_vals[lo_idx], 4),
        "ci_upper": round(boot_vals[hi_idx], 4),
        "n_valid_boots": len(boot_vals),
    }


# ===========================================================================
# DATA LOADING
# ===========================================================================

def load_csv(path: str) -> List[Dict]:
    """Load the IRR comparison CSV."""
    rows = []
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def parse_bool(val: str) -> bool:
    """Parse string boolean from CSV."""
    return val.strip().lower() == "true"


# ===========================================================================
# MAIN ANALYSIS
# ===========================================================================

def analyze(rows: List[Dict]) -> Dict:
    """Run the full IRR analysis and return paper-ready metrics."""

    n = len(rows)
    print(f"  Loaded {n} entries from CSV")

    # Extract paired scores
    dims_continuous = {
        "contradiction_identified": ("opus_contr_id", "gpt52_contr_id"),
        "contradiction_resolved": ("opus_contr_res", "gpt52_contr_res"),
        "reasoning_quality": ("opus_reasoning", "gpt52_reasoning"),
        "gap_abstained": ("opus_gap_abst", "gpt52_gap_abst"),
    }

    results = {"n_entries": n, "dimensions": {}}
    all_opus_binned = []
    all_gpt52_binned = []

    for dim_name, (col_a, col_b) in dims_continuous.items():
        opus_raw = []
        gpt52_raw = []
        for row in rows:
            a = float(row[col_a])
            b = float(row[col_b])
            opus_raw.append(a)
            gpt52_raw.append(b)

        opus_binned = [bin_score(v) for v in opus_raw]
        gpt52_binned = [bin_score(v) for v in gpt52_raw]

        all_opus_binned.extend(opus_binned)
        all_gpt52_binned.extend(gpt52_binned)

        # Raw agreement
        exact_agree = sum(1 for a, b in zip(opus_raw, gpt52_raw) if a == b)
        binned_agree = sum(1 for a, b in zip(opus_binned, gpt52_binned) if a == b)
        mad = sum(abs(a - b) for a, b in zip(opus_raw, gpt52_raw)) / n

        # Confusion matrix (ordinal)
        conf = build_confusion_matrix(opus_binned, gpt52_binned, N_BINS)

        # Kappa variants
        k_uw = cohens_kappa(opus_binned, gpt52_binned, N_BINS, "unweighted")
        k_lin = cohens_kappa(opus_binned, gpt52_binned, N_BINS, "linear")
        k_quad = cohens_kappa(opus_binned, gpt52_binned, N_BINS, "quadratic")

        # Prevalence-adjusted metrics
        pabak_val = pabak(opus_binned, gpt52_binned, N_BINS)
        ac1_val = gwets_ac1(opus_binned, gpt52_binned, N_BINS)

        # Bootstrap CIs for key metrics
        def _kappa_linear(r1, r2):
            return cohens_kappa(r1, r2, N_BINS, "linear")
        def _ac1(r1, r2):
            return gwets_ac1(r1, r2, N_BINS)

        ci_kappa = bootstrap_ci(opus_binned, gpt52_binned, _kappa_linear)
        ci_ac1 = bootstrap_ci(opus_binned, gpt52_binned, _ac1)
        ci_pabak = bootstrap_ci(opus_binned, gpt52_binned,
                                lambda r1, r2: pabak(r1, r2, N_BINS))

        # Disagreement direction
        opus_higher = sum(1 for a, b in zip(opus_raw, gpt52_raw) if a > b)
        gpt52_higher = sum(1 for a, b in zip(opus_raw, gpt52_raw) if b > a)

        # Disagreement details
        disagreements = []
        for row_data, a, b in zip(rows, opus_raw, gpt52_raw):
            if a != b:
                disagreements.append({
                    "entry_id": row_data["entry_id"],
                    "model": row_data["model"],
                    "scenario": row_data["scenario"],
                    "opus": a,
                    "gpt52": b,
                    "diff": round(a - b, 4),
                })

        dim_result = {
            "n": n,
            "exact_agreement": exact_agree,
            "exact_agreement_pct": round(exact_agree / n, 4),
            "binned_agreement": binned_agree,
            "binned_agreement_pct": round(binned_agree / n, 4),
            "mean_absolute_difference": round(mad, 4),
            "confusion_matrix_ordinal": {
                "rows": "Opus (low/mid/high)",
                "cols": "GPT-5.2 (low/mid/high)",
                "matrix": conf,
            },
            "cohens_kappa": {
                "unweighted": round(k_uw, 4) if k_uw is not None else None,
                "linear": round(k_lin, 4) if k_lin is not None else None,
                "quadratic": round(k_quad, 4) if k_quad is not None else None,
                "linear_95ci": ci_kappa,
            },
            "pabak": {
                "value": round(pabak_val, 4),
                "95ci": ci_pabak,
                "note": "Prevalence-adjusted bias-adjusted kappa (Byrt et al. 1993)",
            },
            "gwets_ac1": {
                "value": round(ac1_val, 4) if ac1_val is not None else None,
                "95ci": ci_ac1,
                "note": "Gwet's AC1 (2008) — prevalence-robust agreement",
            },
            "disagreement_direction": {
                "opus_scored_higher": opus_higher,
                "gpt52_scored_higher": gpt52_higher,
                "n_disagreements": len(disagreements),
            },
            "disagreement_details": disagreements,
        }

        results["dimensions"][dim_name] = dim_result

    # --- Fabrication (binary) ---
    opus_fab = [1 if parse_bool(row["opus_fab"]) else 0 for row in rows]
    gpt52_fab = [1 if parse_bool(row["gpt52_fab"]) else 0 for row in rows]

    fab_agree = sum(1 for a, b in zip(opus_fab, gpt52_fab) if a == b)
    k_fab = cohens_kappa_binary(opus_fab, gpt52_fab)
    ac1_fab = gwets_ac1_binary(opus_fab, gpt52_fab)

    ci_kfab = bootstrap_ci(opus_fab, gpt52_fab, cohens_kappa_binary)
    ci_ac1fab = bootstrap_ci(opus_fab, gpt52_fab, gwets_ac1_binary)

    tp = sum(1 for a, b in zip(opus_fab, gpt52_fab) if a == 1 and b == 1)
    fp = sum(1 for a, b in zip(opus_fab, gpt52_fab) if a == 0 and b == 1)
    fn = sum(1 for a, b in zip(opus_fab, gpt52_fab) if a == 1 and b == 0)
    tn = sum(1 for a, b in zip(opus_fab, gpt52_fab) if a == 0 and b == 0)

    fab_disagreements = []
    for row_data, a, b in zip(rows, opus_fab, gpt52_fab):
        if a != b:
            fab_disagreements.append({
                "entry_id": row_data["entry_id"],
                "model": row_data["model"],
                "scenario": row_data["scenario"],
                "opus_fabrication": bool(a),
                "gpt52_fabrication": bool(b),
            })

    results["dimensions"]["fabrication_present"] = {
        "n": n,
        "agreement": fab_agree,
        "agreement_pct": round(fab_agree / n, 4),
        "opus_positive": sum(opus_fab),
        "gpt52_positive": sum(gpt52_fab),
        "confusion_matrix": {
            "true_positive": tp,
            "false_positive_gpt52": fp,
            "false_negative_gpt52": fn,
            "true_negative": tn,
        },
        "cohens_kappa": {
            "value": round(k_fab, 4) if k_fab is not None else None,
            "95ci": ci_kfab,
        },
        "gwets_ac1": {
            "value": round(ac1_fab, 4) if ac1_fab is not None else None,
            "95ci": ci_ac1fab,
        },
        "disagreement_details": fab_disagreements,
    }

    # --- Overall continuous ---
    n_total = len(all_opus_binned)
    overall_agree = sum(1 for a, b in zip(all_opus_binned, all_gpt52_binned) if a == b)
    k_overall_lin = cohens_kappa(all_opus_binned, all_gpt52_binned, N_BINS, "linear")
    ac1_overall = gwets_ac1(all_opus_binned, all_gpt52_binned, N_BINS)
    pabak_overall = pabak(all_opus_binned, all_gpt52_binned, N_BINS)

    results["overall_continuous"] = {
        "n_comparisons": n_total,
        "binned_agreement": overall_agree,
        "binned_agreement_pct": round(overall_agree / n_total, 4),
        "cohens_kappa_linear": round(k_overall_lin, 4) if k_overall_lin is not None else None,
        "gwets_ac1": round(ac1_overall, 4) if ac1_overall is not None else None,
        "pabak": round(pabak_overall, 4),
    }

    # --- Per-model breakdown ---
    by_model = defaultdict(list)
    for row in rows:
        by_model[row["model"]].append(row)

    model_breakdown = {}
    for model_name in sorted(by_model.keys()):
        model_rows = by_model[model_name]
        m_n = len(model_rows)

        # Compute per-model agreement for each dimension
        model_dims = {}
        for dim_name, (col_a, col_b) in dims_continuous.items():
            a_binned = [bin_score(float(r[col_a])) for r in model_rows]
            b_binned = [bin_score(float(r[col_b])) for r in model_rows]
            agree = sum(1 for x, y in zip(a_binned, b_binned) if x == y)
            model_dims[dim_name] = {
                "binned_agreement_pct": round(agree / m_n, 4),
                "n_disagree": m_n - agree,
            }

        # Fabrication
        a_fab = [1 if parse_bool(r["opus_fab"]) else 0 for r in model_rows]
        b_fab = [1 if parse_bool(r["gpt52_fab"]) else 0 for r in model_rows]
        fab_agree_m = sum(1 for x, y in zip(a_fab, b_fab) if x == y)
        model_dims["fabrication_present"] = {
            "agreement_pct": round(fab_agree_m / m_n, 4),
            "opus_positive": sum(a_fab),
            "gpt52_positive": sum(b_fab),
        }

        model_breakdown[model_name] = {"n": m_n, "dimensions": model_dims}

    results["per_model"] = model_breakdown

    # --- Comparison with old human IRR (from paper) ---
    results["comparison_human_vs_gpt52_irr"] = {
        "note": "Compares the original human-vs-Opus IRR (n=20) with new GPT-5.2-vs-Opus IRR (n=100)",
        "dimensions": {
            "contradiction_identified": {
                "human_irr": {"agreement": "100%", "kappa": "undef (prevalence)", "n": 20},
                "gpt52_irr": {
                    "agreement": f"{results['dimensions']['contradiction_identified']['binned_agreement_pct']:.0%}",
                    "kappa": "undef (prevalence)",
                    "ac1": results["dimensions"]["contradiction_identified"]["gwets_ac1"]["value"],
                    "n": 100,
                },
            },
            "contradiction_resolved": {
                "human_irr": {"agreement": "100%", "kappa_linear": 1.0, "n": 20},
                "gpt52_irr": {
                    "agreement": f"{results['dimensions']['contradiction_resolved']['binned_agreement_pct']:.0%}",
                    "kappa_linear": results["dimensions"]["contradiction_resolved"]["cohens_kappa"]["linear"],
                    "ac1": results["dimensions"]["contradiction_resolved"]["gwets_ac1"]["value"],
                    "pabak": results["dimensions"]["contradiction_resolved"]["pabak"]["value"],
                    "n": 100,
                },
            },
            "reasoning_quality": {
                "human_irr": {"agreement": "95%", "kappa_linear": 0.643, "n": 20},
                "gpt52_irr": {
                    "agreement": f"{results['dimensions']['reasoning_quality']['binned_agreement_pct']:.0%}",
                    "kappa_linear": results["dimensions"]["reasoning_quality"]["cohens_kappa"]["linear"],
                    "ac1": results["dimensions"]["reasoning_quality"]["gwets_ac1"]["value"],
                    "pabak": results["dimensions"]["reasoning_quality"]["pabak"]["value"],
                    "n": 100,
                },
            },
            "gap_abstained": {
                "human_irr": {"agreement": "70%", "kappa_linear": 0.149, "n": 20},
                "gpt52_irr": {
                    "agreement": f"{results['dimensions']['gap_abstained']['binned_agreement_pct']:.0%}",
                    "kappa_linear": results["dimensions"]["gap_abstained"]["cohens_kappa"]["linear"],
                    "ac1": results["dimensions"]["gap_abstained"]["gwets_ac1"]["value"],
                    "n": 100,
                },
            },
            "fabrication_present": {
                "human_irr": {"agreement": "90%", "kappa": 0.460, "n": 20},
                "gpt52_irr": {
                    "agreement": f"{results['dimensions']['fabrication_present']['agreement_pct']:.0%}",
                    "kappa": results["dimensions"]["fabrication_present"]["cohens_kappa"]["value"],
                    "ac1": results["dimensions"]["fabrication_present"]["gwets_ac1"]["value"],
                    "n": 100,
                },
            },
        },
    }

    # --- Paper-ready summary table ---
    print("\n" + "=" * 80)
    print("PAPER-READY IRR TABLE: Claude Opus 4.6 vs GPT-5.2 (n=100)")
    print("=" * 80)
    print(f"  {'Dimension':<28} {'Agree':>7} {'κ_lin':>7} {'PABAK':>7} {'AC1':>7} {'Note'}")
    print(f"  {'-'*28} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*20}")

    for dim_name in ["contradiction_identified", "contradiction_resolved",
                     "reasoning_quality", "gap_abstained"]:
        d = results["dimensions"][dim_name]
        agree = f"{d['binned_agreement_pct']:.0%}"
        kl = d["cohens_kappa"]["linear"]
        kl_str = f"{kl:.3f}" if kl is not None else "undef"
        pb = d["pabak"]["value"]
        ac = d["gwets_ac1"]["value"]
        ac_str = f"{ac:.3f}" if ac is not None else "undef"

        note = ""
        if kl is not None and kl < 0 and d["binned_agreement_pct"] > 0.90:
            note = "Prevalence paradox"
        elif d["binned_agreement_pct"] == 1.0:
            note = "Perfect (prevalence)"

        print(f"  {dim_name:<28} {agree:>7} {kl_str:>7} {pb:>7.3f} {ac_str:>7} {note}")

    # Fabrication
    fd = results["dimensions"]["fabrication_present"]
    fa = f"{fd['agreement_pct']:.0%}"
    fk = fd["cohens_kappa"]["value"]
    fk_str = f"{fk:.3f}" if fk is not None else "undef"
    fac = fd["gwets_ac1"]["value"]
    fac_str = f"{fac:.3f}" if fac is not None else "undef"
    print(f"  {'fabrication_present':<28} {fa:>7} {fk_str:>7} {'—':>7} {fac_str:>7}")

    # Overall
    ov = results["overall_continuous"]
    print(f"\n  {'OVERALL (4 cont. dims)':<28} {ov['binned_agreement_pct']:.0%}"
          f"    κ_lin={ov['cohens_kappa_linear']:.3f}"
          f"  AC1={ov['gwets_ac1']:.3f}"
          f"  PABAK={ov['pabak']:.3f}")

    # Comparison
    print("\n" + "=" * 80)
    print("COMPARISON: Human IRR (n=20) vs GPT-5.2 IRR (n=100)")
    print("=" * 80)
    print(f"  {'Dimension':<28} {'Human κ':>9} {'GPT52 κ':>9} {'GPT52 AC1':>10} {'GPT52 Agree':>12}")
    print(f"  {'-'*28} {'-'*9} {'-'*9} {'-'*10} {'-'*12}")
    comp = results["comparison_human_vs_gpt52_irr"]["dimensions"]
    for dim_name in ["contradiction_identified", "contradiction_resolved",
                     "reasoning_quality", "gap_abstained", "fabrication_present"]:
        h = comp[dim_name]["human_irr"]
        g = comp[dim_name]["gpt52_irr"]
        hk = h.get("kappa_linear", h.get("kappa", "undef"))
        hk_str = f"{hk:.3f}" if isinstance(hk, (int, float)) else str(hk)
        gk = g.get("kappa_linear", g.get("kappa", "undef"))
        gk_str = f"{gk:.3f}" if isinstance(gk, (int, float)) else "undef"
        gac = g.get("ac1", None)
        gac_str = f"{gac:.3f}" if gac is not None else "undef"
        print(f"  {dim_name:<28} {hk_str:>9} {gk_str:>9} {gac_str:>10} {g['agreement']:>12}")

    # Fabrication disagreement detail
    print("\n  --- Fabrication Disagreements ---")
    for d in results["dimensions"]["fabrication_present"]["disagreement_details"]:
        direction = "Opus=yes, GPT52=no" if d["opus_fabrication"] else "Opus=no, GPT52=yes"
        print(f"    {d['entry_id']}: {direction}")

    return results


# ===========================================================================
# JSON SAFETY
# ===========================================================================

def ensure_serializable(obj):
    """Recursively ensure JSON serialization safety."""
    if isinstance(obj, dict):
        return {k: ensure_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [ensure_serializable(v) for v in obj]
    elif isinstance(obj, float):
        if obj != obj:  # NaN
            return None
        if obj == float('inf') or obj == float('-inf'):
            return None
        return round(obj, 6)
    elif isinstance(obj, (bool, int, str)) or obj is None:
        return obj
    else:
        return str(obj)


# ===========================================================================
# MAIN
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Compute paper-ready IRR metrics for Opus vs GPT-5.2"
    )
    parser.add_argument("--csv", required=True,
                        help="Path to irr_comparison.csv")
    parser.add_argument("--output", required=True,
                        help="Path to output JSON")
    args = parser.parse_args()

    print("=" * 80)
    print("IRR PAPER METRICS: Claude Opus 4.6 vs GPT-5.2")
    print("=" * 80)

    rows = load_csv(args.csv)
    results = analyze(rows)

    # Save
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(ensure_serializable(results), f, indent=2, ensure_ascii=False)
    print(f"\n  Full results saved: {args.output}")

    print(f"\n{'='*80}")
    print("DONE")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
