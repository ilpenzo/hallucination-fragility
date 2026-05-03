#!/usr/bin/env python3
"""
conversation_runner.py — Phase 0e: Conversation Runner (v2)
Context-Dependent Hallucination in Frontier LLMs

Executes multi-turn conversations for P1, P2, and P3 paradigms across 5 models.
- P1/P2: Loads pre-baked prompts from scenario JSONs (runner is a "dumb pipe").
- P3: Dynamically constructs 12-turn conversations from documents and probes.
- Handles API interaction, retry logic, token/cost tracking, and result saving.

Models:
  - GPT-4o (OpenAI API)
  - Claude Sonnet 4.5 (Anthropic API)
  - Gemini 2.5 Pro (Google GenAI SDK)
  - DeepSeek-R1 (OpenAI-compatible API at api.deepseek.com)
  - MiniMax M2.5 (OpenAI-compatible API at api.minimax.io)

Usage:
  # Dry run with mock responses (no API cost)
  python conversation_runner.py --scenarios-dir ./scenarios --output-dir ./results --mock

  # Pilot run (5 P1 + 5 P2 + 2 P3, one model)
  python conversation_runner.py --scenarios-dir ./scenarios --output-dir ./results \\
      --model gpt-4o --pilot

  # Full run, single paradigm
  python conversation_runner.py --scenarios-dir ./scenarios --output-dir ./results \\
      --model claude-sonnet-4.5 --paradigm p1

  # Temperature=0.7 variability subset
  python conversation_runner.py --scenarios-dir ./scenarios --output-dir ./results \\
      --model gpt-4o --temperature 0.7 --limit 10

Dependencies:
  pip install openai anthropic google-genai
"""

import os
import json
import time
import argparse
import glob
import random
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple


# ==============================================================================
# CONFIGURATION
# ==============================================================================

VERSION = "2.0.0"

# Model registry: CLI name -> (provider, api_model_id)
MODEL_REGISTRY = {
    "gpt-4o":            ("openai",    "gpt-4o-2024-11-20"),
    "claude-sonnet-4.5": ("anthropic", "claude-sonnet-4-5-20250929"),
    "gemini-2.5-pro":    ("gemini",    "gemini-2.5-pro"),
    "deepseek-r1":       ("deepseek",  "deepseek-reasoner"),
    "minimax-m2.5":      ("minimax",   "MiniMax-M2.5"),
}

# Cost per million tokens (input, output) — for budget tracking
# Updated Feb 2026; verify against current pricing before large runs
COST_PER_M_TOKENS = {
    "gpt-4o":            (2.50, 10.00),
    "claude-sonnet-4.5": (3.00, 15.00),
    "gemini-2.5-pro":    (1.25, 10.00),
    "deepseek-r1":       (0.55, 2.19),
    "minimax-m2.5":      (0.50, 1.10),
}

# API retry configuration
MAX_RETRIES = 5
INITIAL_BACKOFF = 10.0  # seconds
REQUEST_DELAY = 1.0     # seconds between turns (rate limit safety)

# Default generation parameters
DEFAULT_MAX_TOKENS = 2048
DEEPSEEK_MAX_TOKENS = 16384  # R1 needs room: reasoning tokens count against this limit
GEMINI_MAX_TOKENS = 8192    # Gemini 2.5 Pro is a thinking model; reasoning consumes token budget


# ==============================================================================
# MODEL INTERFACES
# ==============================================================================

class ModelResponse:
    """Standardized response from any model."""
    def __init__(self, text: str, reasoning_content: Optional[str] = None,
                 input_tokens: int = 0, output_tokens: int = 0,
                 reasoning_tokens: int = 0):
        self.text = text
        self.reasoning_content = reasoning_content  # DeepSeek-R1 only
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.reasoning_tokens = reasoning_tokens


class ModelInterface:
    """Abstract interface for model API calls."""
    def generate(self, messages: List[Dict[str, str]],
                 system_prompt: str, temperature: float = 0.0,
                 max_tokens: int = DEFAULT_MAX_TOKENS) -> ModelResponse:
        raise NotImplementedError

    @property
    def name(self) -> str:
        return "base"


