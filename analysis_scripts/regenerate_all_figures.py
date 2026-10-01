#!/usr/bin/env python3
"""
regenerate_all_figures.py — Generate all 6 updated paper figures.

Figures:
  1. p1_decay_curves.png             Per-turn P1 accuracy + probe checkpoints
  2. retrieval_failure_profiles.png   Retrieval failure rate at each checkpoint
  3. p1_correction_propagation.png    T19 identification vs T20 propagation
  4. p2_decay_curves.png              P2 satisfaction at checkpoints (enhanced parser)
  5. cross_paradigm_radar.png         Cross-paradigm model profiles
  6. cross_paradigm_heatmap.png       Cross-paradigm performance heatmap

NOT regenerated (unaffected by Gemini fix):
  - p3_authority_split.png            Keep from previous version

Required input files:
  --scored-results   scored_results_enhanced.json   (P1 per-turn accuracy)
  --three-paradigm   three_paradigm_summary.json    (cross-paradigm metrics)
  --analysis-3b      analysis_3b_retrieval_vs_computation.json
  --p2-rescore       p2_rescore_comparison.json     (P2 per-turn data)
  --output-dir       Directory for output figures

Usage:
  python regenerate_all_figures.py \\
    --scored-results ./results/scored_full/scored_results_enhanced.json \\
    --three-paradigm ./analysis/three_paradigm_summary.json \\
    --analysis-3b    ./analysis/analysis_3b_retrieval_vs_computation.json \\
    --p2-rescore     ./p2_rescore_results/p2_rescore_comparison.json \\
    --output-dir     ./figures
"""

import os
import sys
import json
import argparse
from collections import defaultdict

try:
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    import matplotlib.colors as mcolors
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install numpy matplotlib")
    sys.exit(1)


# ==============================================================================
# CONFIGURATION
# ==============================================================================

MODEL_IDS = [
    "claude-sonnet-4.5",
    "deepseek-r1",
    "gemini-2.5-pro",
    "gpt-4o",
    "minimax-m2.5",
]

MODEL_DISPLAY = {
    "claude-sonnet-4.5": "Sonnet 4.5",
    "deepseek-r1": "DeepSeek-R1",
    "gemini-2.5-pro": "Gemini 2.5 Pro",
    "gpt-4o": "GPT-4o",
    "minimax-m2.5": "MiniMax M2.5",
}

MODEL_COLORS = {
    "claude-sonnet-4.5": "#ff7f0e",   # Orange
    "deepseek-r1": "#2ca02c",         # Green
    "gemini-2.5-pro": "#d62728",      # Red
    "gpt-4o": "#1f77b4",              # Blue
    "minimax-m2.5": "#9467bd",        # Purple
}

MODEL_MARKERS = {
    "claude-sonnet-4.5": "^",
    "deepseek-r1": "o",
    "gemini-2.5-pro": "D",
    "gpt-4o": "s",
    "minimax-m2.5": "v",
}

PROBE_TURNS = [5, 10, 15, 20]
P2_CHECKPOINTS = ["T6", "T11", "T17", "T20"]
P2_CHECKPOINT_X = [6, 11, 17, 20]
DPI = 300


def load_json(path):
    with open(path) as f:
        return json.load(f)


# ==============================================================================
# P1 DATA EXTRACTION (from scored_results_enhanced.json)
# ==============================================================================

def extract_p1_per_turn(scored_results):
    """
    Compute per-turn P1 accuracy from scored_results_enhanced.json.
    Returns: {model: {turn_number: accuracy}} for turns 1-20.
    """
    # Handle both list and dict-wrapped formats
    if isinstance(scored_results, dict):
        if "results" in scored_results:
            scored_results = scored_results["results"]
        else:
            scored_results = list(scored_results.values())

    # Filter to P1 entries
    p1_entries = [e for e in scored_results
                  if e.get("scenario_id", "").startswith("P1")]

    # Accumulate scores per (model, turn)
    model_turn_scores = defaultdict(lambda: defaultdict(list))

    for entry in p1_entries:
        model = entry["model"]
        for turn in entry.get("turns", []):
            t_num = turn.get("turn_number")
            is_correct = turn.get("is_correct")
            if t_num is not None and is_correct is not None:
                model_turn_scores[model][t_num].append(
                    1 if is_correct else 0
                )

    # Compute mean accuracy per (model, turn)
    per_turn = {}
    for model in MODEL_IDS:
        per_turn[model] = {}
        for t in range(1, 21):
            scores = model_turn_scores[model].get(t, [])
            per_turn[model][t] = (
                sum(scores) / len(scores) if scores else None
            )
    return per_turn


