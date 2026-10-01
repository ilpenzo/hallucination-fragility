#!/usr/bin/env python3
"""
find_qualitative_examples.py — Scan result files to identify the best
illustrative conversation excerpts for each failure mode.

Outputs:
  1. Best P1 correction dissociation (T19 correct, T20 wrong) — Sonnet ideal
  2. Best P1 retrieval failure (probe fail + adjacent fresh pass) — any model
  3. Best P2 conflict detection success + post-revision failure — Gemini ideal
  4. Best P3 "missing evidence" fabrication trigger — whichever scenario triggered 3/5

For each, prints the scenario ID so the user can share the full conversation file.

Usage:
  python find_qualitative_examples.py \
      --results-dir ./results \
      --scored-results ./results/scored_full/scored_results_enhanced.json \
      --p3-source ./p3_source_data.json \
      --p3-judged-dir ./results/p3_judged/individual
"""

import json
import os
import argparse
import glob


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def find_correction_dissociation(scored, results_dir):
    """
    Find the best example of a model identifying a correction at T19
    but failing to propagate it at T20.
    Sonnet is the poster child (1.000 at T19, 0.120 at T20 overall).
    We want a specific scenario where T19 is clearly correct and T20 is wrong.
    """
    print("=" * 70)
    print("EXAMPLE 1: Correction Dissociation (T19 correct, T20 wrong)")
    print("=" * 70)

    candidates = []
    for entry in scored:
        if entry.get("paradigm") != "P1":
            continue
        scores = entry.get("scores", {})
        # T19 = correction identification, T20 = correction propagation
        t19 = scores.get("T19", {})
        t20 = scores.get("T20", {})

        t19_correct = t19.get("correct", False) if isinstance(t19, dict) else False
        t20_correct = t20.get("correct", False) if isinstance(t20, dict) else False

        if t19_correct and not t20_correct:
            model = entry.get("model", "unknown")
            scenario = entry.get("scenario_id", "unknown")
            candidates.append({
                "model": model,
                "scenario_id": scenario,
                "t19_score": t19,
                "t20_score": t20,
            })

    # Group by model
    by_model = {}
    for c in candidates:
        by_model.setdefault(c["model"], []).append(c)

    print(f"\nTotal T19-correct + T20-wrong cases: {len(candidates)}")
    for model, cases in sorted(by_model.items()):
        print(f"  {model}: {len(cases)} cases")

    # Prefer Sonnet (the most dramatic dissociation), show first 3
    preferred = ["claude-sonnet-4.5", "claude-sonnet-4-5"]
    shown = []
    for model in preferred:
        if model in by_model:
            shown = by_model[model][:3]
            break
    if not shown and candidates:
        shown = candidates[:3]

    print("\nBest candidates to pull conversation from:")
    for c in shown:
        print(f"  {c['model']} / {c['scenario_id']}")
        result_path = os.path.join(
            results_dir, c["model"], f"{c['scenario_id']}.json"
        )
        alt_paths = glob.glob(
            os.path.join(results_dir, "*", f"{c['scenario_id']}.json")
        )
        found_paths = [p for p in alt_paths if os.path.exists(p)]
        if found_paths:
            print(f"    File: {found_paths[0]}")
        else:
            print(f"    File: (not found at {result_path})")

    return shown


