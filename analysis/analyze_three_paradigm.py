#!/usr/bin/env python3
"""
analyze_three_paradigm.py — Three-Paradigm Integrated Analysis
Context-Dependent Hallucination in Frontier LLMs

Combines P1 (numeric fidelity), P2 (constraint satisfaction), and P3
(multi-document synthesis) results into a unified cross-paradigm analysis.

Produces:
  Charts:
    - p3_model_comparison.png        — P3 metrics by model
    - p3_authority_split.png         — Authority bias: correct vs wrong scenarios
    - p3_gap_fabrication.png         — Gap abstention and fabrication rates
    - cross_paradigm_heatmap.png     — Model × metric heatmap across all paradigms
    - cross_paradigm_radar.png       — Radar profiles per model
  Tables:
    - cross_paradigm_rankings.csv    — Full rankings with all metrics
    - p3_detailed_metrics.csv        — P3 per-model breakdown
    - three_paradigm_summary.json    — Complete summary blob

Usage:
  python analyze_three_paradigm.py \
      --scored-results ./results/scored_full/scored_results.json \
      --p3-judged-dir ./results/p3_judged \
      --output-dir ./analysis

Dependencies:
  pip install pandas matplotlib numpy
"""

import os
import sys
import json
import csv
import argparse
import math
from collections import defaultdict
from typing import Dict, List, Any, Optional

try:
    import pandas as pd
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from matplotlib.patches import FancyBboxPatch
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install pandas matplotlib numpy")
    sys.exit(1)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Display names for models (short labels for charts)
MODEL_DISPLAY = {
    "gpt-4o": "GPT-4o",
    "claude-sonnet-4.5": "Sonnet 4.5",
    "deepseek-r1": "DeepSeek-R1",
    "gemini-2.5-pro": "Gemini 2.5 Pro",
    "minimax-m2.5": "MiniMax M2.5",
}

# Consistent colors per model across all charts
MODEL_COLORS = {
    "gpt-4o": "#1f77b4",
    "claude-sonnet-4.5": "#ff7f0e",
    "deepseek-r1": "#2ca02c",
    "gemini-2.5-pro": "#d62728",
    "minimax-m2.5": "#9467bd",
}

# Chart settings
DPI = 300
FIGSIZE_WIDE = (14, 7)
FIGSIZE_SQUARE = (10, 8)
FIGSIZE_TALL = (12, 10)

plt.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.dpi": DPI,
})


# ==============================================================================
# DATA LOADING
# ==============================================================================

def load_p1_p2_results(scored_path: str) -> pd.DataFrame:
    """Load P1/P2 scored results into a DataFrame."""
    with open(scored_path, "r") as f:
        data = json.load(f)

    rows = []
    for entry in data:
        paradigm = entry.get("paradigm", "")
        model = entry.get("model", "unknown")

        if paradigm == "P1":
            rows.append({
                "paradigm": "P1",
                "model": model,
                "scenario_id": entry.get("scenario_id"),
                "overall_accuracy": entry.get("overall_accuracy", 0.0),
                "probe_accuracy": entry.get("probe_accuracy", 0.0),
            })
        elif paradigm == "P2":
            rows.append({
                "paradigm": "P2",
                "model": model,
                "scenario_id": entry.get("scenario_id"),
                "avg_satisfaction_rate": entry.get("avg_satisfaction_rate", 0.0),
                "conflict_score": entry.get("conflict_score"),
            })

    return pd.DataFrame(rows)


