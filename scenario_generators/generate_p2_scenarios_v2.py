#!/usr/bin/env python3
"""P2 scenario generator, version 2.0.0 (released with the revised manuscript; NOT used for the reported results).

The reported case study uses the historical scenarios produced by generate_p2_scenarios.py (version 1.0.0), which
are preserved unchanged. Version 2 reuses that generator's construction and corrects four task-definition defects
found when the historical scenarios were audited:

  1. Verified feasibility. After generation, every checkpoint request (turns 6, 11, 17, 20) and the turn-15
     request are checked by exhaustive search over all item placements, with the turn-12 replacement applied and
     all slot capacities enforced. Each is labelled feasible (a satisfying plan is stored as a witness) or
     infeasible. `--conflict-mode` selects what the turn-15 requirement must do:
        infeasible  every request from turn 15 on is unsatisfiable (a genuine conflict);
        feasible    every request remains satisfiable although the reference plan is broken;
        any         keep whatever the construction yields (as in version 1), but label it.
  2. Effective requirements are materialised. Each checkpoint lists the requirements in force with the turn-12
     replacement already applied (`effective_constraints`), so a scorer cannot check the superseded requirement.
  3. One capacity value per slot, with a unit. The explicit capacity sentence never exceeds the table value and
     says that it replaces it; the capacity table states that capacity is a maximum number of items per slot.
  4. Explicit priority rule. The system prompt says what to do when the requirements cannot all be satisfied:
     say so, name the conflicting requirements, and still give a complete plan that satisfies every requirement
     except the most recently added one.

Usage: python generate_p2_scenarios_v2.py --output-dir p2_scenarios_v2 --conflict-mode infeasible [--seed N] [--n 40]"""
import argparse, copy, itertools, json, os
import generate_p2_scenarios as G

VERSION = "2.0.0"
PRIORITY_RULE = (" If the requirements cannot all be satisfied together, say so explicitly and name the requirements that conflict. "
                 "Then still give a complete plan that satisfies every requirement except the most recently added one.")

# ---- defect 3: one capacity value per slot, unit stated -------------------------------------------------------
def _derive_capacity_v2(rng, sol, dom, trk):
    avail = [s["id"] for s in dom["slots"] if s["id"] not in trk["cap"]]
    if not avail: return None
    slot = rng.choice(avail); trk["cap"].add(slot)
    actual = sum(1 for v in sol.values() if v == slot); table = G.get_slot(dom, slot)["capacity"]
    return {"type": "capacity", "slot": slot, "max": max(1, min(table, actual + rng.choice([0, 1])))}

_constraint_nl_v1 = G.constraint_nl
def _constraint_nl_v2(c, dom):
    if c["type"] == "capacity":
        table = G.get_slot(dom, c["slot"])["capacity"]; base = f"{G.sname(dom, c['slot'])} can hold at most {c['max']} {dom['items_label']}"
        return base + (", as listed in the capacity table." if c["max"] == table else "; this replaces the capacity listed for it in the table.")
    return _constraint_nl_v1(c, dom)

def _format_slots_table_v2(dom):
    hdrs = [dom["slot_label"].title(), f"Capacity (max {dom['items_label']} per {dom['slot_label']})"]
    rows = [(s["name"], str(s["capacity"])) for s in dom["slots"]]
    widths = [max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(hdrs)]
    lines = ["| " + " | ".join(h.ljust(w) for h, w in zip(hdrs, widths)) + " |", "| " + " | ".join("-" * w for w in widths) + " |"]
    return "\n".join(lines + ["| " + " | ".join(v.ljust(w) for v, w in zip(r, widths)) + " |" for r in rows])

def _install():
    G._DERIVERS["capacity"] = _derive_capacity_v2
    if "capacity" in getattr(G, "_FALLBACKS", {}) and G._FALLBACKS["capacity"] is G._derive_capacity: G._FALLBACKS["capacity"] = _derive_capacity_v2
    G.constraint_nl = _constraint_nl_v2; G.format_slots_table = _format_slots_table_v2
    G.SYSTEM_PROMPT = G.SYSTEM_PROMPT + PRIORITY_RULE

# ---- defects 1 and 2: effective requirements and verified feasibility --------------------------------------------
def effective_constraints(sc, turn):
    """Requirements in force at `turn`, with the turn-12 replacement applied."""
    ids = turn.get("active_constraint_ids") or []
    by = {c["id"]: copy.deepcopy(c) for c in sc["constraints"]}; mod = sc.get("modification") or {}
    if mod and int(turn["turn_number"]) >= G.MODIFICATION_TURN:
        c = by.get(mod.get("original_constraint_id"))
        if c is not None and c["type"] == "fixed_assignment": c["slot"] = mod["new_slot"]; c["replaced_at_turn"] = G.MODIFICATION_TURN
    return [by[i] for i in ids if i in by]