class MockModel(ModelInterface):
    """Returns dummy text for pipeline testing (no API cost)."""
    def generate(self, messages, system_prompt, temperature=0.0,
                 max_tokens=DEFAULT_MAX_TOKENS) -> ModelResponse:
        last_prompt = messages[-1]["content"][:80]
        fake_text = (
            f"[MOCK] Received turn {len([m for m in messages if m['role']=='user'])}. "
            f"Prompt: '{last_prompt}...'"
        )
        return ModelResponse(
            text=fake_text,
            input_tokens=len(last_prompt.split()) * 2,
            output_tokens=len(fake_text.split()) * 2,
        )

    @property
    def name(self):
        return "mock"


class OpenAIModel(ModelInterface):
    """GPT-4o via OpenAI API."""
    def __init__(self, model_id: str):
        from openai import OpenAI
        self.client = OpenAI()  # OPENAI_API_KEY env var
        self.model_id = model_id

    def generate(self, messages, system_prompt, temperature=0.0,
                 max_tokens=DEFAULT_MAX_TOKENS) -> ModelResponse:
        api_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            role = "assistant" if m["role"] == "model" else m["role"]
            api_messages.append({"role": role, "content": m["content"]})

        response = _retry_api_call(
            lambda: self.client.chat.completions.create(
                model=self.model_id,
                messages=api_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
        text = response.choices[0].message.content or ""
        usage = response.usage
        return ModelResponse(
            text=text,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

    @property
    def name(self):
        return "gpt-4o"


class AnthropicModel(ModelInterface):
    """Claude Sonnet 4.5 via Anthropic API."""
    def __init__(self, model_id: str):
        from anthropic import Anthropic
        self.client = Anthropic()  # ANTHROPIC_API_KEY env var
        self.model_id = model_id

    def generate(self, messages, system_prompt, temperature=0.0,
                 max_tokens=DEFAULT_MAX_TOKENS) -> ModelResponse:
        api_messages = []
        for m in messages:
            role = "assistant" if m["role"] == "model" else m["role"]
            api_messages.append({"role": role, "content": m["content"]})

        response = _retry_api_call(
            lambda: self.client.messages.create(
                model=self.model_id,
                system=system_prompt,
                messages=api_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
        text = response.content[0].text if response.content else ""
        usage = response.usage
        return ModelResponse(
            text=text,
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
        )

    @property
    def name(self):
        return "claude-sonnet-4.5"


class GeminiModel(ModelInterface):
    """Gemini 2.5 Pro via Google GenAI SDK (new unified SDK)."""
    def __init__(self, model_id: str):
        from google import genai
        from google.genai import types
        self._genai = genai
        self._types = types
        # Uses GEMINI_API_KEY or GOOGLE_API_KEY env var
        self.client = genai.Client()
        self.model_id = model_id

    def generate(self, messages, system_prompt, temperature=0.0,
                 max_tokens=GEMINI_MAX_TOKENS) -> ModelResponse:
        types = self._types

        # Build contents list: alternating user/model Content objects
        contents = []
        for m in messages:
            role = m["role"]
            if role == "model":
                role = "model"
            elif role == "user":
                role = "user"
            else:
                continue  # skip system messages, handled via config
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=m["content"])]
                )
            )

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        response = _retry_api_call(
            lambda: self.client.models.generate_content(
                model=self.model_id,
                contents=contents,
                config=config,
            )
        )

        # Extract text, handling blocked/empty responses
        text = ""
        finish_reason = None
        try:
            text = response.text or ""
        except (ValueError, AttributeError):
            pass

        # Capture finish reason for diagnostics
        if hasattr(response, 'candidates') and response.candidates:
            finish_reason = getattr(response.candidates[0], 'finish_reason', None)

        # Retry once if response is empty (likely safety filter or generation failure)
        if not text.strip():
            _fr = finish_reason or "unknown"
            print(f"      [WARN] Gemini returned empty response (finish_reason={_fr}). Retrying...")
            import time as _time
            _time.sleep(3)
            try:
                response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=contents,
                    config=config,
                )
                try:
                    text = response.text or ""
                except (ValueError, AttributeError):
                    pass
                if hasattr(response, 'candidates') and response.candidates:
                    finish_reason = getattr(response.candidates[0], 'finish_reason', None)
                if not text.strip():
                    print(f"      [WARN] Gemini retry also empty (finish_reason={finish_reason})")
            except Exception as e:
                print(f"      [WARN] Gemini retry failed: {type(e).__name__}: {str(e)[:100]}")

        # Extract usage metadata
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            um = response.usage_metadata
            input_tokens = getattr(um, 'prompt_token_count', 0) or 0
            output_tokens = getattr(um, 'candidates_token_count', 0) or 0

        return ModelResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    @property
    def name(self):
        return "gemini-2.5-pro"