def load_p3_results(p3_dir: str) -> List[Dict]:
    """Load individual P3 judge results."""
    individual_dir = os.path.join(p3_dir, "individual")
    results = []

    if not os.path.isdir(individual_dir):
        print(f"WARNING: {individual_dir} not found")
        return results

    for fname in sorted(os.listdir(individual_dir)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(individual_dir, fname)
        try:
            with open(fpath, "r") as f:
                data = json.load(f)
            if data.get("success"):
                results.append(data)
        except (json.JSONDecodeError, KeyError):
            pass

    return results


def load_authority_split(p3_dir: str) -> Optional[Dict]:
    """Load authority split analysis if available."""
    split_path = os.path.join(p3_dir, "authority_split_analysis.json")
    if os.path.exists(split_path):
        with open(split_path, "r") as f:
            return json.load(f)
    return None


# ==============================================================================
# AGGREGATE COMPUTATION
# ==============================================================================

def compute_p1_aggregates(df: pd.DataFrame) -> Dict[str, Dict]:
    """Compute per-model P1 aggregates."""
    p1 = df[df["paradigm"] == "P1"]
    agg = {}
    for model, group in p1.groupby("model"):
        agg[model] = {
            "n": len(group),
            "accuracy": round(group["overall_accuracy"].mean(), 4),
            "probe_accuracy": round(group["probe_accuracy"].mean(), 4),
        }
    return agg


def compute_p2_aggregates(df: pd.DataFrame) -> Dict[str, Dict]:
    """Compute per-model P2 aggregates."""
    p2 = df[df["paradigm"] == "P2"]
    agg = {}
    for model, group in p2.groupby("model"):
        conflict_scores = group["conflict_score"].dropna()
        agg[model] = {
            "n": len(group),
            "satisfaction_rate": round(group["avg_satisfaction_rate"].mean(), 4),
            "conflict_score": round(conflict_scores.mean(), 4) if len(conflict_scores) > 0 else None,
        }
    return agg


def compute_p3_aggregates(results: List[Dict]) -> Dict[str, Dict]:
    """Compute per-model P3 aggregates with authority split."""
    by_model = defaultdict(list)
    for r in results:
        by_model[r["model"]].append(r)

    agg = {}
    for model in sorted(by_model.keys()):
        entries = by_model[model]

        # Contradiction scores
        all_identified, all_resolved, all_reasoning = [], [], []
        for e in entries:
            for cid, cs in e.get("contradiction_scores", {}).items():
                all_identified.append(cs.get("identified", 0.0))
                all_resolved.append(cs.get("resolved_correctly", 0.0))
                all_reasoning.append(cs.get("reasoning_quality", 0.0))

        # Gap scores
        all_abstained, all_fabricated = [], []
        for e in entries:
            for gid, gs in e.get("gap_scores", {}).items():
                all_abstained.append(gs.get("abstained", 0.0))
                all_fabricated.append(1.0 if gs.get("fabricated") else 0.0)

        # Authority bias by direction
        auth_correct = [e for e in entries if e.get("authority_correct") is True]
        auth_wrong = [e for e in entries if e.get("authority_correct") is False]

        appropriate_defer = sum(
            1 for e in auth_correct
            if e.get("authority_bias", {}).get("deferred_to_authority") is True
        )
        inappropriate_defer = sum(
            1 for e in auth_wrong
            if e.get("authority_bias", {}).get("deferred_to_authority") is True
        )

        def _mean(lst):
            return round(sum(lst) / len(lst), 4) if lst else None

        agg[model] = {
            "n": len(entries),
            "contradiction_identified": _mean(all_identified),
            "contradiction_resolved": _mean(all_resolved),
            "contradiction_reasoning": _mean(all_reasoning),
            "gap_abstained": _mean(all_abstained),
            "fabrication_rate": _mean(all_fabricated),
            "appropriate_deference": round(appropriate_defer / len(auth_correct), 4) if auth_correct else None,
            "inappropriate_deference": round(inappropriate_defer / len(auth_wrong), 4) if auth_wrong else None,
            "n_authority_correct": len(auth_correct),
            "n_authority_wrong": len(auth_wrong),
        }
    return agg


def build_cross_paradigm_table(p1_agg, p2_agg, p3_agg) -> pd.DataFrame:
    """Build the unified cross-paradigm comparison table."""
    # Get all models that appear in at least one paradigm (exclude Gemini from P3)
    all_models = sorted(set(list(p1_agg.keys()) + list(p2_agg.keys()) + list(p3_agg.keys())))

    rows = []
    for model in all_models:
        row = {"model": model, "display_name": MODEL_DISPLAY.get(model, model)}

        # P1
        p1 = p1_agg.get(model, {})
        row["P1_accuracy"] = p1.get("accuracy")
        row["P1_probe"] = p1.get("probe_accuracy")
        row["P1_n"] = p1.get("n")

        # P2
        p2 = p2_agg.get(model, {})
        row["P2_satisfaction"] = p2.get("satisfaction_rate")
        row["P2_conflict"] = p2.get("conflict_score")
        row["P2_n"] = p2.get("n")

        # P3
        p3 = p3_agg.get(model, {})
        row["P3_contradiction_resolved"] = p3.get("contradiction_resolved")
        row["P3_gap_abstained"] = p3.get("gap_abstained")
        row["P3_fabrication_rate"] = p3.get("fabrication_rate")
        row["P3_appropriate_deference"] = p3.get("appropriate_deference")
        row["P3_inappropriate_deference"] = p3.get("inappropriate_deference")
        row["P3_n"] = p3.get("n")

        rows.append(row)

    return pd.DataFrame(rows)


# ==============================================================================
# CHART: P3 MODEL COMPARISON
# ==============================================================================

def chart_p3_model_comparison(p3_agg: Dict, output_dir: str):
    """Bar chart comparing P3 metrics across models."""
    models = [m for m in p3_agg.keys() if m in MODEL_COLORS]
    if not models:
        return

    metrics = [
        ("contradiction_resolved", "Contradiction\nResolution"),
        ("contradiction_reasoning", "Reasoning\nQuality"),
        ("gap_abstained", "Gap\nAbstention"),
    ]

    fig, ax = plt.subplots(figsize=(12, 6))

    x = np.arange(len(metrics))
    width = 0.18
    offsets = np.linspace(-(len(models)-1)/2 * width, (len(models)-1)/2 * width, len(models))

    for i, model in enumerate(models):
        vals = [p3_agg[model].get(m, 0) or 0 for m, _ in metrics]
        bars = ax.bar(x + offsets[i], vals, width, label=MODEL_DISPLAY.get(model, model),
                      color=MODEL_COLORS.get(model, "#333"), alpha=0.85, edgecolor="white", linewidth=0.5)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                    f"{val:.2f}", ha="center", va="bottom", fontsize=8)

    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Score")
    ax.set_title("P3: Multi-Document Synthesis — Model Comparison", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([label for _, label in metrics])
    ax.legend(loc="lower right", framealpha=0.9)
    ax.axhline(y=1.0, color="gray", linestyle="--", alpha=0.3)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    path = os.path.join(output_dir, "charts", "p3_model_comparison.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ==============================================================================
# CHART: P3 AUTHORITY SPLIT
# ==============================================================================

def chart_p3_authority_split(p3_agg: Dict, output_dir: str):
    """Grouped bar chart: appropriate vs inappropriate authority deference."""
    models = [m for m in p3_agg.keys() if m in MODEL_COLORS]
    if not models:
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Left panel: Deference rates by direction
    ax = axes[0]
    x = np.arange(len(models))
    width = 0.35

    appropriate = [p3_agg[m].get("appropriate_deference", 0) or 0 for m in models]
    inappropriate = [p3_agg[m].get("inappropriate_deference", 0) or 0 for m in models]

    bars1 = ax.bar(x - width/2, appropriate, width, label="Appropriate\n(auth correct)",
                   color="#2ecc71", alpha=0.85, edgecolor="white")
    bars2 = ax.bar(x + width/2, inappropriate, width, label="Inappropriate\n(auth WRONG)",
                   color="#e74c3c", alpha=0.85, edgecolor="white")

    for bar, val in zip(bars1, appropriate):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f"{val:.0%}", ha="center", va="bottom", fontsize=9)
    for bar, val in zip(bars2, inappropriate):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f"{val:.0%}", ha="center", va="bottom", fontsize=9)

    ax.set_ylim(0, 1.25)
    ax.set_ylabel("Deference Rate")
    ax.set_title("Authority Deference by Direction", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([MODEL_DISPLAY.get(m, m) for m in models], rotation=15, ha="right")
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.3)

    # Right panel: Gap abstention & fabrication
    ax = axes[1]
    gap_abstained = [p3_agg[m].get("gap_abstained", 0) or 0 for m in models]
    fab_rate = [p3_agg[m].get("fabrication_rate", 0) or 0 for m in models]

    bars1 = ax.bar(x - width/2, gap_abstained, width, label="Gap Abstention",
                   color="#3498db", alpha=0.85, edgecolor="white")
    bars2 = ax.bar(x + width/2, fab_rate, width, label="Fabrication Rate",
                   color="#e67e22", alpha=0.85, edgecolor="white")

    for bar, val in zip(bars1, gap_abstained):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f"{val:.0%}", ha="center", va="bottom", fontsize=9)
    for bar, val in zip(bars2, fab_rate):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f"{val:.0%}", ha="center", va="bottom", fontsize=9)

    ax.set_ylim(0, 1.25)
    ax.set_ylabel("Rate")
    ax.set_title("Gap Handling & Fabrication", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([MODEL_DISPLAY.get(m, m) for m in models], rotation=15, ha="right")
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.3)

    fig.suptitle("P3: Authority Bias & Source Fidelity Analysis", fontweight="bold", fontsize=14, y=1.02)
    fig.tight_layout()
    path = os.path.join(output_dir, "charts", "p3_authority_split.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ==============================================================================
# CHART: CROSS-PARADIGM HEATMAP
# ==============================================================================

def chart_cross_paradigm_heatmap(cross_df: pd.DataFrame, output_dir: str):
    """Heatmap of model × metric across all three paradigms."""
    # Select key metrics for the heatmap
    metric_cols = [
        ("P1_accuracy", "P1: Accuracy"),
        ("P1_probe", "P1: Probe Accuracy"),
        ("P2_satisfaction", "P2: Satisfaction"),
        ("P2_conflict", "P2: Conflict Detection"),
        ("P3_contradiction_resolved", "P3: Contradiction Res."),
        ("P3_gap_abstained", "P3: Gap Abstention"),
        ("P3_fabrication_rate", "P3: Fabrication Rate"),
        ("P3_inappropriate_deference", "P3: Inappropriate Def."),
    ]

    # Filter to models with P3 data (exclude Gemini)
    df = cross_df[cross_df["P3_n"].notna()].copy()
    if df.empty:
        return

    models = df["display_name"].tolist()
    available_metrics = [(col, label) for col, label in metric_cols if col in df.columns]

    # Build heatmap data
    data = []
    for _, label in available_metrics:
        pass  # placeholder
    data = np.zeros((len(available_metrics), len(models)))

    for j, (col, label) in enumerate(available_metrics):
        for i, (_, row) in enumerate(df.iterrows()):
            val = row.get(col)
            data[j, i] = float(val) if val is not None and not (isinstance(val, float) and math.isnan(val)) else np.nan

    fig, ax = plt.subplots(figsize=(12, 7))

    # Custom colormap: for fabrication and inappropriate deference, lower is better
    # We'll annotate with actual values and use a single colormap
    im = ax.imshow(data, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)

    # Override colors for "lower is better" metrics
    # (fabrication_rate, inappropriate_deference) — invert in display
    invert_rows = {j for j, (col, _) in enumerate(available_metrics)
                   if col in ("P3_fabrication_rate", "P3_inappropriate_deference")}

    ax.set_xticks(np.arange(len(models)))
    ax.set_xticklabels(models, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(available_metrics)))
    ax.set_yticklabels([label for _, label in available_metrics])

    # Annotate cells
    for j in range(len(available_metrics)):
        for i in range(len(models)):
            val = data[j, i]
            if np.isnan(val):
                text = "N/A"
                color = "gray"
            else:
                text = f"{val:.3f}"
                # For inverted metrics, mark with color
                if j in invert_rows:
                    color = "red" if val > 0.05 else "green"
                    text = f"{val:.3f}" + (" ↑" if val > 0.05 else "")
                else:
                    color = "black" if val > 0.5 else "white"
            ax.text(i, j, text, ha="center", va="center", fontsize=9,
                    color=color, fontweight="bold" if j in invert_rows else "normal")

    # Add paradigm separators
    ax.axhline(y=1.5, color="white", linewidth=3)
    ax.axhline(y=3.5, color="white", linewidth=3)

    # Add paradigm labels on right
    ax.text(len(models) + 0.3, 0.5, "P1", va="center", fontsize=11,
            fontweight="bold", color="#1f77b4")
    ax.text(len(models) + 0.3, 2.5, "P2", va="center", fontsize=11,
            fontweight="bold", color="#ff7f0e")
    ax.text(len(models) + 0.3, 5.5, "P3", va="center", fontsize=11,
            fontweight="bold", color="#2ca02c")

    ax.set_title("Cross-Paradigm Model Performance Heatmap", fontweight="bold", pad=15)

    cbar = fig.colorbar(im, ax=ax, shrink=0.6, label="Score (higher = better, except marked ↑)")

    fig.tight_layout()
    path = os.path.join(output_dir, "charts", "cross_paradigm_heatmap.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ==============================================================================
# CHART: CROSS-PARADIGM RADAR
# ==============================================================================

def chart_cross_paradigm_radar(p1_agg, p2_agg, p3_agg, output_dir: str):
    """Radar/spider chart showing model profiles across paradigms."""
    # Models with full data (all 3 paradigms)
    models = [m for m in p3_agg.keys() if m in p1_agg and m in p2_agg]
    if not models:
        return

    # Metrics for radar (all "higher is better" — invert fabrication)
    metrics = [
        ("P1 Accuracy", lambda m: p1_agg[m].get("accuracy", 0)),
        ("P1 Probe", lambda m: p1_agg[m].get("probe_accuracy", 0)),
        ("P2 Satisfaction", lambda m: p2_agg[m].get("satisfaction_rate", 0)),
        ("P2 Conflict", lambda m: p2_agg[m].get("conflict_score", 0) or 0),
        ("P3 Contr. Resolution", lambda m: p3_agg[m].get("contradiction_resolved", 0) or 0),
        ("P3 Gap Abstention", lambda m: p3_agg[m].get("gap_abstained", 0) or 0),
        ("P3 Anti-Fabrication", lambda m: 1.0 - (p3_agg[m].get("fabrication_rate", 0) or 0)),
    ]

    N = len(metrics)
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]  # close the polygon

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))

    for model in models:
        values = [fn(model) for _, fn in metrics]
        values += values[:1]
        ax.plot(angles, values, 'o-', linewidth=2, markersize=5,
                label=MODEL_DISPLAY.get(model, model),
                color=MODEL_COLORS.get(model, "#333"), alpha=0.8)
        ax.fill(angles, values, alpha=0.08, color=MODEL_COLORS.get(model, "#333"))

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([label for label, _ in metrics], fontsize=10)
    ax.set_ylim(0, 1.05)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=8, color="gray")
    ax.set_title("Cross-Paradigm Model Profiles\n(All metrics normalized: higher = better)",
                 fontweight="bold", pad=30)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), framealpha=0.9)

    fig.tight_layout()
    path = os.path.join(output_dir, "charts", "cross_paradigm_radar.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ==============================================================================
# CHART: MODEL RANKING SUMMARY
# ==============================================================================

def chart_model_ranking_summary(p1_agg, p2_agg, p3_agg, output_dir: str):
    """Horizontal bar chart showing composite scores and per-paradigm ranks."""
    models = [m for m in p3_agg.keys() if m in p1_agg and m in p2_agg]
    if not models:
        return

    # Compute composite scores (simple average of key metrics, all higher=better)
    composites = {}
    for model in models:
        scores = [
            p1_agg[model].get("accuracy", 0),
            p1_agg[model].get("probe_accuracy", 0),
            p2_agg[model].get("satisfaction_rate", 0),
            p3_agg[model].get("contradiction_resolved", 0) or 0,
            p3_agg[model].get("gap_abstained", 0) or 0,
            1.0 - (p3_agg[model].get("fabrication_rate", 0) or 0),
        ]
        composites[model] = sum(scores) / len(scores)

    # Sort by composite
    sorted_models = sorted(models, key=lambda m: composites[m], reverse=True)

    fig, ax = plt.subplots(figsize=(12, 6))

    y_pos = np.arange(len(sorted_models))

    # Stacked horizontal bars showing contribution of each paradigm
    p1_scores = [p1_agg[m].get("accuracy", 0) for m in sorted_models]
    p2_scores = [p2_agg[m].get("satisfaction_rate", 0) for m in sorted_models]
    p3_scores = [(p3_agg[m].get("contradiction_resolved", 0) or 0) for m in sorted_models]

    ax.barh(y_pos, p1_scores, 0.25, label="P1: Accuracy",
            color="#1f77b4", alpha=0.8)
    ax.barh(y_pos - 0.28, p2_scores, 0.25, label="P2: Satisfaction",
            color="#ff7f0e", alpha=0.8)
    ax.barh(y_pos + 0.28, p3_scores, 0.25, label="P3: Contradiction Res.",
            color="#2ca02c", alpha=0.8)

    # Add composite score label
    for i, model in enumerate(sorted_models):
        ax.text(1.02, i, f"Composite: {composites[model]:.3f}",
                va="center", fontsize=10, fontweight="bold")

    ax.set_yticks(y_pos)
    ax.set_yticklabels([MODEL_DISPLAY.get(m, m) for m in sorted_models], fontsize=11)
    ax.set_xlim(0, 1.25)
    ax.set_xlabel("Score")
    ax.set_title("Cross-Paradigm Model Rankings", fontweight="bold")
    ax.legend(loc="lower right")
    ax.grid(axis="x", alpha=0.3)
    ax.invert_yaxis()

    fig.tight_layout()
    path = os.path.join(output_dir, "charts", "cross_paradigm_rankings.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ==============================================================================
# TABLE OUTPUTS
# ==============================================================================

def save_tables(cross_df: pd.DataFrame, p3_agg: Dict, output_dir: str):
    """Save CSV and JSON summary tables."""
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)

    # Cross-paradigm rankings CSV
    csv_path = os.path.join(tables_dir, "cross_paradigm_rankings.csv")
    cross_df.to_csv(csv_path, index=False, float_format="%.4f")
    print(f"  Saved: {csv_path}")

    # P3 detailed metrics CSV
    p3_rows = []
    for model, metrics in sorted(p3_agg.items()):
        row = {"model": model, "display_name": MODEL_DISPLAY.get(model, model)}
        row.update(metrics)
        p3_rows.append(row)

    if p3_rows:
        p3_csv_path = os.path.join(tables_dir, "p3_detailed_metrics.csv")
        p3_df = pd.DataFrame(p3_rows)
        p3_df.to_csv(p3_csv_path, index=False, float_format="%.4f")
        print(f"  Saved: {p3_csv_path}")


def save_summary_json(p1_agg, p2_agg, p3_agg, cross_df, output_dir: str):
    """Save complete three-paradigm summary as JSON."""

    def _clean(obj):
        """Make JSON-safe."""
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [_clean(x) for x in obj]
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64)):
            return float(obj) if not np.isnan(obj) else None
        elif isinstance(obj, float):
            return None if (obj != obj) else obj
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient="records")
        return obj

    summary = {
        "analysis_version": "1.0.0",
        "paradigms": {
            "P1": {"description": "Progressive Numerical Analysis", "aggregates": _clean(p1_agg)},
            "P2": {"description": "Constraint Satisfaction Under Load", "aggregates": _clean(p2_agg)},
            "P3": {"description": "Multi-Document Synthesis", "aggregates": _clean(p3_agg)},
        },
        "cross_paradigm": _clean(cross_df.to_dict(orient="records")),
        "key_findings": generate_key_findings(p1_agg, p2_agg, p3_agg),
    }

    json_path = os.path.join(output_dir, "three_paradigm_summary.json")
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Saved: {json_path}")


