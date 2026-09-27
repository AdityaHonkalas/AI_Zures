"""
LLM client — Azure AI Inference SDK backend.

Environment variables:
  AZURE_INFERENCE_ENDPOINT   Full endpoint URL of the Azure AI model deployment.
                             Example: https://hub-proxy-service.thankfulfield-16b4d5d6.eastus.azurecontainerapps.io
  AZURE_INFERENCE_KEY        API key (sent as Authorization: Bearer <key>)

  LLM_MODEL    Model name for reasoning tasks  (Agents 1–4)  default: gpt-4o
  CODE_MODEL   Model name for code generation  (Agent 5)     default: gpt-4o
  EMBED_MODEL  Model name for embeddings       (Agent 3)     default: text-embedding-3-large

Models are resolved via the Azure AI Inference ChatCompletionsClient and EmbeddingsClient,
both of which speak the OpenAI wire format and work against any Azure-hosted deployment.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from azure.ai.inference import ChatCompletionsClient, EmbeddingsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

logger = logging.getLogger(__name__)

# ── Model constants ───────────────────────────────────────────────────────────
REASONING_MODEL = os.environ.get("LLM_MODEL",   "gpt-4o")
CODE_MODEL      = os.environ.get("CODE_MODEL",  "gpt-4o")
EMBEDDING_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-large")

# ── Default tuning params ─────────────────────────────────────────────────────
_REASONING_TEMPERATURE = 0.2
_CODE_TEMPERATURE      = 0.3

# Request timeout in seconds
_CHAT_TIMEOUT  = 120
_EMBED_TIMEOUT = 30


# ── Client factory helpers ────────────────────────────────────────────────────

def _endpoint() -> str:
    url = os.environ.get("AZURE_INFERENCE_ENDPOINT", "").strip().rstrip("/")
    if not url:
        raise EnvironmentError(
            "AZURE_INFERENCE_ENDPOINT is not set. "
            "Add it to your .env file."
        )
    return url


def _credential() -> AzureKeyCredential:
    key = os.environ.get("AZURE_INFERENCE_KEY", "").strip()
    if not key:
        raise EnvironmentError(
            "AZURE_INFERENCE_KEY is not set. "
            "Add it to your .env file."
        )
    return AzureKeyCredential(key)


def _chat_client() -> ChatCompletionsClient:
    return ChatCompletionsClient(
        endpoint=_endpoint(),
        credential=_credential(),
    )


def _embed_client() -> EmbeddingsClient:
    return EmbeddingsClient(
        endpoint=_endpoint(),
        credential=_credential(),
    )


# ── JSON extraction helper ────────────────────────────────────────────────────

def _extract_json(text: str) -> Any:
    """
    Extract the first valid JSON object or array from a string.
    Handles cases where the model wraps JSON in markdown code fences.
    """
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
    num_ctx: int = 8192,           # kept for API compatibility; ignored by Azure
    system: str | None = None,
    expect_json: bool = False,
) -> str | Any:
    """
    Send a chat prompt to an Azure AI Inference deployment.

    Args:
        prompt:      The user message content.
        model:       Azure deployment name (defaults to LLM_MODEL env var).
        temperature: Sampling temperature; uses model default if None.
        num_ctx:     Ignored (Ollama-only parameter kept for call-site compatibility).
        system:      Optional system prompt prepended to the conversation.
        expect_json: If True, appends a JSON-only instruction and parses the response.

    Returns:
        str  — raw response text when expect_json=False
        dict — parsed JSON when expect_json=True

    Raises:
        EnvironmentError       — when AZURE_INFERENCE_ENDPOINT or AZURE_INFERENCE_KEY is missing
        azure.core.HttpResponseError — on non-2xx HTTP response
        ValueError             — when expect_json=True but response is not valid JSON
    """
    if temperature is None:
        temperature = _CODE_TEMPERATURE if model == CODE_MODEL else _REASONING_TEMPERATURE

    messages = []
    if system:
        messages.append(SystemMessage(content=system))

    user_content = prompt
    if expect_json:
        user_content = (
            prompt
            + "\n\nIMPORTANT: Respond ONLY with valid JSON. "
            "Do not include any explanation, markdown fences, or extra text outside the JSON."
        )
    messages.append(UserMessage(content=user_content))

    logger.debug("Azure chat  model=%s  temperature=%.2f", model, temperature)

    client = _chat_client()
    response = client.complete(
        messages=messages,
        model=model,
        temperature=temperature,
    )
    content: str = response.choices[0].message.content

    if expect_json:
        return _extract_json(content)
    return content


def embed(text: str, model: str = EMBEDDING_MODEL) -> list[float]:
    """
    Generate an embedding vector via Azure AI Inference.

    Args:
        text:  The text to embed.
        model: Azure embedding deployment name (defaults to EMBED_MODEL env var).

    Returns:
        List of floats representing the embedding vector.

    Raises:
        EnvironmentError       — when AZURE_INFERENCE_ENDPOINT or AZURE_INFERENCE_KEY is missing
        azure.core.HttpResponseError — on non-2xx HTTP response
    """
    logger.debug("Azure embed  model=%s  len=%d", model, len(text))

    client = _embed_client()
    response = client.embed(
        input=[text],
        model=model,
    )
    return response.data[0].embedding