def find_plan(sc, constraints):
    """Exhaustive search for a complete plan satisfying every constraint and every table capacity; None if none exists."""
    dom = copy.deepcopy(G.DOMAINS[sc["domain"]]); items = [i["id"] for i in dom["items"]]; slots = [s["id"] for s in dom["slots"]]
    cap = {s["id"]: s["capacity"] for s in dom["slots"]}; allowed = {it: set(slots) for it in items}
    for c in constraints:
        if c["type"] == "fixed_assignment": allowed[c["item"]] &= {c["slot"]}
        elif c["type"] == "exclusion": allowed[c["item"]].discard(c["slot"])
        elif c["type"] == "capacity": cap[c["slot"]] = min(cap[c["slot"]], c["max"])
    for placement in itertools.product(*(sorted(allowed[it]) for it in items)):
        counts = {}
        for sl in placement: counts[sl] = counts.get(sl, 0) + 1
        if any(n > cap[sl] for sl, n in counts.items()): continue
        a = dict(zip(items, placement))
        if all(G.check_constraint(c, a, dom) for c in constraints): return a
    return None

def annotate(sc):
    labels = {}
    for t in sc["turns"]:
        tn = int(t["turn_number"])
        if not (t.get("is_checkpoint") or tn == G.CONFLICT_TURN): continue
        eff = effective_constraints(sc, t); w = find_plan(sc, eff)
        t["effective_constraints"] = eff; t["feasibility"] = {"feasible": w is not None, "witness_plan": w, "method": "exhaustive search, capacities enforced"}
        labels[tn] = w is not None
    sc["generator_version"] = VERSION; sc["feasibility_by_turn"] = {str(k): v for k, v in sorted(labels.items())}
    return labels

def generate(num, domain_key, seed, mode, max_resamples=200):
    for k in range(max_resamples):
        sc = G.generate_scenario(num, domain_key, seed + k * 104729); labels = annotate(sc)
        assert labels.get(6) and labels.get(11), "pre-revision checkpoints must be feasible by construction"
        post = [labels[t] for t in (15, 17, 20) if t in labels]
        if mode == "any" or (mode == "infeasible" and not any(post)) or (mode == "feasible" and all(post)):
            sc["conflict_mode"] = mode; sc["resamples_used"] = k; return sc
    raise RuntimeError(f"no scenario with conflict mode '{mode}' after {max_resamples} resamples")

def main():
    ap = argparse.ArgumentParser(description="Generate P2 scenarios (version 2: verified feasibility, single capacity value, priority rule)")
    ap.add_argument("--output-dir", default="p2_scenarios_v2"); ap.add_argument("--seed", type=int, default=G.MASTER_SEED)
    ap.add_argument("--conflict-mode", choices=["infeasible", "feasible", "any"], default="infeasible"); ap.add_argument("--n", type=int, default=G.N_SCENARIOS)
    args = ap.parse_args(); _install(); os.makedirs(args.output_dir, exist_ok=True)
    keys = [dk for dk in G.DOMAINS for _ in range(G.SCENARIOS_PER_DOMAIN)][:args.n]; manifest = []
    for i, dk in enumerate(keys, 1):
        sc = generate(i, dk, args.seed, args.conflict_mode); issues = G.validate_scenario(sc)
        json.dump(sc, open(os.path.join(args.output_dir, f"P2_{i:03d}.json"), "w"), indent=2)
        manifest.append({"scenario_id": sc["scenario_id"], "domain": dk, "feasibility_by_turn": sc["feasibility_by_turn"], "resamples_used": sc["resamples_used"], "v1_validator_issues": issues})
        print(f"  P2_{i:03d} ({dk:12s}) feasible by turn: {sc['feasibility_by_turn']}  resamples: {sc['resamples_used']}  v1 validator issues: {len(issues)}")
    json.dump({"generator_version": VERSION, "seed": args.seed, "conflict_mode": args.conflict_mode, "scenarios": manifest}, open(os.path.join(args.output_dir, "manifest.json"), "w"), indent=2)
    print(f"wrote {len(manifest)} scenarios to {args.output_dir}")

if __name__ == "__main__":
    main()
