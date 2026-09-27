"""
Ollama LLM client — thin wrapper around the Ollama Python SDK.

Provides:
  - chat():  send a prompt, optionally parse JSON response
  - embed(): generate embeddings using nomic-embed-text

Model defaults per task:
  - Reasoning (analysis, scoring, ranking): llama3.1:8b  temperature=0.2
  - Code / Gherkin generation:             qwen2.5-coder:7b  temperature=0.3
  - Embeddings:                            nomic-embed-text
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import ollama as _ollama

logger = logging.getLogger(__name__)

# ── Model constants ──────────────────────────────────────────────────────────
REASONING_MODEL  = "llama3.1:8b"
CODE_MODEL       = "qwen2.5-coder:7b"
EMBEDDING_MODEL  = "nomic-embed-text"

# ── Default tuning params ────────────────────────────────────────────────────
_REASONING_OPTIONS = {"temperature": 0.2, "num_ctx": 8192}
_CODE_OPTIONS      = {"temperature": 0.3, "num_ctx": 8192}


def _base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


def _client() -> _ollama.Client:
    return _ollama.Client(host=_base_url())


def _extract_json(text: str) -> Any:
    """
    Extract the first JSON object or array from a string.
    Handles cases where the model wraps JSON in markdown fences.
    """
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object or array within the text
    for pattern in (r"\{.*\}", r"\[.*\]"):
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Could not extract valid JSON from LLM response:\n{text[:500]}")


def chat(
    prompt: str,
    model: str = REASONING_MODEL,
    temperature: float | None = None,
    num_ctx: int = 8192,
    system: str | None = None,
    expect_json: bool = False,
) -> str | Any:
    """
    Send a chat prompt to Ollama and return the response text.

    Args:
        prompt:      The user message
        model:       Ollama model name (default: llama3.1:8b)
        temperature: Override temperature (uses model default if None)
        num_ctx:     Context window size
        system:      Optional system prompt
        expect_json: If True, appends a JSON instruction and parses the response

    Returns:
        str if expect_json=False, parsed dict/list if expect_json=True
    """
    if temperature is None:
        temperature = _CODE_OPTIONS["temperature"] if model == CODE_MODEL else _REASONING_OPTIONS["temperature"]

    options = {"temperature": temperature, "num_ctx": num_ctx}

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

    logger.debug("LLM call: model=%s temperature=%.2f prompt_len=%d", model, temperature, len(prompt))

    client = _client()
    response = client.chat(
        model=model,
        messages=messages,
        options=options,
    )
    # Support both typed response (ollama >= 0.4) and dict response (ollama < 0.4)
    if hasattr(response, "message"):
        content: str = response.message.content
    else:
        content: str = response["message"]["content"]

    if expect_json:
        return _extract_json(content)
    return content


def embed(text: str, model: str = EMBEDDING_MODEL) -> list[float]:
    """
    Generate an embedding vector for the given text using Ollama.

    Args:
        text:  The text to embed
        model: Embedding model (default: nomic-embed-text)

    Returns:
        List of floats representing the embedding vector
    """
    client = _client()
    response = client.embeddings(model=model, prompt=text)
    # Support both typed response (ollama >= 0.4) and dict response
    if hasattr(response, "embedding"):
        return response.embedding
    return response["embedding"]
