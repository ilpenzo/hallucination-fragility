#!/usr/bin/env python3
"""
Regenerate cross_paradigm_heatmap.png with all 5 models (including Gemini 2.5 Pro)
and correct enhanced-parser P2 values.

All numbers verified against context_handoff_v9.md and source JSON files.

Usage:
    python generate_heatmap.py

Dependencies: matplotlib, numpy (pip install matplotlib numpy)
Output: cross_paradigm_heatmap.png
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# --- Data: 5 models, 9 metrics ---
models = ["Sonnet 4.5", "DeepSeek-R1", "GPT-4o", "Gemini 2.5 Pro", "MiniMax M2.5"]

metric_names = [
    "P1: Accuracy",
    "P1: Probe Accuracy",
    "P2: Satisfaction",
    "P2: Conflict Detection",
    "P3: Contradiction Res.",
    "P3: Gap Abstention",
    "P3: Fabrication Rate",
    "P3: Inappropriate Def.",
]

# Paradigm groupings for right-side labels
paradigm_labels = {
    0: "P1", 1: "P1",
    2: "P2", 3: "P2",
    4: "P3", 5: "P3", 6: "P3", 7: "P3",
}

# Data matrix (rows=metrics, cols=models)
# Order: Sonnet, DeepSeek, GPT-4o, Gemini, MiniMax
data = np.array([
    [0.801, 0.866, 0.862, 0.835, 0.715],  # P1 Accuracy
    [0.690, 0.870, 0.870, 0.732, 0.485],  # P1 Probe
    [0.832, 0.961, 0.785, 0.783, 0.862],  # P2 Satisfaction
    [1.000, 0.969, 1.000, 0.956, 0.994],  # P2 Conflict Detection
    [0.980, 1.000, 0.973, 1.000, 1.000],  # P3 Contradiction Res.
    [0.885, 0.875, 0.875, 0.930, 0.975],  # P3 Gap Abstention
    [0.050, 0.100, 0.100, 0.000, 0.000],  # P3 Fabrication Rate
    [0.000, 0.000, 0.000, 0.000, 0.000],  # P3 Inappropriate Def.
])

# Rows where LOWER is WORSE (inverted coloring: red = high value)
inverted_rows = {6, 7}  # Fabrication Rate, Inappropriate Deference

n_metrics, n_models = data.shape

fig, ax = plt.subplots(figsize=(14, 7))

# Create custom diverging colormap: red -> yellow -> green
cmap_normal = mcolors.LinearSegmentedColormap.from_list(
    "rg", ["#d32f2f", "#ffeb3b", "#2e7d32"], N=256
)
cmap_inverted = mcolors.LinearSegmentedColormap.from_list(
    "gr", ["#2e7d32", "#ffeb3b", "#d32f2f"], N=256
)

# Draw cells
cell_height = 1.0
cell_width = 1.0
for i in range(n_metrics):
    cmap = cmap_inverted if i in inverted_rows else cmap_normal
    row_vals = data[i]
    # Normalize within row for coloring
    vmin, vmax = row_vals.min(), row_vals.max()
    if vmax == vmin:
        # All same value - use middle color
        norms = [0.5] * n_models
    else:
        norms = [(v - vmin) / (vmax - vmin) for v in row_vals]

    for j in range(n_models):
        color = cmap(norms[j])
        rect = plt.Rectangle(
            (j * cell_width, (n_metrics - 1 - i) * cell_height),
            cell_width, cell_height,
            facecolor=color, edgecolor="white", linewidth=2
        )
        ax.add_patch(rect)

        # Text color: white on dark backgrounds, dark on light
        luminance = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
        text_color = "white" if luminance < 0.5 else "#333333"

        # Format value
        val = data[i, j]
        if i in inverted_rows and val > 0:
            label = f"{val:.3f} \u2191"  # up arrow = worse
        else:
            label = f"{val:.3f}"

        ax.text(
            j * cell_width + cell_width / 2,
            (n_metrics - 1 - i) * cell_height + cell_height / 2,
            label, ha="center", va="center",
            fontsize=11, fontweight="bold", color=text_color
        )

# Draw paradigm group separators
separator_positions = [2, 4]  # After P1 (row 1), after P2 (row 3)
for sep in separator_positions:
    y = (n_metrics - sep) * cell_height
    ax.plot([-0.02, n_models * cell_width + 0.02], [y, y],
            color="black", linewidth=2, clip_on=False)

# Paradigm labels on right side
paradigm_ranges = {"P1": (0, 2), "P2": (2, 4), "P3": (4, 8)}
for label, (start, end) in paradigm_ranges.items():
    y_center = (n_metrics - start - (end - start) / 2) * cell_height
    ax.text(
        n_models * cell_width + 0.3, y_center, label,
        ha="left", va="center", fontsize=14, fontweight="bold",
        color={"P1": "#e67e22", "P2": "#2980b9", "P3": "#27ae60"}[label]
    )

# Axis labels
ax.set_xlim(-0.02, n_models * cell_width + 0.8)
ax.set_ylim(-0.02, n_metrics * cell_height + 0.02)
ax.set_xticks([j * cell_width + cell_width / 2 for j in range(n_models)])
ax.set_xticklabels(models, fontsize=11, rotation=30, ha="right")
ax.set_yticks([(n_metrics - 1 - i) * cell_height + cell_height / 2 for i in range(n_metrics)])
ax.set_yticklabels(metric_names, fontsize=10)
ax.set_title("Cross-Paradigm Model Performance Heatmap", fontsize=14, fontweight="bold", pad=15)
ax.set_aspect("equal")
ax.axis("off")

# Redraw y-tick labels manually since axis is off
for i, name in enumerate(metric_names):
    ax.text(
        -0.15, (n_metrics - 1 - i) * cell_height + cell_height / 2,
        name, ha="right", va="center", fontsize=10
    )

# Redraw x-tick labels
for j, name in enumerate(models):
    ax.text(
        j * cell_width + cell_width / 2, -0.15,
        name, ha="center", va="top", fontsize=11, rotation=30
    )

# Colorbar
sm = plt.cm.ScalarMappable(cmap=cmap_normal, norm=plt.Normalize(0, 1))
sm.set_array([])
cbar = plt.colorbar(sm, ax=ax, fraction=0.02, pad=0.12, aspect=30)
cbar.set_label("Score (higher = better, except marked \u2191)", fontsize=10)

plt.tight_layout()
plt.savefig("cross_paradigm_heatmap.png", dpi=300, bbox_inches="tight")
print("Saved: cross_paradigm_heatmap.png")
plt.close()