# ==============================================================================
# FIGURE 1: P1 DECAY CURVES
# ==============================================================================

def fig_p1_decay(per_turn, output_dir):
    """
    Two-panel figure:
      Left:  per-turn accuracy across all 20 turns, correction phase shaded.
      Right: probe accuracy at checkpoint turns T5, T10, T15, T20.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    turns = list(range(1, 21))

    # --- Left panel: per-turn accuracy ---
    for model in MODEL_IDS:
        accs = [per_turn[model].get(t) for t in turns]
        valid = [(t, a) for t, a in zip(turns, accs) if a is not None]
        if valid:
            ts, vals = zip(*valid)
            ax1.plot(ts, vals, "-", linewidth=1.5, alpha=0.75,
                     color=MODEL_COLORS[model], label=MODEL_DISPLAY[model])

    ax1.axvspan(18.5, 20.5, alpha=0.10, color="red", label="Correction phase")
    ax1.set_xlabel("Turn", fontsize=12)
    ax1.set_ylabel("Accuracy", fontsize=12)
    ax1.set_title("Per-Turn Accuracy", fontweight="bold", fontsize=13)
    ax1.set_xticks([1, 5, 10, 15, 20])
    ax1.set_ylim(-0.05, 1.08)
    ax1.legend(fontsize=8, loc="lower left")
    ax1.grid(True, alpha=0.3)

    # --- Right panel: probe accuracy at checkpoints ---
    for model in MODEL_IDS:
        probe_accs = [per_turn[model].get(t) for t in PROBE_TURNS]
        valid = [(t, a) for t, a in zip(PROBE_TURNS, probe_accs)
                 if a is not None]
        if valid:
            ts, vals = zip(*valid)
            ax2.plot(ts, vals, "o-", linewidth=2.5, markersize=8,
                     color=MODEL_COLORS[model],
                     marker=MODEL_MARKERS[model],
                     label=MODEL_DISPLAY[model])

    ax2.set_xlabel("Probe Checkpoint", fontsize=12)
    ax2.set_ylabel("Probe Accuracy", fontsize=12)
    ax2.set_title("Probe Accuracy at Checkpoints", fontweight="bold",
                  fontsize=13)
    ax2.set_xticks(PROBE_TURNS)
    ax2.set_xticklabels(["T5", "T10", "T15", "T20"])
    ax2.set_ylim(-0.05, 1.08)
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)

    fig.suptitle("Paradigm 1: Context Fidelity Decay",
                 fontweight="bold", fontsize=14, y=1.02)
    fig.tight_layout()
    path = os.path.join(output_dir, "p1_decay_curves.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ==============================================================================
# FIGURE 2: RETRIEVAL FAILURE PROFILES
# ==============================================================================

def fig_retrieval_profiles(analysis_3b, output_dir):
    """
    Line chart of P(probe_fail | fresh_pass) at each checkpoint.
    Models grouped by failure profile (correction-only vs early retrieval).
    """
    fig, ax = plt.subplots(figsize=(8, 5.5))

    checkpoint_labels = ["T5", "T10", "T15", "T20"]
    checkpoint_keys = ["T4_vs_T5", "T9_vs_T10", "T14_vs_T15", "T19_vs_T20"]
    x = np.arange(len(checkpoint_labels))

    profiles = analysis_3b["failure_profiles"]
    paired = analysis_3b["paired_probe_analysis"]

    # Group by profile for visual ordering and color coding
    correction_only = [m for m in MODEL_IDS
                       if profiles[m]["profile"] == "correction_only"]
    early_retrieval = [m for m in MODEL_IDS
                       if profiles[m]["profile"] != "correction_only"]
    plot_order = correction_only + early_retrieval

    # Profile-based color palettes (blue = correction-only, red = early)
    blue_shades = ["#2166ac", "#67a9cf", "#4393c3"]
    red_shades = ["#b2182b", "#d6604d"]
    blue_idx, red_idx = 0, 0

    for model in plot_order:
        profile = profiles[model]["profile"]
        vals = [paired[model][k]["retrieval_failure_rate"]
                for k in checkpoint_keys]

        if profile == "correction_only":
            color = blue_shades[blue_idx % len(blue_shades)]
            linestyle = ["-", "--", "-."][blue_idx % 3]
            blue_idx += 1
        else:
            color = red_shades[red_idx % len(red_shades)]
            linestyle = ["-", "--"][red_idx % 2]
            red_idx += 1

        ax.plot(x, vals, color=color, marker=MODEL_MARKERS[model],
                linestyle=linestyle, linewidth=2, markersize=8,
                label=MODEL_DISPLAY[model], zorder=3)

    # Shade correction phase
    ax.axvspan(2.5, 3.5, alpha=0.08, color="gray", zorder=0)
    ax.text(3.0, 0.96, "Correction\nphase", ha="center", va="top",
            fontsize=8, color="gray", style="italic")

    # Profile annotations
    if correction_only:
        # Position near the correction-only cluster at T20
        co_t20 = [paired[m]["T19_vs_T20"]["retrieval_failure_rate"]
                  for m in correction_only]
        ax.annotate("Correction-only", xy=(3.05, max(co_t20) + 0.04),
                    fontsize=8, color="#2166ac", fontstyle="italic")
    if early_retrieval:
        er_t10 = [paired[m]["T9_vs_T10"]["retrieval_failure_rate"]
                  for m in early_retrieval]
        ax.annotate("Early retrieval", xy=(1.05, max(er_t10) + 0.04),
                    fontsize=8, color="#b2182b", fontstyle="italic")

    ax.set_xticks(x)
    ax.set_xticklabels(checkpoint_labels, fontsize=11)
    ax.set_xlabel("Probe Checkpoint", fontsize=12)
    ax.set_ylabel(
        "$P(\\mathrm{probe\\_fail} \\mid \\mathrm{fresh\\_pass})$",
        fontsize=12,
    )
    ax.set_ylim(-0.03, 1.02)
    ax.yaxis.set_major_formatter(
        mticker.PercentFormatter(xmax=1.0, decimals=0)
    )
    ax.set_title("Retrieval-Specific Failure Rate by Checkpoint",
                 fontweight="bold", fontsize=13)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    path = os.path.join(output_dir, "retrieval_failure_profiles.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ==============================================================================
# FIGURE 3: CORRECTION PROPAGATION
# ==============================================================================

def fig_correction_propagation(per_turn, output_dir):
    """
    Grouped bar chart: T19 (correction identified) vs T20 (correction applied).
    Sorted by T20 descending to highlight Gemini's new leadership.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    t19_vals = {m: per_turn[m].get(19) or 0 for m in MODEL_IDS}
    t20_vals = {m: per_turn[m].get(20) or 0 for m in MODEL_IDS}

    # Sort by T20 descending
    sorted_models = sorted(MODEL_IDS, key=lambda m: t20_vals[m], reverse=True)

    x = np.arange(len(sorted_models))
    bw = 0.35

    ax.bar(
        x - bw / 2,
        [t19_vals[m] for m in sorted_models],
        bw,
        label="T19: Correction Identified",
        color=[MODEL_COLORS[m] for m in sorted_models],
        alpha=0.4,
        edgecolor="white",
    )
    bars_t20 = ax.bar(
        x + bw / 2,
        [t20_vals[m] for m in sorted_models],
        bw,
        label="T20: Correction Propagated",
        color=[MODEL_COLORS[m] for m in sorted_models],
        alpha=0.9,
        edgecolor="white",
    )

    # Value labels on T20 bars
    for bar, model in zip(bars_t20, sorted_models):
        val = t20_vals[model]
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{val:.2f}",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    ax.set_xlabel("Model", fontsize=12)
    ax.set_ylabel("Accuracy", fontsize=12)
    ax.set_title(
        "Correction Propagation: Identification (T19) vs. Application (T20)",
        fontweight="bold",
        fontsize=13,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(
        [MODEL_DISPLAY[m] for m in sorted_models], fontsize=10
    )
    ax.set_ylim(0, 1.15)
    ax.legend(fontsize=10, loc="upper right")
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    path = os.path.join(output_dir, "p1_correction_propagation.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ==============================================================================
# FIGURE 4: P2 DECAY CURVES
# ==============================================================================

def _get_p2_turn_val(model_data, checkpoint):
    """Extract enhanced P2 per-turn value, falling back to original."""
    pt = model_data["per_turn"][checkpoint]
    if isinstance(pt, dict):
        return pt.get("enhanced", pt.get("original", 0))
    return pt  # might be a bare number


def fig_p2_decay(p2_rescore, output_dir):
    """
    Two-panel figure:
      Left:  line chart of satisfaction at each checkpoint.
      Right: grouped bars showing T6 (early), Average, T20 (final).
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # --- Left panel: line chart ---
    for model in MODEL_IDS:
        m_data = p2_rescore["comparison"][model]
        values = [_get_p2_turn_val(m_data, cp) for cp in P2_CHECKPOINTS]
        ax1.plot(
            P2_CHECKPOINT_X, values, "o-", linewidth=2.5, markersize=8,
            label=MODEL_DISPLAY[model], color=MODEL_COLORS[model], alpha=0.85,
        )

    # Conflict region shading
    ax1.axvspan(11.5, 16.5, alpha=0.08, color="red")
    ax1.axvline(x=14, color="red", linestyle="--", alpha=0.3, linewidth=1)
    ax1.text(14, 0.47, "Conflict\nintroduced", ha="center", fontsize=8,
             color="red", alpha=0.6)

    ax1.set_xlabel("Checkpoint Turn", fontsize=12)
    ax1.set_ylabel("Constraint Satisfaction Rate", fontsize=12)
    ax1.set_title("Satisfaction Decay Over Checkpoints",
                  fontweight="bold", fontsize=13)
    ax1.set_xticks(P2_CHECKPOINT_X)
    ax1.set_xticklabels(P2_CHECKPOINTS)
    ax1.set_ylim(0.45, 1.05)
    ax1.legend(fontsize=9, loc="lower left")
    ax1.grid(True, alpha=0.3)

    # --- Right panel: grouped bars ---
    bw = 0.15
    x = np.arange(len(MODEL_IDS))

    t6_vals = [_get_p2_turn_val(p2_rescore["comparison"][m], "T6")
               for m in MODEL_IDS]
    t20_vals = [_get_p2_turn_val(p2_rescore["comparison"][m], "T20")
                for m in MODEL_IDS]
    avg_vals = [p2_rescore["comparison"][m]["satisfaction_enhanced"]
                for m in MODEL_IDS]

    ax2.bar(x - bw, t6_vals, bw, label="T6 (early)",
            color=[MODEL_COLORS[m] for m in MODEL_IDS], alpha=0.7,
            edgecolor="white")
    ax2.bar(x, avg_vals, bw, label="Average",
            color=[MODEL_COLORS[m] for m in MODEL_IDS], alpha=0.9,
            edgecolor="white")
    ax2.bar(x + bw, t20_vals, bw, label="T20 (final)",
            color=[MODEL_COLORS[m] for m in MODEL_IDS], alpha=0.5,
            edgecolor="white")

    ax2.set_xlabel("Model", fontsize=12)
    ax2.set_ylabel("Satisfaction Rate", fontsize=12)
    ax2.set_title("Early vs. Average vs. Final",
                  fontweight="bold", fontsize=13)
    ax2.set_xticks(x)
    ax2.set_xticklabels(
        [MODEL_DISPLAY[m] for m in MODEL_IDS],
        rotation=20, ha="right", fontsize=9,
    )
    ax2.set_ylim(0.45, 1.05)
    ax2.legend(fontsize=9)
    ax2.grid(axis="y", alpha=0.3)

    fig.suptitle(
        "Paradigm 2: Constraint Satisfaction Under Load (Enhanced Parser)",
        fontweight="bold", fontsize=14, y=1.02,
    )
    fig.tight_layout()
    path = os.path.join(output_dir, "p2_decay_curves.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ==============================================================================
# FIGURE 5: CROSS-PARADIGM RADAR
# ==============================================================================

def fig_radar(tp_summary, output_dir):
    """Radar chart of cross-paradigm model profiles (all metrics higher = better)."""
    metrics = [
        "P1 Accuracy",
        "P1 Probe",
        "P2 Satisfaction",
        "P2 Conflict",
        "P3 Contr. Resolution",
        "P3 Anti-Fabrication",
        "P3 Gap Abstention",
    ]
    N = len(metrics)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))

    for entry in tp_summary["cross_paradigm"]:
        model = entry["model"]
        if model not in MODEL_COLORS:
            continue
        values = [
            entry["P1_accuracy"],
            entry["P1_probe"],
            entry["P2_satisfaction"],
            entry["P2_conflict"],
            entry["P3_contradiction_resolved"],
            1.0 - entry["P3_fabrication_rate"],  # invert
            entry["P3_gap_abstained"],
        ]
        values += values[:1]
        ax.plot(
            angles, values, "o-", linewidth=2, markersize=6,
            label=entry["display_name"], color=MODEL_COLORS[model],
            alpha=0.85,
        )
        ax.fill(angles, values, alpha=0.06, color=MODEL_COLORS[model])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, fontsize=10)
    ax.set_ylim(0, 1.05)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(
        ["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=8, color="gray"
    )
    ax.set_title(
        "Cross-Paradigm Model Profiles\n"
        "(All metrics normalized: higher = better)",
        fontweight="bold", fontsize=14, pad=20,
    )
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=10)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    path = os.path.join(output_dir, "cross_paradigm_radar.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ==============================================================================
# FIGURE 6: CROSS-PARADIGM HEATMAP
# ==============================================================================

def fig_heatmap(tp_summary, output_dir):
    """
    Heatmap of all metrics across models and paradigms.
    Green = good, red = concerning. Fabrication/deference rows use inverted colors.
    """
    metric_defs = [
        # (display_label,    json_key,                    inverted?)
        ("P1: Probe Accuracy",   "P1_probe",                  False),
        ("P2: Satisfaction",     "P2_satisfaction",            False),
        ("P2: Conflict Det.",    "P2_conflict",               False),
        ("P3: Contradiction Res.", "P3_contradiction_resolved", False),
        ("P3: Gap Abstention",   "P3_gap_abstained",          False),
        ("P3: Fabrication Rate", "P3_fabrication_rate",        True),
        ("P3: Inappropriate Def.", "P3_inappropriate_deference", True),
    ]

    # Build model lookup from cross_paradigm table
    model_data = {}
    for entry in tp_summary["cross_paradigm"]:
        model_data[entry["model"]] = entry

    n_metrics = len(metric_defs)
    n_models = len(MODEL_IDS)

    data = np.zeros((n_metrics, n_models))
    for j, (_, key, _) in enumerate(metric_defs):
        for i, m in enumerate(MODEL_IDS):
            data[j, i] = model_data.get(m, {}).get(key, 0.0) or 0.0

    fig, ax = plt.subplots(figsize=(14, 7))

    # Custom colormaps
    cmap_normal = mcolors.LinearSegmentedColormap.from_list(
        "rg", ["#d32f2f", "#ffeb3b", "#2e7d32"], N=256
    )
    cmap_inverted = mcolors.LinearSegmentedColormap.from_list(
        "gr", ["#2e7d32", "#ffeb3b", "#d32f2f"], N=256
    )

    inverted_rows = {j for j, (_, _, inv) in enumerate(metric_defs) if inv}

    cell_h, cell_w = 1.0, 1.0
    for i in range(n_metrics):
        cmap = cmap_inverted if i in inverted_rows else cmap_normal
        row = data[i]
        vmin, vmax = row.min(), row.max()
        if vmax == vmin:
            norms = [0.5] * n_models
        else:
            norms = [(v - vmin) / (vmax - vmin) for v in row]

        for j in range(n_models):
            color = cmap(norms[j])
            rect = plt.Rectangle(
                (j * cell_w, (n_metrics - 1 - i) * cell_h),
                cell_w, cell_h,
                facecolor=color, edgecolor="white", linewidth=2,
            )
            ax.add_patch(rect)

            # Text: white on dark, dark on light
            lum = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
            tc = "white" if lum < 0.5 else "#333333"

            val = data[i, j]
            label = f"{val:.3f}"
            if i in inverted_rows and val > 0:
                label += " \u2191"

            ax.text(
                j * cell_w + cell_w / 2,
                (n_metrics - 1 - i) * cell_h + cell_h / 2,
                label, ha="center", va="center",
                fontsize=11, fontweight="bold", color=tc,
            )

    # Paradigm separators
    for sep in [1, 3]:
        y = (n_metrics - sep) * cell_h
        ax.plot(
            [-0.02, n_models * cell_w + 0.02], [y, y],
            color="black", linewidth=2, clip_on=False,
        )

    # Paradigm labels
    paradigm_ranges = {"P1": (0, 1), "P2": (1, 3), "P3": (3, 7)}
    paradigm_colors = {"P1": "#e67e22", "P2": "#2980b9", "P3": "#27ae60"}
    for plabel, (start, end) in paradigm_ranges.items():
        y_center = (n_metrics - start - (end - start) / 2) * cell_h
        ax.text(
            n_models * cell_w + 0.3, y_center, plabel,
            ha="left", va="center", fontsize=14, fontweight="bold",
            color=paradigm_colors[plabel],
        )

    ax.set_xlim(-0.02, n_models * cell_w + 0.8)
    ax.set_ylim(-0.02, n_metrics * cell_h + 0.02)
    ax.set_aspect("equal")
    ax.axis("off")

    # Manual axis labels (since axis is off)
    for i, (name, _, _) in enumerate(metric_defs):
        ax.text(
            -0.15, (n_metrics - 1 - i) * cell_h + cell_h / 2,
            name, ha="right", va="center", fontsize=10,
        )
    for j, m in enumerate(MODEL_IDS):
        ax.text(
            j * cell_w + cell_w / 2, -0.15,
            MODEL_DISPLAY[m], ha="center", va="top",
            fontsize=11, rotation=30,
        )

    ax.set_title(
        "Cross-Paradigm Model Performance Heatmap",
        fontsize=14, fontweight="bold", pad=15,
    )

    sm = plt.cm.ScalarMappable(
        cmap=cmap_normal, norm=plt.Normalize(0, 1)
    )
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, fraction=0.02, pad=0.12, aspect=30)
    cbar.set_label(
        "Score (higher = better, except marked \u2191)", fontsize=10
    )

    fig.tight_layout()
    path = os.path.join(output_dir, "cross_paradigm_heatmap.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Regenerate all 6 updated paper figures"
    )
    parser.add_argument("--scored-results", required=True,
                        help="Path to scored_results_enhanced.json")
    parser.add_argument("--three-paradigm", required=True,
                        help="Path to three_paradigm_summary.json")
    parser.add_argument("--analysis-3b", required=True,
                        help="Path to analysis_3b_retrieval_vs_computation.json")
    parser.add_argument("--p2-rescore", required=True,
                        help="Path to p2_rescore_comparison.json")
    parser.add_argument("--output-dir", required=True,
                        help="Directory for output figures")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # --- Load data ---
    print("Loading data files...")
    scored = load_json(args.scored_results)
    tp = load_json(args.three_paradigm)
    a3b = load_json(args.analysis_3b)
    p2r = load_json(args.p2_rescore)

    print(f"Output directory: {args.output_dir}/\n")

    # --- Extract P1 per-turn data ---
    print("[0/6] Computing P1 per-turn accuracy from scored results...")
    per_turn = extract_p1_per_turn(scored)
    for model in MODEL_IDS:
        n_turns = sum(
            1 for t in range(1, 21)
            if per_turn[model].get(t) is not None
        )
        t20 = per_turn[model].get(20)
        t20_str = f"{t20:.3f}" if t20 is not None else "N/A"
        print(f"  {MODEL_DISPLAY[model]:20s}  {n_turns}/20 turns  "
              f"T20={t20_str}")

    # --- Generate figures ---
    print("\n[1/6] P1 decay curves...")
    fig_p1_decay(per_turn, args.output_dir)

    print("[2/6] Retrieval failure profiles...")
    fig_retrieval_profiles(a3b, args.output_dir)

    print("[3/6] Correction propagation...")
    fig_correction_propagation(per_turn, args.output_dir)

    print("[4/6] P2 decay curves...")
    fig_p2_decay(p2r, args.output_dir)

    print("[5/6] Cross-paradigm radar...")
    fig_radar(tp, args.output_dir)

    print("[6/6] Cross-paradigm heatmap...")
    fig_heatmap(tp, args.output_dir)

    print(f"\nDone. All 6 figures written to {args.output_dir}/")
    print("NOTE: p3_authority_split.png is unaffected — "
          "keep from previous version.")


if __name__ == "__main__":
    main()
