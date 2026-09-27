"""
LLM client — supports two backends, selected automatically by environment:

  Backend A — OpenAI-compatible gateway (preferred when GATEWAY_URL is set)
  ─────────────────────────────────────────────────────────────────────────
  Environment vars:
    GATEWAY_URL   Full base URL of the OpenAI-compatible gateway.
                  The code appends /v1/chat/completions and /v1/embeddings.
                  Example: https://api.us-south.ml.cloud.ibm.com/ml/v1
    GATEWAY_KEY   API key sent as:  Authorization: Bearer <key>

  Wire format (OpenAI):
    POST {GATEWAY_URL}/v1/chat/completions
    Body: { "model": "...", "messages": [...], "temperature": 0.2 }
    Response: { "choices": [{"message": {"content": "..."}}] }

    POST {GATEWAY_URL}/v1/embeddings
    Body: { "model": "...", "input": "..." }
    Response: { "data": [{"embedding": [...]}] }

  Backend B — Ollama REST API (fallback when GATEWAY_URL is not set)
  ─────────────────────────────────────────────────────────────────────────
  Environment vars:
    OLLAMA_BASE_URL  Full base URL of the Ollama server.
                     The code appends /api/chat and /api/embeddings.
                     Example: https://ollama.com  or  http://localhost:11434
    OLLAMA_API_KEY   API key sent as:  Authorization: Bearer <key>
                     Leave blank for local Ollama with no authentication.

  Wire format (Ollama):
    POST {OLLAMA_BASE_URL}/api/chat
    Body: { "model": "...", "messages": [...], "stream": false, "options": {...} }
    Response: { "message": {"role": "assistant", "content": "..."} }

    POST {OLLAMA_BASE_URL}/api/embeddings
    Body: { "model": "...", "prompt": "..." }
    Response: { "embedding": [...] }

Models used per agent task:
  llama3.1:8b        — Reasoning: module mapping, impact, risk ranking, suite composition
  qwen2.5-coder:7b   — Code generation: Gherkin BDD, Playwright TypeScript stubs
  nomic-embed-text   — Embeddings: semantic similarity scoring in Agent 3

  For OpenAI-compatible gateways, override these via:
    REASONING_MODEL_OVERRIDE, CODE_MODEL_OVERRIDE, EMBEDDING_MODEL_OVERRIDE
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ── Model constants ───────────────────────────────────────────────────────────
REASONING_MODEL  = os.environ.get("LLM_MODEL","Beelzebub4883/llama3.1-cloud")        # Agent 1, 2, 3, 4, 5 (reasoning tasks)
CODE_MODEL       = os.environ.get("CODE_MODEL","gemma4")   # Agent 5 (Gherkin + Playwright generation)
EMBEDDING_MODEL  = os.environ.get("EMBED_MODEL","nemotron-3-super")   # Agent 3, seed_chroma (semantic similarity)

# ── Default tuning params ─────────────────────────────────────────────────────
_REASONING_OPTIONS = {"temperature": 0.2, "num_ctx": 8192}
_CODE_OPTIONS      = {"temperature": 0.3, "num_ctx": 8192}

# Request timeout in seconds (chat can be slow for large prompts)
_CHAT_TIMEOUT  = 120
_EMBED_TIMEOUT = 30


# ── Backend detection ─────────────────────────────────────────────────────────

def _use_gateway() -> bool:
    """Return True when an OpenAI-compatible GATEWAY_URL is configured."""
    return bool(os.environ.get("GATEWAY_URL", "").strip())


def _effective_model(model: str) -> str:
    """
    Allow per-model overrides via environment variables.
    Useful when the OpenAI-compatible gateway uses different model name aliases.

    REASONING_MODEL_OVERRIDE  → overrides REASONING_MODEL  (default: llama3.1:8b)
    CODE_MODEL_OVERRIDE       → overrides CODE_MODEL        (default: qwen2.5-coder:7b)
    EMBEDDING_MODEL_OVERRIDE  → overrides EMBEDDING_MODEL   (default: nomic-embed-text)
    """
    if model == REASONING_MODEL:
        return os.environ.get("REASONING_MODEL_OVERRIDE", model)
    if model == CODE_MODEL:
        return os.environ.get("CODE_MODEL_OVERRIDE", model)
    if model == EMBEDDING_MODEL:
        return os.environ.get("EMBEDDING_MODEL_OVERRIDE", model)
    return model


# ── OpenAI-compatible gateway helpers ────────────────────────────────────────

def _gateway_base() -> str:
    return os.environ.get("GATEWAY_URL", "").rstrip("/")


def _gateway_headers() -> dict[str, str]:
    h = {
        "Content-Type": "application/json",
        "Accept":        "application/json",
    }
    key = os.environ.get("GATEWAY_KEY", "").strip()
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


def _gateway_chat(
    messages: list[dict],
    model: str,
    temperature: float,
) -> str:
    """POST to the OpenAI-compatible /v1/chat/completions endpoint."""
    url = f"{_gateway_base()}/v1/chat/completions"
    payload: dict[str, Any] = {
        "model":       _effective_model(model),
        "messages":    messages,
        "temperature": temperature,
    }
    logger.debug("POST %s  model=%s  temperature=%.2f", url, payload["model"], temperature)
    print("\n---------------- OpenAI API ---------------\n")
    print(url)
    print(payload)
    print(_gateway_headers())
    print("\n--------------------\n")
    resp = requests.post(url, headers=_gateway_headers(), json=payload, timeout=_CHAT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _gateway_embed(text: str, model: str) -> list[float]:
    """POST to the OpenAI-compatible /v1/embeddings endpoint."""
    url = f"{_gateway_base()}/v1/embeddings"
    payload = {
        "model": _effective_model(model),
        "input": text,
    }
    logger.debug("POST %s  model=%s", url, payload["model"])
    resp = requests.post(url, headers=_gateway_headers(), json=payload, timeout=_EMBED_TIMEOUT)
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


# ── Ollama REST API helpers ───────────────────────────────────────────────────

def _ollama_base() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def _ollama_headers() -> dict[str, str]:

    h = {
        "Content-Type": "application/json",
    }
    api_key = os.environ.get("OLLAMA_API_KEY", "API_KEY").strip()
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
        print("\n--------- Header ----------------\n")
        print(h)
        print("\n------------------\n")
    return h


def _ollama_chat(
    messages: list[dict],
    model: str,
    temperature: float,
    num_ctx: int,
) -> str:
    """POST to the Ollama /api/chat endpoint."""
    url = f"{_ollama_base()}/api/chat"
    payload = {
        "model":    _effective_model(model),
        "messages": messages,
        "stream":   False,
        "options":  {"temperature": temperature, "num_ctx": num_ctx},
    }
    logger.debug("POST %s  model=%s  temperature=%.2f", url, payload["model"], temperature)
    resp = requests.post(url, headers=_ollama_headers(), json=payload, timeout=_CHAT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _ollama_embed(text: str, model: str) -> list[float]:
    """POST to the Ollama /api/embed endpoint."""
    url = f"{_ollama_base()}/api/embed"
    payload = {
        "model":  _effective_model(model),
        "input": text,
    }
    logger.debug("POST %s  model=%s", url, payload["model"])
    resp = requests.post(url, headers=_ollama_headers(), json=payload, timeout=_EMBED_TIMEOUT)
    resp.raise_for_status()
    return resp.json()["embedding"]


# ── JSON extraction helper ────────────────────────────────────────────────────

def _extract_json(text: str) -> Any:
    """
    Extract the first valid JSON object or array from a string.
    Handles cases where the model wraps JSON in markdown code fences.
    """
    # Strip markdown fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for pattern in (r"\{.*\}", r"\[.*\]"):
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Could not extract valid JSON from LLM response:\n{text[:500]}")


# ── Public API ────────────────────────────────────────────────────────────────

def chat(
    prompt: str,
    model: str = REASONING_MODEL,
    temperature: float | None = None,
    num_ctx: int = 8192,
    system: str | None = None,
    expect_json: bool = False,
) -> str | Any:
    """
    Send a chat prompt to the configured LLM backend (gateway or Ollama).

    Args:
        prompt:      The user message content
        model:       Model name — resolved via _effective_model() for gateway overrides
        temperature: Sampling temperature — uses model default if None
                     (0.2 for reasoning models, 0.3 for code models)
        num_ctx:     Context window size in tokens (Ollama only; ignored for gateway)
        system:      Optional system prompt prepended to the conversation
        expect_json: If True, appends a JSON-only instruction to the prompt
                     and parses the response content as JSON before returning

    Returns:
        str   — raw response text when expect_json=False
        dict  — parsed JSON object/list when expect_json=True

    Raises:
        requests.HTTPError  — on non-2xx HTTP response
        ValueError          — when expect_json=True but response is not valid JSON
    """
    if temperature is None:
        temperature = (
            _CODE_OPTIONS["temperature"]
            if model == CODE_MODEL
            else _REASONING_OPTIONS["temperature"]
        )
    assert temperature is not None  # narrowed for type checker

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})

    user_content = prompt
    if expect_json:
        user_content = (
            prompt
            + "\n\nIMPORTANT: Respond ONLY with valid JSON. "
            "Do not include any explanation, markdown fences, or extra text outside the JSON."
        )
    messages.append({"role": "user", "content": user_content})

    if _use_gateway():
        content = _gateway_chat(messages, model, temperature)
    else:
        content = _ollama_chat(messages, model, temperature, num_ctx)

    if expect_json:
        return _extract_json(content)
    return content


def embed(text: str, model: str = EMBEDDING_MODEL) -> list[float]:
    """
    Generate an embedding vector via the configured LLM backend.

    Args:
        text:  The text to embed
        model: Embedding model name (default: nomic-embed-text)

    Returns:
        List of floats representing the embedding vector.

    Raises:
        requests.HTTPError  — on non-2xx HTTP response
    """
    if _use_gateway():
        return _gateway_embed(text, model)
    return _ollama_embed(text, model)