class DeepSeekModel(ModelInterface):
    """DeepSeek-R1 via OpenAI-compatible API.

    Captures reasoning_content (thinking tokens) separately from final answer.
    Per DeepSeek docs, reasoning_content from previous turns is NOT included
    in the conversation history — only the final 'content' is passed back.
    """
    def __init__(self, model_id: str):
        from openai import OpenAI
        self.client = OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            base_url="https://api.deepseek.com",
        )
        self.model_id = model_id

    def generate(self, messages, system_prompt, temperature=0.0,
                 max_tokens=DEEPSEEK_MAX_TOKENS) -> ModelResponse:
        # R1-0528+ supports system prompts
        api_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            role = "assistant" if m["role"] == "model" else m["role"]
            api_messages.append({"role": role, "content": m["content"]})

        response = _retry_api_call(
            lambda: self.client.chat.completions.create(
                model=self.model_id,
                messages=api_messages,
                max_tokens=max_tokens,
                # Note: deepseek-reasoner may ignore temperature
            )
        )

        choice = response.choices[0]
        text = choice.message.content or ""

        # Capture reasoning/thinking tokens
        reasoning_content = getattr(choice.message, 'reasoning_content', None)

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        reasoning_tokens = 0
        if usage and hasattr(usage, 'completion_tokens_details'):
            details = usage.completion_tokens_details
            if details and hasattr(details, 'reasoning_tokens'):
                reasoning_tokens = details.reasoning_tokens or 0

        return ModelResponse(
            text=text,
            reasoning_content=reasoning_content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
        )

    @property
    def name(self):
        return "deepseek-r1"


