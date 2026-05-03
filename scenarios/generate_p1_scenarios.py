#!/usr/bin/env python3
"""
generate_p1_scenarios.py — Phase 0a: P1 Scenario Generator (v2)
Context-Dependent Hallucination in Frontier LLMs

Produces 50 self-contained scenario files for Paradigm 1 (Progressive Numerical
Analysis). Each scenario contains a synthetic financial dataset, 20 pre-baked
conversation turns with complete prompts, and pre-computed answer keys.

v2 changes (Turn 20 traceability fix):
  - Every turn stores a 'params' dict capturing its deterministic computation
    parameters (metric, quarter, threshold, etc.)
  - recompute_answer() can reproduce any turn's answer from params + arbitrary data
  - Turn 20 ground truth is computed exactly by replaying the referenced turn's
    params against the corrected dataset

Output:
  p1_scenarios/P1_001.json … P1_050.json
  p1_scenarios/p1_manifest.json
  p1_scenarios/p1_validation_report.txt

Accounting identities (always exact):
  Small  (4 metrics): Net Income = Revenue − COGS − OpEx
  Medium (5 metrics): Gross Profit = Revenue − COGS
                      Net Income  = Revenue − COGS − OpEx
  Large  (6 metrics): Gross Profit = Revenue − COGS
                      Net Income  = Revenue − COGS − OpEx − R&D

Usage:
  python3 generate_p1_scenarios.py
  python3 generate_p1_scenarios.py --output-dir ./my_scenarios --seed 12345
"""

import json
import os
import copy
import random
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Any

# ════════════════════════════════════════════════════════════════
# CONSTANTS
# ════════════════════════════════════════════════════════════════

MASTER_SEED = 20260216

SYSTEM_PROMPT = (
    "You are a financial analyst assistant. Answer questions about the "
    "provided financial data accurately and concisely. Show your calculations "
    "when performing any computation. Use the exact figures from the data provided."
)

SIZE_CONFIGS = {
    "small":  {"n_quarters": 8,  "n_metrics": 4, "count": 17,
               "all_metrics": ["revenue", "cogs", "opex", "net_income"],
               "base_metrics": ["revenue", "cogs", "opex"],
               "derived": {"net_income": "revenue - cogs - opex"}},
    "medium": {"n_quarters": 10, "n_metrics": 5, "count": 17,
               "all_metrics": ["revenue", "cogs", "gross_profit", "opex", "net_income"],
               "base_metrics": ["revenue", "cogs", "opex"],
               "derived": {"gross_profit": "revenue - cogs",
                           "net_income": "revenue - cogs - opex"}},
    "large":  {"n_quarters": 12, "n_metrics": 6, "count": 16,
               "all_metrics": ["revenue", "cogs", "gross_profit", "opex", "r_and_d", "net_income"],
               "base_metrics": ["revenue", "cogs", "opex", "r_and_d"],
               "derived": {"gross_profit": "revenue - cogs",
                           "net_income": "revenue - cogs - opex - r_and_d"}},
}

COMPANY_PREFIXES = [
    "Apex", "Nova", "Vertex", "Quantum", "Stellar", "Prism", "Nexus",
    "Cipher", "Forge", "Helix", "Summit", "Atlas", "Crest", "Onyx",
    "Vanta", "Pulse", "Meridian", "Arbor", "Zenith", "Cobalt",
    "Sable", "Lumen", "Vector", "Strand", "Ember", "Catalyst",
    "Pinnacle", "Cortex", "Axiom", "Radiant", "Nimbus", "Solace",
    "Epoch", "Quasar", "Triton", "Aether", "Basalt", "Cirrus",
    "Delphi", "Elara", "Falcon", "Granite", "Halcyon", "Ionic",
    "Jasper", "Kestrel", "Lattice", "Mosaic", "Obsidian", "Paragon",
]

COMPANY_SUFFIXES = [
    "Dynamics", "Systems", "Technologies", "Solutions", "Analytics",
    "Therapeutics", "Robotics", "Materials", "Sciences", "Semiconductors",
    "Logistics", "Aerospace", "Energy", "Networks", "Digital",
    "Labs", "Industries", "Ventures", "Instruments", "Microsystems",
]

INDUSTRIES = [
    "Enterprise Software", "Cloud Infrastructure", "Medical Devices",
    "Green Energy", "Logistics Technology", "Consumer Electronics",
    "Biotechnology", "Cybersecurity", "E-Commerce Platform",
    "Fintech", "Semiconductor Manufacturing", "Aerospace Components",
    "Industrial Automation", "Digital Healthcare", "Supply Chain Technology",
    "Data Analytics", "Telecommunications Equipment", "Renewable Materials",
    "Precision Agriculture", "Quantum Computing",
]

METRIC_DISPLAY = {
    "revenue": "Revenue",
    "cogs": "COGS",
    "gross_profit": "Gross Profit",
    "opex": "Operating Expenses",
    "r_and_d": "R&D Spending",
    "net_income": "Net Income",
}

METRIC_SHORT = {
    "revenue": "revenue",
    "cogs": "COGS",
    "gross_profit": "gross profit",
    "opex": "operating expenses",
    "r_and_d": "R&D spending",
    "net_income": "net income",
}


# ════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ════════════════════════════════════════════════════════════════

def R(x: float) -> float:
    """Round to 1 decimal place. ALL financial values go through this."""
    return round(x, 1)


def R2(x: float) -> float:
    """Round to 2 decimal places (for percentages)."""
    return round(x, 2)


def fmt_dollar(x: float) -> str:
    if x < 0:
        return f"-${abs(x):.1f}M"
    return f"${x:.1f}M"


def fmt_pct(x: float) -> str:
    return f"{x:.1f}%"


def quarter_label(start_year: int, index: int) -> str:
    q = (index % 4) + 1
    y = start_year + index // 4
    return f"Q{q} {y}"


def quarter_year(qlabel: str) -> int:
    return int(qlabel.split()[1])


def quarter_num(qlabel: str) -> int:
    return int(qlabel[1])


def quarters_in_year(quarters: List[str], year: int) -> List[str]:
    return [q for q in quarters if quarter_year(q) == year]


def available_years(quarters: List[str]) -> List[int]:
    year_counts: Dict[int, int] = {}
    for q in quarters:
        y = quarter_year(q)
        year_counts[y] = year_counts.get(y, 0) + 1
    return [y for y, c in sorted(year_counts.items()) if c >= 2]


def full_years(quarters: List[str]) -> List[int]:
    year_counts: Dict[int, int] = {}
    for q in quarters:
        y = quarter_year(q)
        year_counts[y] = year_counts.get(y, 0) + 1
    return [y for y, c in sorted(year_counts.items()) if c == 4]


def compute_derived(row: Dict[str, float], size_class: str) -> Dict[str, float]:
    result = dict(row)
    if size_class in ("medium", "large"):
        result["gross_profit"] = R(result["revenue"] - result["cogs"])
    if size_class == "large":
        result["net_income"] = R(result["revenue"] - result["cogs"]
                                  - result["opex"] - result["r_and_d"])
    else:
        result["net_income"] = R(result["revenue"] - result["cogs"] - result["opex"])
    return result


# ════════════════════════════════════════════════════════════════
# RECOMPUTE ENGINE
#
# Every quantitative question can be exactly reproduced from:
#   (question_type, params, data, quarters, size_class)
#
# This is used for:
#   1. Turn 20 correction verification (replay with corrected_data)
#   2. Validation (round-trip check that params reproduce the stored GT)
# ════════════════════════════════════════════════════════════════