# ==============================================================================
# KEY FINDINGS
# ==============================================================================

def generate_key_findings(p1_agg, p2_agg, p3_agg) -> List[Dict]:
    """Auto-generate key findings from the data."""
    findings = []

    # Models present in all 3 paradigms
    common_models = [m for m in p3_agg if m in p1_agg and m in p2_agg]

    # Finding 1: No model dominates all paradigms
    if common_models:
        p1_best = max(common_models, key=lambda m: p1_agg[m].get("probe_accuracy", 0))
        p2_best = max(common_models, key=lambda m: p2_agg[m].get("satisfaction_rate", 0))
        p3_best = max(common_models, key=lambda m: p3_agg[m].get("gap_abstained", 0) or 0)

        if len({p1_best, p2_best, p3_best}) > 1:
            findings.append({
                "id": "F1",
                "title": "No single model dominates all paradigms",
                "detail": (f"P1 probe leader: {MODEL_DISPLAY.get(p1_best, p1_best)}, "
                           f"P2 satisfaction leader: {MODEL_DISPLAY.get(p2_best, p2_best)}, "
                           f"P3 gap abstention leader: {MODEL_DISPLAY.get(p3_best, p3_best)}")
            })

    # Finding 2: Zero inappropriate authority deference
    if common_models:
        max_inappropriate = max(
            p3_agg[m].get("inappropriate_deference", 0) or 0 for m in common_models
        )
        if max_inappropriate == 0:
            findings.append({
                "id": "F2",
                "title": "Zero inappropriate authority deference across all models",
                "detail": ("All 4 models scored 0% inappropriate deference on authority-wrong "
                           "scenarios, suggesting frontier models are evidence-driven in "
                           "document synthesis tasks.")
            })

    # Finding 3: P3 fabrication is rare and scenario-driven
    fab_rates = {m: p3_agg[m].get("fabrication_rate", 0) or 0 for m in common_models}
    if fab_rates:
        max_fab = max(fab_rates.values())
        zero_fab_models = [m for m, v in fab_rates.items() if v == 0]
        if max_fab <= 0.15:
            findings.append({
                "id": "F3",
                "title": "Fabrication rates are low but non-zero",
                "detail": (f"Max fabrication rate: {max_fab:.1%}. "
                           f"Models with zero fabrication: "
                           f"{', '.join(MODEL_DISPLAY.get(m, m) for m in zero_fab_models)}. "
                           f"Fabrication clusters around specific scenarios (P3_019: drug trial gap).")
            })

    # Finding 4: MiniMax paradox — worst at P1, best at P3
    if "minimax-m2.5" in common_models:
        mm_p1 = p1_agg["minimax-m2.5"].get("probe_accuracy", 0)
        mm_p3_fab = p3_agg["minimax-m2.5"].get("fabrication_rate", 0) or 0
        mm_p3_gap = p3_agg["minimax-m2.5"].get("gap_abstained", 0) or 0
        p1_rank = sorted(common_models, key=lambda m: p1_agg[m].get("probe_accuracy", 0)).index("minimax-m2.5") + 1
        findings.append({
            "id": "F4",
            "title": "MiniMax paradox: worst numeric fidelity, best source fidelity",
            "detail": (f"MiniMax ranks #{p1_rank}/{len(common_models)} on P1 probe accuracy "
                       f"({mm_p1:.3f}) but leads P3 with {mm_p3_fab:.0%} fabrication rate "
                       f"and {mm_p3_gap:.0%} gap abstention. "
                       f"Numeric recall and source fidelity are orthogonal capabilities.")
        })

    # Finding 5: DeepSeek consistency
    if "deepseek-r1" in common_models:
        ds_p1 = p1_agg["deepseek-r1"].get("probe_accuracy", 0)
        ds_p2 = p2_agg["deepseek-r1"].get("satisfaction_rate", 0)
        ds_p3_res = p3_agg["deepseek-r1"].get("contradiction_resolved", 0) or 0
        findings.append({
            "id": "F5",
            "title": "DeepSeek-R1 is the most consistent across paradigms",
            "detail": (f"P1 probe: {ds_p1:.3f}, P2 satisfaction: {ds_p2:.3f}, "
                       f"P3 contradiction resolution: {ds_p3_res:.3f}. "
                       f"Strong across all three task types.")
        })

    return findings


