#!/usr/bin/env python3
"""
supplementary_analyses.py — Orthogonality Stats, R1 Thinking Analysis, Cohen's Kappa

Three analyses in one script:

  1. ORTHOGONALITY TESTS (--orthogonality)
     Kendall's W and Spearman correlations across P1/P2/P3 model rankings.
     Tests the paper's central claim that hallucination dimensions are independent.

  2. R1 THINKING ANALYSIS (--r1-thinking)
     Compares DeepSeek-R1's reasoning_content (thinking tokens) against final answers.
     Identifies cases where thinking diverges from output — a unique diagnostic.

  3. COHEN'S KAPPA FRAMEWORK (--kappa-sample)
     Generates a stratified sample of P3 judge outputs for human annotation,
     plus a scoring template. Run this, annotate, then re-run with --kappa-score.

Usage:
  # All analyses
  python supplementary_analyses.py \
    --results-dir ./results \
    --scenarios-dir ./p2_scenarios \
    --p2-rescore ./p2_rescore_results/p2_rescore_comparison.json \
    --three-paradigm ./three_paradigm_summary.json \
    --output-dir ./supplementary_analysis \
    --orthogonality --r1-thinking --kappa-sample

  # Just orthogonality
  python supplementary_analyses.py \
    --three-paradigm ./three_paradigm_summary.json \
    --p2-rescore ./p2_rescore_results/p2_rescore_comparison.json \
    --output-dir ./supplementary_analysis \
    --orthogonality

  # Score Kappa after human annotation
  python supplementary_analyses.py \
    --output-dir ./supplementary_analysis \
    --kappa-score --kappa-annotations ./supplementary_analysis/kappa_annotations_filled.json
"""

import json
import os
import re
import argparse
import glob
import math
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Optional
from itertools import combinations


# ==============================================================================
# 1. ORTHOGONALITY TESTS
# ==============================================================================

