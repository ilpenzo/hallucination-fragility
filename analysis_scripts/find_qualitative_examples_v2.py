#!/usr/bin/env python3
"""
find_qualitative_examples_v2.py — Corrected version using actual data schema.

Schema notes:
  P1: turn_scores = [{turn_number, score (0/1), phase, is_probe, question_type, details}, ...]
  P2: turn_scores = [{turn_number, type (checkpoint/recall), satisfaction_rate, conflict_score, ...}, ...]
  P3: separate judged files in p3_judged/individual/

Usage:
  python find_qualitative_examples_v2.py
"""

import json
import os
import glob


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def find_correction_dissociation(scored):
    """T19 (correction identification) score=1.0, T20 (correction propagation) score=0.0"""
    print("=" * 70)
    print("EXAMPLE 1: Correction Dissociation (T19 correct, T20 wrong)")
    print("=" * 70)

    candidates = []
    for entry in scored:
        if entry.get("paradigm") != "P1":
            continue
        model = entry.get("model", "?")
        sid = entry.get("scenario_id", "?")
        turns = entry.get("turn_scores", [])

        t19 = next((t for t in turns if t["turn_number"] == 19), None)
        t20 = next((t for t in turns if t["turn_number"] == 20), None)

        if t19 and t20 and t19["score"] == 1.0 and t20["score"] == 0.0:
            candidates.append({
                "model": model,
                "scenario_id": sid,
                "t19_reason": t19.get("reason", ""),
                "t20_reason": t20.get("reason", ""),
                "t20_details": t20.get("details", {}),
            })

    by_model = {}
    for c in candidates:
        by_model.setdefault(c["model"], []).append(c)

    print(f"\nTotal T19=1, T20=0 cases: {len(candidates)}")
    for model, cases in sorted(by_model.items()):
        print(f"  {model}: {len(cases)} cases")

    # Show top 3 from each model, prefer Sonnet
    for model in ["claude-sonnet-4.5"] + [m for m in by_model if m != "claude-sonnet-4.5"]:
        if model in by_model:
            print(f"\n  Best from {model}:")
            for c in by_model[model][:3]:
                print(f"    {c['scenario_id']}: T19={c['t19_reason'][:60]}")
                print(f"      T20={c['t20_reason'][:80]}")
                det = c["t20_details"]
                if det:
                    print(f"      Model gave: {det.get('model_value')}, Expected: {det.get('target_value')}")


def find_retrieval_failure(scored):
    """Probe turn (is_probe=True) score=0, adjacent non-probe turn score=1."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Retrieval Failure (probe wrong, adjacent fresh correct)")
    print("=" * 70)

    candidates = []
    for entry in scored:
        if entry.get("paradigm") != "P1":
            continue
        model = entry.get("model", "?")
        sid = entry.get("scenario_id", "?")
        turns = entry.get("turn_scores", [])

        # Index turns by number
        by_num = {t["turn_number"]: t for t in turns}

        # Check probe turns: 5, 10, 15, 20
        for probe_tn in [5, 10, 15, 20]:
            probe = by_num.get(probe_tn)
            if not probe or not probe.get("is_probe") or probe["score"] != 0.0:
                continue

            # Check adjacent non-probe turns (next 1-2 turns)
            for adj_tn in [probe_tn + 1, probe_tn + 2]:
                adj = by_num.get(adj_tn)
                if adj and not adj.get("is_probe") and adj["score"] == 1.0:
                    candidates.append({
                        "model": model,
                        "scenario_id": sid,
                        "probe_turn": probe_tn,
                        "probe_reason": probe.get("reason", ""),
                        "probe_details": probe.get("details", {}),
                        "fresh_turn": adj_tn,
                        "fresh_type": adj.get("question_type", ""),
                    })
                    break  # One example per probe turn per scenario

    by_model = {}
    for c in candidates:
        by_model.setdefault(c["model"], []).append(c)

    print(f"\nTotal probe-fail + fresh-pass cases: {len(candidates)}")
    for model, cases in sorted(by_model.items()):
        by_probe = {}
        for c in cases:
            by_probe.setdefault(c["probe_turn"], []).append(c)
        summary = ", ".join(f"T{t}: {len(cs)}" for t, cs in sorted(by_probe.items()))
        print(f"  {model}: {len(cases)} cases ({summary})")

    # Show examples, prefer MiniMax T10 or Sonnet T20
    for model in ["minimax-m2.5", "claude-sonnet-4.5"] + list(by_model.keys()):
        if model in by_model:
            # Prefer T10 or T20 examples
            t10 = [c for c in by_model[model] if c["probe_turn"] == 10]
            t20 = [c for c in by_model[model] if c["probe_turn"] == 20]
            best = (t10 or t20 or by_model[model])[:2]
            print(f"\n  Best from {model}:")
            for c in best:
                print(f"    {c['scenario_id']} probe T{c['probe_turn']}: {c['probe_reason'][:80]}")
                det = c["probe_details"]
                if det:
                    print(f"      Probe gave: {det.get('model_value')}, Expected: {det.get('target_value')}")
                print(f"      Fresh T{c['fresh_turn']} ({c['fresh_type']}): CORRECT")


def find_constraint_failure(scored):
    """P2: High satisfaction at T6/T11, large drop at T17/T20, conflict detected."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Constraint Maintenance Failure")
    print("=" * 70)

    candidates = []
    for entry in scored:
        if entry.get("paradigm") != "P2":
            continue
        model = entry.get("model", "?")
        sid = entry.get("scenario_id", "?")
        turns = entry.get("turn_scores", [])

        checkpoints = [t for t in turns if t.get("type") == "checkpoint"]
        by_tn = {t["turn_number"]: t for t in checkpoints}

        t6 = by_tn.get(6, {})
        t11 = by_tn.get(11, {})
        t17 = by_tn.get(17, {})
        t20 = by_tn.get(20, {})

        t6_sat = t6.get("satisfaction_rate")
        t11_sat = t11.get("satisfaction_rate")
        t17_sat = t17.get("satisfaction_rate")
        t20_sat = t20.get("satisfaction_rate")

        conflict_detected = t17.get("conflict_score", 0)

        if t6_sat is not None and t17_sat is not None:
            pre = t6_sat if t11_sat is None else (t6_sat + t11_sat) / 2
            post = t17_sat if t20_sat is None else (t17_sat + t20_sat) / 2
            drop = pre - post

            if drop > 0.15:
                candidates.append({
                    "model": model,
                    "scenario_id": sid,
                    "t6": t6_sat,
                    "t11": t11_sat,
                    "t17": t17_sat,
                    "t20": t20_sat,
                    "drop": round(drop, 3),
                    "conflict_detected": conflict_detected,
                    "t17_violated": t17.get("n_violated", 0),
                    "t17_omitted": t17.get("n_omitted", 0),
                })

    candidates.sort(key=lambda x: -x["drop"])

    by_model = {}
    for c in candidates:
        by_model.setdefault(c["model"], []).append(c)

    print(f"\nTotal large-drop cases (>0.15): {len(candidates)}")
    for model, cases in sorted(by_model.items()):
        avg_drop = sum(c["drop"] for c in cases) / len(cases)
        print(f"  {model}: {len(cases)} cases (avg drop: {avg_drop:.3f})")

    # Show top examples, prefer Gemini
    for model in ["gemini-2.5-pro"] + [m for m in by_model if m != "gemini-2.5-pro"]:
        if model in by_model:
            print(f"\n  Worst drops from {model}:")
            for c in by_model[model][:3]:
                print(f"    {c['scenario_id']}: T6={c['t6']}, T11={c['t11']}, "
                      f"T17={c['t17']}, T20={c['t20']} (drop={c['drop']})")
                print(f"      Conflict detected: {c['conflict_detected']}, "
                      f"T17 violated: {c['t17_violated']}, omitted: {c['t17_omitted']}")