def recompute_answer(
    question_type: str,
    params: Dict,
    data: Dict,
    quarters: List[str],
    size_class: str,
) -> Dict:
    """
    Deterministically compute a ground-truth answer from stored params + data.

    Returns a ground_truth dict with at least 'value' and 'display'.
    Does NOT produce prompt text — that's frozen at generation time.
    """
    if question_type == "direct_lookup":
        m, q = params["metric"], params["quarter"]
        val = data[q][m]
        return {
            "value": val,
            "display": fmt_dollar(val),
            "derivation": f"Direct lookup: {m} for {q}",
            "scoring_type": "exact_numeric",
            "tolerance_pct": 1.0,
            "tolerance_abs": 0.1,
        }

    elif question_type == "max_quarter":
        m = params["metric"]
        find_max = params["find_max"]
        direction = "highest" if find_max else "lowest"
        vals = [(data[q][m], q) for q in quarters]
        if find_max:
            best_val, best_q = max(vals, key=lambda x: x[0])
        else:
            best_val, best_q = min(vals, key=lambda x: x[0])
        return {
            "value": best_val,
            "value_str": best_q,
            "display": f"{best_q} ({fmt_dollar(best_val)})",
            "derivation": f"Find {direction} {m} across all quarters",
            "scoring_type": "quarter_and_value",
            "tolerance_pct": 1.0,
            "tolerance_abs": 0.1,
        }

    elif question_type == "year_total":
        m, year = params["metric"], params["year"]
        yr_qs = quarters_in_year(quarters, year)
        total = R(sum(data[q][m] for q in yr_qs))
        return {
            "value": total,
            "display": fmt_dollar(total),
            "derivation": f"Sum {m} for {', '.join(yr_qs)}",
            "scoring_type": "exact_numeric",
            "tolerance_pct": 1.0,
            "tolerance_abs": 0.5,
        }

    elif question_type == "count_above":
        m, threshold = params["metric"], params["threshold"]
        count = sum(1 for q in quarters if data[q][m] > threshold)
        return {
            "value": count,
            "display": str(count),
            "derivation": f"Count quarters where {m} > {threshold}",
            "scoring_type": "exact_integer",
        }

    elif question_type == "compare_two":
        m = params["metric"]
        q1, q2 = params["q1"], params["q2"]
        v1, v2 = data[q1][m], data[q2][m]
        higher_q = q1 if v1 > v2 else q2
        diff = R(abs(v1 - v2))
        return {
            "value": diff,
            "value_str": higher_q,
            "display": f"{higher_q} was higher by {fmt_dollar(diff)}",
            "derivation": f"Compare {m}: {q1}={v1}, {q2}={v2}",
            "scoring_type": "quarter_and_value",
            "tolerance_pct": 1.0,
            "tolerance_abs": 0.1,
        }

    elif question_type == "qoq_change":
        m = params["metric"]
        q_prev, q_curr = params["q_prev"], params["q_curr"]
        v_prev, v_curr = data[q_prev][m], data[q_curr][m]
        if v_prev == 0:
            v_prev = 0.1
        pct = R2((v_curr - v_prev) / abs(v_prev) * 100)
        return {
            "value": pct,
            "display": fmt_pct(pct),
            "derivation": f"({v_curr} - {v_prev}) / |{v_prev}| × 100 = {pct}%",
            "scoring_type": "percentage",
            "tolerance_pct": 1.0,
            "tolerance_abs": 0.5,
        }

    elif question_type == "margin":
        q = params["quarter"]
        margin_type = params["margin_type"]
        rev = data[q]["revenue"]
        if margin_type == "gross_margin":
            numerator = data[q]["gross_profit"]
        else:
            numerator = data[q]["net_income"]
        pct = R2(numerator / rev * 100)
        return {
            "value": pct,
            "display": fmt_pct(pct),
            "derivation": f"{numerator} / {rev} × 100 = {pct}%",
            "scoring_type": "percentage",
            "tolerance_pct": 1.0,
            "tolerance_abs": 0.5,
        }

    elif question_type == "ratio":
        m, q = params["metric"], params["quarter"]
        rev = data[q]["revenue"]
        val = data[q][m]
        pct = R2(val / rev * 100)
        return {
            "value": pct,
            "display": fmt_pct(pct),
            "derivation": f"{val} / {rev} × 100 = {pct}%",
            "scoring_type": "percentage",
            "tolerance_pct": 1.0,
            "tolerance_abs": 0.5,
        }

    elif question_type == "year_average":
        m, year = params["metric"], params["year"]
        yr_qs = quarters_in_year(quarters, year)
        avg = R2(sum(data[q][m] for q in yr_qs) / len(yr_qs))
        return {
            "value": avg,
            "display": fmt_dollar(avg),
            "derivation": f"Average {m} over {', '.join(yr_qs)} = {avg}",
            "scoring_type": "exact_numeric",
            "tolerance_pct": 1.0,
            "tolerance_abs": 0.2,
        }

    elif question_type == "yoy_growth":
        m = params["metric"]
        q_prev, q_curr = params["q_prev"], params["q_curr"]
        v_prev, v_curr = data[q_prev][m], data[q_curr][m]
        if v_prev == 0:
            v_prev = 0.1
        yoy = R2((v_curr - v_prev) / abs(v_prev) * 100)
        return {
            "value": yoy,
            "display": fmt_pct(yoy),
            "derivation": f"({v_curr} - {v_prev}) / |{v_prev}| × 100 = {yoy}%",
            "scoring_type": "percentage",
            "tolerance_pct": 1.0,
            "tolerance_abs": 0.5,
        }

    elif question_type == "cumulative":
        m = params["metric"]
        start_q, end_q = params["start_quarter"], params["end_quarter"]
        si = quarters.index(start_q)
        ei = quarters.index(end_q)
        span = quarters[si:ei + 1]
        total = R(sum(data[q][m] for q in span))
        return {
            "value": total,
            "display": fmt_dollar(total),
            "derivation": (f"Sum {m} for {span[0]}..{span[-1]}: "
                           f"{' + '.join(str(data[q][m]) for q in span)} = {total}"),
            "scoring_type": "exact_numeric",
            "tolerance_pct": 1.0,
            "tolerance_abs": 0.5,
        }

    elif question_type == "conditional_average":
        metric_a = params["metric_a"]
        metric_b = params["metric_b"]
        threshold = params["threshold"]
        qualifying = [q for q in quarters if data[q][metric_b] > threshold]
        if not qualifying:
            qualifying = quarters[:1]  # safety
        avg = R2(sum(data[q][metric_a] for q in qualifying) / len(qualifying))
        return {
            "value": avg,
            "display": fmt_dollar(avg),
            "derivation": (f"Quarters where {metric_b} > {threshold}: "
                           f"{', '.join(qualifying)}. Average {metric_a} = {avg}"),
            "scoring_type": "exact_numeric",
            "tolerance_pct": 1.0,
            "tolerance_abs": 0.3,
            "qualifying_quarters": qualifying,
        }

    elif question_type == "top_k":
        m = params["metric"]
        ranked = sorted(quarters, key=lambda q: data[q][m], reverse=True)
        top3 = ranked[:3]
        top3_vals = [data[q][m] for q in top3]
        return {
            "value": top3_vals,
            "value_str": top3,
            "display": ", ".join(f"{q}: {fmt_dollar(data[q][m])}" for q in top3),
            "derivation": f"Sort {m} descending, take top 3",
            "scoring_type": "ranked_list",
            "tolerance_abs": 0.1,
        }

    elif question_type == "max_gap":
        ma, mb = params["metric_a"], params["metric_b"]
        gaps = [(R(abs(data[q][ma] - data[q][mb])), q) for q in quarters]
        max_gap_val, max_q = max(gaps, key=lambda x: x[0])
        return {
            "value": max_gap_val,
            "value_str": max_q,
            "display": f"{max_q}: gap of {fmt_dollar(max_gap_val)}",
            "derivation": (f"|{ma} - {mb}| for each quarter. "
                           f"Max at {max_q}: |{data[max_q][ma]} - {data[max_q][mb]}| = {max_gap_val}"),
            "scoring_type": "quarter_and_value",
            "tolerance_pct": 1.0,
            "tolerance_abs": 0.2,
        }

    elif question_type == "conditional_aggregate":
        cost_metric = params["cost_metric"]
        threshold_pct = params["threshold_pct"]
        target_metric = params["target_metric"]
        qualifying = [q for q in quarters
                      if (data[q][cost_metric] / data[q]["revenue"] * 100) < threshold_pct]
        total = R(sum(data[q][target_metric] for q in qualifying))
        return {
            "value": total,
            "display": fmt_dollar(total),
            "derivation": (f"Quarters where {cost_metric}/revenue < {threshold_pct}%: "
                           f"{', '.join(qualifying)}. Total {target_metric} = {total}"),
            "scoring_type": "exact_numeric",
            "tolerance_pct": 1.0,
            "tolerance_abs": 0.5,
            "qualifying_quarters": qualifying,
        }

    else:
        raise ValueError(f"Cannot recompute question_type={question_type!r}")


