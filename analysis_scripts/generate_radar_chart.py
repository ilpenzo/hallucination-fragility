#!/usr/bin/env python3
"""
Regenerate cross_paradigm_radar.png with all 5 models (including Gemini 2.5 Pro)
and correct enhanced-parser P2 values.

Data sourced from: three_paradigm_summary.json, scored results, and P3 judged results.
All numbers verified against context_handoff_v9.md Table cross-paradigm (Table 10 in paper).

Usage:
    python generate_radar_chart.py

Dependencies: matplotlib, numpy (pip install matplotlib numpy)
Output: cross_paradigm_radar.png
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# --- Data from Table 10 (cross-paradigm summary) ---
models = ["Sonnet 4.5", "DeepSeek-R1", "GPT-4o", "Gemini 2.5 Pro", "MiniMax M2.5"]

# Metrics: all oriented so higher = better
# For fabrication rate, we invert (1 - fab_rate) to get "anti-fabrication"
metrics = [
    "P1 Probe",
    "P1 Accuracy",
    "P2 Satisfaction",
    "P2 Conflict",
    "P3 Contr. Resolution",
    "P3 Anti-Fabrication",
    "P3 Gap Abstention",
]

data = {
    "Sonnet 4.5":     [0.690, 0.801, 0.832, 1.000, 0.980, 1-0.050, 0.885],
    "DeepSeek-R1":    [0.870, 0.866, 0.961, 0.969, 1.000, 1-0.100, 0.875],
    "GPT-4o":         [0.870, 0.862, 0.785, 1.000, 0.973, 1-0.100, 0.875],
    "Gemini 2.5 Pro": [0.732, 0.835, 0.783, 0.956, 1.000, 1-0.000, 0.930],
    "MiniMax M2.5":   [0.485, 0.715, 0.862, 0.994, 1.000, 1-0.000, 0.975],
}

# --- Colors ---
colors = {
    "Sonnet 4.5":     "#e67e22",  # Orange
    "DeepSeek-R1":    "#27ae60",  # Green
    "GPT-4o":         "#2980b9",  # Blue
    "Gemini 2.5 Pro": "#8e44ad",  # Purple
    "MiniMax M2.5":   "#7f8c8d",  # Gray
}

# --- Radar chart ---
N = len(metrics)
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
angles += angles[:1]  # close the polygon

fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))

for model in models:
    values = data[model]
    values += values[:1]  # close the polygon
    ax.plot(angles, values, 'o-', linewidth=2, label=model, color=colors[model], markersize=5)
    ax.fill(angles, values, alpha=0.08, color=colors[model])

# Formatting
ax.set_xticks(angles[:-1])
ax.set_xticklabels(metrics, fontsize=10)
ax.set_ylim(0, 1.05)
ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=8, color="gray")
ax.set_title(
    "Cross-Paradigm Model Profiles\n(All metrics normalized: higher = better)",
    fontsize=14, fontweight="bold", pad=20
)
ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=10)
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("cross_paradigm_radar.png", dpi=300, bbox_inches="tight")
print("Saved: cross_paradigm_radar.png")
plt.close()