def find_fabrication_trigger(p3_judged_dir):
    """Scan P3 judged files for fabrication."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Fabrication Trigger (P3 judged files)")
    print("=" * 70)

    judged_files = sorted(glob.glob(os.path.join(p3_judged_dir, "*.json")))
    print(f"\nFound {len(judged_files)} judged files")

    if not judged_files:
        return

    # Show structure of first file
    first = load_json(judged_files[0])
    print(f"\nFirst file keys: {list(first.keys())}")
    print(f"First file (truncated): {json.dumps(first, indent=2, default=str)[:2000]}")

    # Try to find fabrication indicators across all files
    fabrication_cases = []
    for jf in judged_files:
        data = load_json(jf)
        model = data.get("model", "?")
        sid = data.get("scenario_id", "?")

        # Walk entire structure looking for fabrication-related keys
        text = json.dumps(data, default=str).lower()
        has_fab = ("fabricat" in text) or ("gap_abstention" in text and "0." in text)

        # Check all nested dicts for gap/fabrication scores
        scores = data.get("scores", data.get("evaluation", data.get("results", {})))
        fab_info = None

        if isinstance(scores, dict):
            for key, val in scores.items():
                key_l = key.lower()
                if "fab" in key_l or "gap" in key_l:
                    fab_info = fab_info or {}
                    fab_info[key] = val

        # Also check top-level
        for key in data:
            key_l = key.lower()
            if "fab" in key_l or "gap" in key_l:
                fab_info = fab_info or {}
                fab_info[key] = data[key]

        if fab_info:
            fabrication_cases.append({
                "model": model,
                "scenario_id": sid,
                "file": os.path.basename(jf),
                "fab_info": fab_info,
            })

    print(f"\nFiles with fabrication/gap-related fields: {len(fabrication_cases)}")

    # Group by scenario
    by_scenario = {}
    for c in fabrication_cases:
        by_scenario.setdefault(c["scenario_id"], []).append(c)

    # For each scenario, check if any model actually fabricated
    print("\nPer-scenario fabrication summary:")
    for sid in sorted(by_scenario.keys()):
        entries = by_scenario[sid]
        fab_models = []
        for e in entries:
            info = e["fab_info"]
            # Check various possible indicators
            fab_rate = info.get("fabrication_rate", info.get("fabrication", None))
            gap_abst = info.get("gap_abstention", info.get("gap_abstention_rate", None))
            if (fab_rate is not None and fab_rate > 0) or \
               (gap_abst is not None and gap_abst < 1.0):
                fab_models.append(e["model"])
        if fab_models:
            print(f"  {sid}: fabricated by {fab_models}")
            for e in entries:
                if e["model"] in fab_models:
                    print(f"    {e['model']}: {e['fab_info']}")


def main():
    scored_path = "./results/scored_full/scored_results_enhanced.json"
    p3_judged_dir = "./results/p3_judged/individual"

    scored = load_json(scored_path)

    find_correction_dissociation(scored)
    find_retrieval_failure(scored)
    find_constraint_failure(scored)
    find_fabrication_trigger(p3_judged_dir)

    print("\n" + "=" * 70)
    print("DONE. Share requested conversation files for qualitative excerpts.")
    print("=" * 70)


if __name__ == "__main__":
    main()