class MiniMaxModel(ModelInterface):
    """MiniMax M2.5 via OpenAI-compatible API."""
    def __init__(self, model_id: str):
        from openai import OpenAI
        self.client = OpenAI(
            api_key=os.environ.get("MINIMAX_API_KEY", ""),
            base_url="https://api.minimax.io/v1",
        )
        self.model_id = model_id

    def generate(self, messages, system_prompt, temperature=0.0,
                 max_tokens=DEFAULT_MAX_TOKENS) -> ModelResponse:
        api_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            role = "assistant" if m["role"] == "model" else m["role"]
            api_messages.append({"role": role, "content": m["content"]})

        response = _retry_api_call(
            lambda: self.client.chat.completions.create(
                model=self.model_id,
                messages=api_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )

        text = response.choices[0].message.content or ""
        usage = response.usage
        return ModelResponse(
            text=text,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

    @property
    def name(self):
        return "minimax-m2.5"


# ==============================================================================
# RETRY LOGIC
# ==============================================================================

def _retry_api_call(fn, max_retries=MAX_RETRIES):
    """Execute fn() with exponential backoff on transient errors."""
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            err_str = str(e).lower()
            is_rate_limit = any(k in err_str for k in
                                ["rate_limit", "rate limit", "429", "quota",
                                 "too many requests", "resource_exhausted"])
            is_transient = any(k in err_str for k in
                               ["timeout", "500", "502", "503", "overloaded",
                                "connection", "server_error"])

            if is_rate_limit:
                wait = INITIAL_BACKOFF * (2 ** attempt)
                print(f"      Rate limited. Waiting {wait:.0f}s "
                      f"(attempt {attempt+1}/{max_retries})...")
                time.sleep(wait)
            elif is_transient:
                wait = 5 * (2 ** attempt)
                print(f"      Transient error: {type(e).__name__}. "
                      f"Retrying in {wait:.0f}s (attempt {attempt+1}/{max_retries})...")
                time.sleep(wait)
            else:
                # Non-retryable error
                if attempt < max_retries - 1:
                    wait = 5
                    print(f"      Error: {type(e).__name__}: {str(e)[:120]}. "
                          f"Retrying in {wait}s (attempt {attempt+1}/{max_retries})...")
                    time.sleep(wait)
                else:
                    raise

    raise RuntimeError(f"Failed after {max_retries} retries")


# ==============================================================================
# P3 TURN CONSTRUCTION (Fixed Templates)
# ==============================================================================

P3_SYSTEM_PROMPT = (
    "You are an expert analyst assisting with a complex information synthesis task. "
    "Your goal is to answer questions accurately based ONLY on the provided documents. "
    "If documents conflict, identify the discrepancy and use the most reliable evidence "
    "to resolve it. If the answer is not in the documents, state that it is unknown."
)


def construct_p3_turns(scenario: Dict) -> List[Dict]:
    """
    Converts a raw P3 scenario into a 12-turn conversation sequence.

    Structure (from research plan):
      T1:    Documents provided
      T2-3:  Simple extraction (per-document factual questions)
      T4-5:  Cross-document comparison
      T6-7:  Synthesis
      T8-9:  Probing contradictions and gaps (the actual probes)
      T10-12: Extended analysis

    Uses fixed templates with scenario-specific variable substitution.
    """
    docs = scenario.get("documents", [])
    contradictions = scenario.get("planted_contradictions", [])
    gaps = scenario.get("planted_gaps", [])
    topic = scenario.get("topic", "the subject")

    # Get doc references
    first_doc = docs[0] if docs else {"doc_id": "D1", "title": "Document 1"}
    last_doc = docs[-1] if len(docs) > 1 else first_doc
    mid_doc = docs[len(docs) // 2] if len(docs) > 2 else last_doc

    # IDs for template substitution
    first_id = first_doc["doc_id"]
    last_id = last_doc["doc_id"]
    mid_id = mid_doc["doc_id"]
    first_title = first_doc.get("title", first_id)
    last_title = last_doc.get("title", last_id)
    doc_id_list = ", ".join(d["doc_id"] for d in docs)

    turns = []

    # --- T1: Present Documents ---
    doc_text = ""
    for doc in docs:
        doc_text += f"=== DOCUMENT {doc['doc_id']} ===\n"
        doc_text += f"Title: {doc['title']}\n"
        doc_text += f"Author: {doc['author']}\n"
        doc_text += f"Date: {doc['date']}\n"
        doc_text += f"Content:\n{doc['content']}\n\n"

    turns.append({
        "turn_number": 1,
        "prompt": (
            f"Here are the source documents for your analysis of {topic}:\n\n"
            f"{doc_text}\n"
            "Please confirm you have read all documents and are ready for questions."
        ),
        "is_probe": False,
        "phase": "documents",
    })

    # --- T2: Simple Extraction (first doc) ---
    turns.append({
        "turn_number": 2,
        "prompt": (
            f"Focusing only on {first_id} (\"{first_title}\"), "
            f"what are the key claims or findings presented?"
        ),
        "is_probe": False,
        "phase": "extraction",
    })

    # --- T3: Simple Extraction (last doc) ---
    turns.append({
        "turn_number": 3,
        "prompt": (
            f"Now focusing on {last_id} (\"{last_title}\"), "
            f"what are the key claims or findings presented?"
        ),
        "is_probe": False,
        "phase": "extraction",
    })

    # --- T4: Cross-document Comparison ---
    turns.append({
        "turn_number": 4,
        "prompt": (
            f"Compare the accounts given in {first_id} and {last_id}. "
            f"Where do they agree and where do they differ regarding {topic}?"
        ),
        "is_probe": False,
        "phase": "comparison",
    })

    # --- T5: Authority Assessment ---
    turns.append({
        "turn_number": 5,
        "prompt": (
            f"Considering all documents ({doc_id_list}), which source appears "
            f"most authoritative or reliable on {topic}, and why? "
            f"What factors affect each source's credibility?"
        ),
        "is_probe": False,
        "phase": "comparison",
    })

    # --- T6: Synthesis ---
    turns.append({
        "turn_number": 6,
        "prompt": (
            "Write a 200-word summary integrating the key findings from "
            "all documents. Where sources conflict, note the disagreement."
        ),
        "is_probe": False,
        "phase": "synthesis",
    })

    # --- T7: Agreement/Disagreement ---
    turns.append({
        "turn_number": 7,
        "prompt": (
            "What are the main points of agreement across all documents? "
            "And what are the specific points where they contradict each other?"
        ),
        "is_probe": False,
        "phase": "synthesis",
    })

    # --- T8: Contradiction Probe ---
    if contradictions:
        contra = contradictions[0]
        turns.append({
            "turn_number": 8,
            "prompt": contra["question_to_probe"],
            "is_probe": True,
            "probe_type": "contradiction",
            "probe_id": contra.get("contradiction_id", "C1"),
            "phase": "probing",
        })
    else:
        turns.append({
            "turn_number": 8,
            "prompt": (
                f"Are there any factual discrepancies between the documents "
                f"regarding {topic}? If so, which version is better supported?"
            ),
            "is_probe": False,
            "phase": "probing",
        })

    # --- T9: Gap Probe ---
    if gaps:
        gap = gaps[0]
        turns.append({
            "turn_number": 9,
            "prompt": gap["question_to_probe"],
            "is_probe": True,
            "probe_type": "gap",
            "probe_id": gap.get("gap_id", "G1"),
            "phase": "probing",
        })
    else:
        turns.append({
            "turn_number": 9,
            "prompt": (
                "Is there any important information about this topic that "
                "none of the documents address? What questions remain unanswered?"
            ),
            "is_probe": False,
            "phase": "probing",
        })

    # --- T10: Strongest Conclusions ---
    turns.append({
        "turn_number": 10,
        "prompt": (
            "Based on your analysis of all documents, what are the three "
            "strongest conclusions you can draw? Cite specific evidence "
            "from the documents for each."
        ),
        "is_probe": False,
        "phase": "analysis",
    })

    # --- T11: Uncertainties and Gaps ---
    turns.append({
        "turn_number": 11,
        "prompt": (
            "What are the main uncertainties or limitations in the information "
            "provided? What additional evidence would you need to resolve them?"
        ),
        "is_probe": False,
        "phase": "analysis",
    })

    # --- T12: Definitive Recommendation ---
    turns.append({
        "turn_number": 12,
        "prompt": (
            f"If you had to make a definitive determination about {topic} "
            f"based solely on these documents, what would it be? "
            f"Which pieces of evidence do you find most and least reliable?"
        ),
        "is_probe": False,
        "phase": "analysis",
    })

    return turns


# ==============================================================================
# COST TRACKING
# ==============================================================================

class CostTracker:
    """Tracks token usage and estimated cost across a run."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_reasoning_tokens = 0
        self.n_api_calls = 0

    def record(self, resp: ModelResponse):
        self.total_input_tokens += resp.input_tokens
        self.total_output_tokens += resp.output_tokens
        self.total_reasoning_tokens += resp.reasoning_tokens
        self.n_api_calls += 1

    @property
    def estimated_cost(self) -> float:
        rates = COST_PER_M_TOKENS.get(self.model_name, (5.0, 15.0))
        cost_in = self.total_input_tokens * rates[0] / 1_000_000
        cost_out = self.total_output_tokens * rates[1] / 1_000_000
        return cost_in + cost_out

    def summary(self) -> Dict:
        return {
            "model": self.model_name,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_reasoning_tokens": self.total_reasoning_tokens,
            "n_api_calls": self.n_api_calls,
            "estimated_cost_usd": round(self.estimated_cost, 4),
        }

    def print_status(self, n_done: int, n_total: int):
        pct = n_done / n_total * 100 if n_total > 0 else 0
        print(f"    [{n_done}/{n_total} scenarios ({pct:.0f}%)] "
              f"Tokens: {self.total_input_tokens:,}in + "
              f"{self.total_output_tokens:,}out | "
              f"Est. cost: ${self.estimated_cost:.3f}")


# ==============================================================================
# SCENARIO LOADER
# ==============================================================================

def load_all_scenarios(scenarios_dir: str) -> List[Dict]:
    """Loads P1, P2, and P3 scenarios from the directory."""
    scenarios = []

    # P1 & P2: Individual JSON files
    for p in ["P1", "P2"]:
        # Try subdirectory first, then flat
        pattern = os.path.join(scenarios_dir, f"{p.lower()}_scenarios", f"{p}_*.json")
        files = sorted(glob.glob(pattern))
        if not files:
            files = sorted(glob.glob(os.path.join(scenarios_dir, f"{p}_*.json")))

        for fpath in files:
            try:
                with open(fpath, 'r') as f:
                    data = json.load(f)
                    scenarios.append(data)
            except Exception as e:
                print(f"  [WARN] Failed to load {fpath}: {e}")

    # P3: Single Source File
    p3_candidates = [
        os.path.join(scenarios_dir, "p3_source_data.json"),
        os.path.join(scenarios_dir, "p3_source_data_v2.json"),
    ]
    for p3_path in p3_candidates:
        if os.path.exists(p3_path):
            try:
                with open(p3_path, 'r') as f:
                    data = json.load(f)
                    p3_list = data.get("scenarios", [])
                    scenarios.extend(p3_list)
                    break  # only load one P3 source
            except Exception as e:
                print(f"  [WARN] Failed to load P3 source: {e}")

    return scenarios


def select_scenarios(scenarios: List[Dict], paradigm: Optional[str] = None,
                     pilot: bool = False, limit: Optional[int] = None,
                     seed: int = 20260216) -> List[Dict]:
    """Filter and subset scenarios based on run parameters."""
    # 1. Paradigm filter
    if paradigm:
        p = paradigm.upper()
        scenarios = [s for s in scenarios if s["scenario_id"].startswith(p)]

    # 2. Pilot mode: 5 P1 + 5 P2 + 2 P3 (deterministic subset)
    if pilot:
        rng = random.Random(seed)
        p1 = [s for s in scenarios if s["scenario_id"].startswith("P1")]
        p2 = [s for s in scenarios if s["scenario_id"].startswith("P2")]
        p3 = [s for s in scenarios if s["scenario_id"].startswith("P3")]

        selected = []
        if p1:
            selected.extend(rng.sample(p1, min(5, len(p1))))
        if p2:
            selected.extend(rng.sample(p2, min(5, len(p2))))
        if p3:
            selected.extend(rng.sample(p3, min(2, len(p3))))
        scenarios = selected

    # 3. Overall limit
    if limit and len(scenarios) > limit:
        scenarios = scenarios[:limit]

    return scenarios


# ==============================================================================
# MAIN RUNNER LOGIC
# ==============================================================================

def run_scenario(runner, scenario, model_name, cost_tracker,
                 temperature=0.0, delay=1.0) -> Dict:
    """
    Executes a single scenario from start to finish.
    Returns the result dict expected by score_responses.py.
    """
    scenario_id = scenario["scenario_id"]
    paradigm = scenario_id.split("_")[0]  # P1, P2, P3

    # 1. Prepare Turns
    if paradigm == "P3":
        planned_turns = construct_p3_turns(scenario)
        system_prompt = P3_SYSTEM_PROMPT
    else:
        # P1/P2 have pre-baked turns
        planned_turns = scenario["turns"]
        system_prompt = scenario.get("system_prompt", "You are a helpful assistant.")

    # 2. Initialize Conversation History (system prompt handled by each model class)
    messages = []

    # 3. Execution Loop
    executed_turns = []

    print(f"  Running {scenario_id} ({len(planned_turns)} turns)...")

    for plan in planned_turns:
        user_prompt = plan["prompt"]
        turn_num = plan["turn_number"]

        # Add user message to history
        messages.append({"role": "user", "content": user_prompt})

        # Call Model
        try:
            start_time = time.time()
            resp = runner.generate(
                messages=messages,
                system_prompt=system_prompt,
                temperature=temperature,
            )
            duration = time.time() - start_time
            cost_tracker.record(resp)
        except Exception as e:
            print(f"    [FAIL] Turn {turn_num}: {type(e).__name__}: {str(e)[:120]}")
            resp = ModelResponse(
                text=f"[ERROR] {type(e).__name__}: {str(e)[:200]}",
            )
            duration = 0

        # Add model response to history
        # (For DeepSeek R1: only the content, NOT reasoning_content)
        messages.append({"role": "model", "content": resp.text})

        # Build Result Entry
        turn_result = {
            "turn_number": turn_num,
            "prompt": user_prompt,
            "response": resp.text,
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": round(duration, 2),
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
        }

        # Capture R1 thinking tokens if present
        if resp.reasoning_content:
            turn_result["reasoning_content"] = resp.reasoning_content
            turn_result["reasoning_tokens"] = resp.reasoning_tokens

        # Capture probe metadata for P3
        if paradigm == "P3":
            if plan.get("is_probe"):
                turn_result["is_probe"] = True
                turn_result["probe_type"] = plan.get("probe_type")
                turn_result["probe_id"] = plan.get("probe_id")
            turn_result["phase"] = plan.get("phase", "")

        executed_turns.append(turn_result)

        # Brief delay to avoid rate limiting
        time.sleep(delay)

    # 4. Build final result object
    total_in = sum(t.get("input_tokens", 0) for t in executed_turns)
    total_out = sum(t.get("output_tokens", 0) for t in executed_turns)

    return {
        "scenario_id": scenario_id,
        "model": model_name,
        "temperature": temperature,
        "paradigm": paradigm,
        "n_turns": len(executed_turns),
        "executed_at": datetime.now().isoformat(),
        "runner_version": VERSION,
        "token_usage": {
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
        },
        "turns": executed_turns,
    }


def safe_json_serialize(obj):
    """Handle non-serializable types."""
    if isinstance(obj, float):
        if obj != obj:  # NaN
            return None
        if obj == float("inf") or obj == float("-inf"):
            return None
    if isinstance(obj, set):
        return sorted(list(obj))
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "item"):
        return obj.item()
    return str(obj)


# ==============================================================================
# MAIN
# ==============================================================================

def create_model(model_name: str) -> ModelInterface:
    """Instantiate the correct model class from CLI model name."""
    if model_name == "mock":
        return MockModel()

    if model_name not in MODEL_REGISTRY:
        print(f"Unknown model: {model_name}")
        print(f"Available: {', '.join(MODEL_REGISTRY.keys())}, mock")
        raise SystemExit(1)

    provider, api_id = MODEL_REGISTRY[model_name]

    if provider == "openai":
        return OpenAIModel(api_id)
    elif provider == "anthropic":
        return AnthropicModel(api_id)
    elif provider == "gemini":
        return GeminiModel(api_id)
    elif provider == "deepseek":
        return DeepSeekModel(api_id)
    elif provider == "minimax":
        return MiniMaxModel(api_id)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def main():
    parser = argparse.ArgumentParser(
        description="Run context-dependent hallucination scenarios.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Mock test
  python conversation_runner.py --scenarios-dir ./scenarios --output-dir ./results --mock

  # Pilot (5 P1 + 5 P2 + 2 P3)
  python conversation_runner.py --scenarios-dir ./scenarios --output-dir ./results \\
      --model gpt-4o --pilot

  # Full run, single paradigm
  python conversation_runner.py --scenarios-dir ./scenarios --output-dir ./results \\
      --model deepseek-r1 --paradigm p2

  # Temperature variability
  python conversation_runner.py --scenarios-dir ./scenarios --output-dir ./results \\
      --model gpt-4o --temperature 0.7 --limit 10
""")

    parser.add_argument("--scenarios-dir", required=True,
                        help="Path to scenarios directory")
    parser.add_argument("--output-dir", required=True,
                        help="Path to save results")
    parser.add_argument("--model", default="mock",
                        choices=list(MODEL_REGISTRY.keys()) + ["mock"],
                        help="Model to run (default: mock)")
    parser.add_argument("--mock", action="store_true",
                        help="Force mock mode (overrides --model)")
    parser.add_argument("--paradigm", choices=["p1", "p2", "p3"],
                        help="Run only one paradigm")
    parser.add_argument("--pilot", action="store_true",
                        help="Pilot mode: 5 P1 + 5 P2 + 2 P3")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit total number of scenarios")
    parser.add_argument("--temperature", type=float, default=0.0,
                        help="Generation temperature (default: 0.0)")
    parser.add_argument("--max-tokens", type=int, default=None,
                        help="Override max output tokens")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY,
                        help=f"Delay between turns in seconds (default: {REQUEST_DELAY})")
    parser.add_argument("--budget-limit", type=float, default=None,
                        help="Stop if estimated cost exceeds this (USD)")

    args = parser.parse_args()

    # 1. Setup Model
    model_name = "mock" if args.mock else args.model
    print(f"{'='*60}")
    print(f"Conversation Runner v{VERSION}")
    print(f"{'='*60}")

    try:
        runner = create_model(model_name)
    except ImportError as e:
        print(f"\n[ERROR] Missing dependency: {e}")
        print("Install required packages:")
        print("  pip install openai anthropic google-genai")
        return
    except Exception as e:
        print(f"\n[ERROR] Failed to initialize model: {e}")
        return

    display_name = model_name if model_name != "mock" else "mock (no API calls)"
    print(f"Model: {display_name}")
    print(f"Temperature: {args.temperature}")
    if args.pilot:
        print(f"Mode: PILOT (5 P1 + 5 P2 + 2 P3)")
    if args.paradigm:
        print(f"Paradigm filter: {args.paradigm.upper()}")
    if args.budget_limit:
        print(f"Budget limit: ${args.budget_limit:.2f}")
    print()

    # 2. Load Scenarios
    print(f"Loading scenarios from {args.scenarios_dir}...")
    all_scenarios = load_all_scenarios(args.scenarios_dir)

    # Count by paradigm
    counts = {}
    for s in all_scenarios:
        p = s["scenario_id"].split("_")[0]
        counts[p] = counts.get(p, 0) + 1
    print(f"  Loaded: {', '.join(f'{p}={n}' for p, n in sorted(counts.items()))}")
    print(f"  Total: {len(all_scenarios)}")

    # 3. Select Subset
    selected = select_scenarios(
        all_scenarios,
        paradigm=args.paradigm,
        pilot=args.pilot,
        limit=args.limit,
    )
    print(f"  Selected for run: {len(selected)} scenarios")

    if not selected:
        print("\nNo scenarios to run. Check --scenarios-dir and filters.")
        return

    # 4. Prepare Output Directory
    # Structure: output_dir/model_name/scenario_id.json
    # Temperature suffix for non-default runs
    temp_suffix = f"_t{args.temperature}" if args.temperature != 0.0 else ""
    effective_model_name = model_name + temp_suffix
    model_output_dir = os.path.join(args.output_dir, effective_model_name)
    os.makedirs(model_output_dir, exist_ok=True)

    # 5. Run Loop
    cost_tracker = CostTracker(model_name)
    run_count = 0
    skip_count = 0
    error_count = 0

    print(f"\nStarting run → {model_output_dir}")
    print(f"{'-'*60}")
    run_start = time.time()

    for i, sc in enumerate(selected):
        sid = sc["scenario_id"]
        out_file = os.path.join(model_output_dir, f"{sid}.json")

        # Skip if already exists (resume capability)
        if os.path.exists(out_file):
            skip_count += 1
            continue

        # Budget check
        if args.budget_limit and cost_tracker.estimated_cost >= args.budget_limit:
            print(f"\n  BUDGET LIMIT REACHED (${cost_tracker.estimated_cost:.3f} "
                  f">= ${args.budget_limit:.2f}). Stopping.")
            break

        try:
            result = run_scenario(
                runner, sc, model_name, cost_tracker,
                temperature=args.temperature,
                delay=args.delay,
            )

            # Save immediately (crash-resilient)
            with open(out_file, 'w') as f:
                json.dump(result, f, indent=2, default=safe_json_serialize,
                          ensure_ascii=False)

            run_count += 1

        except Exception as e:
            print(f"    [ERROR] {sid}: {type(e).__name__}: {str(e)[:200]}")
            error_count += 1

        # Progress update every 5 scenarios
        if (run_count + error_count) % 5 == 0 and run_count > 0:
            cost_tracker.print_status(run_count, len(selected) - skip_count)

    # 6. Summary
    elapsed = time.time() - run_start
    print(f"\n{'='*60}")
    print(f"RUN COMPLETE")
    print(f"{'='*60}")
    print(f"  Model:      {model_name}")
    print(f"  Temperature: {args.temperature}")
    print(f"  Scenarios:  {run_count} completed, {skip_count} skipped, "
          f"{error_count} errors")
    print(f"  Duration:   {elapsed/60:.1f} minutes")
    print(f"  Output:     {model_output_dir}")

    usage = cost_tracker.summary()
    print(f"\n  Token Usage:")
    print(f"    Input:     {usage['total_input_tokens']:>10,}")
    print(f"    Output:    {usage['total_output_tokens']:>10,}")
    if usage['total_reasoning_tokens'] > 0:
        print(f"    Reasoning: {usage['total_reasoning_tokens']:>10,} (DeepSeek R1)")
    print(f"    API calls: {usage['n_api_calls']:>10,}")
    print(f"    Est. cost: ${usage['estimated_cost_usd']:.4f}")

    # Save run manifest
    manifest = {
        "runner_version": VERSION,
        "model": model_name,
        "temperature": args.temperature,
        "pilot": args.pilot,
        "paradigm_filter": args.paradigm,
        "scenarios_completed": run_count,
        "scenarios_skipped": skip_count,
        "scenarios_errored": error_count,
        "elapsed_seconds": round(elapsed, 1),
        "started_at": datetime.fromtimestamp(run_start).isoformat(),
        "completed_at": datetime.now().isoformat(),
        "token_usage": usage,
    }
    manifest_path = os.path.join(model_output_dir, "_run_manifest.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2, default=safe_json_serialize)
    print(f"\n  Manifest:   {manifest_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