def run_orthogonality(three_paradigm_path: str, p2_rescore_path: str,
                      output_dir: str):
    """
    Compute Kendall's W and pairwise Spearman correlations across paradigm rankings.

    Uses updated P2 scores from enhanced parser. Computes:
    - Kendall's W (concordance across all paradigm rankings)
    - Pairwise Spearman rho between each pair of paradigm metrics
    - Both with and without Gemini (missing P3 data)
    """
    print(f"\n{'='*70}")
    print("ORTHOGONALITY ANALYSIS")
    print(f"{'='*70}")

    # Load data
    with open(three_paradigm_path) as f:
        tp = json.load(f)

    with open(p2_rescore_path) as f:
        p2_rescore = json.load(f)

    # Build model data with UPDATED P2 scores
    models_all = []
    models_no_gemini = []

    for entry in tp["cross_paradigm"]:
        model = entry["model"]
        p1_probe = entry["P1_probe"]

        # Use enhanced P2 satisfaction from rescore
        p2_enhanced = p2_rescore["comparison"].get(model, {}).get("satisfaction_enhanced")
        if p2_enhanced is None:
            # Fall back to original
            p2_enhanced = entry.get("P2_satisfaction", 0)

        # P3 composite: use 1 - fabrication_rate as the "source fidelity" metric
        # (higher = better, comparable direction to P1 and P2)
        p3_fab = entry.get("P3_fabrication_rate")
        p3_gap = entry.get("P3_gap_abstained")
        p3_resolve = entry.get("P3_contradiction_resolved")

        has_p3 = p3_fab is not None and p3_gap is not None

        record = {
            "model": model,
            "P1_probe": p1_probe,
            "P2_satisfaction": p2_enhanced,
        }

        if has_p3:
            # Source fidelity composite: average of gap abstention and (1 - fabrication)
            record["P3_source_fidelity"] = (p3_gap + (1.0 - p3_fab)) / 2.0
            record["P3_fabrication_rate"] = p3_fab
            record["P3_gap_abstained"] = p3_gap
            record["P3_contradiction_resolved"] = p3_resolve

        models_all.append(record)
        if model != "gemini-2.5-pro":
            models_no_gemini.append(record)

    # --- Compute rankings ---
    def rank_models(models: List[Dict], metric: str, reverse=True) -> Dict[str, int]:
        """Rank models by metric. Returns {model: rank}. Higher value = rank 1 if reverse=True."""
        sorted_models = sorted(models, key=lambda x: x.get(metric, 0),
                               reverse=reverse)
        return {m["model"]: i + 1 for i, m in enumerate(sorted_models)}

    # P1 and P2 rankings (all 5 models)
    p1_ranks_all = rank_models(models_all, "P1_probe")
    p2_ranks_all = rank_models(models_all, "P2_satisfaction")

    # P3 rankings (4 models, no Gemini)
    p3_ranks = rank_models(models_no_gemini, "P3_source_fidelity")
    p3_fab_ranks = rank_models(models_no_gemini, "P3_fabrication_rate", reverse=False)

    print("\n  Model Rankings (updated P2 via enhanced parser):")
    print(f"  {'Model':25s} {'P1 Probe':>10s} {'P2 Sat':>10s} {'P3 Fidelity':>12s}")
    for m in models_all:
        p3_str = f"{m.get('P3_source_fidelity', 'N/A')}" if "P3_source_fidelity" in m else "N/A"
        if isinstance(p3_str, float):
            p3_str = f"{p3_str:.3f}"
        print(f"  {m['model']:25s} {m['P1_probe']:10.3f} {m['P2_satisfaction']:10.3f} {p3_str:>12s}")

    print(f"\n  Rankings:")
    print(f"  {'Model':25s} {'P1 Rank':>8s} {'P2 Rank':>8s} {'P3 Rank':>8s}")
    for m in models_all:
        p1r = p1_ranks_all[m["model"]]
        p2r = p2_ranks_all[m["model"]]
        p3r = p3_ranks.get(m["model"], "N/A")
        print(f"  {m['model']:25s} {p1r:>8d} {p2r:>8d} {str(p3r):>8s}")

    # --- Kendall's W (without Gemini, since it lacks P3) ---
    print(f"\n  --- Kendall's W (4 models, 3 paradigms, excluding Gemini) ---")
    p1_ranks_4 = rank_models(models_no_gemini, "P1_probe")
    p2_ranks_4 = rank_models(models_no_gemini, "P2_satisfaction")
    p3_ranks_4 = rank_models(models_no_gemini, "P3_source_fidelity")

    # Build ranking matrix: k raters (paradigms) × n objects (models)
    model_names_4 = [m["model"] for m in models_no_gemini]
    ranking_matrix = []
    for ranks in [p1_ranks_4, p2_ranks_4, p3_ranks_4]:
        ranking_matrix.append([ranks[m] for m in model_names_4])

    W = kendalls_w(ranking_matrix)
    k = len(ranking_matrix)  # number of raters (paradigms)
    n = len(model_names_4)   # number of objects (models)

    # Chi-square approximation for significance
    chi2 = k * (n - 1) * W
    df = n - 1

    # Chi-square p-value approximation (simple upper-tail)
    p_value = chi2_p_value(chi2, df)

    print(f"    W = {W:.4f}")
    print(f"    χ²({df}) = {chi2:.3f}, p ≈ {p_value:.4f}")
    if W < 0.3:
        print(f"    Interpretation: WEAK concordance — rankings are largely INDEPENDENT")
        print(f"    This SUPPORTS the orthogonality claim.")
    elif W < 0.6:
        print(f"    Interpretation: MODERATE concordance — partial agreement in rankings")
    else:
        print(f"    Interpretation: STRONG concordance — rankings are similar (AGAINST orthogonality)")

    # --- Also compute W for P1 vs P2 only (all 5 models) ---
    print(f"\n  --- Kendall's W (5 models, P1 vs P2 only) ---")
    model_names_5 = [m["model"] for m in models_all]
    ranking_matrix_2 = [
        [p1_ranks_all[m] for m in model_names_5],
        [p2_ranks_all[m] for m in model_names_5],
    ]
    W_2 = kendalls_w(ranking_matrix_2)
    chi2_2 = 2 * (5 - 1) * W_2
    p_2 = chi2_p_value(chi2_2, 4)
    print(f"    W = {W_2:.4f}")
    print(f"    χ²(4) = {chi2_2:.3f}, p ≈ {p_2:.4f}")

    # --- Pairwise Spearman correlations ---
    print(f"\n  --- Pairwise Spearman Rank Correlations (4 models, excl. Gemini) ---")

    paradigm_values = {
        "P1_probe": [m["P1_probe"] for m in models_no_gemini],
        "P2_satisfaction": [m["P2_satisfaction"] for m in models_no_gemini],
        "P3_source_fidelity": [m["P3_source_fidelity"] for m in models_no_gemini],
    }

    spearman_results = {}
    for (name_a, vals_a), (name_b, vals_b) in combinations(paradigm_values.items(), 2):
        rho = spearman_rho(vals_a, vals_b)
        pair_key = f"{name_a} × {name_b}"
        spearman_results[pair_key] = rho
        print(f"    {pair_key:45s}  ρ = {rho:+.4f}")

    # Also with all 5 models for P1 × P2
    vals_p1_5 = [m["P1_probe"] for m in models_all]
    vals_p2_5 = [m["P2_satisfaction"] for m in models_all]
    rho_p1p2_5 = spearman_rho(vals_p1_5, vals_p2_5)
    print(f"\n    P1_probe × P2_satisfaction (5 models)        ρ = {rho_p1p2_5:+.4f}")

    # --- Save results ---
    ortho_results = {
        "kendalls_w_3paradigm_4models": {
            "W": round(W, 4),
            "chi2": round(chi2, 3),
            "df": df,
            "p_value": round(p_value, 4),
            "models": model_names_4,
            "note": "Excluding Gemini (no P3 data)",
        },
        "kendalls_w_p1p2_5models": {
            "W": round(W_2, 4),
            "chi2": round(chi2_2, 3),
            "df": 4,
            "p_value": round(p_2, 4),
            "models": model_names_5,
        },
        "spearman_correlations_4models": {
            k: round(v, 4) for k, v in spearman_results.items()
        },
        "spearman_p1_p2_5models": round(rho_p1p2_5, 4),
        "model_scores_used": {
            m["model"]: {
                "P1_probe": m["P1_probe"],
                "P2_satisfaction": m["P2_satisfaction"],
                "P3_source_fidelity": m.get("P3_source_fidelity"),
            } for m in models_all
        },
        "rankings_used": {
            "P1_probe": p1_ranks_all,
            "P2_satisfaction": p2_ranks_all,
            "P3_source_fidelity": p3_ranks,
        },
    }

    out_path = os.path.join(output_dir, "orthogonality_results.json")
    with open(out_path, "w") as f:
        json.dump(ortho_results, f, indent=2)
    print(f"\n  Results written to: {out_path}")


