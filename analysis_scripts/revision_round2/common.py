"""Shared paths, model order, and labels for the round-2 revision analyses.

The scripts run unchanged from two layouts, detected automatically:
  * development tree:  <root>/TBench/revision_round2/scripts/   (root holds results/, p2_scenarios/, ...)
  * released artifact: <root>/analysis_scripts/revision_round2/ (root holds model_outputs/, scenarios/, ...)
Every script imports its locations from here; none builds a path from ROOT directly."""
import os, json
HERE = os.path.dirname(os.path.abspath(__file__))
_ART = os.path.abspath(os.path.join(HERE, '..', '..'))
_DEV = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
LAYOUT = 'artifact' if os.path.isdir(os.path.join(_ART, 'model_outputs')) else 'dev'
ROOT = _ART if LAYOUT == 'artifact' else _DEV
def _p(*parts): return os.path.join(ROOT, *parts)
def rel(path):
    """Root-relative form of a path, for writing into output files (keeps outputs free of local paths)."""
    try: return os.path.relpath(path, ROOT)
    except ValueError: return os.path.basename(path)
MODELS = ['claude-sonnet-4.5', 'deepseek-r1', 'gemini-2.5-pro', 'gpt-4o', 'minimax-m2.5']
# NOTE: the directory/key name 'deepseek-r1' is historical. DeepSeek's changelog shows that the
# 'deepseek-reasoner' endpoint used in Feb 2026 served DeepSeek-V3.2 (thinking mode).
LABELS = {'claude-sonnet-4.5': 'Sonnet 4.5', 'deepseek-r1': 'DeepSeek-V3.2', 'gemini-2.5-pro': 'Gemini 2.5 Pro',
          'gpt-4o': 'GPT-4o', 'minimax-m2.5': 'MiniMax M2.5'}
if LAYOUT == 'artifact':
    OUT = _p('analysis_outputs', 'revision_round2'); FIG = os.path.join(OUT, 'figures')
    SCORING_DIR = _p('scoring_scripts')                                   # p2_rescore.py (historical scorer, imported for helpers)
    RESULTS = _p('model_outputs', 'core'); RESULTS_REPL = _p('model_outputs', 'replication')
    P2_SCEN = _p('scenarios', 'p2_scenarios')
    FIXED = _p('scored_results', 'core', 'scored_full', 'scored_results_enhanced.json')   # post P1-fix (canonical in the artifact)
    ADJUDICATED = _p('scored_results', 'core', 'scored_full', 'scored_results_p1_adjudicated.json')
    FIXED_REPL = _p('scored_results', 'replication', 'scored_full', 'scored_results_fixed.json')
    JUDGED = _p('scored_results', 'core', 'p3_judged', 'individual')
    JUDGED_SUPP = _p('scored_results', 'supplementary', 'p3_judged', 'individual')
    JUDGED_R2 = _p('scored_results', 'supplementary_r2', 'p3_judged', 'individual')
    JUDGED_R2_CTRL = _p('scored_results', 'supplementary_r2_controls', 'p3_judged', 'individual')
    IRR_CSV = _p('analysis_outputs', 'gpt52_irr_results', 'irr_comparison.csv')
    SUMMARY = _p('analysis_outputs', 'analysis', 'three_paradigm_summary.json')
    P3_SUPP_SRC = _p('scenarios', 'p3_supplementary', 'p3_source_data.json'); P3_R2_SRC = _p('scenarios', 'p3_supplementary_r2', 'p3_source_data.json')
    AI_REVIEW = os.path.join(OUT, 'ai_review')
    PREFIX = V2 = RESCORE_CMP = ASSIGN = REPL = None                      # development-only inputs of superseded analyses
else:
    OUT = os.path.join(HERE, '..', 'outputs'); FIG = os.path.join(HERE, '..', 'figures')
    SCORING_DIR = ROOT
    RESULTS = _p('results'); RESULTS_REPL = _p('results_replication')
    P2_SCEN = _p('p2_scenarios')
    FIXED = _p('results', 'scored_full', 'scored_results_fixed.json')      # post P1-fix (canonical)
    ADJUDICATED = _p('results', 'scored_full', 'scored_results_p1_adjudicated.json')
    FIXED_REPL = _p('results_replication', 'scored_full', 'scored_results_fixed.json')
    JUDGED = _p('results', 'p3_judged', 'individual')
    JUDGED_SUPP = _p('results_supplementary', 'p3_judged', 'individual')
    JUDGED_R2 = _p('results_supplementary_r2', 'p3_judged', 'individual')
    JUDGED_R2_CTRL = _p('results_supplementary_r2_controls', 'p3_judged', 'individual')
    IRR_CSV = _p('gpt52_irr_results', 'irr_comparison.csv')
    SUMMARY = _p('analysis', 'three_paradigm_summary.json')
    P3_SUPP_SRC = _p('p3_supplementary', 'p3_source_data.json'); P3_R2_SRC = _p('p3_supplementary_r2', 'p3_source_data.json')
    AI_REVIEW = _p('TBench', '_not_for_submission', 'revision_round2_audit_20260917')
    PREFIX = _p('results', 'scored_full', 'scored_results_enhanced.json')  # pre P1-fix (replication baseline)
    V2 = _p('results', 'scored_full', 'scored_results.json')               # intermediate P2 parser
    RESCORE_CMP = _p('p2_rescore_results', 'p2_rescore_comparison.json')
    ASSIGN = _p('p2_parser_analysis', 'p2_enhanced_assignments.json')
    REPL = _p('results_replication', 'scored_full', 'scored_results_enhanced.json')
def load(p):
    with open(p) as f: return json.load(f)
def save(name, obj, md=None):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name + '.json'), 'w') as f: json.dump(obj, f, indent=2)
    if md is not None:
        with open(os.path.join(OUT, name + '.md'), 'w') as f: f.write(md)
    print('wrote', os.path.join(OUT, name + '.json'))
def ranks_desc(vals):
    order = sorted(range(len(vals)), key=lambda i: -vals[i]); r = [0] * len(vals); i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and abs(vals[order[j + 1]] - vals[order[i]]) < 1e-12: j += 1
        for k in range(i, j + 1): r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r
