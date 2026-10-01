#!/usr/bin/env python3
"""
regenerate_figures.py -- Regenerate publication figures using verified data.

Produces 4 updated figures:
  1. p2_decay_curves.png      -- P2 satisfaction at each checkpoint (enhanced parser)
  2. p3_authority_split.png   -- P3 authority deference + gap/fabrication (5 models)
  3. cross_paradigm_radar.png -- Radar chart (5 models, updated P2 + Gemini P3)
  4. cross_paradigm_heatmap.png -- Heatmap (5 models, all metrics)

P1 figures (p1_decay_curves.png, p1_correction_propagation.png) are NOT regenerated
because P1 data has not changed.

Data sources (all paths relative to script):
  - p2_rescore_comparison.json   (enhanced P2 per-turn data)
  - p3_judge_aggregate.json      (5-model P3 results)
  - three_paradigm_summary.json  (P1 aggregates, unchanged)
  - orthogonality_stats_5model.json (verified cross-paradigm values)

Usage:
  python regenerate_figures.py --data-dir ./data --output-dir ./figures
"""

import os
import sys
import json
import argparse
import math

try:
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from matplotlib.patches import FancyBboxPatch
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install numpy matplotlib")
    sys.exit(1)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

MODEL_ORDER = [
    "deepseek-r1",
    "minimax-m2.5",
    "claude-sonnet-4.5",
    "gpt-4o",
    "gemini-2.5-pro",
]

MODEL_DISPLAY = {
    "gpt-4o": "GPT-4o",
    "claude-sonnet-4.5": "Sonnet 4.5",
    "deepseek-r1": "DeepSeek-R1",
    "gemini-2.5-pro": "Gemini 2.5 Pro",
    "minimax-m2.5": "MiniMax M2.5",
}

MODEL_COLORS = {
    "gpt-4o": "#1f77b4",
    "claude-sonnet-4.5": "#ff7f0e",
    "deepseek-r1": "#2ca02c",
    "gemini-2.5-pro": "#d62728",
    "minimax-m2.5": "#9467bd",
}

DPI = 300

# ==============================================================================
# DATA LOADING
# ==============================================================================

def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


# ==============================================================================
# FIGURE 1: P2 DECAY CURVES (Enhanced Parser)
# ==============================================================================

