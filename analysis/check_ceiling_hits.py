#!/usr/bin/env python3
"""
check_ceiling_hits.py — Identify which turns hit the token ceiling and whether they were scored.

Usage:
  python3 check_ceiling_hits.py --results-dir ./results --scenarios-dir .
"""

import json
import os
import glob
import argparse
from collections import defaultdict

CEILING = {
    "claude-sonnet-4.5": 2048,
    "minimax-m2.5": 2048,
}

# P1 scored turns: all except synthesis (T16-18 are synthesis, score=-1)
# P2 scored turns: checkpoints at T6, T11, T17, T20
P2_CHECKPOINTS = {6, 11, 17, 20}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--scenarios-dir", required=True)
    parser.add_argument("--output", default="ceiling_hits.json")
    args = parser.parse_args()

    # Load P1 scenario metadata to know which turns are synthesis
    p1_synthesis_turns = {}  # scenario_id -> set of synthesis turn numbers
    p1_dir = os.path.join(args.scenarios_dir, "p1_scenarios")
    if os.path.isdir(p1_dir):
        for fpath in glob.glob(os.path.join(p1_dir, "P1_*.json")):
            with open(fpath) as f:
                sc = json.load(f)
            sid = sc["scenario_id"]
            synth = set()
            for t in sc.get("turns", []):
                if t.get("phase") == "synthesis":
                    synth.add(t["turn_number"])
                # Also check if ground_truth scoring_type is synthesis
                gt = t.get("ground_truth", {})
                if gt.get("scoring_type") == "synthesis":
                    synth.add(t["turn_number"])
            p1_synthesis_turns[sid] = synth

    hits = []

    for model in ["claude-sonnet-4.5", "minimax-m2.5"]:
        ceiling = CEILING[model]
        model_dir = os.path.join(args.results_dir, model)
        if not os.path.isdir(model_dir):
            print(f"WARN: {model_dir} not found")
            continue

        for fpath in sorted(glob.glob(os.path.join(model_dir, "*.json"))):
            fname = os.path.basename(fpath)
            if fname.startswith("_"):
                continue
            try:
                with open(fpath) as f:
                    data = json.load(f)
            except Exception:
                continue

            sid = data.get("scenario_id", "")
            paradigm = data.get("paradigm", "")

            for turn in data.get("turns", []):
                out_tok = turn.get("output_tokens", 0)
                if out_tok >= ceiling:
                    tn = turn["turn_number"]

                    # Determine if this turn is scored
                    is_scored = True
                    score_note = "scored"

                    if paradigm == "P1":
                        synth_set = p1_synthesis_turns.get(sid, set())
                        if tn in synth_set:
                            is_scored = False
                            score_note = "synthesis (not scored)"
                        else:
                            score_note = "scored (numeric)"
                    elif paradigm == "P2":
                        if tn in P2_CHECKPOINTS:
                            score_note = "checkpoint (scored)"
                        else:
                            is_scored = False
                            score_note = "non-checkpoint (not scored)"
                    elif paradigm == "P3":
                        score_note = "P3 (LLM-judged)"

                    hits.append({
                        "model": model,
                        "scenario_id": sid,
                        "paradigm": paradigm,
                        "turn_number": tn,
                        "output_tokens": out_tok,
                        "ceiling": ceiling,
                        "is_scored": is_scored,
                        "score_note": score_note,
                        "response_preview": turn.get("response", "")[-200:],
                    })

    # Print summary
    print(f"\n{'='*70}")
    print(f"CEILING HITS: {len(hits)} total")
    print(f"{'='*70}")

    for model in ["claude-sonnet-4.5", "minimax-m2.5"]:
        model_hits = [h for h in hits if h["model"] == model]
        scored_hits = [h for h in model_hits if h["is_scored"]]
        print(f"\n{model}: {len(model_hits)} ceiling hits, "
              f"{len(scored_hits)} on scored turns")

        by_paradigm = defaultdict(list)
        for h in model_hits:
            by_paradigm[h["paradigm"]].append(h)

        for p in sorted(by_paradigm):
            p_hits = by_paradigm[p]
            p_scored = [h for h in p_hits if h["is_scored"]]
            print(f"  {p}: {len(p_hits)} hits, {len(p_scored)} scored")
            for h in p_hits:
                truncated = "TRUNCATED?" if h["response_preview"].rstrip()[-1] not in ".!?:)\"]'" else "likely complete"
                print(f"    {h['scenario_id']} T{h['turn_number']:2d} "
                      f"({h['output_tokens']} tok) [{h['score_note']}] "
                      f"— ends: ...{h['response_preview'][-80:].strip()}")

    # Write output
    with open(args.output, "w") as f:
        json.dump({
            "total_hits": len(hits),
            "summary": {
                model: {
                    "total": len([h for h in hits if h["model"] == model]),
                    "scored": len([h for h in hits if h["model"] == model and h["is_scored"]]),
                    "not_scored": len([h for h in hits if h["model"] == model and not h["is_scored"]]),
                }
                for model in ["claude-sonnet-4.5", "minimax-m2.5"]
            },
            "hits": hits,
        }, f, indent=2, ensure_ascii=False)
    print(f"\nOutput: {args.output}")


if __name__ == "__main__":
    main()
