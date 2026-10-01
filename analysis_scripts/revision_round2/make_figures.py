"""Regenerate Figures 1 and 2 (R1 comment 1; R2 comments 7-8): serif fonts matching the body text,
colorblind-safe palette, legend above the right-hand panels, readable annotations on the heatmap."""
import numpy as np, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from common import *
names = {f.name for f in font_manager.fontManager.ttflist}
serif = 'Times New Roman' if 'Times New Roman' in names else ('STIXGeneral' if 'STIXGeneral' in names else 'DejaVu Serif')
plt.rcParams.update({'font.family': 'serif', 'font.serif': [serif], 'font.size': 9, 'axes.titlesize': 9, 'axes.labelsize': 9, 'legend.fontsize': 8, 'xtick.labelsize': 8.5, 'ytick.labelsize': 8.5, 'mathtext.fontset': 'stix', 'pdf.fonttype': 42})
COL = {'claude-sonnet-4.5': '#0072B2', 'deepseek-r1': '#E69F00', 'gemini-2.5-pro': '#009E73', 'gpt-4o': '#D55E00', 'minimax-m2.5': '#CC79A7'}
MK = {'claude-sonnet-4.5': 'o', 'deepseek-r1': 's', 'gemini-2.5-pro': '^', 'gpt-4o': 'D', 'minimax-m2.5': 'v'}
rep = load(os.path.join(OUT, 'p2_v3_core.json'))['A_feasible']
xp = load(os.path.join(OUT, 'cross_paradigm_v3.json'))['point']   # run cross_paradigm_v3.py first
P1 = {m: xp[m]['P1'] for m in MODELS}; P3 = {m: xp[m]['P3'] for m in MODELS}; P2V = {m: xp[m]['P2_valid'] for m in MODELS}
os.makedirs(FIG, exist_ok=True); x = np.arange(len(MODELS)); w = 0.26; turns = [6, 11, 17, 20]
# Figure 1
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.9), gridspec_kw={'width_ratios': [1.15, 1]})
for m in MODELS:
    ax1.plot(turns, [rep[m][f'T{t}']['sat_v3'][0] for t in turns], marker=MK[m], color=COL[m], lw=1.6, ms=5, label=LABELS[m])
ax1.axvspan(11.5, 15.5, color='0.92', zorder=0); ax1.axvline(15, color='0.4', ls=':', lw=1); ax1.text(15.1, 0.52, 'requirement\nadded (T15)', fontsize=7.5, color='0.3', va='bottom')
ax1.set_xticks(turns); ax1.set_xticklabels(['6', '11', '17\n(feasible)', '20\n(feasible)']); ax1.set_xlabel('Checkpoint turn'); ax1.set_ylabel('Satisfaction of effective requirements'); ax1.set_ylim(0.5, 1.02); ax1.grid(alpha=0.3); ax1.legend(loc='lower center', bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False, handlelength=2.0, columnspacing=1.0, borderaxespad=0.2, fontsize=7.5)
ax1.set_title('(a) Fractional satisfaction, feasible checkpoints', loc='left', fontsize=9, pad=28)
vals = {'T6': [rep[m]['T6']['valid_complete'][0] for m in MODELS], 'T11': [rep[m]['T11']['valid_complete'][0] for m in MODELS], 'Post-revision (feasible)': [P2V[m] for m in MODELS]}
shades = {'T6': '#9ecae1', 'T11': '#4292c6', 'Post-revision (feasible)': '#08519c'}
for i, (k, v) in enumerate(vals.items()): ax2.bar(x + (i - 1) * w, v, w, color=shades[k], edgecolor='black', lw=0.4, label=k)
ax2.set_xticks(x); ax2.set_xticklabels([LABELS[m] for m in MODELS], rotation=25, ha='right'); ax2.set_ylim(0, 1.02); ax2.set_ylabel('Complete valid plan rate'); ax2.grid(axis='y', alpha=0.3)
ax2.legend(loc='lower center', bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False, borderaxespad=0.2); ax2.set_title('(b) Complete valid plans', loc='left', fontsize=9, pad=28)
fig.tight_layout(w_pad=1.5)
for ext in ('pdf', 'png'): fig.savefig(os.path.join(FIG, f'p2_decay_curves.{ext}'), dpi=300, bbox_inches='tight')
plt.close(fig)
# Figure 2
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.6), gridspec_kw={'width_ratios': [1.05, 1]})
rows = [('P1 phase-end accuracy', P1), ('P2 valid plans (feasible)', P2V), ('P3 gap abstention', P3)]
M = np.array([[d[m] for m in MODELS] for _, d in rows]); im = ax1.imshow(M, cmap='Blues', vmin=0.0, vmax=1.0, aspect='auto')
for i in range(M.shape[0]):
    for j in range(M.shape[1]): ax1.text(j, i, f'{M[i, j]:.2f}', ha='center', va='center', fontsize=8.5, color='white' if M[i, j] > 0.6 else 'black')
ax1.set_xticks(range(len(MODELS))); ax1.set_xticklabels([LABELS[m] for m in MODELS], rotation=25, ha='right'); ax1.set_yticks(range(len(rows))); ax1.set_yticklabels([r[0] for r in rows])
cb = fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.03); cb.set_label('Score', fontsize=8); cb.ax.tick_params(labelsize=7.5); ax1.set_title('(a) Primary metric by paradigm', loc='left', fontsize=9)
fr = {'P1 numeric error': [1 - P1[m] for m in MODELS], 'P2 no valid plan (feasible)': [1 - P2V[m] for m in MODELS], 'P3 abstention failure': [1 - P3[m] for m in MODELS]}
fc = {'P1 numeric error': '#fdae6b', 'P2 no valid plan (feasible)': '#e6550d', 'P3 abstention failure': '#7f2704'}
for i, (k, v) in enumerate(fr.items()): ax2.bar(x + (i - 1) * w, v, w, color=fc[k], edgecolor='black', lw=0.4, label=k)
ax2.set_xticks(x); ax2.set_xticklabels([LABELS[m] for m in MODELS], rotation=25, ha='right'); ax2.set_ylabel('Failure rate (1 $-$ score)'); ax2.set_ylim(0, 1.0); ax2.grid(axis='y', alpha=0.3)
ax2.legend(loc='lower center', bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False, borderaxespad=0.2, fontsize=7.5); ax2.set_title('(b) Failure rates', loc='left', fontsize=9, pad=16)
fig.tight_layout(w_pad=1.5)
for ext in ('pdf', 'png'): fig.savefig(os.path.join(FIG, f'cross_paradigm_figure.{ext}'), dpi=300, bbox_inches='tight')
print('figures written to', FIG, 'font:', serif)
