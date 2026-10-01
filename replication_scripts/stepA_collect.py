#!/usr/bin/env python3
"""Step A collection (contemporary P3 supplement), one model per invocation.

Implements the frozen protocol (TBench/revision_round2/stepA_protocol.md): the 8 new scenarios (P3_029-P3_036) and the
8 re-collected missing-evidence comparison scenarios (P3_021-P3_028) are run in ONE session per model in alternating
order (new, control, new, control, ...), temperature 0, the runner's unchanged P3 turn construction and settings.
New scenarios are written to results_supplementary_r2/<model>/, controls to results_supplementary_r2_controls/<model>/.
Existing output files are never overwritten (resume only). A per-model manifest records order, times, and errors.
Usage: python stepA_collect.py --model gpt-4o [--mock] [--budget-limit 5]"""
import argparse, json, os, time, datetime
import conversation_runner as CR
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(); ap.add_argument('--model', required=True); ap.add_argument('--mock', action='store_true'); ap.add_argument('--budget-limit', type=float, default=5.0)
ap.add_argument('--out-new', default=os.path.join(HERE, 'results_supplementary_r2')); ap.add_argument('--out-controls', default=os.path.join(HERE, 'results_supplementary_r2_controls')); args = ap.parse_args()
new = {s['scenario_id']: s for s in json.load(open(os.path.join(HERE, 'p3_supplementary_r2', 'p3_source_data.json')))['scenarios']}
ctl = {s['scenario_id']: s for s in json.load(open(os.path.join(HERE, 'p3_supplementary', 'p3_source_data.json')))['scenarios']}
new_ids = [f'P3_{i:03d}' for i in range(29, 37)]; ctl_ids = [f'P3_{i:03d}' for i in range(21, 29)]
assert all(i in new for i in new_ids) and all(i in ctl for i in ctl_ids), 'scenario files do not contain the planned ids'
order = [x for pair in zip(new_ids, ctl_ids) for x in pair]
runner = CR.create_model('mock' if args.mock else args.model); tracker = CR.CostTracker(args.model)
man = {'model': args.model, 'mock': args.mock, 'started': datetime.datetime.now().isoformat(), 'order': order, 'events': []}
for sid in order:
    is_new = sid in new; out_dir = os.path.join(args.out_new if is_new else args.out_controls, args.model); os.makedirs(out_dir, exist_ok=True); out = os.path.join(out_dir, sid + '.json')
    if os.path.exists(out): man['events'].append({'scenario': sid, 'status': 'exists_skipped'}); continue
    if tracker.estimated_cost >= args.budget_limit: man['events'].append({'scenario': sid, 'status': 'budget_stop', 'cost': tracker.estimated_cost}); break
    t0 = time.time()
    try:
        res = CR.run_scenario(runner, new[sid] if is_new else ctl[sid], args.model, tracker, temperature=0.0, delay=1.0)
        res['stepA'] = {'batch': 'contemporary_2026_09', 'set': 'new' if is_new else 'control', 'collected': datetime.datetime.now().isoformat()}
        json.dump(res, open(out, 'w'), indent=2, default=CR.safe_json_serialize, ensure_ascii=False)
        man['events'].append({'scenario': sid, 'status': 'ok', 'seconds': round(time.time() - t0, 1), 'cost_so_far': round(tracker.estimated_cost, 4)})
    except Exception as e:
        man['events'].append({'scenario': sid, 'status': 'error', 'error': f'{type(e).__name__}: {str(e)[:300]}'})
    print(man['events'][-1], flush=True)
man['finished'] = datetime.datetime.now().isoformat(); man['estimated_cost_usd'] = round(tracker.estimated_cost, 4)
mdir = os.path.join(args.out_new, '_manifests'); os.makedirs(mdir, exist_ok=True)
json.dump(man, open(os.path.join(mdir, f"{args.model}{'_mock' if args.mock else ''}_{int(time.time())}.json"), 'w'), indent=1); print('done', args.model, 'estimated cost', man['estimated_cost_usd'])
