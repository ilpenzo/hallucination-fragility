"""Corrected P2 scoring (round-2 revision).

Fixes two defects found in the audit of 2026-09-17:
  1. The turn-12 replacement was never applied by the scorers: after T12 the generator replaces the slot of one
     fixed-assignment constraint (same id), but p2_rescore.score_checkpoint / ScorerP2 kept checking the original slot.
     Here the replacement is applied for every checkpoint at or after the modification turn.
  2. The T15 "trap" constraint was constructed to break the generator's reference plan, not to be unsatisfiable.
     Each checkpoint is therefore classified by exhaustive search (respecting the slot capacities stated in the task
     prompt) as a GENUINE conflict (no assignment satisfies every active constraint including the trap) or a
     SPURIOUS conflict (such an assignment exists).

Reported per checkpoint: satisfaction over non-trap constraints (comparable definition to the paper, corrected),
satisfaction over all active constraints (trap included; the appropriate target when the conflict is spurious),
whether the trap was satisfied, whether a conflict was flagged (existing keyword detector), capacity violations,
and the feasibility class.
"""
import copy, itertools, sys, os
from common import *
sys.path.insert(0, SCORING_DIR); import p2_rescore as R

def active_constraints(scenario, turn):
    """Active constraints at a checkpoint with the T12 replacement applied when applicable."""
    ids = turn.get('active_constraint_ids') or list(turn['ground_truth']['constraint_satisfaction'].keys())
    by = {c['id']: copy.deepcopy(c) for c in scenario['constraints']}
    mod = scenario.get('modification') or {}
    mod_turn = next((t['turn_number'] for t in scenario['turns'] if t.get('phase') == 'modification'), 12)
    if mod and int(turn['turn_number']) >= int(mod_turn):
        c = by.get(mod.get('original_constraint_id'))
        if c is not None and c['type'] == 'fixed_assignment':
            c['slot'] = mod['new_slot']
    return [by[i] for i in ids if i in by]

def domain_of(scenario):
    return copy.deepcopy(R.P2_DOMAINS[scenario.get('domain') or scenario.get('domain_key')])

def capacity_ok(assignment, dom):
    counts = {}
    for it, sl in assignment.items(): counts[sl] = counts.get(sl, 0) + 1
    return all(counts.get(s['id'], 0) <= s['capacity'] for s in dom['slots'])

def find_witness(scenario, constraints):
    """Exhaustive search for an assignment satisfying all constraints and the stated slot capacities."""
    dom = domain_of(scenario); items = [i['id'] for i in dom['items']]; slots = [s['id'] for s in dom['slots']]
    allowed = {it: set(slots) for it in items}
    for c in constraints:
        if c['type'] == 'fixed_assignment': allowed[c['item']] &= {c['slot']}
        elif c['type'] == 'exclusion': allowed[c['item']].discard(c['slot'])
    for placement in itertools.product(*(sorted(allowed[it]) for it in items)):
        a = dict(zip(items, placement))
        if not capacity_ok(a, dom): continue
        if all(R.check_constraint(c, a, dom) for c in constraints): return a
    return None

def classify_checkpoint(scenario, turn):
    cs = active_constraints(scenario, turn)
    trap = [c for c in cs if c['id'] == 'C_trap']
    if not trap: return 'no_trap', None
    return ('spurious_conflict', w) if (w := find_witness(scenario, cs)) is not None else ('genuine_conflict', None)

def score_checkpoint_corrected(assignment, scenario, turn, response):
    cs = active_constraints(scenario, turn); dom = domain_of(scenario); domain_key = scenario.get('domain') or scenario.get('domain_key')
    n_sat = n_viol = n_om = 0; trap_sat = None; flagged = None; all_sat = 0; all_n = 0
    for c in cs:
        involved = [c[k] for k in ('item', 'item_a', 'item_b', 'if_item', 'then_item') if k in c]
        present = all(it in assignment for it in involved)
        sat = R.check_constraint(c, assignment, dom) if present else False
        all_n += 1; all_sat += sat
        if c['id'] == 'C_trap':
            trap_sat = sat if present else False
            flagged = R.detect_conflict_flagged(response, c, domain_key)
            continue
        if not present: n_om += 1
        elif sat: n_sat += 1
        else: n_viol += 1
    n_nt = n_sat + n_viol + n_om
    return {'sat_nontrap': (n_sat / n_nt if n_nt else 0.0), 'sat_all': (all_sat / all_n if all_n else 0.0), 'trap_satisfied': trap_sat,
            'flagged': flagged, 'capacity_ok': capacity_ok(assignment, dom) if assignment else False, 'n_items_assigned': len(assignment or {}),
            'n_satisfied': n_sat, 'n_violated': n_viol, 'n_omitted': n_om}