# ════════════════════════════════════════════════════════════════
# DATA GENERATION
# ════════════════════════════════════════════════════════════════

def generate_company(rng: random.Random) -> Dict[str, str]:
    prefix = rng.choice(COMPANY_PREFIXES)
    suffix = rng.choice(COMPANY_SUFFIXES)
    industry = rng.choice(INDUSTRIES)
    return {"name": f"{prefix} {suffix}", "industry": industry}


def generate_financial_data(
    rng: random.Random,
    n_quarters: int,
    size_class: str,
) -> Tuple[List[str], Dict[str, Dict[str, float]], Dict[str, Any]]:
    """
    Generate a synthetic financial dataset with planted patterns.

    Returns:
        quarters: ordered list of quarter labels
        data: {quarter_label: {metric: value}}
        patterns: description of planted patterns
    """
    start_year = rng.choice([2022, 2023])
    quarters = [quarter_label(start_year, i) for i in range(n_quarters)]

    base_revenue = R(rng.uniform(28, 75))
    quarterly_growth = rng.uniform(0.015, 0.045)
    seasonal_bump = rng.uniform(0.10, 0.22)

    inflection_idx = rng.randint(n_quarters // 3, 2 * n_quarters // 3)
    post_inflection_growth = quarterly_growth * rng.uniform(1.3, 2.0)

    anomaly_idx = rng.randint(2, n_quarters - 3)
    anomaly_type = rng.choice(["cogs_spike", "revenue_dip"])

    cogs_ratio = rng.uniform(0.32, 0.52)
    opex_ratio = rng.uniform(0.15, 0.28)
    rnd_ratio = rng.uniform(0.06, 0.14) if size_class == "large" else 0.0

    data = {}
    for i, q in enumerate(quarters):
        trend_factor = (1 + quarterly_growth) ** min(i, inflection_idx)
        if i > inflection_idx:
            trend_factor *= (1 + post_inflection_growth) ** (i - inflection_idx)
        seasonal = 1.0 + (seasonal_bump if (i % 4 == 3) else 0.0)
        noise = rng.gauss(1.0, 0.025)
        rev = R(base_revenue * trend_factor * seasonal * noise)

        if i == anomaly_idx and anomaly_type == "revenue_dip":
            rev = R(rev * rng.uniform(0.82, 0.90))

        cogs_noise = rng.gauss(1.0, 0.03)
        cogs_r = cogs_ratio * cogs_noise
        if i == anomaly_idx and anomaly_type == "cogs_spike":
            cogs_r *= rng.uniform(1.15, 1.30)
        cogs = R(rev * cogs_r)

        opex_scale = 1.0 - (i * 0.003)
        opex = R(rev * opex_ratio * opex_scale * rng.gauss(1.0, 0.03))

        row = {"revenue": rev, "cogs": cogs, "opex": opex}

        if size_class == "large":
            rnd = R(rev * rnd_ratio * rng.gauss(1.0, 0.04))
            row["r_and_d"] = rnd

        row = compute_derived(row, size_class)
        data[q] = row

    patterns = {
        "base_revenue_M": base_revenue,
        "quarterly_growth_pct": R2(quarterly_growth * 100),
        "seasonal_q4_bump_pct": R2(seasonal_bump * 100),
        "growth_inflection_quarter": quarters[inflection_idx],
        "post_inflection_growth_pct": R2(post_inflection_growth * 100),
        "anomalous_quarter": quarters[anomaly_idx],
        "anomaly_type": anomaly_type,
        "base_cogs_ratio_pct": R2(cogs_ratio * 100),
        "base_opex_ratio_pct": R2(opex_ratio * 100),
    }
    if size_class == "large":
        patterns["base_rnd_ratio_pct"] = R2(rnd_ratio * 100)

    return quarters, data, patterns


def format_data_table(
    quarters: List[str],
    data: Dict[str, Dict[str, float]],
    size_class: str,
) -> str:
    cfg = SIZE_CONFIGS[size_class]
    metrics = cfg["all_metrics"]
    headers = ["Quarter"] + [f"{METRIC_DISPLAY[m]} ($M)" for m in metrics]
    sep = ["-" * len(h) for h in headers]

    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(sep) + " |")
    for q in quarters:
        vals = [q] + [f"{data[q][m]:.1f}" for m in metrics]
        lines.append("| " + " | ".join(vals) + " |")

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════
# QUESTION GENERATORS
#
# Each returns (prompt_text, ground_truth_dict, depends_on_list, params_dict)
#
# params_dict: pure-data dict that, together with (data, quarters, size_class),
# is sufficient to exactly reproduce ground_truth via recompute_answer().
# ════════════════════════════════════════════════════════════════

def q_direct_lookup(
    rng: random.Random,
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
    used_pairs: set,
) -> Tuple[str, Dict, List, Dict]:
    cfg = SIZE_CONFIGS[size_class]
    metrics = cfg["all_metrics"]
    for _ in range(100):
        m = rng.choice(metrics)
        q = rng.choice(quarters)
        if (m, q) not in used_pairs:
            break
    used_pairs.add((m, q))

    params = {"metric": m, "quarter": q}
    gt = recompute_answer("direct_lookup", params, data, quarters, size_class)
    prompt = f"What was {company}'s {METRIC_SHORT[m]} in {q}?"
    return prompt, gt, [(m, q)], params


def q_max_quarter(
    rng: random.Random,
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
    **_,
) -> Tuple[str, Dict, List, Dict]:
    cfg = SIZE_CONFIGS[size_class]
    m = rng.choice(cfg["all_metrics"])
    find_max = rng.choice([True, False])
    direction = "highest" if find_max else "lowest"

    params = {"metric": m, "find_max": find_max}
    gt = recompute_answer("max_quarter", params, data, quarters, size_class)
    prompt = f"Which quarter had the {direction} {METRIC_SHORT[m]}?"
    deps = [(m, q) for q in quarters]
    return prompt, gt, deps, params


def q_year_total(
    rng: random.Random,
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
    **_,
) -> Tuple[str, Dict, List, Dict]:
    cfg = SIZE_CONFIGS[size_class]
    yrs = full_years(quarters)
    if not yrs:
        yrs = available_years(quarters)
    year = rng.choice(yrs)
    m = rng.choice(cfg["all_metrics"])
    yr_quarters = quarters_in_year(quarters, year)

    params = {"metric": m, "year": year}
    gt = recompute_answer("year_total", params, data, quarters, size_class)
    prompt = (f"What was {company}'s total {METRIC_SHORT[m]} "
              f"for fiscal year {year}?")
    deps = [(m, q) for q in yr_quarters]
    return prompt, gt, deps, params


def q_count_above(
    rng: random.Random,
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
    **_,
) -> Tuple[str, Dict, List, Dict]:
    cfg = SIZE_CONFIGS[size_class]
    m = rng.choice([x for x in cfg["all_metrics"] if x != "net_income"])
    vals = sorted([data[q][m] for q in quarters])
    median_idx = len(vals) // 2
    threshold = R(vals[median_idx] - rng.uniform(0.5, 2.0))

    params = {"metric": m, "threshold": threshold}
    gt = recompute_answer("count_above", params, data, quarters, size_class)
    prompt = (f"In how many quarters did {company}'s {METRIC_SHORT[m]} "
              f"exceed {fmt_dollar(threshold)}?")
    deps = [(m, q) for q in quarters]
    return prompt, gt, deps, params


