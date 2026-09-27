# Plan: Migrate Gateway Backend to OpenAI Python SDK

## Overview

**Goal:** Replace the raw `requests.post()` implementation inside the gateway backend helpers
(`_gateway_chat`, `_gateway_embed`) with calls through the official `openai` Python SDK
(`OpenAI` client). The Ollama backend, the public `chat()` / `embed()` signatures, all
agent callers, and all 31 existing tests remain unchanged.

**Scope:** `app/utils/llm_client.py` and `requirements.txt` only.

**Non-goals:**
- No change to the Ollama backend (`_ollama_chat`, `_ollama_embed`).
- No change to public API signatures (`chat`, `embed`, `REASONING_MODEL`, `CODE_MODEL`,
  `EMBEDDING_MODEL`).
- No change to any agent file, test file, or `scripts/seed_chroma.py`.
- No new environment variables (reuse `GATEWAY_URL` and `GATEWAY_KEY`).

---

## Architecture

```
chat() / embed()          ← unchanged public API
      │
      ├── _use_gateway() → True
      │       ├── _gateway_chat()    ← REPLACE requests.post → openai SDK
      │       └── _gateway_embed()   ← REPLACE requests.post → openai SDK
      │
      └── _use_gateway() → False
              ├── _ollama_chat()     ← unchanged
              └── _ollama_embed()    ← unchanged
```

The `OpenAI` client is constructed lazily (once per process) via a module-level singleton
helper so the SDK is never imported when the Ollama backend is active.

---

## Sub-Tasks

---

### Sub-Task 1 — Add `openai` to `requirements.txt`

**Status:** `[ ] pending`

**Intent:**
The `openai` package is not yet listed as a dependency. It must be pinned so the
installation is reproducible.

**Expected Outcomes:**
- `requirements.txt` contains `openai>=1.0.0` (SDK v1 introduced the `OpenAI` client class).
- `pip install -r requirements.txt` installs the package without conflict.

**Todo List:**
1. Add `openai>=1.0.0` to `requirements.txt`.

**Relevant Context:**
- File: `AI_Zures/requirements.txt`
- `model_test.py` already uses `from openai import OpenAI` — the package is available in
  the team's environment but not yet declared as a project dependency.

---

### Sub-Task 2 — Replace gateway helpers with OpenAI SDK calls

**Status:** `[ ] pending`

**Intent:**
Swap out the two `requests.post()` implementations inside `_gateway_chat` and
`_gateway_embed` for calls through an `openai.OpenAI` client instance. The client is
constructed lazily (i.e. on first use, not at module-import time) so that importing
`llm_client` never fails when `GATEWAY_URL` / `GATEWAY_KEY` are not set.

**Expected Outcomes:**
- `_gateway_chat` calls `client.chat.completions.create(...)` and returns the string content
  from `response.choices[0].message.content`.
- `_gateway_embed` calls `client.embeddings.create(...)` and returns the list of floats from
  `response.data[0].embedding`.
- The `requests` import is no longer needed for the gateway path (Ollama path still uses it).
- The `_gateway_headers` helper and the raw `requests.post` calls inside both gateway
  helpers are removed.
- The `_use_gateway`, `_gateway_base`, and `_ollama_base` private helpers keep their
  existing signatures (required by `scripts/seed_chroma.py`).

**Todo List:**
1. Add a lazy singleton helper `_openai_client() -> openai.OpenAI` that constructs the
   client from `GATEWAY_URL` (as `base_url`) and `GATEWAY_KEY` (as `api_key`). The
   `base_url` passed to `OpenAI` must end in `/v1` — append it if not already present.
2. Replace the body of `_gateway_chat` to call `_openai_client().chat.completions.create()`
   with the same `model`, `messages`, and `temperature` arguments; return
   `response.choices[0].message.content`.
3. Replace the body of `_gateway_embed` to call `_openai_client().embeddings.create()`
   with the same `model` and `input` arguments; return `response.data[0].embedding`.
4. Remove the `_gateway_headers` helper function (no longer needed).
5. Preserve the `import requests` statement — it is still required for the Ollama backend.

**Relevant Context:**
- File: `AI_Zures/app/utils/llm_client.py`
- Lines to modify: `_gateway_headers` (104–112), `_gateway_chat` (115–130),
  `_gateway_embed` (133–143).
