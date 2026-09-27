# Agentic Regression Testing Platform — Local Development

An AI-powered agentic platform that analyses a GitHub Pull Request and automatically:
- Identifies impacted application modules
- Maps the blast radius via dependency traversal
- Scores and ranks test cases by risk
- Recommends an optimised regression suite
- Generates Gherkin BDD scenarios and Playwright stubs for uncovered journeys

---

## Table of Contents

1. [What This App Does](#what-this-app-does)
2. [How It Works — Architecture](#how-it-works--architecture)
3. [LLM Backend Options](#llm-backend-options)
4. [Before You Begin — Prerequisites](#before-you-begin--prerequisites)
5. [Step-by-Step Setup Guide](#step-by-step-setup-guide)
   - [Step 1 — Install Python](#step-1--install-python)
   - [Step 2 — Get the Code](#step-2--get-the-code)
   - [Step 3 — Create a Virtual Environment](#step-3--create-a-python-virtual-environment-recommended)
   - [Step 4 — Install Dependencies](#step-4--install-python-dependencies)
   - [Step 5 — Configure Environment Variables](#step-5--configure-environment-variables)
   - [Step 6 — Seed the Vector Database](#step-6--seed-the-vector-database-one-time-only)
   - [Step 7 — Run the Application](#step-7--run-the-application)
6. [Using the App](#using-the-app)
7. [Running the Tests](#running-the-tests)
8. [Troubleshooting](#troubleshooting)
9. [Project Structure](#project-structure)
10. [Environment Variables Reference](#environment-variables-reference)
11. [Future Enhancements — Azure Migration](#future-enhancements--azure-migration)

---

## What This App Does

When a developer raises a Pull Request on GitHub, a QA team normally has to run the
**entire regression test suite** across multiple browsers and environments — even when only
a small part of the application changed. This is slow and expensive.

This platform solves that by:

1. **Reading the PR diff** — what files and functions changed?
2. **Mapping the impact** — which modules and user journeys does the change touch?
3. **Scoring the risk** — which tests are most likely to catch a defect?
4. **Recommending a trimmed suite** — only the tests that matter, within your time budget.
5. **Generating new tests** — for journeys that have no existing coverage.

---

## How It Works — Architecture

```
Flask UI (PR URL input)
        │
        ▼
Agent 1: Change Analyser    (GitHub diff + AST + LLM module mapping)
        │
        ▼
Agent 2: Impact Mapper       (dependency graph + journey mapping + browser matrix)
        │
        ▼
Agent 3: Risk Scorer         (defect + telemetry + churn + semantic similarity)
        │
        ▼
Agent 4: Suite Recommender   (dedup + budget solver + coverage guarantee)
        │
        ▼
Agent 5: Scenario Generator  (gap detection + Gherkin + Playwright stubs)
        │
        ▼
Flask UI (4-tab results dashboard)
```

---

## LLM Backend Options

The app supports **two backends**, selected automatically based on your `.env`:

### Option A — OpenAI-Compatible Gateway (recommended)

Set `GATEWAY_URL` and `GATEWAY_KEY` in your `.env`. When `GATEWAY_URL` is present the app
uses the OpenAI wire protocol (`/v1/chat/completions`, `/v1/embeddings`).

This works with any OpenAI-compatible endpoint, including:
- **IBM watsonx.ai** (`https://api.us-south.ml.cloud.ibm.com/ml/v1`)
- **OpenAI** (`https://api.openai.com`)
- Any self-hosted or proxied gateway

Set model name overrides to map to the gateway's model aliases:

```env
GATEWAY_URL=https://your-gateway.example.com
GATEWAY_KEY=your_api_key

REASONING_MODEL_OVERRIDE=gpt-5-gig           # or gpt-4o, ibm/granite-13b-chat-v2, etc.
CODE_MODEL_OVERRIDE=gpt-5-gig
EMBEDDING_MODEL_OVERRIDE=text-embedding-3-large-gig
```

### Option B — Local Ollama (fallback)

Leave `GATEWAY_URL` unset (or blank). The app calls the Ollama REST API directly at
`OLLAMA_BASE_URL` (defaults to `http://localhost:11434`).

| Task | Default model | Temperature |
|---|---|---|
| Reasoning (module mapping, impact, ranking) | `llama3.1:8b` | 0.2 |
| Code / Gherkin generation | `qwen2.5-coder:7b` | 0.3 |
| Semantic embeddings | `nomic-embed-text` | — |

Pull models once with:

```bash
ollama pull llama3.1:8b
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
```

> **Minimum RAM for Ollama:** 8 GB to run `llama3.1:8b`. 16 GB recommended.

---

## Before You Begin — Prerequisites

| Tool | Version | Why it's needed |
|---|---|---|
| **Python** | 3.11 or higher | Runs the Flask app and all agent code |
| **pip** | Comes with Python | Installs Python packages |
| **Git** | Any recent version | Clones the repository |
| **Internet access** | — | To call the LLM gateway / Ollama cloud and fetch GitHub PR diffs |
| **Ollama** *(Option B only)* | Latest | Only needed if using local Ollama as the LLM backend |

> **Windows users:** Use PowerShell or Command Prompt for all commands below.  
> **Mac/Linux users:** Use Terminal.

---

## Step-by-Step Setup Guide

### Step 1 — Install Python

1. Go to [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Download and install **Python 3.11 or higher**.
3. During installation on Windows, **tick the box** that says **"Add Python to PATH"**.
4. Verify the installation:

```bash
python --version
```

You should see something like `Python 3.11.9` or higher.

---

### Step 2 — Get the Code

Clone the repository:

```bash
git clone https://github.com/your-org/AI_Zures.git
cd AI_Zures
```

---

### Step 3 — Create a Python Virtual Environment (Recommended)

```bash
# Create the virtual environment (only needed once)
python -m venv venv
```

Now **activate** it:

**Windows (PowerShell):**
```powershell
venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
venv\Scripts\activate.bat
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

After activation you will see `(venv)` at the start of your terminal prompt.
**You need to activate it every time you open a new terminal.**

---

### Step 4 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs Flask, ChromaDB, tree-sitter, requests, and all other libraries.
It may take 2–5 minutes.

To verify the key packages installed correctly:

```bash
python -c "import flask, chromadb, unidiff; print('All packages OK')"
```

---

### Step 5 — Configure Environment Variables

Create your `.env` from the provided template:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in the values for your chosen backend:

**Option A — OpenAI-compatible gateway:**
```env
GATEWAY_URL=https://your-gateway-url-here
GATEWAY_KEY=your_api_key_here

# Set these to the model names your gateway uses:
REASONING_MODEL_OVERRIDE=gpt-5-gig
CODE_MODEL_OVERRIDE=gpt-5-gig
EMBEDDING_MODEL_OVERRIDE=text-embedding-3-large-gig
```

**Option B — Local Ollama:**
```env
# Comment out or leave GATEWAY_URL blank
OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_API_KEY=   ← leave blank for local Ollama
```

**GitHub token (both options):**
```env
GITHUB_TOKEN=your_github_pat_here
# Leave blank for public repos. Required for private repos.
```

> **Do I need a GitHub token?**  
> - **Public repos:** No token needed. Leave `GITHUB_TOKEN` blank.  
> - **Private repos:** Yes. Go to GitHub → Settings → Developer settings →
>   Personal access tokens → Generate new token → tick `repo` scope → copy here.

---

### Step 6 — Seed the Vector Database (One-Time Only)

This embeds the fixture data (test cases and defect history) into ChromaDB
so Agent 3 can perform semantic similarity search. Run this **once** after setup.

```bash
python scripts/seed_chroma.py
```

Expected output:

```
Seeding ChromaDB from fixture files...
  LLM backend:   gateway  (https://your-gateway-url-here)
  ChromaDB path: ./chroma_db

  ✓ test-case-index: 20 items upserted (0 were already present)
  ✓ defect-history-index: 10 items upserted (0 were already present)

✅ ChromaDB seeding complete.
```

> This step makes a real call to the LLM backend to generate embeddings. Make sure your
> `GATEWAY_URL` / `GATEWAY_KEY` (or Ollama) is correctly configured first.

---

### Step 7 — Run the Application

```bash
python run.py
```

You should see:

```
 * Running on http://0.0.0.0:5000
 * Debug mode: on
```

Open your browser at **[http://localhost:5000](http://localhost:5000)**.

> **To stop the app**, press `Ctrl + C` in the terminal.

---

## Using the App

### Submitting a PR for Analysis

1. Open [http://localhost:5000](http://localhost:5000) in your browser.
2. Paste a GitHub Pull Request URL into the input box.

   **Example URL format:**
   ```
   https://github.com/owner/repository/pull/42
   ```

3. Click **Analyse PR**.
4. Wait while the pipeline runs (typically 30–120 seconds depending on PR size).

### Reading the Results

Results are shown across **4 tabs**:

| Tab | What it shows |
|---|---|
| 🗺 **Impact Map** | Which modules are directly and transitively affected. The user journeys impacted. The browser and environment combinations that need testing. |
| ⚠ **Risk Scores** | Every candidate test case ranked by composite risk score. Each score is broken down into defect history, telemetry, code churn, and semantic similarity signals. |
| ✅ **Recommended Suite** | The final optimised list of tests to run, ordered by priority. Shows estimated duration, browser, environment, and why each test was selected. |
| 🧬 **Generated Tests** | For any user journeys with no existing test coverage, this tab shows AI-generated Gherkin BDD feature files and Playwright TypeScript test stubs ready for review. |

If any agent encountered an error, a warning banner appears at the top of the results page
listing what went wrong without stopping the rest of the analysis.

---

## Running the Tests

The project includes 31 unit tests covering all 5 agents. Tests mock all HTTP calls to the
LLM backend and ChromaDB, so **no live API credentials are needed** to run tests.

```bash
pytest tests/ -v
```

All 31 tests should pass:

```
tests/test_agent1.py::test_run_returns_change_context PASSED
tests/test_agent1.py::test_repo_test_files_stored_in_context PASSED
...
======================== 31 passed in 4.15s ==============================
```

---

## Troubleshooting

### HTTP error when running seed_chroma.py or the app

**Cause:** The LLM gateway is unreachable or the API key is wrong.  
**Fix:**
- Verify `GATEWAY_URL` is correct (no trailing slash, no `/v1` path appended by hand).
- Check `GATEWAY_KEY` is set correctly in `.env`.
- Test connectivity: `curl -H "Authorization: Bearer $GATEWAY_KEY" $GATEWAY_URL/v1/models`

If using **local Ollama** instead: make sure Ollama is running (`ollama serve`) and
`GATEWAY_URL` is either blank or commented out in `.env`.

---

### "Model not found" error (Ollama backend)

**Cause:** One of the three models has not been pulled yet.  
**Fix:**
```bash
ollama pull llama3.1:8b
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
```

---

### "ModuleNotFoundError: No module named 'flask'" (or any other module)

**Cause:** Packages not installed, or the virtual environment is not active.  
**Fix:**
1. Make sure you activated the virtual environment (`(venv)` should be visible in your prompt).
2. Run `pip install -r requirements.txt` again.

---

### The analysis takes a very long time (> 5 minutes)

**With local Ollama:** `llama3.1:8b` on CPU takes 1–3 minutes per inference call.
Consider a smaller model by setting `REASONING_MODEL_OVERRIDE=llama3.2:3b` in `.env`.

**With a gateway:** Check your gateway's rate limits and whether the chosen model is available.

---

### GitHub API rate limit error

**Cause:** Too many unauthenticated requests to the GitHub API.  
**Fix:** Add a GitHub Personal Access Token to `.env`:
1. Go to [https://github.com/settings/tokens](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Tick the **`repo`** scope
4. Paste it as `GITHUB_TOKEN=ghp_...` in `.env`

---

### Flask app starts but the browser shows "404 Not Found"

**Fix:** Go to [http://localhost:5000](http://localhost:5000) — not `https://` and not port 8000.

---

## Project Structure

```
AI_Zures/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── routes.py            # GET / and POST /analyse endpoints
│   ├── pipeline.py          # Sequential agent orchestrator
│   ├── agents/
│   │   ├── change_analyser.py    # Agent 1 — diff + AST + LLM module mapping
│   │   ├── impact_mapper.py      # Agent 2 — dependency graph + journey mapping
│   │   ├── risk_scorer.py        # Agent 3 — 4-signal scoring + composite ranking
│   │   ├── suite_recommender.py  # Agent 4 — dedup + budget + coverage guarantee
│   │   └── scenario_generator.py # Agent 5 — Gherkin + Playwright stub generation
│   ├── utils/
│   │   ├── github_client.py   # GitHub PR diff, file contents, repo tree fetcher
│   │   ├── diff_parser.py     # unidiff-based diff parser
│   │   ├── ast_analyser.py    # tree-sitter symbol extractor (Python + JS)
│   │   ├── llm_client.py      # Dual-backend LLM client (gateway + Ollama)
│   │   ├── vector_store.py    # ChromaDB wrapper
│   │   └── fixture_loader.py  # JSON fixture loader
│   └── templates/
│       ├── index.html         # PR URL input form
│       └── results.html       # 4-tab results dashboard
├── data/                      # Static JSON fixture files (simulate knowledge stores)
│   ├── dependency_graph.json  # Module nodes + edges
│   ├── test_cases.json        # 20 test cases with metadata
│   ├── defect_history.json    # Per-module defect counts and severity
│   ├── telemetry.json         # Per-module page views and error rates
│   ├── browser_matrix.json    # Module → browser/environment mapping
│   └── user_stories.json      # User stories with acceptance criteria
├── scripts/
│   └── seed_chroma.py         # One-time ChromaDB seeding script
├── tests/
│   ├── test_agent1.py         # 8 tests for Change Analyser
│   ├── test_agent2.py         # 7 tests for Impact Mapper
│   ├── test_agent3.py         # 6 tests for Risk Scorer
│   ├── test_agent4.py         # 5 tests for Suite Recommender
│   └── test_agent5.py         # 5 tests for Scenario Generator
├── chroma_db/                 # ChromaDB persistent vector store (git-ignored)
├── requirements.txt           # Python package dependencies
├── .env.example               # Environment variable template
├── .env                       # Your local config (git-ignored, create from .env.example)
└── run.py                     # Flask app entrypoint
```

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `GITHUB_TOKEN` | *(empty)* | GitHub PAT — optional for public repos, required for private repos |
| `GATEWAY_URL` | *(empty)* | OpenAI-compatible gateway base URL. When set, takes priority over Ollama |
| `GATEWAY_KEY` | *(empty)* | API key for the gateway (`Authorization: Bearer <key>`) |
| `REASONING_MODEL_OVERRIDE` | *(empty)* | Override the reasoning model name for the gateway |
| `CODE_MODEL_OVERRIDE` | *(empty)* | Override the code/Gherkin model name for the gateway |
| `EMBEDDING_MODEL_OVERRIDE` | *(empty)* | Override the embedding model name for the gateway |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL (used when `GATEWAY_URL` is not set) |
| `OLLAMA_API_KEY` | *(empty)* | Optional API key for authenticated Ollama endpoints |
| `CHROMA_DB_PATH` | `./chroma_db` | Folder where ChromaDB stores vector data |
| `BUDGET_LIMIT_SECONDS` | `1800` | Maximum allowed total test suite duration in seconds (1800 = 30 min) |
| `FLASK_DEBUG` | `true` | Set to `false` in production |
| `FLASK_PORT` | `5000` | Port the Flask app listens on |

---

## Future Enhancements — Azure Migration

When ready to migrate from local to Azure, replace each component one-for-one:

| Local Component | Azure Equivalent |
|---|---|
| OpenAI-compatible gateway / Ollama | Azure OpenAI GPT-4o / IBM watsonx.ai |
| ChromaDB (local file) | Azure AI Search (vector + hybrid search) |
| Sequential Python function calls | Azure Service Bus topics |
| Static JSON fixtures in `data/` | Azure AI Search indexes + Azure App Insights |
| Flask app | Azure Container Apps or Azure App Service |
| Manual PR URL input | GitHub / Azure DevOps webhook (Agent 6 — CI/CD Integration) |
