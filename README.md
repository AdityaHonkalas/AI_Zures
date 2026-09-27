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
3. [Models Used](#models-used-ollama)
4. [Before You Begin — Prerequisites](#before-you-begin--prerequisites)
5. [Step-by-Step Setup Guide](#step-by-step-setup-guide)
   - [Step 1 — Install Python](#step-1--install-python)
   - [Step 2 — Install Ollama](#step-2--install-ollama)
   - [Step 3 — Pull AI Models](#step-3--pull-the-required-ai-models)
   - [Step 4 — Get the Code](#step-4--get-the-code)
   - [Step 5 — Create a Virtual Environment](#step-5--create-a-python-virtual-environment-recommended)
   - [Step 6 — Install Dependencies](#step-6--install-python-dependencies)
   - [Step 7 — Configure Environment Variables](#step-7--configure-environment-variables)
   - [Step 8 — Seed the Vector Database](#step-8--seed-the-vector-database-one-time-only)
   - [Step 9 — Run the Application](#step-9--run-the-application)
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

All of this runs locally on your machine using open-source AI models via Ollama.

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

## Models Used (Ollama)

| Task | Model | Temperature |
|---|---|---|
| Reasoning (module mapping, impact, ranking, suite composition) | `llama3.1:8b` | 0.2 |
| Code / Gherkin generation (scenario writer, Playwright scaffolder) | `qwen2.5-coder:7b` | 0.3 |
| Semantic embeddings (test similarity scoring) | `nomic-embed-text` | — |

> **Minimum RAM:** 8 GB to run `llama3.1:8b`. 16 GB recommended to run all three models comfortably.

---

## Before You Begin — Prerequisites

You will need the following tools installed on your machine before starting:

| Tool | Version | Why it's needed |
|---|---|---|
| **Python** | 3.11 or higher | Runs the Flask app and all agent code |
| **pip** | Comes with Python | Installs Python packages |
| **Ollama** | Latest | Runs the local AI models |
| **Git** | Any recent version | Clones the repository |
| **Internet access** | — | To download models and fetch GitHub PR diffs |

> **Windows users:** Use PowerShell or Command Prompt for all commands below.  
> **Mac/Linux users:** Use Terminal.

---

## Step-by-Step Setup Guide

### Step 1 — Install Python

1. Go to [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Download and install **Python 3.11 or higher**.
3. During installation on Windows, **tick the box** that says **"Add Python to PATH"**.
4. Verify the installation by opening a terminal and running:

```bash
python --version
```

You should see something like `Python 3.11.9` or higher.

---

### Step 2 — Install Ollama

Ollama lets you run open-source AI models locally on your machine.

1. Go to [https://ollama.com/download](https://ollama.com/download)
2. Download and install Ollama for your operating system (Windows / macOS / Linux).
3. After installation, Ollama runs automatically as a background service.
4. Verify it is running by opening a terminal and running:

```bash
ollama --version
```

You should see a version number printed.

> **Note:** Ollama must be running in the background whenever you use this app.
> On Windows it appears in the system tray. On Mac it appears in the menu bar.

---

### Step 3 — Pull the Required AI Models

This downloads the three AI models the platform uses. Each model is a large file
(2–5 GB each), so make sure you have a good internet connection and enough disk space (~15 GB total).

Open a terminal and run these three commands **one at a time**:

```bash
ollama pull llama3.1:8b
```
```bash
ollama pull qwen2.5-coder:7b
```
```bash
ollama pull nomic-embed-text
```

Each command will show a download progress bar. Wait for each to complete before running the next.

To verify all three models are ready:

```bash
ollama list
```

You should see `llama3.1:8b`, `qwen2.5-coder:7b`, and `nomic-embed-text` in the list.

---

### Step 4 — Get the Code

Clone the repository to your local machine:

```bash
git clone https://github.com/your-org/AI_Zures.git
cd AI_Zures
```

> If you already have the code on your machine, just navigate to the `AI_Zures` folder:
> ```bash
> cd path/to/AI_Zures
> ```

---

### Step 5 — Create a Python Virtual Environment (Recommended)

A virtual environment keeps the project's packages separate from your system Python
and prevents version conflicts.

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

After activation you will see `(venv)` at the start of your terminal prompt. This means
the virtual environment is active. **You need to activate it every time you open a new terminal.**

---

### Step 6 — Install Python Dependencies

With the virtual environment active, install all required packages:

```bash
pip install -r requirements.txt
```

This installs Flask, ChromaDB, the Ollama SDK, tree-sitter, and all other libraries
the platform needs. It may take 2–5 minutes.

To verify the key packages installed correctly:

```bash
python -c "import flask, chromadb, ollama, unidiff; print('All packages OK')"
```

You should see `All packages OK`.

---

### Step 7 — Configure Environment Variables

The app reads configuration from a `.env` file. Create yours from the provided template:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

Now open `.env` in any text editor (Notepad, VS Code, etc.) and review the settings:

```
# GitHub Personal Access Token
# Leave blank for public repos.
# For private repos: go to GitHub → Settings → Developer settings → Personal access tokens
# → Generate new token → tick "repo" scope → copy the token here.
GITHUB_TOKEN=your_github_pat_here

# Ollama server URL — leave this as-is unless you changed Ollama's port
OLLAMA_BASE_URL=http://localhost:11434

# Where ChromaDB stores its data (a folder will be created automatically)
CHROMA_DB_PATH=./chroma_db

# Maximum allowed test suite duration in seconds (default: 30 minutes)
BUDGET_LIMIT_SECONDS=1800
```

> **Do I need a GitHub token?**  
> - **Public repos:** No token needed. Leave `GITHUB_TOKEN` blank.  
> - **Private repos:** Yes. Follow the instructions in the comment above.

---

### Step 8 — Seed the Vector Database (One-Time Only)

This step embeds the fixture data (test cases and defect history) into ChromaDB
so Agent 3 can perform semantic similarity search. You only need to run this **once**.

Make sure Ollama is running, then:

```bash
python scripts/seed_chroma.py
```

Expected output:

```
Seeding ChromaDB from fixture files...
  Ollama URL:    http://localhost:11434
  ChromaDB path: ./chroma_db

  ✓ test-case-index: 20 items upserted (0 were already present)
  ✓ defect-history-index: 10 items upserted (0 were already present)

✅ ChromaDB seeding complete.
```

> **This step requires Ollama to be running** because it uses the `nomic-embed-text`
> model to create embeddings. If you see a connection error, check that Ollama is running.

---

### Step 9 — Run the Application

Start the Flask web server:

```bash
python run.py
```

You should see output like:

```
 * Running on http://0.0.0.0:5000
 * Debug mode: on
```

Open your web browser and go to:

**[http://localhost:5000](http://localhost:5000)**

The application home page will load with a PR URL input form.

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

3. Click the **Analyse PR** button.
4. Wait while the pipeline runs (typically 30–120 seconds depending on PR size and model speed).

### Reading the Results

Results are shown across **4 tabs**:

| Tab | What it shows |
|---|---|
| 🗺 **Impact Map** | Which modules are directly and transitively affected. The user journeys impacted. The browser and environment combinations that need testing. |
| ⚠ **Risk Scores** | Every candidate test case ranked by composite risk score. Each score is broken down into defect history, telemetry, code churn, and semantic similarity signals. A one-line justification is provided for the top tests. |
| ✅ **Recommended Suite** | The final optimised list of tests to run, ordered by priority. Shows estimated duration, browser, environment, and why each test was selected. |
| 🧬 **Generated Tests** | For any user journeys with no existing test coverage, this tab shows AI-generated Gherkin BDD feature files and Playwright TypeScript test stubs ready for review. |

If any agent encountered an error, a warning banner appears at the top of the results page
listing what went wrong without stopping the rest of the analysis.

---

## Running the Tests

The project includes 28 unit tests covering all 5 agents. Tests use mocks for Ollama and
ChromaDB, so **Ollama does not need to be running** to run the tests.

```bash
pytest tests/ -v
```

All 28 tests should pass:

```
tests/test_agent1.py::test_run_returns_change_context PASSED
tests/test_agent1.py::test_impacted_modules_are_valid_nodes PASSED
...
======================== 28 passed in 1.22s ==============================
```

---

## Troubleshooting

### "Connection refused" when running seed_chroma.py or the app

**Cause:** Ollama is not running.  
**Fix:** Start Ollama. On Windows, look for the Ollama icon in the system tray and click it.
On Mac, look in the menu bar. Or run `ollama serve` in a terminal.

---

### "Model not found" error

**Cause:** One of the three models has not been pulled yet.  
**Fix:** Run the missing pull command:
```bash
ollama pull llama3.1:8b
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
```

---

### "ModuleNotFoundError: No module named 'flask'" (or any other module)

**Cause:** Python packages are not installed, or the virtual environment is not active.  
**Fix:**
1. Make sure you activated the virtual environment (you should see `(venv)` in your prompt).
2. Run `pip install -r requirements.txt` again.

---

### The analysis takes a very long time (> 5 minutes)

**Cause:** The AI models are running on CPU instead of GPU, which is much slower.  
**Fix:** This is expected on machines without a GPU. llama3.1:8b on CPU takes 1–3 minutes
per inference call. Consider using a smaller model like `llama3.2:3b` by editing
`REASONING_MODEL` in [`app/utils/llm_client.py`](app/utils/llm_client.py).

---

### GitHub API rate limit error

**Cause:** Too many unauthenticated requests to the GitHub API.  
**Fix:** Add a GitHub Personal Access Token to your `.env` file:
1. Go to [https://github.com/settings/tokens](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Tick the **`repo`** scope
4. Copy the token and paste it as `GITHUB_TOKEN=ghp_...` in your `.env` file

---

### Flask app starts but the browser shows "404 Not Found"

**Cause:** You may be accessing the wrong port or path.  
**Fix:** Make sure you are going to [http://localhost:5000](http://localhost:5000)
(not `https://` and not port 8000).

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
│   │   ├── github_client.py   # GitHub PR diff fetcher
│   │   ├── diff_parser.py     # unidiff-based diff parser
│   │   ├── ast_analyser.py    # tree-sitter symbol extractor (Python + JS)
│   │   ├── llm_client.py      # Ollama chat + embed wrapper
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
│   ├── test_agent1.py         # 5 tests for Change Analyser
│   ├── test_agent2.py         # 7 tests for Impact Mapper
│   ├── test_agent3.py         # 6 tests for Risk Scorer
│   ├── test_agent4.py         # 5 tests for Suite Recommender
│   └── test_agent5.py         # 5 tests for Scenario Generator
├── output/                    # Generated Gherkin + Playwright files (git-ignored)
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
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL of the local Ollama server |
| `CHROMA_DB_PATH` | `./chroma_db` | Folder path where ChromaDB stores vector data |
| `BUDGET_LIMIT_SECONDS` | `1800` | Maximum allowed total test suite duration in seconds (1800 = 30 min) |
| `FLASK_DEBUG` | `true` | Set to `false` in production to disable debug mode |
| `FLASK_PORT` | `5000` | Port the Flask app listens on |

---

## Future Enhancements — Azure Migration

When ready to migrate from local to Azure, replace each component one-for-one:

| Local Component | Azure Equivalent |
|---|---|
| Ollama `llama3.1:8b` / `qwen2.5-coder:7b` | Azure OpenAI GPT-4o |
| Ollama `nomic-embed-text` | Azure OpenAI `text-embedding-3-large` |
| ChromaDB (local file) | Azure AI Search (vector + hybrid search) |
| Sequential Python function calls | Azure Service Bus topics |
| Static JSON fixtures in `data/` | Azure AI Search indexes + Azure App Insights |
| Flask app | Azure Container Apps or Azure App Service |
| `output/` directory | Azure Blob Storage |
| Manual PR URL input | GitHub / Azure DevOps webhook (Agent 6 — CI/CD Integration) |
