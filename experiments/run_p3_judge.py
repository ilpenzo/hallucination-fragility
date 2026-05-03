#!/usr/bin/env python3
"""
run_p3_judge.py — P3 LLM-as-Judge Runner
Context-Dependent Hallucination in Frontier LLMs

Sends pre-generated judge prompts to Claude Opus (or configurable model) via
the Anthropic API. Uses async concurrency for fast completion (~10-15 min for 80 calls).

Features:
  - Async concurrent API calls (configurable concurrency limit)
  - Resume logic: skips already-judged entries
  - Exponential backoff retries on rate limits / transient errors
  - JSON response parsing with regex fallback
  - Per-entry results saved individually + aggregate summary
  - Safe JSON serialization (handles floats, booleans, None)
  - Cost tracking

Usage:
  # Default: Opus 4.6, concurrency=5
  python run_p3_judge.py --input-dir ./results/scored_full --output-dir ./results/p3_judged

  # Use Sonnet 4.6 as cheaper fallback
  python run_p3_judge.py --input-dir ./results/scored_full --output-dir ./results/p3_judged \
      --model claude-sonnet-4-6

  # Dry run (no API calls, tests parsing pipeline)
  python run_p3_judge.py --input-dir ./results/scored_full --output-dir ./results/p3_judged --dry-run

  # Higher concurrency (check your rate limits)
  python run_p3_judge.py --input-dir ./results/scored_full --output-dir ./results/p3_judged --concurrency 10

Dependencies:
  pip install anthropic
"""

import os
import sys
import json
import re
import time
import asyncio
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

# ==============================================================================
# CONFIGURATION
# ==============================================================================

VERSION = "1.0.0"

# Model defaults
DEFAULT_MODEL = "claude-opus-4-6"
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TEMPERATURE = 0.0

# Concurrency and retry settings
DEFAULT_CONCURRENCY = 5
MAX_RETRIES = 5
INITIAL_BACKOFF_S = 5