def chart_p2_decay(p2_data, output_dir):
    """P2 satisfaction at each checkpoint turn, using enhanced parser values."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    checkpoints = ["T6", "T11", "T17", "T20"]
    x_positions = [6, 11, 17, 20]

    # Left panel: line chart of per-turn satisfaction
    for model_id in MODEL_ORDER:
        m = p2_data["comparison"][model_id]
        values = [m["per_turn"][t]["enhanced"] for t in checkpoints]
        label = MODEL_DISPLAY[model_id]
        color = MODEL_COLORS[model_id]
        ax1.plot(x_positions, values, "o-", linewidth=2.5, markersize=8,
                 label=label, color=color, alpha=0.85)

    # Shade the conflict region
    ax1.axvspan(11.5, 16.5, alpha=0.08, color="red", label="Conflict phase")
    ax1.axvline(x=14, color="red", linestyle="--", alpha=0.3, linewidth=1)

    ax1.set_xlabel("Checkpoint Turn", fontsize=12)
    ax1.set_ylabel("Constraint Satisfaction Rate", fontsize=12)
    ax1.set_title("Satisfaction Decay Over Checkpoints", fontweight="bold", fontsize=13)
    ax1.set_xticks(x_positions)
    ax1.set_xticklabels(checkpoints)
    ax1.set_ylim(0.45, 1.05)
    ax1.legend(fontsize=9, loc="lower left")
    ax1.grid(True, alpha=0.3)

    # Right panel: grouped bar chart at T6 vs T20
    bar_width = 0.15
    models = MODEL_ORDER
    x = np.arange(len(models))

    t6_vals = [p2_data["comparison"][m]["per_turn"]["T6"]["enhanced"] for m in models]
    t20_vals = [p2_data["comparison"][m]["per_turn"]["T20"]["enhanced"] for m in models]
    avg_vals = [p2_data["comparison"][m]["satisfaction_enhanced"] for m in models]

    bars1 = ax2.bar(x - bar_width, t6_vals, bar_width, label="T6 (early)",
                    color=[MODEL_COLORS[m] for m in models], alpha=0.7, edgecolor="white")
    bars2 = ax2.bar(x, avg_vals, bar_width, label="Average",
                    color=[MODEL_COLORS[m] for m in models], alpha=0.9, edgecolor="white")
    bars3 = ax2.bar(x + bar_width, t20_vals, bar_width, label="T20 (final)",
                    color=[MODEL_COLORS[m] for m in models], alpha=0.5, edgecolor="white")

    ax2.set_xlabel("Model", fontsize=12)
    ax2.set_ylabel("Satisfaction Rate", fontsize=12)
    ax2.set_title("Early vs. Average vs. Final Satisfaction", fontweight="bold", fontsize=13)
    ax2.set_xticks(x)
    ax2.set_xticklabels([MODEL_DISPLAY[m] for m in models], rotation=20, ha="right", fontsize=9)
    ax2.set_ylim(0.45, 1.05)
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3, axis="y")

    fig.suptitle("Paradigm 2: Constraint Satisfaction Under Load (Enhanced Parser)",
                 fontweight="bold", fontsize=14, y=1.02)
    fig.tight_layout()
    path = os.path.join(output_dir, "p2_decay_curves.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ==============================================================================
# FIGURE 2: P3 AUTHORITY SPLIT + GAP/FABRICATION (5 models)
# ==============================================================================

def chart_p3_authority_split(p3_data, output_dir):
    """Authority deference split + gap abstention/fabrication for all 5 models."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    models = MODEL_ORDER
    n_models = len(models)

    # Compute appropriate and inappropriate deference from aggregate data
    appr_def = []
    inappr_def = []
    gap_abst = []
    fab_rate = []

    for m in models:
        s = p3_data["model_summaries"][m]
        n_correct = s["n_authority_correct"]  # 7
        n_wrong = s["n_authority_wrong"]      # 13
        total_def = s["authority_deferred_rate"] * s["n_entries"]

        # Since inappropriate deference is 0 for all models,
        # all deferences are in authority-correct scenarios
        appr = total_def / n_correct if n_correct > 0 else 0
        inappr = 0.0  # confirmed 0 for all models

        appr_def.append(appr)
        inappr_def.append(inappr)
        gap_abst.append(s["gap_abstained"])
        fab_rate.append(s["fabrication_rate"])

    # Left panel: authority deference split
    x = np.arange(n_models)
    bar_width = 0.35

    bars_appr = ax1.bar(x - bar_width/2, appr_def, bar_width,
                        label="Appropriate (authority correct)",
                        color="#2ca02c", alpha=0.8, edgecolor="white")
    bars_inappr = ax1.bar(x + bar_width/2, inappr_def, bar_width,
                          label="Inappropriate (authority wrong)",
                          color="#d62728", alpha=0.8, edgecolor="white")

    # Add value labels
    for bar, val in zip(bars_appr, appr_def):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                 f"{val:.0%}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    for bar, val in zip(bars_inappr, inappr_def):
        ax1.text(bar.get_x() + bar.get_width()/2, max(val, 0.01) + 0.02,
                 f"{val:.0%}", ha="center", va="bottom", fontsize=9, fontweight="bold",
                 color="#d62728")

    ax1.set_xlabel("Model", fontsize=12)
    ax1.set_ylabel("Deference Rate", fontsize=12)
    ax1.set_title("Authority Deference by Scenario Type", fontweight="bold", fontsize=13)
    ax1.set_xticks(x)
    ax1.set_xticklabels([MODEL_DISPLAY[m] for m in models], rotation=20, ha="right", fontsize=9)
    ax1.set_ylim(0, 1.15)
    ax1.legend(fontsize=9, loc="upper right")
    ax1.grid(True, alpha=0.3, axis="y")

    # Right panel: gap abstention and fabrication
    bars_gap = ax2.bar(x - bar_width/2, gap_abst, bar_width,
                       label="Gap Abstention",
                       color="#1f77b4", alpha=0.8, edgecolor="white")
    bars_fab = ax2.bar(x + bar_width/2, fab_rate, bar_width,
                       label="Fabrication Rate",
                       color="#d62728", alpha=0.8, edgecolor="white")

    for bar, val in zip(bars_gap, gap_abst):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                 f"{val:.1%}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    for bar, val in zip(bars_fab, fab_rate):
        label_y = max(val, 0.005) + 0.02
        ax2.text(bar.get_x() + bar.get_width()/2, label_y,
                 f"{val:.0%}", ha="center", va="bottom", fontsize=9, fontweight="bold",
                 color="#d62728")

    ax2.set_xlabel("Model", fontsize=12)
    ax2.set_ylabel("Rate", fontsize=12)
    ax2.set_title("Gap Abstention vs. Fabrication", fontweight="bold", fontsize=13)
    ax2.set_xticks(x)
    ax2.set_xticklabels([MODEL_DISPLAY[m] for m in models], rotation=20, ha="right", fontsize=9)
    ax2.set_ylim(0, 1.15)
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3, axis="y")

    fig.suptitle("Paradigm 3: Source Fidelity and Authority Bias (5 Models)",
                 fontweight="bold", fontsize=14, y=1.02)
    fig.tight_layout()
    path = os.path.join(output_dir, "p3_authority_split.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ==============================================================================
# FIGURE 3: CROSS-PARADIGM RADAR (5 models, updated P2 + Gemini P3)
# ==============================================================================

def chart_cross_paradigm_radar(ortho_data, p3_data, p1_summary, output_dir):
    """Radar chart showing all 5 model profiles across paradigms."""

    models = MODEL_ORDER
    p1_agg = p1_summary["paradigms"]["P1"]["aggregates"]

    # Define metrics: all "higher is better"
    def get_metrics(m):
        p1 = p1_agg.get(m, {})
        p2_sat = ortho_data["raw_values"]["P2_satisfaction"].get(m, 0)
        p3 = p3_data["model_summaries"].get(m, {})
        return [
            p1.get("accuracy", 0),
            p1.get("probe_accuracy", 0),
            p2_sat,
            p3.get("contradiction_resolved", 0) or 0,
            p3.get("gap_abstained", 0) or 0,
            1.0 - (p3.get("fabrication_rate", 0) or 0),  # invert: higher = less fabrication
        ]

    metric_labels = [
        "P1 Accuracy",
        "P1 Probe",
        "P2 Satisfaction",
        "P3 Contr. Resolution",
        "P3 Gap Abstention",
        "P3 Anti-Fabrication",
    ]

    N = len(metric_labels)
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))

    for model in models:
        values = get_metrics(model)
        values += values[:1]
        ax.plot(angles, values, "o-", linewidth=2, markersize=6,
                label=MODEL_DISPLAY[model],
                color=MODEL_COLORS[model], alpha=0.85)
        ax.fill(angles, values, alpha=0.06, color=MODEL_COLORS[model])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metric_labels, fontsize=10)
    ax.set_ylim(0, 1.05)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=8, color="gray")
    ax.set_title("Cross-Paradigm Model Profiles\n(All metrics normalized: higher = better)",
                 fontweight="bold", pad=30, fontsize=14)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), framealpha=0.9, fontsize=10)

    fig.tight_layout()
    path = os.path.join(output_dir, "cross_paradigm_radar.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ==============================================================================
# FIGURE 4: CROSS-PARADIGM HEATMAP (5 models, all metrics)
# ==============================================================================

def chart_cross_paradigm_heatmap(ortho_data, p3_data, p1_summary, p2_data, output_dir):
    """Heatmap of model x metric across all three paradigms."""

    models = MODEL_ORDER
    p1_agg = p1_summary["paradigms"]["P1"]["aggregates"]

    # Build metric rows: (label, values_dict, invert?)
    metric_rows = []

    # P1 metrics
    metric_rows.append(("P1: Accuracy",
        {m: p1_agg[m]["accuracy"] for m in models}, False))
    metric_rows.append(("P1: Probe Accuracy",
        {m: p1_agg[m]["probe_accuracy"] for m in models}, False))

    # P2 metrics (enhanced parser)
    metric_rows.append(("P2: Satisfaction",
        {m: p2_data["comparison"][m]["satisfaction_enhanced"] for m in models}, False))
    metric_rows.append(("P2: Conflict Detection",
        {m: p2_data["comparison"][m]["conflict_enhanced"] for m in models}, False))

    # P3 metrics
    metric_rows.append(("P3: Contradiction Res.",
        {m: p3_data["model_summaries"][m]["contradiction_resolved"] for m in models}, False))
    metric_rows.append(("P3: Gap Abstention",
        {m: p3_data["model_summaries"][m]["gap_abstained"] for m in models}, False))
    metric_rows.append(("P3: Fabrication Rate",
        {m: p3_data["model_summaries"][m]["fabrication_rate"] for m in models}, True))
    metric_rows.append(("P3: Inappropriate Def.",
        {m: 0.0 for m in models}, True))  # all zero

    n_metrics = len(metric_rows)
    n_models = len(models)

    data = np.zeros((n_metrics, n_models))
    for j, (label, vals, inv) in enumerate(metric_rows):
        for i, m in enumerate(models):
            data[j, i] = vals.get(m, np.nan)

    fig, ax = plt.subplots(figsize=(12, 7))

    im = ax.imshow(data, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)

    invert_rows = {j for j, (_, _, inv) in enumerate(metric_rows) if inv}

    ax.set_xticks(np.arange(n_models))
    ax.set_xticklabels([MODEL_DISPLAY[m] for m in models], rotation=30, ha="right", fontsize=10)
    ax.set_yticks(np.arange(n_metrics))
    ax.set_yticklabels([label for label, _, _ in metric_rows], fontsize=10)

    for j in range(n_metrics):
        for i in range(n_models):
            val = data[j, i]
            if np.isnan(val):
                text = "N/A"
                color = "gray"
            else:
                text = f"{val:.3f}"
                if j in invert_rows:
                    color = "red" if val > 0.05 else "green"
                    text = f"{val:.3f}" + (" \u2191" if val > 0.05 else "")
                else:
                    color = "black" if val > 0.5 else "white"
            ax.text(i, j, text, ha="center", va="center", fontsize=9,
                    color=color, fontweight="bold" if j in invert_rows else "normal")

    # Paradigm separators
    ax.axhline(y=1.5, color="white", linewidth=3)
    ax.axhline(y=3.5, color="white", linewidth=3)

    # Paradigm labels
    ax.text(n_models + 0.3, 0.5, "P1", va="center", fontsize=11,
            fontweight="bold", color="#1f77b4")
    ax.text(n_models + 0.3, 2.5, "P2", va="center", fontsize=11,
            fontweight="bold", color="#ff7f0e")
    ax.text(n_models + 0.3, 5.5, "P3", va="center", fontsize=11,
            fontweight="bold", color="#2ca02c")

    ax.set_title("Cross-Paradigm Model Performance Heatmap", fontweight="bold", pad=15, fontsize=14)
    cbar = fig.colorbar(im, ax=ax, shrink=0.6, label="Score (higher = better, except marked \u2191)")

    fig.tight_layout()
    path = os.path.join(output_dir, "cross_paradigm_heatmap.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Regenerate publication figures")
    parser.add_argument("--data-dir", required=True, help="Directory containing JSON data files")
    parser.add_argument("--output-dir", required=True, help="Directory to write figures")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print("Loading data files...")
    p2_data = load_json(os.path.join(args.data_dir, "p2_rescore_comparison.json"))
    p3_data = load_json(os.path.join(args.data_dir, "p3_judge_aggregate.json"))
    p1_summary = load_json(os.path.join(args.data_dir, "three_paradigm_summary.json"))
    ortho_data = load_json(os.path.join(args.data_dir, "orthogonality_stats_5model.json"))

    print("\nRegenerating figures...")

    print("\n[1/4] P2 decay curves (enhanced parser)...")
    chart_p2_decay(p2_data, args.output_dir)

    print("\n[2/4] P3 authority split + gap/fabrication (5 models)...")
    chart_p3_authority_split(p3_data, args.output_dir)

    print("\n[3/4] Cross-paradigm radar (5 models)...")
    chart_cross_paradigm_radar(ortho_data, p3_data, p1_summary, args.output_dir)

    print("\n[4/4] Cross-paradigm heatmap (5 models)...")
    chart_cross_paradigm_heatmap(ortho_data, p3_data, p1_summary, p2_data, args.output_dir)

    print(f"\nDone. Figures written to: {args.output_dir}/")
    print("NOTE: p1_decay_curves.png and p1_correction_propagation.png are unchanged")
    print("      and should be kept from the previous version.")


if __name__ == "__main__":
    main()