- How `model_test.py` constructs the client:
  ```python
  client = OpenAI(
      base_url=os.environ["GATEWAY_URL"].rstrip("/") + "/v1",
      api_key=os.environ["GATEWAY_KEY"],
  )
  ```
- The `_effective_model(model)` call must be retained in both gateway helpers — it
  applies the `REASONING_MODEL_OVERRIDE` / `CODE_MODEL_OVERRIDE` /
  `EMBEDDING_MODEL_OVERRIDE` env var logic.
- `openai.OpenAI` raises `openai.OpenAIError` on API failures; the public `chat()` and
  `embed()` docstrings currently document `requests.HTTPError` — update them to
  `openai.OpenAIError | requests.HTTPError` to reflect both backends.

**Wire format produced by the SDK (matches current raw implementation):**
```
POST {GATEWAY_URL}/v1/chat/completions
Body: { "model": "...", "messages": [...], "temperature": 0.2 }

POST {GATEWAY_URL}/v1/embeddings
Body: { "model": "...", "input": "..." }
```

---

### Sub-Task 3 — Update module docstring and `.env.example`

**Status:** `[ ] pending`

**Intent:**
Keep the module-level docstring accurate — it currently documents the raw HTTP wire
format, which is now handled internally by the SDK. The `.env.example` requires no new
variables but the comment should mention the SDK is used.

**Expected Outcomes:**
- The module docstring in `llm_client.py` describes the SDK client (not raw HTTP) for the
  gateway backend section.
- The docstrings of `chat()` and `embed()` list the correct exception types for both
  backends.
- `.env.example` comment for `GATEWAY_URL` notes the SDK is used (one-line change).

**Todo List:**
1. Update the gateway section of the module docstring in `llm_client.py` to say the `openai`
   SDK client is used rather than describing raw JSON request/response bodies.
2. Update the `Raises:` section of `chat()` and `embed()` docstrings to list
   `openai.OpenAIError` (gateway) and `requests.HTTPError` (Ollama).
3. Add one comment line to `.env.example` noting the OpenAI SDK is used for the gateway.

**Relevant Context:**
- File: `AI_Zures/app/utils/llm_client.py` lines 1–46 (module docstring), 248–254
  (chat raises), 294–299 (embed raises).
- File: `AI_Zures/.env.example` lines 9–20 (gateway section).

---

### Sub-Task 4 — Verify tests still pass

**Status:** `[ ] pending`

**Intent:**
The existing 31 tests all mock `llm_client.chat` and `llm_client.embed` at the module
level, so they are unaffected by the internal implementation change. This sub-task
confirms that by running the full test suite and checking there are no import-time
breakages introduced by the new `import openai` statement.

**Expected Outcomes:**
- `pytest tests/ -v` reports `31 passed`.
- No `ImportError` or `ModuleNotFoundError` on `import openai`.

**Todo List:**
1. Run `pytest tests/ -v` and confirm all 31 tests pass.
2. If any test fails, record the failure here and fix before marking complete.

**Relevant Context:**
- All test files patch `app.agents.<agent>.llm_client.chat` and `.embed` — they bypass
  both the gateway and Ollama implementations entirely, so the SDK switch is transparent.
- The `openai` package must be installed in the active virtual environment before running
  tests (`pip install openai>=1.0.0`).

---

## Files Changed

| File | Nature of change |
|---|---|
| `requirements.txt` | Add `openai>=1.0.0` |
| `app/utils/llm_client.py` | Add `import openai`; add `_openai_client()` singleton; replace `_gateway_chat` and `_gateway_embed` bodies; remove `_gateway_headers`; update docstrings |
| `.env.example` | One-line comment update in gateway section |

## Files Unchanged

| File | Why unchanged |
|---|---|
| `app/agents/*.py` | Call `llm_client.chat()` / `llm_client.embed()` — public API is identical |
| `scripts/seed_chroma.py` | Uses `_use_gateway()`, `_gateway_base()`, `_ollama_base()` — all preserved |
| `tests/test_agent[1-5].py` | Mock at `llm_client.chat` / `llm_client.embed` level — bypass implementation |
| `app/utils/vector_store.py` | Unrelated to LLM client |
| `app/utils/github_client.py` | Unrelated to LLM client |