def kendalls_w(ranking_matrix: List[List[int]]) -> float:
    """
    Compute Kendall's W (coefficient of concordance).

    ranking_matrix: k lists of length n, where each list is one rater's ranking
                    of n objects (1 = best).
    Returns W in [0, 1]. 0 = no agreement, 1 = perfect agreement.
    """
    k = len(ranking_matrix)      # number of raters
    n = len(ranking_matrix[0])   # number of objects

    # Sum of ranks for each object across all raters
    rank_sums = [0] * n
    for rater_ranks in ranking_matrix:
        for j in range(n):
            rank_sums[j] += rater_ranks[j]

    # Mean rank sum
    mean_sum = sum(rank_sums) / n

    # S = sum of squared deviations from mean
    S = sum((rs - mean_sum) ** 2 for rs in rank_sums)

    # Maximum possible S
    S_max = (k ** 2 * (n ** 3 - n)) / 12.0

    if S_max == 0:
        return 0.0

    W = S / S_max
    return W


def spearman_rho(x: List[float], y: List[float]) -> float:
    """Compute Spearman's rank correlation coefficient."""
    n = len(x)
    if n < 2:
        return 0.0

    # Convert to ranks
    rx = _to_ranks(x)
    ry = _to_ranks(y)

    # Pearson correlation of ranks
    mean_rx = sum(rx) / n
    mean_ry = sum(ry) / n

    num = sum((rx[i] - mean_rx) * (ry[i] - mean_ry) for i in range(n))
    den_x = math.sqrt(sum((rx[i] - mean_rx) ** 2 for i in range(n)))
    den_y = math.sqrt(sum((ry[i] - mean_ry) ** 2 for i in range(n)))

    if den_x == 0 or den_y == 0:
        return 0.0

    return num / (den_x * den_y)