# Pricing per million tokens (USD) — for cost estimation
MODEL_PRICING = {
    "claude-opus-4-6":            {"input": 5.00, "output": 25.00},
    "claude-opus-4-5-20251101":   {"input": 5.00, "output": 25.00},
    "claude-sonnet-4-6":          {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
}


# ==============================================================================
# JSON PARSING
# ==============================================================================

def extract_json_from_response(text: str) -> Optional[Dict]:
    """
    Parse JSON from model response. Tries multiple strategies:
    1. Direct JSON parse of full text
    2. Extract JSON block from markdown code fences
    3. Find first { ... } block via brace matching
    """
    text = text.strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Markdown code fence extraction
    # Matches ```json ... ``` or ``` ... ```
    fence_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    fence_matches = re.findall(fence_pattern, text, re.DOTALL)
    for match in fence_matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Strategy 3: Brace matching — find outermost { ... }
    start = text.find('{')
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                candidate = text[start:i+1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None

    return None


def validate_judge_output(parsed: Dict) -> Dict[str, Any]:
    """
    Validate and normalize the judge output against expected schema.
    Returns a dict with 'valid' bool and 'warnings' list.
    """
    warnings = []

    # Check top-level keys
    expected_keys = {"contradiction_scores", "gap_scores", "authority_bias"}
    actual_keys = set(parsed.keys())
    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys

    if missing:
        warnings.append(f"Missing top-level keys: {missing}")
    if extra:
        warnings.append(f"Extra top-level keys (ignored): {extra}")

    # Validate contradiction_scores
    cs = parsed.get("contradiction_scores", {})
    if isinstance(cs, list):
        # Some models may return a list instead of dict — convert
        cs_dict = {}
        for i, entry in enumerate(cs):
            cs_dict[f"C{i+1}"] = entry
        parsed["contradiction_scores"] = cs_dict
        warnings.append("contradiction_scores was a list, converted to dict")
        cs = cs_dict

    for cid, scores in cs.items():
        for field in ["identified", "resolved_correctly", "reasoning_quality"]:
            val = scores.get(field)
            if val is None:
                warnings.append(f"{cid}.{field} missing, defaulting to 0.0")
                scores[field] = 0.0
            elif not isinstance(val, (int, float)):
                warnings.append(f"{cid}.{field} is {type(val).__name__}, not float")

    # Validate gap_scores
    gs = parsed.get("gap_scores", {})
    if isinstance(gs, list):
        gs_dict = {}
        for i, entry in enumerate(gs):
            gs_dict[f"G{i+1}"] = entry
        parsed["gap_scores"] = gs_dict
        warnings.append("gap_scores was a list, converted to dict")
        gs = gs_dict

    for gid, scores in gs.items():
        if "abstained" not in scores:
            warnings.append(f"{gid}.abstained missing, defaulting to 0.0")
            scores["abstained"] = 0.0
        if "fabricated" not in scores:
            warnings.append(f"{gid}.fabricated missing, defaulting to False")
            scores["fabricated"] = False
        if "fabrication_detail" not in scores:
            scores["fabrication_detail"] = ""

    # Validate authority_bias
    ab = parsed.get("authority_bias", {})
    if "deferred_to_authority" not in ab:
        warnings.append("authority_bias.deferred_to_authority missing")
        ab["deferred_to_authority"] = None
    if "cited_evidence" not in ab:
        ab["cited_evidence"] = None
    if "reasoning_note" not in ab:
        ab["reasoning_note"] = ""
    parsed["authority_bias"] = ab

    return {
        "valid": len(missing) == 0,
        "warnings": warnings,
        "parsed": parsed,
    }


# ==============================================================================
# SAFE JSON SERIALIZATION
# ==============================================================================

def ensure_json_serializable(obj):
    """Recursively convert non-serializable types for JSON output."""
    if isinstance(obj, dict):
        return {k: ensure_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [ensure_json_serializable(item) for item in obj]
    elif isinstance(obj, float):
        if obj != obj:  # NaN
            return None
        if obj == float('inf') or obj == float('-inf'):
            return None
        return obj
    elif isinstance(obj, (bool, int, str)) or obj is None:
        return obj
    else:
        return str(obj)


# ==============================================================================
# ASYNC API CALLER
# ==============================================================================

async def call_judge_api(
    client,
    prompt: str,
    model: str,
    entry_id: str,
    semaphore: asyncio.Semaphore,
    max_retries: int = MAX_RETRIES,
) -> Dict[str, Any]:
    """
    Send a single judge prompt to the Anthropic API with retry logic.
    Returns dict with response text, usage, timing, and any errors.
    """
    async with semaphore:
        for attempt in range(max_retries):
            try:
                t0 = time.monotonic()
                response = await client.messages.create(
                    model=model,
                    max_tokens=DEFAULT_MAX_TOKENS,
                    temperature=DEFAULT_TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}],
                )
                elapsed = time.monotonic() - t0

                text = response.content[0].text if response.content else ""
                usage = response.usage

                return {
                    "success": True,
                    "text": text,
                    "input_tokens": usage.input_tokens if usage else 0,
                    "output_tokens": usage.output_tokens if usage else 0,
                    "elapsed_s": round(elapsed, 2),
                    "attempts": attempt + 1,
                    "error": None,
                }

            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = any(k in err_str for k in
                                    ["rate_limit", "rate limit", "429",
                                     "too many requests", "quota"])
                is_transient = any(k in err_str for k in
                                   ["timeout", "500", "502", "503",
                                    "overloaded", "connection", "server_error"])

                if is_rate_limit:
                    wait = INITIAL_BACKOFF_S * (2 ** attempt)
                    print(f"    [{entry_id}] Rate limited. Waiting {wait:.0f}s "
                          f"(attempt {attempt+1}/{max_retries})...")
                    await asyncio.sleep(wait)
                elif is_transient or attempt < max_retries - 1:
                    wait = 5 * (2 ** attempt)
                    print(f"    [{entry_id}] {type(e).__name__}: {str(e)[:100]}. "
                          f"Retrying in {wait:.0f}s (attempt {attempt+1}/{max_retries})...")
                    await asyncio.sleep(wait)
                else:
                    return {
                        "success": False,
                        "text": "",
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "elapsed_s": 0,
                        "attempts": attempt + 1,
                        "error": f"{type(e).__name__}: {str(e)[:200]}",
                    }

        return {
            "success": False,
            "text": "",
            "input_tokens": 0,
            "output_tokens": 0,
            "elapsed_s": 0,
            "attempts": max_retries,
            "error": f"Failed after {max_retries} retries",
        }


# ==============================================================================
# PROCESS A SINGLE ENTRY
# ==============================================================================

async def process_entry(
    client,
    entry: Dict,
    prompts_dir: str,
    output_dir: str,
    model: str,
    semaphore: asyncio.Semaphore,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Process a single P3 judge entry:
    1. Read the judge prompt file
    2. Call the API (or mock in dry run)
    3. Parse and validate the JSON response
    4. Save the individual result
    """
    scenario_id = entry["scenario_id"]
    tested_model = entry["model"]
    entry_id = f"{scenario_id}_{tested_model}"
    prompt_file = entry["judge_prompt_file"]
    prompt_path = os.path.join(prompts_dir, prompt_file)

    # Read the judge prompt
    if not os.path.exists(prompt_path):
        return {
            "entry_id": entry_id,
            "scenario_id": scenario_id,
            "model": tested_model,
            "success": False,
            "error": f"Prompt file not found: {prompt_path}",
        }

    with open(prompt_path, "r") as f:
        prompt = f.read()

    prompt_chars = len(prompt)
    print(f"  [{entry_id}] Sending prompt ({prompt_chars:,} chars)...", end="", flush=True)

    # API call (or dry run)
    if dry_run:
        api_result = {
            "success": True,
            "text": json.dumps({
                "contradiction_scores": {"C1": {"identified": 0.5, "resolved_correctly": 0.5, "reasoning_quality": 0.5}},
                "gap_scores": {"G1": {"abstained": 0.5, "fabricated": False, "fabrication_detail": ""}},
                "authority_bias": {"deferred_to_authority": False, "cited_evidence": True, "reasoning_note": "dry run"}
            }),
            "input_tokens": 0,
            "output_tokens": 0,
            "elapsed_s": 0.0,
            "attempts": 0,
            "error": None,
        }
    else:
        api_result = await call_judge_api(
            client, prompt, model, entry_id, semaphore
        )

    if not api_result["success"]:
        print(f" FAILED ({api_result['error']})")
        return {
            "entry_id": entry_id,
            "scenario_id": scenario_id,
            "model": tested_model,
            "success": False,
            "error": api_result["error"],
            "attempts": api_result["attempts"],
        }

    # Parse JSON response
    parsed = extract_json_from_response(api_result["text"])

    if parsed is None:
        print(f" PARSE FAILED")
        # Save raw response for debugging
        raw_path = os.path.join(output_dir, "raw_failures", f"{entry_id}_raw.txt")
        os.makedirs(os.path.dirname(raw_path), exist_ok=True)
        with open(raw_path, "w") as f:
            f.write(api_result["text"])

        return {
            "entry_id": entry_id,
            "scenario_id": scenario_id,
            "model": tested_model,
            "success": False,
            "error": "JSON parse failed — raw response saved",
            "raw_file": f"{entry_id}_raw.txt",
            "input_tokens": api_result["input_tokens"],
            "output_tokens": api_result["output_tokens"],
            "elapsed_s": api_result["elapsed_s"],
        }

    # Validate
    validation = validate_judge_output(parsed)
    judge_scores = validation["parsed"]

    elapsed = api_result["elapsed_s"]
    tokens_in = api_result["input_tokens"]
    tokens_out = api_result["output_tokens"]
    warns = len(validation["warnings"])
    print(f" OK ({elapsed:.1f}s, {tokens_in}+{tokens_out} tok"
          f"{f', {warns} warnings' if warns else ''})")

    # Build result
    result = {
        "entry_id": entry_id,
        "scenario_id": scenario_id,
        "model": tested_model,
        "paradigm": "P3",
        "judge_model": model,
        "success": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        # Metadata from input
        "authority_correct": entry.get("authority_correct"),
        "topic": entry.get("topic"),
        "domain": entry.get("domain"),
        "difficulty": entry.get("difficulty"),
        "n_contradictions": entry.get("n_contradictions"),
        "n_gaps": entry.get("n_gaps"),
        # Judge scores
        "contradiction_scores": judge_scores.get("contradiction_scores", {}),
        "gap_scores": judge_scores.get("gap_scores", {}),
        "authority_bias": judge_scores.get("authority_bias", {}),
        # Validation
        "validation_warnings": validation["warnings"],
        # Usage
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "elapsed_s": elapsed,
        "attempts": api_result["attempts"],
    }

    # Save individual result
    result_path = os.path.join(output_dir, "individual", f"{entry_id}.json")
    os.makedirs(os.path.dirname(result_path), exist_ok=True)
    serializable = ensure_json_serializable(result)
    with open(result_path, "w") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)

    return result


# ==============================================================================
# AGGREGATE SUMMARY
# ==============================================================================

def compute_aggregate(results: List[Dict], model_used: str) -> Dict:
    """Compute aggregate statistics across all judged entries."""
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    if not successful:
        return {"error": "No successful results to aggregate"}

    # Per tested-model aggregation
    by_model = {}
    for r in successful:
        m = r["model"]
        if m not in by_model:
            by_model[m] = []
        by_model[m].append(r)

    model_summaries = {}
    for m, entries in sorted(by_model.items()):
        # Contradiction scores
        all_identified = []
        all_resolved = []
        all_reasoning = []
        for e in entries:
            for cid, cs in e.get("contradiction_scores", {}).items():
                all_identified.append(cs.get("identified", 0.0))
                all_resolved.append(cs.get("resolved_correctly", 0.0))
                all_reasoning.append(cs.get("reasoning_quality", 0.0))

        # Gap scores
        all_abstained = []
        all_fabricated = []
        for e in entries:
            for gid, gs in e.get("gap_scores", {}).items():
                all_abstained.append(gs.get("abstained", 0.0))
                all_fabricated.append(1.0 if gs.get("fabricated") else 0.0)

        # Authority bias
        deferred_count = sum(
            1 for e in entries
            if e.get("authority_bias", {}).get("deferred_to_authority") is True
        )
        cited_count = sum(
            1 for e in entries
            if e.get("authority_bias", {}).get("cited_evidence") is True
        )

        # Authority-correct vs authority-wrong split
        auth_correct = [e for e in entries if e.get("authority_correct") is True]
        auth_wrong = [e for e in entries if e.get("authority_correct") is False]

        def _safe_mean(lst):
            return round(sum(lst) / len(lst), 4) if lst else None

        model_summaries[m] = {
            "n_entries": len(entries),
            "contradiction_identified": _safe_mean(all_identified),
            "contradiction_resolved": _safe_mean(all_resolved),
            "contradiction_reasoning": _safe_mean(all_reasoning),
            "gap_abstained": _safe_mean(all_abstained),
            "fabrication_rate": _safe_mean(all_fabricated),
            "authority_deferred_rate": round(deferred_count / len(entries), 4) if entries else None,
            "authority_cited_rate": round(cited_count / len(entries), 4) if entries else None,
            "n_authority_correct": len(auth_correct),
            "n_authority_wrong": len(auth_wrong),
        }

    # Token usage
    total_input = sum(r.get("input_tokens", 0) for r in successful)
    total_output = sum(r.get("output_tokens", 0) for r in successful)
    pricing = MODEL_PRICING.get(model_used, {"input": 5.0, "output": 25.0})
    est_cost = (total_input / 1_000_000 * pricing["input"] +
                total_output / 1_000_000 * pricing["output"])

    return {
        "judge_model": model_used,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_total": len(results),
        "n_successful": len(successful),
        "n_failed": len(failed),
        "failed_entries": [{"entry_id": r.get("entry_id"), "error": r.get("error")}
                           for r in failed],
        "model_summaries": model_summaries,
        "token_usage": {
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "estimated_cost_usd": round(est_cost, 4),
        },
    }


# ==============================================================================
# MAIN
# ==============================================================================

async def run_judge(args):
    """Main async entry point."""
    input_dir = args.input_dir
    output_dir = args.output_dir
    model = args.model
    concurrency = args.concurrency
    dry_run = args.dry_run
    limit = args.limit

    # Load judge inputs
    inputs_path = os.path.join(input_dir, "p3_judge_inputs.json")
    if not os.path.exists(inputs_path):
        print(f"ERROR: {inputs_path} not found")
        sys.exit(1)

    with open(inputs_path, "r") as f:
        judge_inputs = json.load(f)

    prompts_dir = os.path.join(input_dir, "p3_judge_prompts")
    if not os.path.isdir(prompts_dir):
        print(f"ERROR: {prompts_dir} not found")
        sys.exit(1)

    print(f"{'='*60}")
    print(f"P3 Judge Runner v{VERSION}")
    print(f"{'='*60}")
    print(f"  Judge model:  {model}")
    print(f"  Entries:      {len(judge_inputs)}")
    print(f"  Concurrency:  {concurrency}")
    print(f"  Dry run:      {dry_run}")
    print(f"  Output dir:   {output_dir}")

    # Resume logic: check which entries are already judged
    individual_dir = os.path.join(output_dir, "individual")
    os.makedirs(individual_dir, exist_ok=True)

    already_done = set()
    if os.path.isdir(individual_dir):
        for fname in os.listdir(individual_dir):
            if fname.endswith(".json"):
                try:
                    fpath = os.path.join(individual_dir, fname)
                    with open(fpath, "r") as f:
                        existing = json.load(f)
                    if existing.get("success"):
                        already_done.add(existing.get("entry_id"))
                except (json.JSONDecodeError, KeyError):
                    pass

    # Filter to entries that still need processing
    to_process = []
    for entry in judge_inputs:
        entry_id = f"{entry['scenario_id']}_{entry['model']}"
        if entry_id in already_done:
            continue
        to_process.append(entry)

    if already_done:
        print(f"  Resuming:     {len(already_done)} already done, "
              f"{len(to_process)} remaining")

    if limit and limit < len(to_process):
        to_process = to_process[:limit]
        print(f"  Limited to:   {limit} entries")

    if not to_process:
        print("\n  All entries already judged! Nothing to do.")
        print(f"  Re-run with --force to re-judge all entries.")
        # Still compute aggregate from existing results
        all_results = []
        for fname in os.listdir(individual_dir):
            if fname.endswith(".json"):
                fpath = os.path.join(individual_dir, fname)
                with open(fpath, "r") as f:
                    all_results.append(json.load(f))
        if all_results:
            aggregate = compute_aggregate(all_results, model)
            _save_and_print_aggregate(aggregate, output_dir)
        return

    # Initialize Anthropic async client
    if not dry_run:
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            print("ERROR: anthropic package not installed. Run: pip install anthropic")
            sys.exit(1)

        client = AsyncAnthropic()  # Uses ANTHROPIC_API_KEY env var
    else:
        client = None

    # Process all entries concurrently
    semaphore = asyncio.Semaphore(concurrency)
    t_start = time.monotonic()

    print(f"\n--- Processing {len(to_process)} entries ---\n")

    tasks = [
        process_entry(
            client, entry, prompts_dir, output_dir,
            model, semaphore, dry_run
        )
        for entry in to_process
    ]

    new_results = await asyncio.gather(*tasks)

    t_total = time.monotonic() - t_start
    print(f"\n--- Completed in {t_total:.1f}s ---")

    # Load all results (including previously completed)
    all_results = list(new_results)
    for fname in os.listdir(individual_dir):
        if fname.endswith(".json"):
            entry_id = fname.replace(".json", "")
            # Don't double-count entries we just processed
            if any(r.get("entry_id") == entry_id for r in new_results if r.get("success")):
                continue
            fpath = os.path.join(individual_dir, fname)
            try:
                with open(fpath, "r") as f:
                    all_results.append(json.load(f))
            except (json.JSONDecodeError, KeyError):
                pass

    # Compute and save aggregate
    aggregate = compute_aggregate(all_results, model)
    _save_and_print_aggregate(aggregate, output_dir)


def _save_and_print_aggregate(aggregate: Dict, output_dir: str):
    """Save aggregate summary and print to console."""
    # Save aggregate
    agg_path = os.path.join(output_dir, "p3_judge_aggregate.json")
    serializable = ensure_json_serializable(aggregate)
    with open(agg_path, "w") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)

    # Also save a flat CSV-friendly summary
    csv_rows = []
    for m, summary in aggregate.get("model_summaries", {}).items():
        row = {"model": m}
        row.update(summary)
        csv_rows.append(row)

    if csv_rows:
        csv_path = os.path.join(output_dir, "p3_judge_summary.csv")
        import csv
        fieldnames = list(csv_rows[0].keys())
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)

    # Print summary
    print(f"\n{'='*60}")
    print("P3 JUDGE RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  Total: {aggregate['n_total']} | "
          f"Success: {aggregate['n_successful']} | "
          f"Failed: {aggregate['n_failed']}")

    usage = aggregate.get("token_usage", {})
    print(f"  Tokens: {usage.get('total_input_tokens', 0):,} input + "
          f"{usage.get('total_output_tokens', 0):,} output")
    print(f"  Estimated cost: ${usage.get('estimated_cost_usd', 0):.2f}")

    print(f"\n  Per-Model Results:")
    print(f"  {'Model':<22} {'Contr.ID':>8} {'Contr.Res':>9} {'Reasoning':>9} "
          f"{'Gap.Abst':>8} {'Fabr.Rate':>9} {'Auth.Def':>8} {'n':>4}")
    print(f"  {'-'*22} {'-'*8} {'-'*9} {'-'*9} {'-'*8} {'-'*9} {'-'*8} {'-'*4}")

    for m, s in sorted(aggregate.get("model_summaries", {}).items()):
        def _fmt(v):
            return f"{v:.3f}" if v is not None else "  N/A"

        print(f"  {m:<22} {_fmt(s['contradiction_identified']):>8} "
              f"{_fmt(s['contradiction_resolved']):>9} "
              f"{_fmt(s['contradiction_reasoning']):>9} "
              f"{_fmt(s['gap_abstained']):>8} "
              f"{_fmt(s['fabrication_rate']):>9} "
              f"{_fmt(s['authority_deferred_rate']):>8} "
              f"{s['n_entries']:>4}")

    if aggregate.get("n_failed"):
        print(f"\n  Failed entries:")
        for fe in aggregate["failed_entries"]:
            print(f"    - {fe['entry_id']}: {fe['error']}")

    agg_path = os.path.join(output_dir, "p3_judge_aggregate.json")
    print(f"\n  Aggregate saved: {agg_path}")
    csv_path = os.path.join(output_dir, "p3_judge_summary.csv")
    print(f"  CSV summary:    {csv_path}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="P3 LLM-as-Judge Runner — send judge prompts to Claude API"
    )
    parser.add_argument(
        "--input-dir", required=True,
        help="Directory containing p3_judge_inputs.json and p3_judge_prompts/"
    )
    parser.add_argument(
        "--output-dir", required=True,
        help="Directory for judge results"
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"Judge model (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
        help=f"Max concurrent API calls (default: {DEFAULT_CONCURRENCY})"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Skip API calls, test parsing pipeline with mock responses"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Limit number of entries to process (for testing)"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-judge all entries, ignoring existing results"
    )

    args = parser.parse_args()

    # If --force, clear existing individual results
    if args.force:
        individual_dir = os.path.join(args.output_dir, "individual")
        if os.path.isdir(individual_dir):
            import shutil
            shutil.rmtree(individual_dir)
            print(f"Cleared existing results in {individual_dir}")

    asyncio.run(run_judge(args))


if __name__ == "__main__":
    main()
