"""Every plan extraction that differs between the first release of the block-scoped extractor
(superseded/p2_plan_extractor_v31a.py) and revision b (p2_plan_extractor.py), over all 1,000 checkpoint
responses (800 core, 200 replication). Writes the before/after record and the text of the block now used,
so each change can be checked by reading it."""
import sys, glob, importlib.util, collections
from common import *
sys.path.insert(0, SCORING_DIR); import p2_rescore as R
import p2_plan_extractor as NEW
spec = importlib.util.spec_from_file_location('p2_plan_extractor_v31a', os.path.join(HERE, 'superseded', 'p2_plan_extractor_v31a.py')); OLD = importlib.util.module_from_spec(spec); spec.loader.exec_module(OLD)
scen = R.load_scenarios(P2_SCEN); ch = []; n = 0
for tag, rd in (('core', RESULTS), ('replication', RESULTS_REPL)):
    for f in sorted(glob.glob(os.path.join(rd, '*', 'P2_*.json'))):
        d = load(f); s = scen[d['scenario_id']]; dk = s.get('domain') or s.get('domain_key'); m = {'deepseek-v3.2': 'deepseek-r1'}.get(d['model'], d['model'])
        for t in d['turns']:
            tn = int(t['turn_number'])
            if not any(int(x['turn_number']) == tn and x.get('is_checkpoint') for x in s['turns']): continue
            n += 1; txt = t.get('response') or ''; o = OLD.extract_plan(txt, dk); w = NEW.extract_plan(txt, dk)
            if o['assignment'] != w['assignment'] or o['label'] != w['label'] or sorted(o['unassigned']) != sorted(w['unassigned']) or sorted(o['flags']) != sorted(w['flags']):
                L = NEW.stripped_lines(txt); blk = [l for l in L[w['span'][0]:w['span'][1] + 1] if l.strip()] if w['span'] else []
                ch.append({'batch': tag, 'model': m, 'scenario': d['scenario_id'], 'turn': tn, 'before': {'label': o['label'], 'n_assigned': len(o['assignment']), 'span': o['span']},
                           'after': {'label': w['label'], 'n_assigned': len(w['assignment']), 'span': w['span'], 'flags': w['flags'], 'unassigned': w['unassigned']}, 'block_now_used': blk})
md = f'# Plan extraction, revision b: {len(ch)} of {n} checkpoint extractions changed\n\nReview status: AI review (not human validation).\n\n| Batch | Model | Scenario | Turn | Before | After |\n|---|---|---|---|---|---|\n'
for c in ch: md += f"| {c['batch']} | {LABELS[c['model']]} | {c['scenario']} | {c['turn']} | {c['before']['label']} ({c['before']['n_assigned']}) | {c['after']['label']} ({c['after']['n_assigned']}) |\n"
for c in ch: md += f"\n## {c['batch']} / {LABELS[c['model']]} / {c['scenario']} / T{c['turn']}: {c['before']['label']} ({c['before']['n_assigned']}) -> {c['after']['label']} ({c['after']['n_assigned']})\n```\n" + '\n'.join(c['block_now_used']) + '\n```\n'
print(md[:md.index('\n## ')] if '\n## ' in md else md); save('plan_extraction_revision_b_changes', {'n_checkpoints': n, 'n_changed': len(ch), 'review_status': 'AI review (not human validation)', 'changes': ch}, md)