def _to_ranks(values: List[float]) -> List[float]:
    """Convert values to ranks (1 = smallest). Handles ties with average rank."""
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * len(values)

    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j + 1) / 2.0  # average rank for ties
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j

    return ranks


def chi2_p_value(chi2: float, df: int) -> float:
    """
    Approximate upper-tail p-value for chi-square distribution.
    Uses Wilson-Hilferty normal approximation.
    """
    if df <= 0 or chi2 <= 0:
        return 1.0

    # Wilson-Hilferty approximation
    z = ((chi2 / df) ** (1.0 / 3.0) - (1 - 2.0 / (9 * df))) / math.sqrt(2.0 / (9 * df))

    # Standard normal CDF approximation (Abramowitz & Stegun)
    p_lower = _normal_cdf(z)
    return max(0.0, 1.0 - p_lower)


def _normal_cdf(z: float) -> float:
    """Approximate standard normal CDF."""
    # Abramowitz & Stegun approximation 26.2.17
    if z < -8:
        return 0.0
    if z > 8:
        return 1.0

    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = 1 if z >= 0 else -1
    z_abs = abs(z)

    t = 1.0 / (1.0 + p * z_abs)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-z_abs * z_abs / 2.0)

    return 0.5 * (1.0 + sign * y)


# ==============================================================================
# 2. R1 THINKING ANALYSIS
# ==============================================================================