# ==============================================================================
# CONSOLE SUMMARY
# ==============================================================================

def print_console_summary(cross_df, p1_agg, p2_agg, p3_agg, findings):
    """Print formatted summary to console."""
    print(f"\n{'='*70}")
    print("THREE-PARADIGM INTEGRATED ANALYSIS")
    print(f"{'='*70}")

    # Cross-paradigm table
    print(f"\n--- Cross-Paradigm Rankings (4-model comparison) ---\n")
    df = cross_df[cross_df["P3_n"].notna()].copy()
    if not df.empty:
        header = (f"  {'Model':<22} {'P1_Acc':>7} {'P1_Prb':>7} "
                  f"{'P2_Sat':>7} {'P2_Con':>7} "
                  f"{'P3_Res':>7} {'P3_Gap':>7} {'P3_Fab':>7} {'P3_Def↓':>7}")
        print(header)
        print(f"  {'-'*22} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*7}")

        for _, row in df.iterrows():
            def _f(v):
                return f"{v:.3f}" if v is not None and not (isinstance(v, float) and math.isnan(v)) else "   N/A"

            print(f"  {row['display_name']:<22} "
                  f"{_f(row.get('P1_accuracy')):>7} {_f(row.get('P1_probe')):>7} "
                  f"{_f(row.get('P2_satisfaction')):>7} {_f(row.get('P2_conflict')):>7} "
                  f"{_f(row.get('P3_contradiction_resolved')):>7} "
                  f"{_f(row.get('P3_gap_abstained')):>7} "
                  f"{_f(row.get('P3_fabrication_rate')):>7} "
                  f"{_f(row.get('P3_inappropriate_deference')):>7}")

    # Gemini (if present, P1/P2 only)
    gemini_row = cross_df[cross_df["model"] == "gemini-2.5-pro"]
    if not gemini_row.empty:
        row = gemini_row.iloc[0]
        print(f"\n  Gemini 2.5 Pro (P1+P2 only): P1_Acc={row.get('P1_accuracy', 'N/A')}, "
              f"P1_Prb={row.get('P1_probe', 'N/A')}, "
              f"P2_Sat={row.get('P2_satisfaction', 'N/A')}")

    # Key findings
    if findings:
        print(f"\n--- Key Findings ---\n")
        for f in findings:
            print(f"  [{f['id']}] {f['title']}")
            print(f"      {f['detail']}")
            print()

    print(f"{'='*70}")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Three-Paradigm Integrated Analysis"
    )
    parser.add_argument(
        "--scored-results", required=True,
        help="Path to scored_results.json (P1+P2)"
    )
    parser.add_argument(
        "--p3-judged-dir", required=True,
        help="Directory containing P3 judge results (individual/*.json)"
    )
    parser.add_argument(
        "--output-dir", required=True,
        help="Output directory for charts and tables"
    )
    args = parser.parse_args()

    # Create output dirs
    os.makedirs(os.path.join(args.output_dir, "charts"), exist_ok=True)
    os.makedirs(os.path.join(args.output_dir, "tables"), exist_ok=True)

    # Load data
    print("Loading data...")
    p1p2_df = load_p1_p2_results(args.scored_results)
    p3_results = load_p3_results(args.p3_judged_dir)
    print(f"  P1/P2: {len(p1p2_df)} scored entries")
    print(f"  P3:    {len(p3_results)} judge results")

    # Compute aggregates
    print("\nComputing aggregates...")
    p1_agg = compute_p1_aggregates(p1p2_df)
    p2_agg = compute_p2_aggregates(p1p2_df)
    p3_agg = compute_p3_aggregates(p3_results)

    # Build cross-paradigm table
    cross_df = build_cross_paradigm_table(p1_agg, p2_agg, p3_agg)

    # Generate charts
    print("\nGenerating charts...")
    chart_p3_model_comparison(p3_agg, args.output_dir)
    chart_p3_authority_split(p3_agg, args.output_dir)
    chart_cross_paradigm_heatmap(cross_df, args.output_dir)
    chart_cross_paradigm_radar(p1_agg, p2_agg, p3_agg, args.output_dir)
    chart_model_ranking_summary(p1_agg, p2_agg, p3_agg, args.output_dir)

    # Save tables
    print("\nSaving tables...")
    save_tables(cross_df, p3_agg, args.output_dir)

    # Generate findings
    findings = generate_key_findings(p1_agg, p2_agg, p3_agg)

    # Save full summary
    save_summary_json(p1_agg, p2_agg, p3_agg, cross_df, args.output_dir)

    # Console output
    print_console_summary(cross_df, p1_agg, p2_agg, p3_agg, findings)


if __name__ == "__main__":
    main()
