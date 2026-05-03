#!/usr/bin/env python3
"""
run_api_models.py — Consistency probing against OpenAI API models.

Produces output files compatible with the existing analysis pipeline:
  - api_consistency_raw.json  (20 samples per question at T=0.8)
  - api_single_pass.json      (1 sample per question at T=0.0)

Usage:
  python3 run_api_models.py --test                     # Quick validation (3 questions, 2 samples)
  python3 run_api_models.py --model gpt-4o-mini        # Full run
  python3 run_api_models.py --model gpt-4o             # Full run with GPT-4o
  python3 run_api_models.py --model gpt-4o-mini --resume  # Resume interrupted run

Requires: pip install openai
Requires: OPENAI_API_KEY environment variable
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

try:
    from openai import OpenAI, RateLimitError, APIError, APITimeoutError
except ImportError:
    print("ERROR: openai package not installed. Run: pip3 install openai --user")
    sys.exit(1)

# ─── Configuration ──────────────────────────────────────────────────

# NOTE: The implementation_spec.md specifies this prompt (and says "identical to v2"):
#   "You are a factual question-answering assistant. Answer each question as
#    concisely as possible. If you are uncertain or the question contains a
#    false premise, say so clearly. Do not guess or fabricate information."
#
# However, the paper's .tex file says:
#   "You are a helpful AI assistant. Answer factually and concisely."
#
# IMPORTANT: Verify which prompt your local models actually used, and set it
# here to match EXACTLY. Check your original probing script or raw output files.
# Using the wrong prompt would introduce a confound.

SYSTEM_PROMPT = (
    "You are a factual question-answering assistant. "
    "Answer each question as concisely as possible. "
    "If you are uncertain or the question contains a false premise, "
    "say so clearly. Do not guess or fabricate information."
)
# ^^^ CHANGE THIS if your local models used the implementation_spec version instead.

CONSISTENCY_SAMPLES = 20
CONSISTENCY_TEMP = 0.8
SINGLE_PASS_TEMP = 0.0
MAX_TOKENS = 300
TOP_LOGPROBS = 5
REQUEST_DELAY = 3.0        # seconds between requests (conservative default)
MAX_RETRIES = 5
INITIAL_BACKOFF = 10.0     # seconds for first retry on rate limit

# ─── Helpers ────────────────────────────────────────────────────────

def safe_serialize(obj):
    """Handle numpy/datetime types for JSON serialization."""
    if isinstance(obj, float):
        if obj != obj:  # NaN
            return None
        if obj == float("inf") or obj == float("-inf"):
            return str(obj)
    if hasattr(obj, "item"):
        return obj.item()
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def call_openai(client, model, question, temperature, max_tokens=MAX_TOKENS,
                top_logprobs=TOP_LOGPROBS, delay=REQUEST_DELAY):
    """
    Make a single OpenAI API call with retry logic.
    Returns dict with 'text' and 'logprobs' keys, matching the existing schema.
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                logprobs=True,
                top_logprobs=top_logprobs,
            )

            choice = response.choices[0]
            text = choice.message.content or ""

            # Extract token-level logprobs
            logprob_list = []
            if choice.logprobs and choice.logprobs.content:
                for token_info in choice.logprobs.content:
                    logprob_list.append({
                        "token": token_info.token,
                        "logprob": token_info.logprob
                    })

            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }

            time.sleep(delay)
            return {"text": text, "logprobs": logprob_list, "usage": usage}

        except RateLimitError as e:
            wait = INITIAL_BACKOFF * (2 ** attempt)
            print(f"    Rate limited. Waiting {wait:.0f}s (attempt {attempt+1}/{MAX_RETRIES})...")
            time.sleep(wait)

        except (APIError, APITimeoutError) as e:
            wait = 5 * (2 ** attempt)
            print(f"    API error: {e}. Retrying in {wait:.0f}s (attempt {attempt+1}/{MAX_RETRIES})...")
            time.sleep(wait)

        except Exception as e:
            print(f"    Unexpected error: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(10)
            else:
                raise

    raise RuntimeError(f"Failed after {MAX_RETRIES} retries")


# ─── Checkpoint Management ──────────────────────────────────────────

def get_checkpoint_path(model_name):
    """Return path to checkpoint file for this model."""
    os.makedirs("checkpoints", exist_ok=True)
    safe_name = model_name.replace("/", "_").replace(":", "_")
    return f"checkpoints/{safe_name}_checkpoint.json"


def load_checkpoint(model_name):
    """Load completed question IDs and accumulated results from checkpoint."""
    path = get_checkpoint_path(model_name)
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
        return set(data.get("completed_ids", [])), data.get("consistency", []), data.get("single_pass", [])
    return set(), [], []


def save_checkpoint(model_name, completed_ids, consistency_results, single_pass_results):
    """Save checkpoint after each question."""
    path = get_checkpoint_path(model_name)
    data = {
        "completed_ids": list(completed_ids),
        "consistency": consistency_results,
        "single_pass": single_pass_results,
        "last_updated": datetime.now().isoformat()
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=safe_serialize)


# ─── Main Probing Logic ────────────────────────────────────────────

def probe_model(client, model_name, questions, n_samples, delay, resume=False):
    """
    Run consistency probing + single-pass for all questions.
    Returns (consistency_results, single_pass_results).
    """
    if resume:
        completed_ids, consistency_results, single_pass_results = load_checkpoint(model_name)
        print(f"Resuming: {len(completed_ids)} questions already completed.")
    else:
        completed_ids, consistency_results, single_pass_results = set(), [], []

    remaining = [q for q in questions if q["id"] not in completed_ids]
    total = len(questions)
    done = len(completed_ids)

    total_input_tokens = 0
    total_output_tokens = 0
    start_time = time.time()

    for i, q in enumerate(remaining):
        qnum = done + i + 1
        qid = q["id"]
        question_text = q["question"]

        print(f"  [{qnum}/{total}] {qid}: ", end="", flush=True)

        # --- Consistency probing (T=0.8, n_samples times) ---
        samples = []
        for s in range(n_samples):
            result = call_openai(client, model_name, question_text,
                                 temperature=CONSISTENCY_TEMP, delay=delay)
            samples.append({
                "text": result["text"],
                "logprobs": result["logprobs"]
            })
            total_input_tokens += result["usage"]["prompt_tokens"]
            total_output_tokens += result["usage"]["completion_tokens"]

        consistency_entry = {
            "model": model_name,
            "question_id": qid,
            "question": question_text,
            "question_type": q["question_type"],
            "ground_truth": q["ground_truth"],
            "answer_type": q["answer_type"],
            "samples": samples
        }
        consistency_results.append(consistency_entry)

        # --- Single-pass (T=0.0, 1 time) ---
        sp_result = call_openai(client, model_name, question_text,
                                temperature=SINGLE_PASS_TEMP, delay=delay)
        total_input_tokens += sp_result["usage"]["prompt_tokens"]
        total_output_tokens += sp_result["usage"]["completion_tokens"]

        single_pass_entry = {
            "model": model_name,
            "question_id": qid,
            "question": question_text,
            "question_type": q["question_type"],
            "ground_truth": q["ground_truth"],
            "answer_type": q["answer_type"],
            "samples": [{
                "text": sp_result["text"],
                "logprobs": sp_result["logprobs"]
            }]
        }
        single_pass_results.append(single_pass_entry)

        # Checkpoint
        completed_ids.add(qid)
        save_checkpoint(model_name, completed_ids, consistency_results, single_pass_results)

        # Progress
        elapsed = time.time() - start_time
        rate = (i + 1) / elapsed * 60 if elapsed > 0 else 0
        est_cost = (total_input_tokens * 0.15 / 1e6) + (total_output_tokens * 0.60 / 1e6)
        if "gpt-4o" == model_name:
            est_cost = (total_input_tokens * 2.50 / 1e6) + (total_output_tokens * 10.00 / 1e6)

        print(f"OK ({n_samples}+1 calls) | "
              f"{rate:.1f} q/min | "
              f"~${est_cost:.2f} so far")

    return consistency_results, single_pass_results


# ─── Test Mode ──────────────────────────────────────────────────────

def run_test(client, questions):
    """Quick validation: 3 questions, 2 samples each."""
    print("=" * 60)
    print("=== TEST MODE: 3 questions, 2 consistency samples ===")
    print("=" * 60)

    test_qs = questions[:3]
    model = "gpt-4o-mini"

    print(f"\nTesting {model}...")
    for i, q in enumerate(test_qs):
        print(f"  [{i+1}/3] {q['id']}: ", end="", flush=True)

        # 2 consistency samples
        for s in range(2):
            result = call_openai(client, model, q["question"],
                                 temperature=0.8, delay=1.0)
            if not result["text"]:
                print("FAIL (empty response)")
                sys.exit(1)

        # 1 single-pass
        sp = call_openai(client, model, q["question"],
                         temperature=0.0, delay=1.0)

        has_logprobs = len(sp["logprobs"]) > 0
        print(f"OK (logprobs: {'yes' if has_logprobs else 'NO — check model'})")

    # Cost estimate
    # ~100 input tokens/request, ~100 output tokens/request
    n_requests = len(questions) * (CONSISTENCY_SAMPLES + 1)  # consistency + single-pass
    est_input_tokens = n_requests * 100
    est_output_tokens = n_requests * 100
    est_cost_mini = (est_input_tokens * 0.15 + est_output_tokens * 0.60) / 1e6
    est_cost_4o = (est_input_tokens * 2.50 + est_output_tokens * 10.00) / 1e6
    est_minutes = n_requests * REQUEST_DELAY / 60

    print(f"\n{'=' * 60}")
    print(f"Test PASSED.")
    print(f"\nFull run estimates for {len(questions)} questions:")
    print(f"  Requests:      {n_requests:,} total ({CONSISTENCY_SAMPLES} consistency + 1 single-pass per question)")
    print(f"  GPT-4o-mini:   ~${est_cost_mini:.2f}")
    print(f"  GPT-4o:        ~${est_cost_4o:.2f}")
    print(f"  Runtime:       ~{est_minutes:.0f} minutes (at {REQUEST_DELAY}s delay)")
    print(f"{'=' * 60}")


# ─── Entry Point ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run consistency probing against OpenAI API")
    parser.add_argument("--model", type=str, default="gpt-4o-mini",
                        help="Model to probe: gpt-4o-mini or gpt-4o (default: gpt-4o-mini)")
    parser.add_argument("--test", action="store_true",
                        help="Run quick validation test (3 questions, 2 samples)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from checkpoint (skip completed questions)")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY,
                        help=f"Seconds between API requests (default: {REQUEST_DELAY})")
    parser.add_argument("--questions", type=str, default="questions_v3.json",
                        help="Path to question set JSON (default: questions_v3.json)")
    parser.add_argument("--output-dir", type=str, default=".",
                        help="Directory for output files (default: current directory)")
    args = parser.parse_args()

    # Validate API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set.")
        print("  export OPENAI_API_KEY='sk-...'")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    # Load questions
    if not os.path.exists(args.questions):
        print(f"ERROR: Question file not found: {args.questions}")
        sys.exit(1)

    with open(args.questions, "r") as f:
        questions = json.load(f)
    print(f"Loaded {len(questions)} questions from {args.questions}")

    # Test mode
    if args.test:
        run_test(client, questions)
        return

    # Full run
    model = args.model
    print(f"\n{'=' * 60}")
    print(f"FULL RUN: {model}")
    print(f"  Questions: {len(questions)}")
    print(f"  Consistency samples: {CONSISTENCY_SAMPLES} at T={CONSISTENCY_TEMP}")
    print(f"  Single-pass: 1 at T={SINGLE_PASS_TEMP}")
    print(f"  Request delay: {args.delay}s")
    print(f"  Total requests: {len(questions) * (CONSISTENCY_SAMPLES + 1):,}")
    print(f"{'=' * 60}\n")

    start = time.time()

    consistency, single_pass = probe_model(
        client, model, questions, CONSISTENCY_SAMPLES,
        delay=args.delay, resume=args.resume
    )

    elapsed = time.time() - start

    # Save final output files
    os.makedirs(args.output_dir, exist_ok=True)
    safe_model = model.replace("/", "_").replace(":", "_")

    consistency_path = os.path.join(args.output_dir, f"api_consistency_raw_{safe_model}.json")
    single_pass_path = os.path.join(args.output_dir, f"api_single_pass_{safe_model}.json")
    log_path = os.path.join(args.output_dir, f"api_run_log_{safe_model}.txt")

    with open(consistency_path, "w") as f:
        json.dump(consistency, f, indent=2, default=safe_serialize)

    with open(single_pass_path, "w") as f:
        json.dump(single_pass, f, indent=2, default=safe_serialize)

    # Write run log
    with open(log_path, "w") as f:
        f.write(f"Model: {model}\n")
        f.write(f"Questions: {len(questions)}\n")
        f.write(f"Consistency samples: {CONSISTENCY_SAMPLES}\n")
        f.write(f"Temperature (consistency): {CONSISTENCY_TEMP}\n")
        f.write(f"Temperature (single-pass): {SINGLE_PASS_TEMP}\n")
        f.write(f"Max tokens: {MAX_TOKENS}\n")
        f.write(f"Request delay: {args.delay}s\n")
        f.write(f"Total elapsed: {elapsed:.1f}s ({elapsed/60:.1f} min)\n")
        f.write(f"System prompt: {SYSTEM_PROMPT}\n")
        f.write(f"Completed at: {datetime.now().isoformat()}\n")
        f.write(f"Output files:\n")
        f.write(f"  {consistency_path}\n")
        f.write(f"  {single_pass_path}\n")

    print(f"\n{'=' * 60}")
    print(f"COMPLETE")
    print(f"  Elapsed: {elapsed/60:.1f} minutes")
    print(f"  Consistency data: {consistency_path}")
    print(f"  Single-pass data: {single_pass_path}")
    print(f"  Run log: {log_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