def run_r1_thinking(results_dir: str, scenarios_dir: str, output_dir: str):
    """
    Analyze DeepSeek-R1's reasoning_content vs. final answers.

    For P1: Check if thinking tokens contain correct values that don't
    appear in the final answer (thinking-knows-but-output-forgets).

    For P2: Check if thinking traces reference constraints that are violated
    in the final plan (aware-but-non-compliant).
    """
    print(f"\n{'='*70}")
    print("DEEPSEEK-R1 THINKING ANALYSIS")
    print(f"{'='*70}")

    # Load P1 scenarios
    p1_scenarios = {}
    for f in sorted(glob.glob(os.path.join(scenarios_dir, "..", "p1_scenarios", "P1_*.json"))):
        with open(f) as fp:
            s = json.load(fp)
        p1_scenarios[s["scenario_id"]] = s

    # Also try alternate path
    if not p1_scenarios:
        for f in sorted(glob.glob(os.path.join(scenarios_dir, "P1_*.json"))):
            with open(f) as fp:
                s = json.load(fp)
            p1_scenarios[s["scenario_id"]] = s

    # Load DeepSeek results
    ds_dir = os.path.join(results_dir, "deepseek-r1")
    if not os.path.isdir(ds_dir):
        print("  ERROR: No deepseek-r1 directory found in results")
        return

    p1_results = []
    p2_results = []
    for f in sorted(glob.glob(os.path.join(ds_dir, "*.json"))):
        with open(f) as fp:
            result = json.load(fp)
        sid = result.get("scenario_id", "")
        if sid.startswith("P1_"):
            p1_results.append(result)
        elif sid.startswith("P2_"):
            p2_results.append(result)

    print(f"  Loaded {len(p1_results)} P1 and {len(p2_results)} P2 DeepSeek results")

    # --- P1 Thinking Analysis ---
    thinking_stats = {
        "total_turns_with_thinking": 0,
        "total_turns_with_gt": 0,
        "thinking_correct_output_correct": 0,
        "thinking_correct_output_wrong": 0,  # KEY: knows but forgets
        "thinking_wrong_output_correct": 0,
        "thinking_wrong_output_wrong": 0,
        "no_number_in_thinking": 0,
        "divergence_examples": [],
    }

    for result in p1_results:
        sid = result["scenario_id"]
        scenario = p1_scenarios.get(sid)
        if not scenario:
            continue

        scenario_turns = {t["turn_number"]: t for t in scenario["turns"]}

        for turn in result["turns"]:
            tn = turn["turn_number"]
            reasoning = turn.get("reasoning_content", "")
            response = turn.get("response", "")

            if not reasoning:
                continue

            s_turn = scenario_turns.get(tn)
            if not s_turn:
                continue

            gt = s_turn.get("ground_truth", {})
            if not gt or gt.get("scoring_type") not in ("exact_numeric", "exact_integer", "percentage"):
                continue

            target = gt.get("value")
            if target is None:
                continue

            thinking_stats["total_turns_with_gt"] += 1
            thinking_stats["total_turns_with_thinking"] += 1

            tol_pct = gt.get("tolerance_pct", 1.0) / 100.0
            tol_abs = gt.get("tolerance_abs", 0.1)

            # Extract numbers from thinking and output
            thinking_nums = _extract_numbers(reasoning)
            output_nums = _extract_numbers(response)

            if not thinking_nums:
                thinking_stats["no_number_in_thinking"] += 1
                continue

            # Check if any number in thinking is close to target
            thinking_has_correct = any(_is_close(n, target, tol_pct, tol_abs)
                                       for n in thinking_nums)

            # Check if any number in output is close to target
            output_has_correct = any(_is_close(n, target, tol_pct, tol_abs)
                                     for n in output_nums) if output_nums else False

            if thinking_has_correct and output_has_correct:
                thinking_stats["thinking_correct_output_correct"] += 1
            elif thinking_has_correct and not output_has_correct:
                thinking_stats["thinking_correct_output_wrong"] += 1
                # This is the interesting case — save example
                if len(thinking_stats["divergence_examples"]) < 10:
                    thinking_stats["divergence_examples"].append({
                        "scenario_id": sid,
                        "turn": tn,
                        "target": target,
                        "thinking_nums_sample": thinking_nums[:5],
                        "output_nums_sample": output_nums[:5] if output_nums else [],
                        "thinking_excerpt": reasoning[:300] if reasoning else "",
                    })
            elif not thinking_has_correct and output_has_correct:
                thinking_stats["thinking_wrong_output_correct"] += 1
            else:
                thinking_stats["thinking_wrong_output_wrong"] += 1

    print(f"\n  --- P1 Thinking vs. Output Divergence ---")
    total = thinking_stats["total_turns_with_gt"]
    if total > 0:
        tc_oc = thinking_stats["thinking_correct_output_correct"]
        tc_ow = thinking_stats["thinking_correct_output_wrong"]
        tw_oc = thinking_stats["thinking_wrong_output_correct"]
        tw_ow = thinking_stats["thinking_wrong_output_wrong"]
        no_num = thinking_stats["no_number_in_thinking"]

        print(f"    Total scorable turns with thinking: {total}")
        print(f"    No numbers in thinking:             {no_num}")
        print(f"    ")
        print(f"    Thinking correct, output correct:    {tc_oc:3d} ({tc_oc/total*100:.0f}%)")
        print(f"    Thinking correct, output WRONG:      {tc_ow:3d} ({tc_ow/total*100:.0f}%)  ← divergence")
        print(f"    Thinking wrong, output correct:      {tw_oc:3d} ({tw_oc/total*100:.0f}%)")
        print(f"    Thinking wrong, output wrong:        {tw_ow:3d} ({tw_ow/total*100:.0f}%)")

        if tc_ow > 0:
            print(f"\n    Divergence rate (knows but forgets): {tc_ow/total*100:.1f}%")
            print(f"    Sample divergence cases:")
            for ex in thinking_stats["divergence_examples"][:3]:
                print(f"      {ex['scenario_id']} T{ex['turn']}: target={ex['target']}, "
                      f"thinking had {ex['thinking_nums_sample']}, "
                      f"output had {ex['output_nums_sample']}")
    else:
        print("    No scorable turns found with thinking tokens.")

    # --- P2 Thinking Analysis (simpler: just check for constraint awareness) ---
    p2_thinking_stats = {
        "total_turns_with_thinking": 0,
        "avg_thinking_length": 0,
        "thinking_mentions_conflict": 0,
    }

    total_thinking_len = 0
    for result in p2_results:
        for turn in result["turns"]:
            reasoning = turn.get("reasoning_content", "")
            if reasoning:
                p2_thinking_stats["total_turns_with_thinking"] += 1
                total_thinking_len += len(reasoning)
                if any(kw in reasoning.lower() for kw in
                       ["conflict", "contradiction", "cannot satisfy", "impossible",
                        "violat", "incompatible"]):
                    p2_thinking_stats["thinking_mentions_conflict"] += 1

    if p2_thinking_stats["total_turns_with_thinking"] > 0:
        p2_thinking_stats["avg_thinking_length"] = round(
            total_thinking_len / p2_thinking_stats["total_turns_with_thinking"])

    print(f"\n  --- P2 Thinking Summary ---")
    print(f"    Turns with thinking: {p2_thinking_stats['total_turns_with_thinking']}")
    print(f"    Avg thinking length: {p2_thinking_stats['avg_thinking_length']} chars")
    print(f"    Mentions conflict:   {p2_thinking_stats['thinking_mentions_conflict']}")

    # --- Save results ---
    # Clean divergence examples (ensure JSON-safe)
    clean_examples = []
    for ex in thinking_stats.get("divergence_examples", []):
        clean_ex = {}
        for k, v in ex.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                clean_ex[k] = str(v)
            elif isinstance(v, list):
                clean_ex[k] = [str(x) if isinstance(x, float) and (math.isnan(x) or math.isinf(x)) else x for x in v]
            else:
                clean_ex[k] = v
        clean_examples.append(clean_ex)
    thinking_stats["divergence_examples"] = clean_examples

    r1_results = {
        "p1_thinking_analysis": thinking_stats,
        "p2_thinking_summary": p2_thinking_stats,
    }

    out_path = os.path.join(output_dir, "r1_thinking_analysis.json")
    with open(out_path, "w") as f:
        json.dump(r1_results, f, indent=2)
    print(f"\n  Results written to: {out_path}")


