#!/usr/bin/env python3
"""
Generate a grouped bar chart of failure rates (1 - score) by model and paradigm.
Replaces the radar chart (cross_paradigm_radar.png) per reviewer comment.

The radar chart compressed most discriminating information into a thin rim near 1.0.
This bar chart shows failure rates instead, making differences visually prominent.

Output: cross_paradigm_bar.png (and cross_paradigm_bar.pdf for LaTeX)
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# ── Data from paper (Table 4 / cross-paradigm summary) ──
models = [
    'Claude\nSonnet 4.5',
    'DeepSeek-R1',
    'Gemini\n2.5 Pro',
    'GPT-4o',
    'MiniMax\nM2.5',
]

# Raw scores (higher = better)
p1_probe  = [0.995, 0.995, 0.965, 0.955, 0.890]
p2_sat    = [0.832, 0.961, 0.782, 0.785, 0.862]
p3_abst   = [0.885, 0.875, 0.930, 0.875, 0.975]

# Convert to failure rates (higher = worse, more visible bars = more failure)
p1_fail = [1 - x for x in p1_probe]
p2_fail = [1 - x for x in p2_sat]
p3_fail = [1 - x for x in p3_abst]

# ── Plot ──
fig, ax = plt.subplots(figsize=(8, 4.5))

x = np.arange(len(models))
width = 0.25

bars1 = ax.bar(x - width, p1_fail, width, label='P1: Numeric error',
               color='#4878CF', edgecolor='white', linewidth=0.5)
bars2 = ax.bar(x,         p2_fail, width, label='P2: Constraint failure',
               color='#D65F5F', edgecolor='white', linewidth=0.5)
bars3 = ax.bar(x + width, p3_fail, width, label='P3: Abstention failure',
               color='#6ACC65', edgecolor='white', linewidth=0.5)

# Value labels on top of each bar
for bars in [bars1, bars2, bars3]:
    for bar in bars:
        height = bar.get_height()
        if height > 0.01:  # Only label visible bars
            ax.annotate(f'{height:.3f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3), textcoords='offset points',
                        ha='center', va='bottom', fontsize=7)

ax.set_ylabel('Failure rate (1 − score)', fontsize=11)
ax.set_xticks(x)
ax.set_xticklabels(models, fontsize=9)
ax.set_ylim(0, 0.30)  # Cap at 0.30 to keep bars readable
ax.legend(fontsize=9, loc='upper left')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.set_title('Cross-Paradigm Failure Rates by Model', fontsize=12, pad=10)

# Add a light grid for readability
ax.yaxis.grid(True, alpha=0.3, linestyle='--')
ax.set_axisbelow(True)

plt.tight_layout()
plt.savefig('cross_paradigm_bar.png', dpi=300, bbox_inches='tight')
plt.savefig('cross_paradigm_bar.pdf', bbox_inches='tight')
print("Saved: cross_paradigm_bar.png and cross_paradigm_bar.pdf")

# Print the data for verification
print("\nFailure rates:")
for i, m in enumerate(models):
    name = m.replace('\n', ' ')
    print(f"  {name}: P1={p1_fail[i]:.3f}, P2={p2_fail[i]:.3f}, P3={p3_fail[i]:.3f}")
