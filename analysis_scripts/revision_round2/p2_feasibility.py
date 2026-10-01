"""Verified feasibility of every P2 checkpoint request that carries the T15 constraint (T15, T17, T20).

For each of the 40 historical scenarios and each of the three turns, the active requirement set is built with the
T12 replacement applied (p2_corrected_scoring.active_constraints) and an exhaustive search over item placements
looks for an assignment that satisfies every active constraint and every slot capacity. A request is labelled
  spurious_conflict  - the T15 constraint was generated as a "conflict", but a satisfying plan exists (feasible);
  genuine_conflict   - no assignment satisfies the active set (infeasible);
  no_trap            - the turn carries no T15 constraint.
Writes p2_feasibility_classes.json (the labels every other script reads) and p2_feasibility_witnesses.json
(one satisfying plan per feasible request, so each feasibility label can be checked by hand)."""
import sys, collections
from common import *
sys.path.insert(0, SCORING_DIR); import p2_rescore as R
import p2_corrected_scoring as C
scen = R.load_scenarios(P2_SCEN); classes = {}; witnesses = {}
for sid in sorted(scen):
    for turn in (15, 17, 20):
        tdict = next(t for t in scen[sid]['turns'] if int(t['turn_number']) == turn)
        cls, w = C.classify_checkpoint(scen[sid], tdict); classes[f'{sid}|T{turn}'] = cls
        if w is not None: witnesses[f'{sid}|T{turn}'] = w
count = collections.Counter((k.split('|')[1], v) for k, v in classes.items())
md = '| Turn | feasible (satisfying plan exists) | infeasible |\n|---|---|---|\n' + ''.join(f"| T{t} | {count[(f'T{t}', 'spurious_conflict')]} | {count[(f'T{t}', 'genuine_conflict')]} |\n" for t in (15, 17, 20))
print(md)
old = os.path.join(OUT, 'p2_feasibility_classes.json')
if os.path.exists(old): print('identical to existing labels:', load(old) == classes)
save('p2_feasibility_classes', classes, md); save('p2_feasibility_witnesses', witnesses)
