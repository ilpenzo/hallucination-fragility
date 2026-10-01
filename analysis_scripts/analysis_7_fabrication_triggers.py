#!/usr/bin/env python3
"""
Analysis 7: P3 Fabrication Trigger Analysis

Systematic analysis of what scenario properties predict fabrication.
Examines: domain, difficulty, authority direction, document count,
token count, gap type/description, and the "why_plausible" field.

Cross-references P3 judged results with scenario source data.

Reads:
  - p3_source_data.json (scenario metadata + gap descriptions)
  - ./results/p3_judged/individual/*.json (per-model judged results)
Outputs: analysis_7_fabrication_triggers.json

Usage:
  python analysis_7_fabrication_triggers.py \
      --p3-source ./p3_source_data.json \
      --p3-judged-dir ./results/p3_judged/individual \
      --output analysis_7_fabrication_triggers.json
"""

import json
import argparse
import os
from collections import defaultdict


def load_p3_source(path):
    """Load scenario metadata."""
    with open(path, "r") as f:
        data = json.load(f)
    return {s["scenario_id"]: s for s in data["scenarios"]}


def load_p3_judged(judged_dir):
    """Load all individual P3 judged results."""
    results = []
    if not os.path.isdir(judged_dir):
        print(f"WARNING: {judged_dir} not found")
        return results

    for fname in sorted(os.listdir(judged_dir)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(judged_dir, fname)
        try:
            with open(fpath, "r") as f:
                data = json.load(f)
            if data.get("success"):
                results.append(data)
        except (json.JSONDecodeError, KeyError):
            pass

    return results


def build_fabrication_matrix(judged_results, source_data):
    """
    Build a scenario × model matrix of fabrication outcomes.
    For each gap in each scenario, records whether each model fabricated.
    """
    # Structure: {scenario_id: {model: {gap_id: {fabricated, abstained, details}}}}
    matrix = defaultdict(lambda: defaultdict(dict))

    for result in judged_results:
        scenario_id = result["scenario_id"]
        model = result["model"]
        gap_scores = result.get("gap_scores", {})

        for gap_id, gs in gap_scores.items():
            matrix[scenario_id][model][gap_id] = {
                "fabricated": bool(gs.get("fabricated", False)),
                "abstained": float(gs.get("abstained", 0.0)),
                "fabrication_detail": gs.get("fabrication_detail", ""),
            }

    return matrix


def analyze_by_scenario_properties(matrix, source_data, judged_results):
    """
    For each scenario property, compute fabrication rates.
    """
    # Gather all models
    all_models = sorted(set(r["model"] for r in judged_results))

    # Per-scenario fabrication summary
    scenario_fab_summary = {}
    for scenario_id in sorted(matrix.keys()):
        source = source_data.get(scenario_id, {})
        n_models_fabricated = 0
        models_that_fabricated = []
        models_that_abstained = []

        for model in all_models:
            model_gaps = matrix[scenario_id].get(model, {})
            any_fabricated = any(g["fabricated"] for g in model_gaps.values())
            if any_fabricated:
                n_models_fabricated += 1
                models_that_fabricated.append(model)
            else:
                models_that_abstained.append(model)

        scenario_fab_summary[scenario_id] = {
            "domain": source.get("domain", "unknown"),
            "difficulty": source.get("difficulty", "unknown"),
            "authority_correct": source.get("authority_correct"),
            "n_documents": source.get("n_documents"),
            "total_tokens_approx": source.get("total_tokens_approx"),
            "n_models_tested": len(all_models),
            "n_models_fabricated": n_models_fabricated,
            "fabrication_rate_across_models": round(
                n_models_fabricated / len(all_models), 3
            ) if all_models else 0,
            "models_fabricated": models_that_fabricated,
            "models_abstained": models_that_abstained,
            # Gap info
            "gap_descriptions": [
                g["description"] for g in source.get("planted_gaps", [])
            ],
            "gap_why_plausible": [
                g["why_plausible"] for g in source.get("planted_gaps", [])
            ],
        }

    # Aggregate by domain
    by_domain = defaultdict(lambda: {"n_scenarios": 0, "total_fabrications": 0,
                                      "total_opportunities": 0, "scenarios": []})
    for sid, s in scenario_fab_summary.items():
        domain = s["domain"]
        by_domain[domain]["n_scenarios"] += 1
        by_domain[domain]["total_fabrications"] += s["n_models_fabricated"]
        by_domain[domain]["total_opportunities"] += s["n_models_tested"]
        by_domain[domain]["scenarios"].append(sid)

    domain_fab_rates = {}
    for domain in sorted(by_domain.keys()):
        d = by_domain[domain]
        domain_fab_rates[domain] = {
            "n_scenarios": d["n_scenarios"],
            "fabrication_rate": round(
                d["total_fabrications"] / d["total_opportunities"], 4
            ) if d["total_opportunities"] > 0 else 0,
            "total_fabrications": d["total_fabrications"],
            "total_opportunities": d["total_opportunities"],
            "scenarios": d["scenarios"],
        }

    # Aggregate by difficulty
    by_difficulty = defaultdict(lambda: {"n": 0, "fab": 0, "opp": 0})
    for sid, s in scenario_fab_summary.items():
        diff = s["difficulty"]
        by_difficulty[diff]["n"] += 1
        by_difficulty[diff]["fab"] += s["n_models_fabricated"]
        by_difficulty[diff]["opp"] += s["n_models_tested"]

    difficulty_fab_rates = {}
    for diff in sorted(by_difficulty.keys()):
        d = by_difficulty[diff]
        difficulty_fab_rates[diff] = {
            "n_scenarios": d["n"],
            "fabrication_rate": round(d["fab"] / d["opp"], 4) if d["opp"] > 0 else 0,
            "total_fabrications": d["fab"],
            "total_opportunities": d["opp"],
        }

    # Aggregate by authority direction
    by_auth = defaultdict(lambda: {"n": 0, "fab": 0, "opp": 0})
    for sid, s in scenario_fab_summary.items():
        auth_key = "authority_correct" if s["authority_correct"] else "authority_wrong"
        by_auth[auth_key]["n"] += 1
        by_auth[auth_key]["fab"] += s["n_models_fabricated"]
        by_auth[auth_key]["opp"] += s["n_models_tested"]

    auth_fab_rates = {}
    for auth_key in sorted(by_auth.keys()):
        d = by_auth[auth_key]
        auth_fab_rates[auth_key] = {
            "n_scenarios": d["n"],
            "fabrication_rate": round(d["fab"] / d["opp"], 4) if d["opp"] > 0 else 0,
        }

    # Aggregate by n_documents
    by_ndocs = defaultdict(lambda: {"n": 0, "fab": 0, "opp": 0})
    for sid, s in scenario_fab_summary.items():
        ndocs = s["n_documents"]
        by_ndocs[ndocs]["n"] += 1
        by_ndocs[ndocs]["fab"] += s["n_models_fabricated"]
        by_ndocs[ndocs]["opp"] += s["n_models_tested"]

    ndocs_fab_rates = {}
    for ndocs in sorted(by_ndocs.keys()):
        d = by_ndocs[ndocs]
        ndocs_fab_rates[int(ndocs)] = {
            "n_scenarios": d["n"],
            "fabrication_rate": round(d["fab"] / d["opp"], 4) if d["opp"] > 0 else 0,
        }

    # Per-model fabrication profile
    model_profiles = {}
    for model in all_models:
        scenarios_fabricated = []
        scenarios_clean = []
        for sid in sorted(matrix.keys()):
            model_gaps = matrix[sid].get(model, {})
            if any(g["fabricated"] for g in model_gaps.values()):
                scenarios_fabricated.append(sid)
            else:
                scenarios_clean.append(sid)

        n_total = len(scenarios_fabricated) + len(scenarios_clean)
        model_profiles[model] = {
            "n_scenarios": n_total,
            "n_fabricated": len(scenarios_fabricated),
            "fabrication_rate": round(
                len(scenarios_fabricated) / n_total, 4
            ) if n_total > 0 else 0,
            "scenarios_fabricated": scenarios_fabricated,
            "fabrication_details": {},
        }
        # Add fabrication details for failed scenarios
        for sid in scenarios_fabricated:
            model_gaps = matrix[sid].get(model, {})
            for gap_id, g in model_gaps.items():
                if g["fabricated"]:
                    source = source_data.get(sid, {})
                    gap_info = None
                    for pg in source.get("planted_gaps", []):
                        if pg["gap_id"] == gap_id:
                            gap_info = pg
                            break

                    model_profiles[model]["fabrication_details"][f"{sid}_{gap_id}"] = {
                        "scenario_domain": source.get("domain"),
                        "scenario_difficulty": source.get("difficulty"),
                        "gap_description": gap_info["description"] if gap_info else "unknown",
                        "why_plausible": gap_info["why_plausible"] if gap_info else "unknown",
                        "fabrication_detail": g["fabrication_detail"],
                    }

    return {
        "per_scenario": scenario_fab_summary,
        "by_domain": domain_fab_rates,
        "by_difficulty": difficulty_fab_rates,
        "by_authority_direction": auth_fab_rates,
        "by_n_documents": ndocs_fab_rates,
        "per_model": model_profiles,
    }


def compute_scenario_vulnerability_score(scenario_fab_summary):
    """
    Rank scenarios by how many models they tripped up.
    A scenario that triggers fabrication in 3/5 models is more
    "universally tricky" than one that only trips 1 model.
    """
    ranked = sorted(
        scenario_fab_summary.items(),
        key=lambda x: x[1]["n_models_fabricated"],
        reverse=True
    )

    return [
        {
            "scenario_id": sid,
            "n_models_fabricated": s["n_models_fabricated"],
            "fabrication_rate": s["fabrication_rate_across_models"],
            "domain": s["domain"],
            "difficulty": s["difficulty"],
            "gap_descriptions": s["gap_descriptions"],
            "gap_why_plausible": s["gap_why_plausible"],
            "models_fabricated": s["models_fabricated"],
        }
        for sid, s in ranked
    ]


def compute_co_occurrence(matrix, source_data):
    """
    Which pairs of models tend to fabricate on the SAME scenarios?
    High co-occurrence suggests the scenario is universally tricky.
    Low co-occurrence suggests model-specific vulnerabilities.
    """
    all_models = sorted(set(
        model for sid in matrix for model in matrix[sid]
    ))

    # Build per-model fabrication sets
    model_fab_sets = {}
    for model in all_models:
        fab_scenarios = set()
        for sid in matrix:
            model_gaps = matrix[sid].get(model, {})
            if any(g["fabricated"] for g in model_gaps.values()):
                fab_scenarios.add(sid)
        model_fab_sets[model] = fab_scenarios

    # Pairwise co-occurrence
    pairwise = {}
    for i, m1 in enumerate(all_models):
        for m2 in all_models[i + 1:]:
            shared_fab = model_fab_sets[m1] & model_fab_sets[m2]
            either_fab = model_fab_sets[m1] | model_fab_sets[m2]
            jaccard = (
                len(shared_fab) / len(either_fab)
                if len(either_fab) > 0
                else 0
            )
            pairwise[f"{m1} × {m2}"] = {
                "shared_fabrications": sorted(shared_fab),
                "n_shared": len(shared_fab),
                "jaccard_similarity": round(jaccard, 4),
                f"{m1}_only": sorted(model_fab_sets[m1] - model_fab_sets[m2]),
                f"{m2}_only": sorted(model_fab_sets[m2] - model_fab_sets[m1]),
            }

    return {
        "per_model_fabrication_sets": {
            m: sorted(s) for m, s in model_fab_sets.items()
        },
        "pairwise_co_occurrence": pairwise,
    }


def main():
    parser = argparse.ArgumentParser(description="P3 Fabrication Trigger Analysis")
    parser.add_argument("--p3-source", required=True,
                        help="Path to p3_source_data.json")
    parser.add_argument("--p3-judged-dir", required=True,
                        help="Path to p3_judged/individual/ directory")
    parser.add_argument("--output", default="analysis_7_fabrication_triggers.json",
                        help="Output JSON path")
    args = parser.parse_args()

    print(f"Loading P3 source data from {args.p3_source}...")
    source_data = load_p3_source(args.p3_source)
    print(f"  Found {len(source_data)} scenarios")

    print(f"Loading P3 judged results from {args.p3_judged_dir}...")
    judged_results = load_p3_judged(args.p3_judged_dir)
    print(f"  Found {len(judged_results)} judged entries")

    print("\nBuilding fabrication matrix...")
    matrix = build_fabrication_matrix(judged_results, source_data)

    print("\n=== Fabrication by Scenario Properties ===")
    property_analysis = analyze_by_scenario_properties(matrix, source_data, judged_results)

    print("\nBy domain:")
    for domain, stats in sorted(property_analysis["by_domain"].items()):
        print(f"  {domain:30s}: rate={stats['fabrication_rate']:.3f} "
              f"({stats['total_fabrications']}/{stats['total_opportunities']}) "
              f"across {stats['n_scenarios']} scenarios")

    print("\nBy difficulty:")
    for diff, stats in sorted(property_analysis["by_difficulty"].items()):
        print(f"  {diff:10s}: rate={stats['fabrication_rate']:.3f} "
              f"({stats['total_fabrications']}/{stats['total_opportunities']})")

    print("\nBy authority direction:")
    for auth, stats in property_analysis["by_authority_direction"].items():
        print(f"  {auth:20s}: rate={stats['fabrication_rate']:.3f} "
              f"(n={stats['n_scenarios']})")

    print("\nBy number of documents:")
    for ndocs, stats in sorted(property_analysis["by_n_documents"].items()):
        print(f"  {ndocs} docs: rate={stats['fabrication_rate']:.3f} "
              f"(n={stats['n_scenarios']})")

    print("\n=== Scenario Vulnerability Ranking ===")
    vulnerability = compute_scenario_vulnerability_score(
        property_analysis["per_scenario"]
    )
    for v in vulnerability:
        if v["n_models_fabricated"] > 0:
            print(f"  {v['scenario_id']} ({v['domain']}, {v['difficulty']}): "
                  f"{v['n_models_fabricated']} models fabricated")
            print(f"    Gap: {v['gap_descriptions']}")
            print(f"    Why plausible: {v['gap_why_plausible']}")
            print(f"    Models: {v['models_fabricated']}")

    print("\n=== Model Fabrication Profiles ===")
    for model, profile in sorted(property_analysis["per_model"].items()):
        print(f"\n  {model}: {profile['n_fabricated']}/{profile['n_scenarios']} "
              f"scenarios (rate={profile['fabrication_rate']:.3f})")
        for detail_key, detail in profile["fabrication_details"].items():
            print(f"    {detail_key}: {detail['gap_description']}")
            if detail.get("fabrication_detail"):
                # Truncate for console display
                fd = detail["fabrication_detail"]
                if len(fd) > 120:
                    fd = fd[:120] + "..."
                print(f"      Detail: {fd}")

    print("\n=== Co-occurrence Analysis ===")
    co_occurrence = compute_co_occurrence(matrix, source_data)

    for pair, stats in co_occurrence["pairwise_co_occurrence"].items():
        if stats["n_shared"] > 0 or True:  # show all pairs
            print(f"  {pair}: shared={stats['n_shared']}, "
                  f"jaccard={stats['jaccard_similarity']}")

    # Save
    output = {
        "analysis": "P3 Fabrication Trigger Analysis",
        "description": (
            "Examines what scenario properties predict fabrication across models. "
            "Key question: is fabrication primarily a property of the scenario "
            "(epistemic situation) or the model?"
        ),
        "property_analysis": property_analysis,
        "scenario_vulnerability_ranking": vulnerability,
        "co_occurrence": co_occurrence,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