def q_compare_two(
    rng: random.Random,
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
    **_,
) -> Tuple[str, Dict, List, Dict]:
    cfg = SIZE_CONFIGS[size_class]
    m = rng.choice(cfg["all_metrics"])
    for _ in range(50):
        q1, q2 = rng.sample(quarters, 2)
        v1, v2 = data[q1][m], data[q2][m]
        if abs(v1 - v2) >= 0.1:
            break
    else:
        for m2 in cfg["all_metrics"]:
            vals = [data[q][m2] for q in quarters]
            if max(vals) - min(vals) > 1.0:
                m = m2
                sorted_qs = sorted(quarters, key=lambda q: data[q][m])
                q1, q2 = sorted_qs[0], sorted_qs[-1]
                break

    params = {"metric": m, "q1": q1, "q2": q2}
    gt = recompute_answer("compare_two", params, data, quarters, size_class)
    prompt = (f"Was {company}'s {METRIC_SHORT[m]} higher in {q1} or {q2}, "
              f"and by how much?")
    return prompt, gt, [(m, q1), (m, q2)], params


def q_qoq_change(
    rng: random.Random,
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
    **_,
) -> Tuple[str, Dict, List, Dict]:
    cfg = SIZE_CONFIGS[size_class]
    m = rng.choice(cfg["all_metrics"])
    idx = rng.randint(1, len(quarters) - 1)
    q_prev, q_curr = quarters[idx - 1], quarters[idx]

    params = {"metric": m, "q_prev": q_prev, "q_curr": q_curr}
    gt = recompute_answer("qoq_change", params, data, quarters, size_class)
    prompt = (f"What was the quarter-over-quarter percentage change in "
              f"{company}'s {METRIC_SHORT[m]} from {q_prev} to {q_curr}?")
    return prompt, gt, [(m, q_prev), (m, q_curr)], params


def q_margin(
    rng: random.Random,
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
    **_,
) -> Tuple[str, Dict, List, Dict]:
    q = rng.choice(quarters)
    if size_class in ("medium", "large"):
        margin_type = rng.choice(["gross_margin", "net_margin"])
    else:
        margin_type = "net_margin"

    params = {"quarter": q, "margin_type": margin_type}
    gt = recompute_answer("margin", params, data, quarters, size_class)

    if margin_type == "gross_margin":
        prompt = f"What was {company}'s gross margin (gross profit / revenue) in {q}?"
        deps = [("revenue", q), ("gross_profit", q)]
    else:
        prompt = f"What was {company}'s net margin (net income / revenue) in {q}?"
        deps = [("revenue", q), ("net_income", q)]

    return prompt, gt, deps, params


def q_ratio(
    rng: random.Random,
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
    **_,
) -> Tuple[str, Dict, List, Dict]:
    cfg = SIZE_CONFIGS[size_class]
    cost_metrics = [m for m in cfg["all_metrics"]
                    if m not in ("revenue", "gross_profit", "net_income")]
    m = rng.choice(cost_metrics)
    q = rng.choice(quarters)

    params = {"metric": m, "quarter": q}
    gt = recompute_answer("ratio", params, data, quarters, size_class)
    prompt = (f"What percentage of {company}'s revenue was {METRIC_SHORT[m]} "
              f"in {q}?")
    return prompt, gt, [(m, q), ("revenue", q)], params


def q_year_average(
    rng: random.Random,
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
    **_,
) -> Tuple[str, Dict, List, Dict]:
    cfg = SIZE_CONFIGS[size_class]
    yrs = available_years(quarters)
    year = rng.choice(yrs)
    m = rng.choice(cfg["all_metrics"])
    yr_qs = quarters_in_year(quarters, year)

    params = {"metric": m, "year": year}
    gt = recompute_answer("year_average", params, data, quarters, size_class)
    prompt = (f"What was {company}'s average quarterly {METRIC_SHORT[m]} "
              f"in {year}?")
    deps = [(m, q) for q in yr_qs]
    return prompt, gt, deps, params


def q_yoy_growth(
    rng: random.Random,
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
    **_,
) -> Tuple[str, Dict, List, Dict]:
    cfg = SIZE_CONFIGS[size_class]
    m = rng.choice(cfg["all_metrics"])
    valid_pairs = []
    for i, q in enumerate(quarters):
        if i >= 4:
            q_prev = quarters[i - 4]
            if quarter_num(q) == quarter_num(q_prev):
                valid_pairs.append((q_prev, q))
    if not valid_pairs:
        return q_qoq_change(rng, company, quarters, data, size_class)

    q_prev, q_curr = rng.choice(valid_pairs)

    params = {"metric": m, "q_prev": q_prev, "q_curr": q_curr}
    gt = recompute_answer("yoy_growth", params, data, quarters, size_class)
    prompt = (f"What was the year-over-year growth in {company}'s "
              f"{METRIC_SHORT[m]} from {q_prev} to {q_curr}?")
    return prompt, gt, [(m, q_prev), (m, q_curr)], params


# --- Multi-step calculation questions ---

def q_cumulative(
    rng: random.Random,
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
    **_,
) -> Tuple[str, Dict, List, Dict]:
    cfg = SIZE_CONFIGS[size_class]
    m = rng.choice(cfg["all_metrics"])
    start = rng.randint(0, len(quarters) - 4)
    end = rng.randint(start + 2, min(start + 7, len(quarters) - 1))
    span = quarters[start:end + 1]

    params = {"metric": m, "start_quarter": span[0], "end_quarter": span[-1]}
    gt = recompute_answer("cumulative", params, data, quarters, size_class)
    prompt = (f"What was {company}'s cumulative {METRIC_SHORT[m]} "
              f"from {span[0]} through {span[-1]}?")
    deps = [(m, q) for q in span]
    return prompt, gt, deps, params


