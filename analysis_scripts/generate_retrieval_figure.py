#!/usr/bin/env python3
"""
Generate Figure: Retrieval-Specific Failure Profiles

Plots P(probe_fail | fresh_pass) at each checkpoint turn (T5, T10, T15, T20)
for all five models. Data sourced from analysis_3b_retrieval_vs_computation.json.

Output: retrieval_failure_profiles.png (place in same directory as .tex file)

Usage:
    python generate_retrieval_figure.py

Dependencies: matplotlib (pip install matplotlib)
"""

import json
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# --- Data from analysis_3b_retrieval_vs_computation.json ---
# P(probe_fail | fresh_pass) at each checkpoint
data = {
    "Sonnet 4.5":     [0.000, 0.250, 0.045, 0.880],
    "GPT-4o":         [0.000, 0.022, 0.088, 0.382],
    "DeepSeek-R1":    [0.000, 0.070, 0.047, 0.354],
    "Gemini 2.5 Pro": [0.000, 0.000, 0.520, 0.174],
    "MiniMax M2.5":   [0.000, 0.808, 0.389, 0.868],
}

checkpoints = ["T5", "T10", "T15", "T20"]
x = np.arange(len(checkpoints))

# --- Styling ---
# Group by failure profile with distinct colors
colors = {
    "DeepSeek-R1":    "#2166ac",   # Blue - correction-only
    "GPT-4o":         "#67a9cf",   # Light blue - correction-only
    "Gemini 2.5 Pro": "#f4a582",   # Orange - late retrieval
    "Sonnet 4.5":     "#b2182b",   # Red - early retrieval
    "MiniMax M2.5":   "#d6604d",   # Light red - early retrieval
}

markers = {
    "DeepSeek-R1":    "o",
    "GPT-4o":         "s",
    "Gemini 2.5 Pro": "D",
    "Sonnet 4.5":     "^",
    "MiniMax M2.5":   "v",
}

linestyles = {
    "DeepSeek-R1":    "-",
    "GPT-4o":         "--",
    "Gemini 2.5 Pro": "-",
    "Sonnet 4.5":     "-",
    "MiniMax M2.5":   "--",
}

# Plot order: group by profile
plot_order = ["DeepSeek-R1", "GPT-4o", "Gemini 2.5 Pro", "Sonnet 4.5", "MiniMax M2.5"]

fig, ax = plt.subplots(figsize=(8, 5))

for model in plot_order:
    vals = data[model]
    ax.plot(
        x, vals,
        color=colors[model],
        marker=markers[model],
        linestyle=linestyles[model],
        linewidth=2,
        markersize=8,
        label=model,
        zorder=3,
    )

# Shade the correction phase
ax.axvspan(2.5, 3.5, alpha=0.08, color="gray", zorder=0)
ax.text(3.0, 0.95, "Correction\nphase", ha="center", va="top", fontsize=8,
        color="gray", style="italic")

# Formatting
ax.set_xticks(x)
ax.set_xticklabels(checkpoints, fontsize=11)
ax.set_xlabel("Probe Checkpoint", fontsize=12)
ax.set_ylabel("$P(\\mathrm{probe\\_fail} \\mid \\mathrm{fresh\\_pass})$", fontsize=12)
ax.set_ylim(-0.03, 1.02)
ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0, decimals=0))
ax.set_title("Retrieval-Specific Failure Rate by Checkpoint", fontsize=13, fontweight="bold")

# Add profile annotations
ax.annotate(
    "Correction-only",
    xy=(3, 0.37), fontsize=8, color="#2166ac", fontstyle="italic",
    ha="left",
)
ax.annotate(
    "Late retrieval",
    xy=(2.05, 0.55), fontsize=8, color="#f4a582", fontstyle="italic",
    ha="left",
)
ax.annotate(
    "Early retrieval",
    xy=(1.05, 0.83), fontsize=8, color="#b2182b", fontstyle="italic",
    ha="left",
)

ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
ax.grid(axis="y", alpha=0.3)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

plt.tight_layout()
plt.savefig("retrieval_failure_profiles.png", dpi=300, bbox_inches="tight")
print("Saved: retrieval_failure_profiles.png")
plt.close()