def find_retrieval_failure(scored, results_dir):
    """
    Find the best example of retrieval failure: probe question wrong while
    adjacent fresh computation is correct. Look at T10 probe especially.
    MiniMax at T10 has 81% retrieval failure rate — very dramatic.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Retrieval Failure (probe wrong, fresh computation right)")
    print("=" * 70)

    candidates = []
    for entry in scored:
        if entry.get("paradigm") != "P1":
            continue
        scores = entry.get("scores", {})
        model = entry.get("model", "unknown")
        scenario = entry.get("scenario_id", "unknown")

        # Check probe turns (T5, T10, T15) vs adjacent fresh turns
        # T5 is a probe, T6-T9 are fresh; T10 is a probe, T11-T14 fresh;
        # T15 is a probe, T16-T18 fresh
        probe_fresh_pairs = [
            ("T10", ["T11", "T12"]),  # T10 probe, T11-T12 fresh
            ("T5", ["T6", "T7"]),     # T5 probe, T6-T7 fresh
            ("T15", ["T16", "T17"]),  # T15 probe, T16-T17 fresh
        ]

        for probe_key, fresh_keys in probe_fresh_pairs:
            probe = scores.get(probe_key, {})
            probe_correct = probe.get("correct", False) if isinstance(probe, dict) else False

            if probe_correct:
                continue  # We want probe FAIL

            # Check if any adjacent fresh turn is correct
            any_fresh_correct = False
            for fk in fresh_keys:
                ft = scores.get(fk, {})
                if isinstance(ft, dict) and ft.get("correct", False):
                    any_fresh_correct = True
                    break

            if any_fresh_correct:
                candidates.append({
                    "model": model,
                    "scenario_id": scenario,
                    "probe_turn": probe_key,
                    "probe_score": probe,
                })

    by_model = {}
    for c in candidates:
        by_model.setdefault(c["model"], []).append(c)

    print(f"\nTotal probe-fail + fresh-pass cases: {len(candidates)}")
    for model, cases in sorted(by_model.items()):
        # Count by probe turn
        by_turn = {}
        for c in cases:
            by_turn.setdefault(c["probe_turn"], []).append(c)
        turn_summary = ", ".join(f"{t}: {len(cs)}" for t, cs in sorted(by_turn.items()))
        print(f"  {model}: {len(cases)} cases ({turn_summary})")

    # Prefer MiniMax at T10 (most dramatic), or Sonnet at T20
    preferred_models = ["minimax-m2.5", "MiniMax-M2.5"]
    shown = []
    for model in preferred_models:
        if model in by_model:
            # Prefer T10 examples
            t10_cases = [c for c in by_model[model] if c["probe_turn"] == "T10"]
            shown = (t10_cases or by_model[model])[:3]
            break
    if not shown and candidates:
        shown = candidates[:3]

    print("\nBest candidates to pull conversation from:")
    for c in shown:
        print(f"  {c['model']} / {c['scenario_id']} (probe {c['probe_turn']})")
        alt_paths = glob.glob(
            os.path.join(results_dir, "*", f"{c['scenario_id']}.json")
        )
        found_paths = [p for p in alt_paths if os.path.exists(p)]
        if found_paths:
            print(f"    File: {found_paths[0]}")


def find_constraint_failure(scored, results_dir):
    """
    Find the best P2 example: conflict detected but post-revision satisfaction
    drops dramatically. Gemini is ideal (0.979 pre -> 0.556 post).
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Constraint Maintenance Failure (detect conflict, fail revision)")
    print("=" * 70)

    candidates = []
    for entry in scored:
        if entry.get("paradigm") != "P2":
            continue
        scores = entry.get("scores", {})
        model = entry.get("model", "unknown")
        scenario = entry.get("scenario_id", "unknown")

        # Check conflict detection
        conflict = scores.get("conflict_detection", {})
        conflict_detected = False
        if isinstance(conflict, dict):
            conflict_detected = conflict.get("detected", False)
        elif isinstance(conflict, (int, float)):
            conflict_detected = conflict > 0.5

        # Check checkpoint satisfaction scores
        checkpoints = scores.get("checkpoints", {})
        if not isinstance(checkpoints, dict):
            continue

        # Get pre-conflict (T6, T11) and post-conflict (T17, T20) satisfaction
        t6 = checkpoints.get("T6", {})
        t11 = checkpoints.get("T11", {})
        t17 = checkpoints.get("T17", {})
        t20 = checkpoints.get("T20", {})

        def get_sat(cp):
            if isinstance(cp, dict):
                return cp.get("satisfaction", cp.get("score", None))
            elif isinstance(cp, (int, float)):
                return cp
            return None

        t6_sat = get_sat(t6)
        t11_sat = get_sat(t11)
        t17_sat = get_sat(t17)
        t20_sat = get_sat(t20)

        # We want: good pre-conflict, bad post-conflict, conflict detected
        if t6_sat is not None and t17_sat is not None:
            pre_avg = t6_sat if t11_sat is None else (t6_sat + t11_sat) / 2
            post_avg = t17_sat if t20_sat is None else (t17_sat + t20_sat) / 2
            drop = pre_avg - post_avg

            if drop > 0.2 and conflict_detected:
                candidates.append({
                    "model": model,
                    "scenario_id": scenario,
                    "pre_sat": round(pre_avg, 3),
                    "post_sat": round(post_avg, 3),
                    "drop": round(drop, 3),
                    "t6": t6_sat,
                    "t11": t11_sat,
                    "t17": t17_sat,
                    "t20": t20_sat,
                })

    candidates.sort(key=lambda x: -x["drop"])

    by_model = {}
    for c in candidates:
        by_model.setdefault(c["model"], []).append(c)

    print(f"\nTotal conflict-detected + large-drop cases (drop > 0.2): {len(candidates)}")
    for model, cases in sorted(by_model.items()):
        avg_drop = sum(c["drop"] for c in cases) / len(cases) if cases else 0
        print(f"  {model}: {len(cases)} cases (avg drop: {avg_drop:.3f})")

    # Prefer Gemini
    preferred = ["gemini-2.5-pro"]
    shown = []
    for model in preferred:
        if model in by_model:
            shown = by_model[model][:3]
            break
    if not shown and candidates:
        shown = candidates[:3]

    print("\nBest candidates (largest satisfaction drop):")
    for c in shown:
        print(f"  {c['model']} / {c['scenario_id']}")
        print(f"    Pre-conflict: {c['pre_sat']}, Post-conflict: {c['post_sat']}, Drop: {c['drop']}")
        print(f"    T6={c['t6']}, T11={c['t11']}, T17={c['t17']}, T20={c['t20']}")
        alt_paths = glob.glob(
            os.path.join(results_dir, "*", f"{c['scenario_id']}.json")
        )
        found_paths = [p for p in alt_paths if os.path.exists(p)]
        if found_paths:
            print(f"    File: {found_paths[0]}")