def _extract_numbers(text: str) -> List[float]:
    """Extract all numbers from text."""
    clean = text.replace("$", "").replace(",", "").replace("%", "")
    matches = re.findall(r'-?\d+(?:\.\d+)?', clean)
    result = []
    for m in matches:
        try:
            result.append(float(m))
        except ValueError:
            pass
    return result


def _is_close(value: float, target: float, tol_pct: float, tol_abs: float) -> bool:
    """Check if value is close to target within tolerance."""
    if target == 0:
        return abs(value) <= tol_abs
    rel_err = abs(value - target) / abs(target)
    return rel_err <= tol_pct or abs(value - target) <= tol_abs


# ==============================================================================
# 3. COHEN'S KAPPA FRAMEWORK
# ==============================================================================

def generate_kappa_sample(results_dir: str, output_dir: str):
    """
    Generate a stratified sample of P3 judge outputs for human annotation.

    Stratifies by model and scenario to ensure coverage.
    Produces a JSON template that a human annotator can fill in.
    """
    print(f"\n{'='*70}")
    print("COHEN'S KAPPA: GENERATING ANNOTATION SAMPLE")
    print(f"{'='*70}")

    # Find P3 scored results or judge outputs
    scored_dir = os.path.join(results_dir, "scored")
    judge_dir = os.path.join(results_dir, "scored", "p3_judge_prompts")
    scored_full_dir = os.path.join(results_dir, "scored_full")

    # Try to find P3 judge results (the LLM judge's actual scores)
    p3_judge_results = []

    # Look for judge output files
    for search_dir in [scored_dir, scored_full_dir, results_dir]:
        for pattern in ["p3_judge_results*.json", "p3_scored*.json",
                        "scored_results*.json"]:
            for f in glob.glob(os.path.join(search_dir, pattern)):
                try:
                    with open(f) as fp:
                        data = json.load(fp)
                    if isinstance(data, list):
                        p3_entries = [d for d in data if
                                      d.get("paradigm") == "P3" or
                                      d.get("scenario_id", "").startswith("P3_")]
                        if p3_entries:
                            p3_judge_results.extend(p3_entries)
                except (json.JSONDecodeError, KeyError):
                    pass

    # Also load raw P3 result files
    p3_raw = []
    for model_dir in sorted(glob.glob(os.path.join(results_dir, "*"))):
        if not os.path.isdir(model_dir):
            continue
        model_name = os.path.basename(model_dir)
        if model_name.startswith('.') or model_name in ('scored', 'scored_full'):
            continue
        for f in sorted(glob.glob(os.path.join(model_dir, "P3_*.json"))):
            try:
                with open(f) as fp:
                    result = json.load(fp)
                result.setdefault("model", model_name)
                p3_raw.append(result)
            except (json.JSONDecodeError, KeyError):
                pass

    print(f"  Found {len(p3_judge_results)} P3 judge result entries")
    print(f"  Found {len(p3_raw)} P3 raw result files")

    # Build annotation sample
    # Target: 20% of P3 scenarios per model (research plan spec)
    # With 20 scenarios × 4 models = 80 total, 20% = 16 samples
    # Stratify: at least 1 per model, mix of scenarios
    sample_entries = []

    # Group raw results by model
    by_model = defaultdict(list)
    for r in p3_raw:
        by_model[r["model"]].append(r)

    for model, results in sorted(by_model.items()):
        # Sample ~4 per model (20% of 20)
        n_sample = max(1, min(4, len(results)))
        # Deterministic sampling: every 5th scenario
        step = max(1, len(results) // n_sample)
        sampled = results[::step][:n_sample]

        for result in sampled:
            sid = result["scenario_id"]
            # Get the model's final response (last turn)
            turns = result.get("turns", [])
            final_response = turns[-1].get("response", "") if turns else ""

            entry = {
                "scenario_id": sid,
                "model": model,
                "final_response_excerpt": final_response[:500],
                "human_scores": {
                    "contradiction_identified": None,      # 0.0-1.0
                    "contradiction_resolved": None,        # 0.0-1.0
                    "reasoning_quality": None,             # 0.0-1.0
                    "gap_abstained": None,                 # 0.0-1.0
                    "fabrication_present": None,           # true/false
                    "fabrication_detail": "",              # free text
                    "overall_quality": None,               # 0.0-1.0
                },
                "llm_judge_scores": {},  # will be filled from judge results
                "notes": "",
            }

            # Try to match with judge results
            matching_judge = [j for j in p3_judge_results
                              if j.get("scenario_id") == sid and
                              j.get("model") == model]
            if matching_judge:
                entry["llm_judge_scores"] = matching_judge[0]

            sample_entries.append(entry)

    print(f"  Generated {len(sample_entries)} annotation samples")
    print(f"  By model: {dict((m, len([e for e in sample_entries if e['model'] == m])) for m in by_model)}")

    # Write annotation template
    template_path = os.path.join(output_dir, "kappa_annotation_template.json")
    with open(template_path, "w") as f:
        json.dump(sample_entries, f, indent=2, default=str)
    print(f"  Template written to: {template_path}")
    print(f"\n  INSTRUCTIONS:")
    print(f"  1. Open {template_path}")
    print(f"  2. For each entry, fill in the 'human_scores' fields")
    print(f"  3. Save as kappa_annotations_filled.json")
    print(f"  4. Re-run with --kappa-score --kappa-annotations kappa_annotations_filled.json")


def score_kappa(annotations_path: str, output_dir: str):
    """
    Compute Cohen's Kappa between LLM judge and human annotations.
    """
    print(f"\n{'='*70}")
    print("COHEN'S KAPPA: SCORING")
    print(f"{'='*70}")

    with open(annotations_path) as f:
        annotations = json.load(f)

    # Extract paired scores
    metrics = ["contradiction_identified", "contradiction_resolved",
               "reasoning_quality", "gap_abstained"]

    results = {}
    for metric in metrics:
        human_scores = []
        llm_scores = []

        for entry in annotations:
            h_score = entry.get("human_scores", {}).get(metric)
            l_score = entry.get("llm_judge_scores", {}).get(metric)

            if h_score is not None and l_score is not None:
                # Binarize for Kappa: >=0.5 = positive
                human_scores.append(1 if h_score >= 0.5 else 0)
                llm_scores.append(1 if l_score >= 0.5 else 0)

        if len(human_scores) >= 2:
            kappa = cohens_kappa(human_scores, llm_scores)
            results[metric] = {
                "kappa": round(kappa, 4),
                "n_pairs": len(human_scores),
                "human_positive_rate": round(sum(human_scores) / len(human_scores), 3),
                "llm_positive_rate": round(sum(llm_scores) / len(llm_scores), 3),
            }
            print(f"  {metric:35s}  κ = {kappa:.3f}  (n={len(human_scores)})")
        else:
            print(f"  {metric:35s}  Insufficient data (n={len(human_scores)})")

    # Fabrication (binary)
    h_fab = []
    l_fab = []
    for entry in annotations:
        h = entry.get("human_scores", {}).get("fabrication_present")
        l = entry.get("llm_judge_scores", {}).get("fabrication_rate", None)
        if h is not None and l is not None:
            h_fab.append(1 if h else 0)
            l_fab.append(1 if l > 0 else 0)

    if len(h_fab) >= 2:
        kappa_fab = cohens_kappa(h_fab, l_fab)
        results["fabrication_present"] = {
            "kappa": round(kappa_fab, 4),
            "n_pairs": len(h_fab),
        }
        print(f"  {'fabrication_present':35s}  κ = {kappa_fab:.3f}  (n={len(h_fab)})")

    out_path = os.path.join(output_dir, "kappa_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results written to: {out_path}")


def cohens_kappa(rater1: List[int], rater2: List[int]) -> float:
    """Compute Cohen's Kappa for binary ratings."""
    n = len(rater1)
    if n == 0:
        return 0.0

    # Confusion matrix
    a = sum(1 for i in range(n) if rater1[i] == 1 and rater2[i] == 1)  # both positive
    b = sum(1 for i in range(n) if rater1[i] == 1 and rater2[i] == 0)  # r1 pos, r2 neg
    c = sum(1 for i in range(n) if rater1[i] == 0 and rater2[i] == 1)  # r1 neg, r2 pos
    d = sum(1 for i in range(n) if rater1[i] == 0 and rater2[i] == 0)  # both negative

    # Observed agreement
    po = (a + d) / n

    # Expected agreement by chance
    p1_pos = (a + b) / n
    p2_pos = (a + c) / n
    p1_neg = (c + d) / n
    p2_neg = (b + d) / n
    pe = p1_pos * p2_pos + p1_neg * p2_neg

    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0

    return (po - pe) / (1.0 - pe)


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Supplementary analyses: orthogonality, R1 thinking, Cohen's Kappa")

    parser.add_argument("--results-dir", default="./results",
                        help="Directory containing model results")
    parser.add_argument("--scenarios-dir", default="./p2_scenarios",
                        help="Directory containing scenario files")
    parser.add_argument("--three-paradigm", default="./three_paradigm_summary.json",
                        help="Path to three_paradigm_summary.json")
    parser.add_argument("--p2-rescore", default="./p2_rescore_results/p2_rescore_comparison.json",
                        help="Path to p2_rescore_comparison.json")
    parser.add_argument("--output-dir", default="./supplementary_analysis",
                        help="Output directory")

    # Analysis flags
    parser.add_argument("--orthogonality", action="store_true",
                        help="Run orthogonality tests (Kendall's W + Spearman)")
    parser.add_argument("--r1-thinking", action="store_true",
                        help="Run R1 thinking analysis")
    parser.add_argument("--kappa-sample", action="store_true",
                        help="Generate Cohen's Kappa annotation sample")
    parser.add_argument("--kappa-score", action="store_true",
                        help="Score Cohen's Kappa from annotations")
    parser.add_argument("--kappa-annotations", default=None,
                        help="Path to filled annotation file (for --kappa-score)")
    parser.add_argument("--all", action="store_true",
                        help="Run all analyses except kappa-score")

    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    if args.all:
        args.orthogonality = True
        args.r1_thinking = True
        args.kappa_sample = True

    if not any([args.orthogonality, args.r1_thinking, args.kappa_sample, args.kappa_score]):
        print("No analysis selected. Use --orthogonality, --r1-thinking, "
              "--kappa-sample, --kappa-score, or --all")
        return

    if args.orthogonality:
        run_orthogonality(args.three_paradigm, args.p2_rescore, args.output_dir)

    if args.r1_thinking:
        run_r1_thinking(args.results_dir, args.scenarios_dir, args.output_dir)

    if args.kappa_sample:
        generate_kappa_sample(args.results_dir, args.output_dir)

    if args.kappa_score:
        if not args.kappa_annotations:
            print("ERROR: --kappa-score requires --kappa-annotations <path>")
            return
        score_kappa(args.kappa_annotations, args.output_dir)


if __name__ == "__main__":
    main()