def q_conditional_average(
    rng: random.Random,
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
    **_,
) -> Tuple[str, Dict, List, Dict]:
    cfg = SIZE_CONFIGS[size_class]
    metric_a = rng.choice(cfg["all_metrics"])
    metric_b = rng.choice([m for m in cfg["all_metrics"] if m != metric_a])

    vals_b = sorted([data[q][metric_b] for q in quarters])
    target_count = rng.randint(3, min(6, len(quarters) - 2))
    threshold = R(vals_b[-(target_count + 1)] + 0.1)

    qualifying = [q for q in quarters if data[q][metric_b] > threshold]
    if len(qualifying) < 2:
        threshold = R(vals_b[len(vals_b) // 2])
        qualifying = [q for q in quarters if data[q][metric_b] > threshold]
    if len(qualifying) < 1:
        qualifying = quarters[:3]
        threshold = R(min(data[q][metric_b] for q in qualifying) - 0.1)

    params = {"metric_a": metric_a, "metric_b": metric_b, "threshold": threshold}
    gt = recompute_answer("conditional_average", params, data, quarters, size_class)
    prompt = (f"What was {company}'s average {METRIC_SHORT[metric_a]} across "
              f"quarters where {METRIC_SHORT[metric_b]} exceeded "
              f"{fmt_dollar(threshold)}?")
    deps = [(metric_a, q) for q in qualifying] + [(metric_b, q) for q in quarters]
    return prompt, gt, deps, params


def q_top_k(
    rng: random.Random,
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
    **_,
) -> Tuple[str, Dict, List, Dict]:
    cfg = SIZE_CONFIGS[size_class]
    m = rng.choice(cfg["all_metrics"])

    params = {"metric": m}
    gt = recompute_answer("top_k", params, data, quarters, size_class)
    prompt = (f"What were the top 3 quarters for {company} by "
              f"{METRIC_SHORT[m]}? List them with their values.")
    deps = [(m, q) for q in quarters]
    return prompt, gt, deps, params


def q_max_gap(
    rng: random.Random,
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
    **_,
) -> Tuple[str, Dict, List, Dict]:
    cfg = SIZE_CONFIGS[size_class]
    candidates = [m for m in cfg["all_metrics"] if m not in ("net_income",)]
    if len(candidates) < 2:
        candidates = cfg["all_metrics"][:2]
    ma, mb = rng.sample(candidates, 2)

    params = {"metric_a": ma, "metric_b": mb}
    gt = recompute_answer("max_gap", params, data, quarters, size_class)
    prompt = (f"In which quarter was the gap between {company}'s "
              f"{METRIC_SHORT[ma]} and {METRIC_SHORT[mb]} the largest? "
              f"What was the gap?")
    deps = [(ma, q) for q in quarters] + [(mb, q) for q in quarters]
    return prompt, gt, deps, params


def q_conditional_aggregate(
    rng: random.Random,
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
    **_,
) -> Tuple[str, Dict, List, Dict]:
    cfg = SIZE_CONFIGS[size_class]
    cost_metric = rng.choice([m for m in cfg["base_metrics"] if m != "revenue"])
    threshold_pct = rng.choice([30, 35, 40, 45, 50])

    qualifying = [q for q in quarters
                  if (data[q][cost_metric] / data[q]["revenue"] * 100) < threshold_pct]
    while len(qualifying) < 2 and threshold_pct < 90:
        threshold_pct += 5
        qualifying = [q for q in quarters
                      if (data[q][cost_metric] / data[q]["revenue"] * 100) < threshold_pct]

    target_metric = rng.choice(cfg["all_metrics"])

    params = {"cost_metric": cost_metric, "threshold_pct": threshold_pct,
              "target_metric": target_metric}
    gt = recompute_answer("conditional_aggregate", params, data, quarters, size_class)
    prompt = (f"What was {company}'s total {METRIC_SHORT[target_metric]} "
              f"across quarters where {METRIC_SHORT[cost_metric]} was below "
              f"{threshold_pct}% of revenue?")
    deps = ([(cost_metric, q) for q in quarters]
            + [("revenue", q) for q in quarters]
            + [(target_metric, q) for q in qualifying])
    return prompt, gt, deps, params


# --- Synthesis questions (no params — not recomputable for Turn 20) ---

def q_anomaly_detection(
    company: str,
    quarters: List[str],
    data: Dict,
    patterns: Dict,
    size_class: str,
) -> Tuple[str, Dict, List]:
    anomaly_q = patterns["anomalous_quarter"]
    anomaly_type = patterns["anomaly_type"]

    if anomaly_type == "cogs_spike":
        anomaly_metric = "cogs"
        anomaly_desc = "unusually high COGS relative to revenue"
    else:
        anomaly_metric = "revenue"
        anomaly_desc = "revenue decline against the prevailing growth trend"

    anomaly_val = data[anomaly_q][anomaly_metric]
    claims = [
        {"claim": f"identifies {anomaly_q} as anomalous", "required": True},
        {"claim": f"mentions {anomaly_desc}", "required": True},
        {"claim": f"cites correct {anomaly_metric} value for {anomaly_q}",
         "value": anomaly_val, "required": False},
    ]

    prompt = (f"Looking at {company}'s data, which quarter appears most "
              f"anomalous in terms of cost structure or financial performance? "
              f"What stands out and why?")
    gt = {
        "value_str": anomaly_q,
        "display": f"{anomaly_q} — {anomaly_desc}",
        "derivation": f"Planted anomaly: {anomaly_type} in {anomaly_q}",
        "scoring_type": "synthesis",
        "checkable_claims": claims,
    }
    deps = [(m, anomaly_q) for m in data[anomaly_q]]
    return prompt, gt, deps


def q_trend_summary(
    company: str,
    quarters: List[str],
    data: Dict,
    patterns: Dict,
    size_class: str,
) -> Tuple[str, Dict, List]:
    inflection_q = patterns["growth_inflection_quarter"]
    first_rev = data[quarters[0]]["revenue"]
    last_rev = data[quarters[-1]]["revenue"]

    claims = [
        {"claim": "notes overall revenue growth", "required": True},
        {"claim": f"references revenue growing from ~{fmt_dollar(first_rev)} to ~{fmt_dollar(last_rev)}",
         "required": False},
        {"claim": f"identifies growth acceleration around {inflection_q}",
         "required": False},
        {"claim": "comments on profitability trend", "required": True},
    ]

    prompt = (f"Summarize {company}'s overall financial trajectory across "
              f"this {len(quarters)}-quarter period. What are the key trends?")
    gt = {
        "display": f"Revenue grew from {fmt_dollar(first_rev)} to {fmt_dollar(last_rev)} "
                   f"with inflection at {inflection_q}",
        "derivation": "Synthesis of overall trends",
        "scoring_type": "synthesis",
        "checkable_claims": claims,
    }
    deps = [("revenue", q) for q in quarters] + [("net_income", q) for q in quarters]
    return prompt, gt, deps


def q_half_comparison(
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
) -> Tuple[str, Dict, List]:
    mid = len(quarters) // 2
    first_half = quarters[:mid]
    second_half = quarters[mid:]

    avg_rev_h1 = R2(sum(data[q]["revenue"] for q in first_half) / len(first_half))
    avg_rev_h2 = R2(sum(data[q]["revenue"] for q in second_half) / len(second_half))
    avg_ni_h1 = R2(sum(data[q]["net_income"] for q in first_half) / len(first_half))
    avg_ni_h2 = R2(sum(data[q]["net_income"] for q in second_half) / len(second_half))
    rev_change = R2((avg_rev_h2 - avg_rev_h1) / avg_rev_h1 * 100)

    claims = [
        {"claim": "compares revenue between halves", "required": True},
        {"claim": f"first-half avg revenue near {fmt_dollar(avg_rev_h1)}",
         "value": avg_rev_h1, "required": False},
        {"claim": f"second-half avg revenue near {fmt_dollar(avg_rev_h2)}",
         "value": avg_rev_h2, "required": False},
        {"claim": "compares profitability between halves", "required": True},
    ]

    prompt = (f"Compare {company}'s performance in the first half "
              f"({first_half[0]}–{first_half[-1]}) versus the second half "
              f"({second_half[0]}–{second_half[-1]}) of the data. "
              f"Focus on revenue growth and profitability.")
    gt = {
        "display": (f"H1 avg rev: {fmt_dollar(avg_rev_h1)}, "
                    f"H2 avg rev: {fmt_dollar(avg_rev_h2)} ({fmt_pct(rev_change)} change). "
                    f"H1 avg NI: {fmt_dollar(avg_ni_h1)}, H2 avg NI: {fmt_dollar(avg_ni_h2)}"),
        "derivation": "Compare averages across first/second half",
        "scoring_type": "synthesis",
        "checkable_claims": claims,
        "reference_values": {
            "avg_revenue_h1": avg_rev_h1,
            "avg_revenue_h2": avg_rev_h2,
            "avg_net_income_h1": avg_ni_h1,
            "avg_net_income_h2": avg_ni_h2,
            "revenue_change_pct": rev_change,
        },
    }
    deps = [("revenue", q) for q in quarters] + [("net_income", q) for q in quarters]
    return prompt, gt, deps


# ════════════════════════════════════════════════════════════════
# CORRECTION LOGIC
# ════════════════════════════════════════════════════════════════

# Question types that support deterministic recomputation via params
RECOMPUTABLE_TYPES = {
    "direct_lookup", "max_quarter", "year_total", "count_above",
    "compare_two", "qoq_change", "margin", "ratio", "year_average",
    "yoy_growth", "cumulative", "conditional_average", "top_k",
    "max_gap", "conditional_aggregate",
}


def generate_correction(
    rng: random.Random,
    company: str,
    quarters: List[str],
    data: Dict,
    size_class: str,
    turns: List[Dict],
    correction_metric: str,
) -> Tuple[Dict, List[Dict]]:
    """
    Generate correction event for turns 19-20.

    Turn 20 ground truth is computed exactly by replaying the referenced turn's
    stored params against corrected_data via recompute_answer().
    """
    cfg = SIZE_CONFIGS[size_class]

    mid_start = len(quarters) // 4
    mid_end = 3 * len(quarters) // 4
    target_q = rng.choice(quarters[mid_start:mid_end])
    original_val = data[target_q][correction_metric]

    direction = rng.choice([-1, 1])
    pct_change = rng.uniform(0.08, 0.18)
    corrected_val = R(original_val * (1 + direction * pct_change))

    corrected_row = dict(data[target_q])
    corrected_row[correction_metric] = corrected_val
    corrected_row = compute_derived(corrected_row, size_class)

    corrected_data = copy.deepcopy(data)
    corrected_data[target_q] = corrected_row

    # Which derived metrics change?
    if correction_metric in ("revenue", "cogs"):
        changed_derived = set(cfg["derived"].keys())
    elif correction_metric in ("opex", "r_and_d"):
        changed_derived = {"net_income"}
    else:
        changed_derived = set(cfg["derived"].keys())

    # Find affected turns (only recomputable ones eligible for Turn 20 probe)
    affected_turns = []
    affected_recomputable = []

    for turn in turns:
        deps = turn.get("depends_on", [])
        is_affected = any(m == correction_metric and q == target_q for m, q in deps)
        derived_affected = any(q == target_q and m in changed_derived for m, q in deps)

        if is_affected or derived_affected:
            tn = turn["turn_number"]
            affected_turns.append(tn)
            if turn["question_type"] in RECOMPUTABLE_TYPES and turn.get("params"):
                affected_recomputable.append(tn)

    # Propagation depth
    if correction_metric == "revenue":
        depth = "deep"
        affected_derived = (["gross_profit", "net_income"]
                            if size_class != "small" else ["net_income"])
    elif correction_metric == "cogs":
        depth = "medium"
        affected_derived = (["gross_profit", "net_income"]
                            if size_class != "small" else ["net_income"])
    else:
        depth = "shallow"
        affected_derived = ["net_income"]

    # Value changes in the corrected quarter
    value_changes = {}
    for m in cfg["all_metrics"]:
        if data[target_q][m] != corrected_row[m]:
            value_changes[m] = {
                "original": data[target_q][m],
                "corrected": corrected_row[m],
            }

    # --- Turn 19: Introduce correction ---
    prompt_19 = (
        f"I need to make a correction: {company}'s "
        f"{METRIC_SHORT[correction_metric]} for {target_q} should be "
        f"{fmt_dollar(corrected_val)}, not {fmt_dollar(original_val)}. "
        f"Which of our earlier calculations does this affect, and how do the "
        f"derived figures for {target_q} change?"
    )
    gt_19 = {
        "display": (f"Correction: {correction_metric} in {target_q}: "
                    f"{fmt_dollar(original_val)} → {fmt_dollar(corrected_val)}"),
        "derivation": "Identify affected calculations and recompute",
        "scoring_type": "correction_identification",
        "affected_turns": affected_turns,
        "value_changes": value_changes,
        "checkable_claims": [
            {"claim": f"acknowledges {correction_metric} change in {target_q}",
             "required": True},
        ] + [
            {"claim": f"correctly updates {m} to {fmt_dollar(corrected_row[m])}",
             "value": corrected_row[m], "required": True}
            for m in affected_derived if m in corrected_row
        ],
    }

    # --- Turn 20: Verify specific corrected value (PROBE) ---
    if affected_recomputable:
        ref_turn_num = rng.choice(affected_recomputable)
        ref_turn_data = turns[ref_turn_num - 1]

        # THE FIX: Replay stored params against corrected_data
        new_gt = recompute_answer(
            ref_turn_data["question_type"],
            ref_turn_data["params"],
            corrected_data,
            quarters,
            size_class,
        )

        # Also compute original answer for reference
        original_gt_value = ref_turn_data["ground_truth"].get("value")

        prompt_20 = (
            f"Given the corrected {METRIC_SHORT[correction_metric]}, "
            f"can you recalculate the answer to my earlier question from "
            f"turn {ref_turn_num}? "
            f"(It was: \"{ref_turn_data['prompt']}\")"
        )

        gt_20 = new_gt
        gt_20["scoring_type"] = "correction_propagation"
        gt_20["referenced_turn"] = ref_turn_num
        gt_20["original_answer"] = original_gt_value
        gt_20["derivation"] = (
            f"Recompute turn {ref_turn_num} ({ref_turn_data['question_type']}) "
            f"with {correction_metric}={corrected_val} in {target_q}: "
            f"{new_gt['derivation']}"
        )
        gt_20["display"] = (
            f"Recomputed turn {ref_turn_num}: {new_gt['display']} "
            f"(was: {ref_turn_data['ground_truth'].get('display', 'N/A')})"
        )
    else:
        # Fallback: ask about direct derived value in the corrected quarter
        check_metric = affected_derived[0] if affected_derived else "net_income"
        prompt_20 = (
            f"What is {company}'s updated {METRIC_SHORT[check_metric]} "
            f"for {target_q} after this correction?"
        )
        gt_20 = {
            "value": corrected_row[check_metric],
            "display": fmt_dollar(corrected_row[check_metric]),
            "derivation": f"Recompute {check_metric} with corrected {correction_metric}",
            "scoring_type": "exact_numeric",
            "tolerance_pct": 1.0,
            "tolerance_abs": 0.1,
        }

    turn_19 = {
        "turn_number": 19,
        "phase": "correction",
        "question_type": "correction_intro",
        "is_probe": False,
        "prompt": prompt_19,
        "ground_truth": gt_19,
        "depends_on": [(correction_metric, target_q)],
    }
    turn_20 = {
        "turn_number": 20,
        "phase": "correction",
        "question_type": "correction_verify",
        "is_probe": True,
        "prompt": prompt_20,
        "ground_truth": gt_20,
        "depends_on": [(correction_metric, target_q)],
    }

    correction_info = {
        "target_metric": correction_metric,
        "target_quarter": target_q,
        "original_value": original_val,
        "corrected_value": corrected_val,
        "propagation_depth": depth,
        "affected_derived_metrics": affected_derived,
        "value_changes": value_changes,
        "affected_turns": affected_turns,
        "affected_recomputable_turns": affected_recomputable,
        "corrected_quarter_data": corrected_row,
    }

    return correction_info, [turn_19, turn_20]


# ════════════════════════════════════════════════════════════════
# TURN ASSEMBLY
# ════════════════════════════════════════════════════════════════

LOOKUP_GENERATORS = [q_max_quarter, q_year_total, q_count_above, q_compare_two]
SINGLE_STEP_GENERATORS = [q_qoq_change, q_margin, q_ratio, q_year_average]
MULTI_STEP_GENERATORS = [q_cumulative, q_conditional_average, q_top_k, q_max_gap]


def generate_turns(
    rng: random.Random,
    company_name: str,
    quarters: List[str],
    data: Dict,
    patterns: Dict,
    size_class: str,
) -> List[Dict]:
    """Generate all 20 conversation turns (1-18; 19-20 added later)."""
    turns = []
    used_pairs: set = set()
    common_kwargs = {
        "company": company_name,
        "quarters": quarters,
        "data": data,
        "size_class": size_class,
    }

    # --- Turn 1: Data presentation + first lookup ---
    data_table = format_data_table(quarters, data, size_class)
    derived_note = ""
    if size_class == "small":
        derived_note = "\nNote: Net Income = Revenue − COGS − Operating Expenses."
    elif size_class == "medium":
        derived_note = ("\nNote: Gross Profit = Revenue − COGS. "
                        "Net Income = Revenue − COGS − Operating Expenses.")
    elif size_class == "large":
        derived_note = ("\nNote: Gross Profit = Revenue − COGS. "
                        "Net Income = Revenue − COGS − Operating Expenses − R&D.")

    prompt_q, gt_q, deps_q, params_q = q_direct_lookup(
        rng, company_name, quarters, data, size_class, used_pairs)

    # Prompt text for turn 1 is reconstructed in generate_scenario() with
    # correct company industry. Store a placeholder here.
    turns.append({
        "turn_number": 1,
        "phase": "lookup",
        "question_type": "direct_lookup",
        "is_probe": False,
        "prompt": "__TURN1_PLACEHOLDER__",
        "ground_truth": gt_q,
        "depends_on": deps_q,
        "params": params_q,
        "_first_question_prompt": prompt_q,
    })

    # --- Turns 2-4: Lookup (varied types) ---
    lookup_pool = list(LOOKUP_GENERATORS)
    rng.shuffle(lookup_pool)
    for t_num in range(2, 5):
        gen_fn = lookup_pool[(t_num - 2) % len(lookup_pool)]
        prompt, gt, deps, params = gen_fn(rng=rng, used_pairs=used_pairs, **common_kwargs)
        turns.append({
            "turn_number": t_num,
            "phase": "lookup",
            "question_type": gen_fn.__name__[2:],
            "is_probe": False,
            "prompt": prompt,
            "ground_truth": gt,
            "depends_on": deps,
            "params": params,
        })

    # --- Turn 5: Lookup PROBE ---
    prompt, gt, deps, params = q_direct_lookup(
        rng, company_name, quarters, data, size_class, used_pairs)
    turns.append({
        "turn_number": 5,
        "phase": "lookup",
        "question_type": "direct_lookup",
        "is_probe": True,
        "prompt": prompt,
        "ground_truth": gt,
        "depends_on": deps,
        "params": params,
    })

    # --- Turns 6-9: Single-step calculation ---
    ss_pool = list(SINGLE_STEP_GENERATORS)
    rng.shuffle(ss_pool)
    for t_num in range(6, 10):
        gen_fn = ss_pool[(t_num - 6) % len(ss_pool)]
        prompt, gt, deps, params = gen_fn(rng=rng, **common_kwargs)
        turns.append({
            "turn_number": t_num,
            "phase": "single_step",
            "question_type": gen_fn.__name__[2:],
            "is_probe": False,
            "prompt": prompt,
            "ground_truth": gt,
            "depends_on": deps,
            "params": params,
        })

    # --- Turn 10: Single-step PROBE ---
    prompt, gt, deps, params = q_yoy_growth(rng=rng, **common_kwargs)
    turns.append({
        "turn_number": 10,
        "phase": "single_step",
        "question_type": "yoy_growth",
        "is_probe": True,
        "prompt": prompt,
        "ground_truth": gt,
        "depends_on": deps,
        "params": params,
    })

    # --- Turns 11-14: Multi-step calculation ---
    ms_pool = list(MULTI_STEP_GENERATORS)
    rng.shuffle(ms_pool)
    for t_num in range(11, 15):
        gen_fn = ms_pool[(t_num - 11) % len(ms_pool)]
        prompt, gt, deps, params = gen_fn(rng=rng, **common_kwargs)
        turns.append({
            "turn_number": t_num,
            "phase": "multi_step",
            "question_type": gen_fn.__name__[2:],
            "is_probe": False,
            "prompt": prompt,
            "ground_truth": gt,
            "depends_on": deps,
            "params": params,
        })

    # --- Turn 15: Multi-step PROBE ---
    prompt, gt, deps, params = q_conditional_aggregate(rng=rng, **common_kwargs)
    turns.append({
        "turn_number": 15,
        "phase": "multi_step",
        "question_type": "conditional_aggregate",
        "is_probe": True,
        "prompt": prompt,
        "ground_truth": gt,
        "depends_on": deps,
        "params": params,
    })

    # --- Turns 16-18: Synthesis (no params — not recomputable) ---
    prompt, gt, deps = q_anomaly_detection(
        company_name, quarters, data, patterns, size_class)
    turns.append({
        "turn_number": 16,
        "phase": "synthesis",
        "question_type": "anomaly_detection",
        "is_probe": False,
        "prompt": prompt,
        "ground_truth": gt,
        "depends_on": deps,
    })

    prompt, gt, deps = q_trend_summary(
        company_name, quarters, data, patterns, size_class)
    turns.append({
        "turn_number": 17,
        "phase": "synthesis",
        "question_type": "trend_summary",
        "is_probe": False,
        "prompt": prompt,
        "ground_truth": gt,
        "depends_on": deps,
    })

    prompt, gt, deps = q_half_comparison(
        company_name, quarters, data, size_class)
    turns.append({
        "turn_number": 18,
        "phase": "synthesis",
        "question_type": "half_comparison",
        "is_probe": False,
        "prompt": prompt,
        "ground_truth": gt,
        "depends_on": deps,
    })

    return turns


# ════════════════════════════════════════════════════════════════
# SCENARIO ASSEMBLY
# ════════════════════════════════════════════════════════════════

def generate_scenario(
    scenario_num: int,
    size_class: str,
    master_rng: random.Random,
    correction_metric: str,
    base_seed: int = MASTER_SEED,
) -> Dict:
    scenario_seed = base_seed * 100 + scenario_num
    rng = random.Random(scenario_seed)

    company = generate_company(rng)
    n_quarters = SIZE_CONFIGS[size_class]["n_quarters"]
    quarters, data, patterns = generate_financial_data(rng, n_quarters, size_class)

    turns = generate_turns(rng, company["name"], quarters, data, patterns, size_class)

    # Fix turn 1: build proper prompt with correct industry
    data_table = format_data_table(quarters, data, size_class)
    derived_note = ""
    if size_class == "small":
        derived_note = "\nNote: Net Income = Revenue − COGS − Operating Expenses."
    elif size_class == "medium":
        derived_note = ("\nNote: Gross Profit = Revenue − COGS. "
                        "Net Income = Revenue − COGS − Operating Expenses.")
    elif size_class == "large":
        derived_note = ("\nNote: Gross Profit = Revenue − COGS. "
                        "Net Income = Revenue − COGS − Operating Expenses − R&D.")

    first_question = turns[0].pop("_first_question_prompt")
    turns[0]["prompt"] = (
        f"Here is the quarterly financial data for {company['name']}, "
        f"a company in the {company['industry']} sector:\n\n"
        f"{data_table}\n"
        f"\nAll figures are in millions of USD ($M).{derived_note}\n\n"
        f"Let's start with a basic question: {first_question}"
    )

    # Generate correction (turns 19-20)
    correction_info, correction_turns = generate_correction(
        rng, company["name"], quarters, data, size_class, turns, correction_metric)
    turns.extend(correction_turns)

    scenario_id = f"P1_{scenario_num:03d}"
    scenario = {
        "scenario_id": scenario_id,
        "metadata": {
            "size_class": size_class,
            "n_quarters": n_quarters,
            "n_metrics": SIZE_CONFIGS[size_class]["n_metrics"],
            "seed": scenario_seed,
            "correction_target": correction_metric,
            "correction_depth": correction_info["propagation_depth"],
            "generated_at": datetime.now().isoformat(),
            "generator_version": "2.0.0",
        },
        "company": company,
        "system_prompt": SYSTEM_PROMPT,
        "quarters": quarters,
        "metrics": SIZE_CONFIGS[size_class]["all_metrics"],
        "base_metrics": SIZE_CONFIGS[size_class]["base_metrics"],
        "derived_formulas": SIZE_CONFIGS[size_class]["derived"],
        "data": data,
        "data_table_text": data_table,
        "planted_patterns": patterns,
        "correction": correction_info,
        "turns": turns,
    }

    return scenario


# ════════════════════════════════════════════════════════════════
# VALIDATION
# ════════════════════════════════════════════════════════════════

def validate_scenario(scenario: Dict) -> List[str]:
    issues = []
    sid = scenario["scenario_id"]
    data = scenario["data"]
    size_class = scenario["metadata"]["size_class"]
    quarters = scenario["quarters"]
    cfg = SIZE_CONFIGS[size_class]

    # 1. Accounting identities
    for q in quarters:
        row = data[q]
        if size_class in ("medium", "large"):
            expected_gp = R(row["revenue"] - row["cogs"])
            if abs(row["gross_profit"] - expected_gp) > 0.01:
                issues.append(f"{sid} {q}: GP {row['gross_profit']} != {expected_gp}")

        if size_class == "large":
            expected_ni = R(row["revenue"] - row["cogs"]
                           - row["opex"] - row["r_and_d"])
        else:
            expected_ni = R(row["revenue"] - row["cogs"] - row["opex"])
        if abs(row["net_income"] - expected_ni) > 0.01:
            issues.append(f"{sid} {q}: NI {row['net_income']} != {expected_ni}")

    # 2. Turn count
    turns = scenario["turns"]
    if len(turns) != 20:
        issues.append(f"{sid}: expected 20 turns, got {len(turns)}")

    # 3. Turn numbering
    for i, t in enumerate(turns):
        if t["turn_number"] != i + 1:
            issues.append(f"{sid}: turn {i+1} has turn_number={t['turn_number']}")

    # 4. Probe turns at 5, 10, 15, 20
    probe_turns = sorted(t["turn_number"] for t in turns if t["is_probe"])
    if probe_turns != [5, 10, 15, 20]:
        issues.append(f"{sid}: probes at {probe_turns}, expected [5,10,15,20]")

    # 5. Phase correctness
    for t in turns:
        tn = t["turn_number"]
        expected = ("lookup" if tn <= 5 else "single_step" if tn <= 10
                    else "multi_step" if tn <= 15 else "synthesis" if tn <= 18
                    else "correction")
        if t["phase"] != expected:
            issues.append(f"{sid} T{tn}: phase={t['phase']}, expected={expected}")

    # 6. All turns have ground_truth and non-empty prompt
    for t in turns:
        if "ground_truth" not in t:
            issues.append(f"{sid} T{t['turn_number']}: missing ground_truth")
        if not t.get("prompt") or t["prompt"] == "__TURN1_PLACEHOLDER__":
            issues.append(f"{sid} T{t['turn_number']}: empty/placeholder prompt")

    # 7. Correction consistency
    corr = scenario["correction"]
    target_q = corr["target_quarter"]
    target_m = corr["target_metric"]
    if data[target_q][target_m] != corr["original_value"]:
        issues.append(
            f"{sid}: correction original={corr['original_value']} "
            f"!= data={data[target_q][target_m]}")

    # 8. Corrected quarter accounting identities
    corrected_row = corr["corrected_quarter_data"]
    expected_corrected = dict(data[target_q])
    expected_corrected[target_m] = corr["corrected_value"]
    expected_corrected = compute_derived(expected_corrected, size_class)
    for m in cfg["all_metrics"]:
        if abs(corrected_row[m] - expected_corrected[m]) > 0.01:
            issues.append(f"{sid}: corrected {m}={corrected_row[m]} != {expected_corrected[m]}")

    # 9. PARAMS ROUND-TRIP: verify recompute_answer matches stored GT
    for t in turns:
        if t.get("params") and t["question_type"] in RECOMPUTABLE_TYPES:
            recomputed = recompute_answer(
                t["question_type"], t["params"], data, quarters, size_class)
            stored_val = t["ground_truth"].get("value")
            recomp_val = recomputed.get("value")
            if stored_val is not None and recomp_val is not None:
                if isinstance(stored_val, list):
                    for sv, rv in zip(stored_val, recomp_val):
                        if abs(sv - rv) > 0.01:
                            issues.append(
                                f"{sid} T{t['turn_number']}: round-trip mismatch "
                                f"stored={stored_val} recomputed={recomp_val}")
                            break
                elif isinstance(stored_val, (int, float)):
                    if abs(stored_val - recomp_val) > 0.01:
                        issues.append(
                            f"{sid} T{t['turn_number']}: round-trip mismatch "
                            f"stored={stored_val} recomputed={recomp_val}")

    # 10. Turn 20 has a concrete value (the fix)
    t20 = turns[19]
    t20_gt = t20["ground_truth"]
    if t20_gt["scoring_type"] == "correction_propagation":
        if "value" not in t20_gt:
            issues.append(f"{sid} T20: correction_propagation missing 'value'")
        if "referenced_turn" not in t20_gt:
            issues.append(f"{sid} T20: correction_propagation missing 'referenced_turn'")

    return issues


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Generate P1 (Progressive Numerical Analysis) scenarios")
    parser.add_argument("--output-dir", type=str, default="p1_scenarios",
                        help="Output directory (default: p1_scenarios)")
    parser.add_argument("--seed", type=int, default=MASTER_SEED,
                        help=f"Master seed (default: {MASTER_SEED})")
    args = parser.parse_args()

    seed = args.seed
    os.makedirs(args.output_dir, exist_ok=True)
    master_rng = random.Random(seed)

    correction_targets = ["revenue"] * 17 + ["cogs"] * 17 + ["opex"] * 16
    master_rng.shuffle(correction_targets)

    scenarios = []
    all_issues = []

    size_order = []
    for sc, cfg in SIZE_CONFIGS.items():
        size_order.extend([sc] * cfg["count"])
    master_rng.shuffle(size_order)

    print(f"Generating 50 P1 scenarios (seed={seed})...")
    print(f"  Small (8Q×4): 17 | Medium (10Q×5): 17 | Large (12Q×6): 16")
    print(f"  Corrections: 17 revenue, 17 COGS, 16 OpEx")
    print()

    scenario_num = 1
    for i, size_class in enumerate(size_order):
        correction_metric = correction_targets[i]
        scenario = generate_scenario(
            scenario_num, size_class, master_rng, correction_metric,
            base_seed=seed)
        scenarios.append(scenario)

        issues = validate_scenario(scenario)
        if issues:
            all_issues.extend(issues)
            print(f"  {scenario['scenario_id']} ({size_class:6s}, "
                  f"corr={correction_metric:7s}): {len(issues)} ISSUES")
            for iss in issues:
                print(f"    ⚠ {iss}")
        else:
            print(f"  {scenario['scenario_id']} ({size_class:6s}, "
                  f"corr={correction_metric:7s}): OK  "
                  f"[{scenario['company']['name']}]")

        path = os.path.join(args.output_dir, f"{scenario['scenario_id']}.json")
        with open(path, "w") as f:
            json.dump(scenario, f, indent=2, ensure_ascii=False)

        scenario_num += 1

    # --- Manifest ---
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "generator_version": "2.0.0",
        "master_seed": seed,
        "total_scenarios": len(scenarios),
        "size_distribution": {
            sc: sum(1 for s in scenarios if s["metadata"]["size_class"] == sc)
            for sc in ["small", "medium", "large"]
        },
        "correction_distribution": {
            cm: sum(1 for s in scenarios if s["metadata"]["correction_target"] == cm)
            for cm in ["revenue", "cogs", "opex"]
        },
        "system_prompt": SYSTEM_PROMPT,
        "scenarios": [
            {
                "scenario_id": s["scenario_id"],
                "size_class": s["metadata"]["size_class"],
                "n_quarters": s["metadata"]["n_quarters"],
                "company": s["company"]["name"],
                "industry": s["company"]["industry"],
                "correction_target": s["metadata"]["correction_target"],
                "correction_depth": s["metadata"]["correction_depth"],
            }
            for s in scenarios
        ],
    }
    manifest_path = os.path.join(args.output_dir, "p1_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # --- Validation report ---
    report_path = os.path.join(args.output_dir, "p1_validation_report.txt")
    with open(report_path, "w") as f:
        f.write(f"P1 Scenario Validation Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Master seed: {seed}\n")
        f.write(f"Generator version: 2.0.0\n")
        f.write(f"Total scenarios: {len(scenarios)}\n")
        f.write(f"Total issues: {len(all_issues)}\n\n")
        if all_issues:
            f.write("Issues:\n")
            for iss in all_issues:
                f.write(f"  ⚠ {iss}\n")
        else:
            f.write("All scenarios passed validation (including params round-trip).\n")
        f.write(f"\nSize distribution:\n")
        for sc in ["small", "medium", "large"]:
            count = sum(1 for s in scenarios if s["metadata"]["size_class"] == sc)
            f.write(f"  {sc}: {count}\n")
        f.write(f"\nCorrection distribution:\n")
        for cm in ["revenue", "cogs", "opex"]:
            count = sum(1 for s in scenarios if s["metadata"]["correction_target"] == cm)
            f.write(f"  {cm}: {count}\n")

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print(f"DONE: {len(scenarios)} scenarios generated")
    print(f"  Output: {args.output_dir}/")
    print(f"  Manifest: {manifest_path}")
    print(f"  Validation: {report_path}")
    if all_issues:
        print(f"  ⚠ {len(all_issues)} validation issues found!")
    else:
        print(f"  ✓ All scenarios passed validation (including params round-trip)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
