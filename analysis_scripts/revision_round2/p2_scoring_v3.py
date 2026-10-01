"""P2 scoring v3.1 (round-2 protocol, decisions 1-3; validity gated on feasibility after the 2026-09-17 review). Consumes p2_plan_extractor (block-scoped plans),
p2_corrected_scoring (T12 replacement, feasibility classes) and conflict_detector_v3.

Effective requirement set at a checkpoint:
  * active explicit non-capacity constraints with the T12 replacement applied;
  * ONE effective capacity condition per slot = min(stated table capacity, any explicit active capacity
    constraint on that slot)  [explicit capacity constraints are folded in, never counted twice];
  * the T15 trap constraint is included when the checkpoint is FEASIBLE (a plan satisfying everything exists)
    and excluded from the fractional metric when it is INFEASIBLE (it is then reported as an incompatibility case).
Item-level constraints with a missing item count as unsatisfied (no vacuous credit). No plan -> all metrics 0
and valid = False. Duplicate placements or assigned-and-unassigned items -> invalid plan (flag kept).

Per-checkpoint outputs: label (no_plan/partial_plan/complete_plan/no_usable_plan), coverage, sat_v3 (fractional over
the effective set), sat_explicit (explicit non-trap constraints only; continuity with the historical metric under
block-scoped extraction), valid_complete_plan, capacity_violation, trap_satisfied, feasibility class,
incompatibility flag (active-set scope) at T15 and at this checkpoint, requests_resolution.
"""
import copy, sys
from common import *
sys.path.insert(0, SCORING_DIR); import p2_rescore as R
import p2_corrected_scoring as C
from p2_plan_extractor import extract_plan
from conflict_detector_v3 import classify

def effective_requirements(scenario, turn):
    cs = C.active_constraints(scenario, turn); dom = C.domain_of(scenario)
    cap = {s['id']: s['capacity'] for s in dom['slots']}
    explicit, trap = [], None
    for c in cs:
        if c['id'] == 'C_trap': trap = c; continue
        if c['type'] == 'capacity':
            cap[c['slot']] = min(cap[c['slot']], c['max']); continue
        explicit.append(c)
    return explicit, cap, trap, dom

def score(scenario, turn, response, feasibility_class, t15_response=None):
    domain_key = scenario.get('domain') or scenario.get('domain_key')
    ex = extract_plan(response, domain_key); a = ex['assignment']
    explicit, cap, trap, dom = effective_requirements(scenario, turn)
    feasible = feasibility_class in ('spurious_conflict', 'no_trap')
    reqs = list(explicit) + ([trap] if (trap is not None and feasible) else [])
    n_items = len(dom['items'])
    counts = {}
    for it, sl in a.items(): counts[sl] = counts.get(sl, 0) + 1
    cap_ok = {sl: counts.get(sl, 0) <= lim for sl, lim in cap.items()}
    def sat(c):
        involved = [c[k] for k in ('item', 'item_a', 'item_b', 'if_item', 'then_item') if k in c]
        if not all(it in a for it in involved): return False
        return bool(R.check_constraint(c, a, dom))
    if not a:
        s_v3 = 0.0; s_exp = 0.0; valid = False; capviol = None
    else:
        parts = [sat(c) for c in reqs] + [cap_ok[sl] for sl in cap]
        s_v3 = sum(parts) / len(parts)
        s_exp = (sum(sat(c) for c in explicit) / len(explicit)) if explicit else 0.0
        capviol = not all(cap_ok.values())
        reduced_valid = (len(a) == n_items) and not ex['flags'] and all(parts)   # every requirement in the reduced set (trap dropped when infeasible)
        valid = reduced_valid and feasible                                      # full-task validity is impossible on an infeasible state
    trap_sat = sat(trap) if (trap is not None and a) else None
    if not a: reduced_valid = False
    det = classify(response, trap, domain_key) if trap is not None else {'active_set': None}
    det15 = classify(t15_response, trap, domain_key) if (t15_response is not None and trap is not None) else {'active_set': None}
    return {'label': ex['label'], 'coverage': len(a) / n_items, 'n_assigned': len(a), 'unassigned': ex['unassigned'], 'flags': ex['flags'],
            'sat_v3': s_v3, 'sat_explicit': s_exp, 'valid_complete_plan': valid, 'reduced_set_valid_plan': reduced_valid, 'capacity_violation': capviol,
            'trap_satisfied': trap_sat, 'feasible': feasible, 'class': feasibility_class,
            'flag_here': det['active_set'], 'flag_t15': det15['active_set'], 'requests_resolution': ex['requests_resolution'],
            'n_effective_requirements': len(reqs) + len(cap)}

# NOTE: sat_explicit counts explicit non-capacity, non-trap constraints only (capacity conditions excluded); it is
# a continuity diagnostic under block-scoped extraction, not identical to the original rigid-parser metric.