def find_fabrication_trigger(p3_source, p3_judged_dir):
    """
    Find the best P3 example: a 'missing evidence' gap that triggered fabrication.
    The clinical drug trial scenario that triggered 3/5 models is ideal.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Fabrication Trigger (missing evidence gap)")
    print("=" * 70)

    # Load all judged P3 files
    judged_files = glob.glob(os.path.join(p3_judged_dir, "*.json"))
    if not judged_files:
        print(f"  No judged files found in {p3_judged_dir}")
        return

    # Parse source data for gap types
    scenarios = p3_source if isinstance(p3_source, list) else p3_source.get("scenarios", [])
    gap_types_by_scenario = {}
    for s in scenarios:
        sid = s.get("scenario_id", "")
        gaps = s.get("information_gaps", [])
        gap_types_by_scenario[sid] = {
            "gaps": gaps,
            "domain": s.get("domain", "unknown"),
            "topic": s.get("topic", s.get("title", "unknown")),
        }

    # Check each judged file for fabrication
    fabrication_by_scenario = {}
    for jf in sorted(judged_files):
        data = load_json(jf)
        model = data.get("model", "unknown")
        scenario_id = data.get("scenario_id", "")

        # Look for fabrication indicators
        gap_eval = data.get("gap_handling", data.get("gap_evaluation", {}))
        fabricated = False

        if isinstance(gap_eval, dict):
            fabricated = gap_eval.get("fabricated", False)
            if not fabricated:
                fab_rate = gap_eval.get("fabrication_rate", 0)
                fabricated = fab_rate > 0
            if not fabricated:
                response = gap_eval.get("response", "")
                if isinstance(response, str) and "fabricat" in response.lower():
                    fabricated = True

        # Also check top-level scores
        scores = data.get("scores", {})
        if isinstance(scores, dict):
            fab = scores.get("fabrication", scores.get("fabrication_rate", None))
            if fab is not None and fab > 0:
                fabricated = True
            gap_abst = scores.get("gap_abstention", None)
            if gap_abst is not None and gap_abst < 1.0:
                fabricated = True

        if fabricated:
            fabrication_by_scenario.setdefault(scenario_id, []).append({
                "model": model,
                "file": jf,
            })

    # Sort by number of models that fabricated (universal triggers first)
    ranked = sorted(
        fabrication_by_scenario.items(),
        key=lambda x: -len(x[1])
    )

    print(f"\nScenarios with fabrication (by number of models affected):")
    for sid, models in ranked:
        info = gap_types_by_scenario.get(sid, {})
        model_names = [m["model"] for m in models]
        print(f"  {sid}: {len(models)} models fabricated — {model_names}")
        print(f"    Domain: {info.get('domain', '?')}, Topic: {info.get('topic', '?')}")
        gaps = info.get("gaps", [])
        for g in gaps:
            if isinstance(g, dict):
                print(f"    Gap: type={g.get('gap_type', '?')}, desc={g.get('description', g.get('gap_description', '?'))[:80]}")
            elif isinstance(g, str):
                print(f"    Gap: {g[:80]}")

    if ranked:
        best_sid, best_models = ranked[0]
        print(f"\nBest candidate: {best_sid} ({len(best_models)} models)")
        print("  Judged files to examine:")
        for m in best_models:
            print(f"    {m['file']}")


def examine_scored_structure(scored):
    """Debug: show the structure of a few scored entries to understand the schema."""
    print("\n" + "=" * 70)
    print("SCHEMA EXAMINATION (first P1, P2, P3 entry)")
    print("=" * 70)

    for paradigm in ["P1", "P2", "P3"]:
        for entry in scored:
            if entry.get("paradigm") == paradigm:
                print(f"\n--- {paradigm} example ({entry.get('model')}/{entry.get('scenario_id')}) ---")
                scores = entry.get("scores", {})
                if isinstance(scores, dict):
                    for key in sorted(scores.keys()):
                        val = scores[key]
                        if isinstance(val, dict):
                            print(f"  scores.{key}: {json.dumps(val)[:120]}")
                        else:
                            print(f"  scores.{key}: {val}")
                else:
                    print(f"  scores type: {type(scores)}, value: {str(scores)[:200]}")
                break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="./results")
    parser.add_argument("--scored-results",
                        default="./results/scored_full/scored_results_enhanced.json")
    parser.add_argument("--p3-source", default="./p3_source_data.json")
    parser.add_argument("--p3-judged-dir", default="./results/p3_judged/individual")
    args = parser.parse_args()

    scored = load_json(args.scored_results)
    p3_source = load_json(args.p3_source)

    # First, examine the schema so we can interpret correctly
    examine_scored_structure(scored)

    # Then find examples
    find_correction_dissociation(scored, args.results_dir)
    find_retrieval_failure(scored, args.results_dir)
    find_constraint_failure(scored, args.results_dir)
    find_fabrication_trigger(p3_source, args.p3_judged_dir)

    print("\n" + "=" * 70)
    print("NEXT STEP: Share the conversation JSON files listed above.")
    print("I need the raw conversation (turns + responses) to extract")
    print("compelling qualitative excerpts for the paper.")
    print("=" * 70)


if __name__ == "__main__":
    main()
