# Local Development Implementation Plan
# Azure OpenAI-Powered Agentic Testing Platform

## Overview

This plan covers the **local-first implementation** of the Agentic Testing Platform.
The platform analyses a GitHub Pull Request, identifies impacted modules, scores test risk,
recommends an optimised regression suite, and generates new test scenarios — all orchestrated
as a sequential Python pipeline exposed through a Flask web UI.

**Scope:** Agents 1–5 only. Agent 6 (CI/CD Integration & Traceability) and the CI trigger are
explicitly deferred as future enhancements.

**Technology choices (local mode):**

| Concern | Local Choice | Future Azure Equivalent |
|---|---|---|
| LLM (reasoning) | Ollama `llama3.1:8b` | GPT-4o (Azure OpenAI) |
| LLM (code/Gherkin) | Ollama `qwen2.5-coder:7b` | GPT-4o (Azure OpenAI) |
| Embedding model | Ollama `nomic-embed-text` | text-embedding-3-large |
| Vector store | ChromaDB (persistent, file-based) | Azure AI Search |
| Agent messaging | Sequential Python function calls (dict context) | Azure Service Bus |
| State / traceability | In-memory dict + JSON file dump | Azure Cosmos DB |
| Fixture data | Static JSON files in `data/` | Azure AI Search indexes + App Insights |
| Web UI | Flask + Jinja2 (tabbed dashboard) | Azure Static Web Apps (React) |

---

## Project Directory Layout

```
AI_Zures/
├── app/
│   ├── __init__.py
│   ├── routes.py                  # Flask routes
│   ├── pipeline.py                # Top-level orchestrator: runs agents 1→5 in sequence
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── change_analyser.py     # Agent 1
│   │   ├── impact_mapper.py       # Agent 2
│   │   ├── risk_scorer.py         # Agent 3
│   │   ├── suite_recommender.py   # Agent 4
│   │   └── scenario_generator.py  # Agent 5
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── github_client.py       # GitHub diff fetcher
│   │   ├── diff_parser.py         # Raw diff → structured changes
│   │   ├── ast_analyser.py        # tree-sitter AST symbol extractor
│   │   ├── llm_client.py          # Ollama API wrapper (chat + embed)
│   │   ├── vector_store.py        # ChromaDB wrapper (upsert + query)
│   │   └── fixture_loader.py      # Loads JSON fixture files from data/
│   └── templates/
│       ├── index.html             # PR input form
│       └── results.html           # Tabbed results dashboard
├── data/
│   ├── dependency_graph.json
│   ├── defect_history.json
│   ├── telemetry.json
│   ├── test_cases.json
│   ├── browser_matrix.json
│   └── user_stories.json
├── chroma_db/                     # ChromaDB persistent storage (git-ignored)
├── scripts/
│   └── seed_chroma.py             # One-time script to embed fixtures into ChromaDB
├── tests/
│   ├── test_agent1.py
│   ├── test_agent2.py
│   ├── test_agent3.py
│   ├── test_agent4.py
│   └── test_agent5.py
├── requirements.txt
├── .env                           # GITHUB_TOKEN, OLLAMA_BASE_URL
└── run.py                         # Flask entrypoint
```

---

## Agent I/O Contracts

Each agent receives a `PipelineContext` dict that is mutated and passed forward.

```
PipelineContext = {
  "pr_url":             str,                   # Input from UI
  "pr_metadata":        dict,                  # PR number, title, repo, author
  "diff_raw":           str,                   # Raw unified diff text
  "change_context":     ChangeContext,         # Output of Agent 1
  "impact_map":         ImpactMap,             # Output of Agent 2
  "risk_ranked_tests":  RiskRankedTestList,    # Output of Agent 3
  "recommended_suite":  RecommendedSuite,      # Output of Agent 4
  "generated_scenarios": GeneratedScenarios,  # Output of Agent 5
  "errors":             list[str],             # Accumulated non-fatal errors
}
```

### Agent 1 Output — `ChangeContext`
```json
{
  "changed_files": [
    {"file": "src/checkout/cart.py", "change_type": "modified", "added_lines": 12, "removed_lines": 3}
  ],
  "changed_symbols": [
    {"file": "src/checkout/cart.py", "type": "function", "name": "add_item"}
  ],
  "impacted_modules": ["checkout", "payment"],
  "linked_user_stories": ["US-101", "US-204"]
}
```

### Agent 2 Output — `ImpactMap`
```json
{
  "directly_impacted_modules": ["checkout", "payment"],
  "transitively_impacted_modules": ["notification", "order-history"],
  "user_journeys": [
    {"journey_id": "UJ-01", "name": "Add to Cart and Checkout", "impacted_modules": ["checkout"]}
  ],
  "browser_env_matrix": [
    {"browser": "chrome", "env": "staging"},
    {"browser": "edge",   "env": "staging"}
  ]
}
```

### Agent 3 Output — `RiskRankedTestList`
```json
{
  "ranked_tests": [
    {
      "test_id": "TC-042",
      "test_name": "Checkout with valid card",
      "risk_score": 0.87,
      "score_breakdown": {
        "defect_score": 0.9,
        "churn_score": 0.8,
        "telemetry_score": 0.85,
        "semantic_score": 0.83
      },
      "rank": 1,
      "justification": "High defect density and heavy user traffic"
    }
  ]
}
```

### Agent 4 Output — `RecommendedSuite`
```json
{
  "suite": [
    {
      "test_id": "TC-042",
      "test_name": "Checkout with valid card",
      "browser": "chrome",
      "environment": "staging",
      "priority": 1,
      "estimated_duration_s": 45,
      "justification": "Highest risk score; covers primary checkout journey"
    }
  ],
  "total_estimated_duration_s": 720,
  "coverage_gaps": [],
  "budget_limit_s": 1800
}
```

### Agent 5 Output — `GeneratedScenarios`
```json
{
  "coverage_gaps": ["UJ-03: Guest Checkout"],
  "scenarios": [
    {
      "journey_id": "UJ-03",
      "feature_file": "features/guest_checkout.feature",
      "gherkin": "Feature: Guest Checkout\n  Scenario: ...",
      "playwright_stub": "test('Guest Checkout', async ({ page }) => { ... })"
    }
  ]
}
```

---

## Sub-Tasks

---

### Sub-Task 1 — Project Scaffold & Dependencies

**Intent:** Set up the Python project structure, install dependencies, and configure environment
variables so every subsequent sub-task has a stable foundation to build on.

**Expected Outcomes:**
- `requirements.txt` defines all dependencies
- `.env` template documented
- Flask app boots and shows the input form at `http://localhost:5000`
- All directories and `__init__.py` files exist

**Todo List:**
- [ ] Create directory structure as shown in the layout above
- [ ] Write `requirements.txt` with: `flask`, `requests`, `python-dotenv`, `unidiff`,
      `tree-sitter`, `tree-sitter-python`, `tree-sitter-javascript`, `chromadb`,
      `ollama` (Python SDK), `pytest`
- [ ] Write `.env` with `GITHUB_TOKEN`, `OLLAMA_BASE_URL=http://localhost:11434`,
      `CHROMA_DB_PATH=./chroma_db`, `BUDGET_LIMIT_SECONDS=1800`
- [ ] Scaffold `run.py` and `app/__init__.py` (Flask factory)
- [ ] Scaffold `app/routes.py` with a `GET /` (form) and `POST /analyse` (pipeline trigger)
- [ ] Scaffold `app/templates/index.html` (PR URL input form)
- [ ] Scaffold `app/templates/results.html` (4-tab layout: Impact Map, Risk Scores,
      Recommended Suite, Generated Tests)
- [ ] Verify `flask run` renders the form without errors

**Relevant Context:**
- `run.py` → `app/__init__.py` → `app/routes.py`
- `.env` loaded via `python-dotenv` in `app/__init__.py`

**Status:** [ ] pending

---

### Sub-Task 2 — Static Fixture Data

**Intent:** Create realistic JSON fixture files in `data/` that simulate the knowledge stores
all agents draw from. These replace Azure AI Search indexes, Cosmos DB, and App Insights
for local development.

**Expected Outcomes:**
- 6 fixture files exist in `data/` with realistic, consistent test data
- `fixture_loader.py` utility loads any fixture by name
- Fixtures share consistent module/journey/test IDs across files

**Todo List:**
- [ ] Write `data/dependency_graph.json` — module nodes + edges
      (e.g. `checkout → payment → notification`)
- [ ] Write `data/test_cases.json` — 20+ test cases with fields:
      `test_id`, `test_name`, `module`, `journey_id`, `browser`, `environment`,
      `last_run_status`, `estimated_duration_s`, `coverage_fingerprint`
- [ ] Write `data/defect_history.json` — per-module defect counts, severity, recency
- [ ] Write `data/telemetry.json` — per-module `page_views_per_day`, `error_rate`
- [ ] Write `data/browser_matrix.json` — module → `[{browser, env}]` mapping
- [ ] Write `data/user_stories.json` — user story text + acceptance criteria
      linked by `story_id` matching `linked_user_stories` from Agent 1 output
- [ ] Write `app/utils/fixture_loader.py` — single `load_fixture(name: str) -> dict` function

**Relevant Context:**
- All module names and journey IDs must be consistent across all 6 files
- Agent 2 reads `dependency_graph.json` + `browser_matrix.json`
- Agent 3 reads `defect_history.json` + `telemetry.json` + `test_cases.json`
- Agent 5 reads `user_stories.json`

**Status:** [ ] pending

---

### Sub-Task 3 — Utility Layer

**Intent:** Build the shared utility components used by multiple agents —
GitHub diff fetching, diff parsing, AST analysis, Ollama LLM calls, and ChromaDB vector operations.

**Expected Outcomes:**
- `github_client.py` fetches a raw unified diff from a GitHub PR URL
- `diff_parser.py` converts raw diff text into a structured list of changed files/lines
- `ast_analyser.py` extracts changed function/class names from a file's source using tree-sitter
- `llm_client.py` wraps Ollama chat completions and embeddings with consistent JSON-output prompting
- `vector_store.py` wraps ChromaDB for upsert and nearest-neighbour query
- `seed_chroma.py` embeds all test cases and defect history into ChromaDB at startup

**Todo List:**
- [ ] Write `app/utils/github_client.py`:
      - `fetch_pr_diff(pr_url: str) -> tuple[dict, str]`
        returns `(pr_metadata, raw_diff_text)` using GitHub REST API
      - Supports both `github.com/owner/repo/pull/N` and API URL formats
      - Reads `GITHUB_TOKEN` from env (optional — public repos work unauthenticated)
- [ ] Write `app/utils/diff_parser.py`:
      - `parse_diff(raw_diff: str) -> list[dict]`
        returns `[{file, change_type, added_lines, removed_lines, hunks}]`
      - Uses `unidiff` library
- [ ] Write `app/utils/ast_analyser.py`:
      - `extract_symbols(file_path: str, source_code: str, language: str) -> list[dict]`
        returns `[{type, name, start_line, end_line}]`
      - Supports Python and JavaScript via tree-sitter
      - Gracefully falls back to empty list if language unsupported
- [ ] Write `app/utils/llm_client.py`:
      - `chat(prompt: str, model: str, temperature: float, expect_json: bool) -> str | dict`
      - `embed(text: str) -> list[float]`  (uses `nomic-embed-text`)
      - Model defaults: reasoning → `llama3.1:8b`, code → `qwen2.5-coder:7b`
      - Tuning params: reasoning `temperature=0.2, num_ctx=8192`;
        code `temperature=0.3, num_ctx=8192`
      - When `expect_json=True`, appends JSON instruction to prompt and parses response
- [ ] Write `app/utils/vector_store.py`:
      - `upsert(collection: str, ids, documents, embeddings, metadatas)`
      - `query(collection: str, query_embedding, n_results: int) -> list[dict]`
      - Uses ChromaDB persistent client at `CHROMA_DB_PATH`
- [ ] Write `scripts/seed_chroma.py`:
      - Loads `test_cases.json` and `defect_history.json` fixtures
      - Embeds each item's text description via `llm_client.embed()`
      - Upserts into ChromaDB collections `test-case-index` and `defect-history-index`
      - Idempotent (skip if already seeded)

**Relevant Context:**
- `llm_client.py` is the single point of contact with Ollama — all agents import from here
- `vector_store.py` is the single point of contact with ChromaDB
- GitHub API diff endpoint: `GET /repos/{owner}/{repo}/pulls/{pull_number}` with
  `Accept: application/vnd.github.v3.diff`

**Status:** [ ] pending

---

### Sub-Task 4 — Agent 1: Change Analyser

**Intent:** Implement the Change Analyser agent that fetches a PR diff, extracts changed
symbols via AST, maps file paths to logical modules using the LLM, and links user stories
from fixture data.

**Expected Outcomes:**
- Given a valid GitHub PR URL, `run_change_analyser(context)` populates `context["change_context"]`
  with a valid `ChangeContext` dict
- Module mapping uses `llama3.1:8b` with a structured prompt
- Falls back to filename-based heuristic if LLM call fails

**Sub-modules implemented:**
| Sub-Module | Implementation |
|---|---|
| 1.1 Diff Parser | `diff_parser.parse_diff()` utility |
| 1.2 AST Analyser | `ast_analyser.extract_symbols()` utility |
| 1.3 Module Mapper | `llama3.1:8b` prompt with file paths + known module taxonomy |
| 1.4 User Story Linker | PR title/body keyword match against `user_stories.json` fixture |

**Todo List:**
- [ ] Write `app/agents/change_analyser.py`:
      - `run(context: dict) -> dict` — main entry, updates and returns context
      - Call `github_client.fetch_pr_diff()` with `context["pr_url"]`
      - Call `diff_parser.parse_diff()` on raw diff
      - For each changed file, call `ast_analyser.extract_symbols()` if source available
      - Build module mapper prompt: list of changed files + a module taxonomy string
        derived from `dependency_graph.json` node names
      - Call `llm_client.chat()` with `model=llama3.1:8b`, `expect_json=True`
      - Parse LLM response into `impacted_modules: list[str]`
      - Match PR title + description keywords against `user_stories.json` story IDs
      - Write result into `context["change_context"]`
- [ ] Define the module mapper system prompt and few-shot example in the agent file
- [ ] Write `tests/test_agent1.py` with a mocked diff fixture and assert `ChangeContext` shape

**Relevant Context:**
- Module taxonomy comes from `dependency_graph.json` node names (loaded via `fixture_loader`)
- LLM prompt pattern: `"Given these changed files: {files}, and these known modules: {modules},
  return JSON {impacted_modules: [...]}"` 
- User story linking is keyword/title matching — no ADO API call in local mode

**Status:** [ ] pending

---

### Sub-Task 5 — Agent 2: Impact Mapper

**Intent:** Traverse the dependency graph to find transitively impacted modules, map them to
user journeys, and determine the browser/environment test matrix.

**Expected Outcomes:**
- Given a `ChangeContext`, `run_impact_mapper(context)` populates `context["impact_map"]`
  with a valid `ImpactMap` dict
- Transitive resolution uses `llama3.1:8b` with the dependency graph as context
- Browser/env matrix is deterministically derived from `browser_matrix.json` fixture

**Sub-modules implemented:**
| Sub-Module | Implementation |
|---|---|
| 2.1 Dependency Graph Builder | Pre-loaded from `dependency_graph.json` fixture |
| 2.2 Transitive Impact Resolver | `llama3.1:8b` prompt with graph edges as context |
| 2.3 User Journey Mapper | Cross-reference impacted modules against `test_cases.json` journey metadata |
| 2.4 Browser & Env Filter | Lookup `browser_matrix.json` for each impacted module |

**Todo List:**
- [ ] Write `app/agents/impact_mapper.py`:
      - `run(context: dict) -> dict` — main entry
      - Load `dependency_graph.json` and `browser_matrix.json` via `fixture_loader`
      - Build transitive resolver prompt: directly impacted modules + serialised graph edges
      - Call `llm_client.chat()` with `model=llama3.1:8b`, `expect_json=True`
      - Parse LLM response into `transitively_impacted_modules: list[str]`
      - Collect all user journeys from `test_cases.json` that contain any impacted module
      - Collect browser/env matrix rows from `browser_matrix.json` for all impacted modules
      - Deduplicate and write result into `context["impact_map"]`
- [ ] Write `tests/test_agent2.py` with a fixed `ChangeContext` fixture and assert `ImpactMap` shape

**Relevant Context:**
- `dependency_graph.json` format: `{"nodes": ["checkout","payment",...], "edges": [["checkout","payment"],...]}`
- Journey-to-module mapping is read from `test_cases.json` `journey_id` + `module` fields
- LLM is used for transitive resolution (avoids coding a full graph traversal algorithm);
  for a future optimisation, replace with `networkx` BFS traversal

**Status:** [ ] pending

---

### Sub-Task 6 — Agent 3: Risk Scorer & Test Prioritiser

**Intent:** Score every test case in `test_cases.json` that touches an impacted module using
four signals — defect history, code churn (simulated), telemetry, semantic similarity —
then combine into a weighted composite score using `llama3.1:8b`.

**Expected Outcomes:**
- Given an `ImpactMap`, `run_risk_scorer(context)` populates `context["risk_ranked_tests"]`
  with a ranked list of test cases, each with a `risk_score`, `score_breakdown`, and `justification`

**Sub-modules implemented:**
| Sub-Module | Implementation | Model/Data |
|---|---|---|
| 3.1 Defect History Scorer | Lookup per module in `defect_history.json`, normalise 0–1 | Fixture |
| 3.2 Code Churn Scorer | Simulated from `defect_history.json` `recent_commits` field | Fixture |
| 3.3 Telemetry Signal Scorer | Lookup `telemetry.json` error_rate + page_views, normalise 0–1 | Fixture |
| 3.4 Semantic Similarity Scorer | Embed diff content, query ChromaDB `test-case-index` | `nomic-embed-text` |
| 3.5 Composite Risk Ranker | Weighted sum + LLM justification | `llama3.1:8b` |

**Scoring Weights:**
- Defect History: **35%**
- Telemetry: **25%**
- Code Churn: **20%**
- Semantic Similarity: **20%**

**Todo List:**
- [ ] Write `app/agents/risk_scorer.py`:
      - `run(context: dict) -> dict` — main entry
      - Load fixture data: `defect_history.json`, `telemetry.json`, `test_cases.json`
      - Filter `test_cases.json` to only tests whose `module` is in `impacted_modules`
      - For each candidate test, compute `defect_score`, `churn_score`, `telemetry_score`
        by normalising raw fixture values to 0–1 range using min-max scaling
      - Embed the full diff text via `llm_client.embed()` (nomic-embed-text)
      - Query `test-case-index` in ChromaDB for top-N nearest tests; assign `semantic_score`
        as cosine distance mapped to 0–1
      - Compute `composite_score = 0.35*defect + 0.25*telemetry + 0.20*churn + 0.20*semantic`
      - Sort by composite score descending
      - Call `llm_client.chat()` with `model=llama3.1:8b`, `expect_json=True` to generate
        a one-line `justification` for each of the top 10 test cases
      - Write result into `context["risk_ranked_tests"]`
- [ ] Write `tests/test_agent3.py` — fixed `ImpactMap`, assert ranked list is sorted and scores
      are in 0–1 range

**Relevant Context:**
- `defect_history.json` format: `[{"module": "checkout", "defect_count": 14, "recent_commits": 22, "severity_avg": 2.3}]`
- `telemetry.json` format: `[{"module": "checkout", "page_views_per_day": 4500, "error_rate": 0.03}]`
- Semantic scorer requires ChromaDB to be seeded first (Sub-Task 3, `seed_chroma.py`)

**Status:** [ ] pending

---

### Sub-Task 7 — Agent 4: Regression Suite Recommender

**Intent:** From the risk-ranked test list, select the optimal subset that covers all impacted
user journeys, fits within the time budget, and has no redundant tests.

**Expected Outcomes:**
- Given a `RiskRankedTestList`, `run_suite_recommender(context)` populates
  `context["recommended_suite"]` with a `RecommendedSuite` dict
- Suite fits within `BUDGET_LIMIT_SECONDS` from `.env`
- All impacted user journeys have at least one test

**Sub-modules implemented:**
| Sub-Module | Implementation | Model |
|---|---|---|
| 4.1 Coverage Analyser | Check each journey_id has a test; use LLM to flag gaps | `llama3.1:8b` |
| 4.2 Budget Constraint Solver | Greedy selection by risk score until budget consumed | Deterministic |
| 4.3 Deduplication Filter | Group by `coverage_fingerprint` field in `test_cases.json`; keep top-scored per group | Deterministic |
| 4.4 Suite Composer | LLM assembles final JSON with justification notes | `llama3.1:8b` |

**Todo List:**
- [ ] Write `app/agents/suite_recommender.py`:
      - `run(context: dict) -> dict` — main entry
      - Load `test_cases.json` to get `estimated_duration_s` and `coverage_fingerprint`
        for each test in ranked list
      - **Deduplication (4.3):** group by `coverage_fingerprint`; keep highest-risk per group
      - **Budget solver (4.2):** greedy loop — add tests in risk-rank order until
        cumulative `estimated_duration_s` ≥ `BUDGET_LIMIT_SECONDS`
      - **Coverage check (4.1):** for each journey in `impact_map["user_journeys"]`,
        verify at least one selected test covers it; if not, force-add the top-ranked
        test for that journey even if it exceeds budget
      - **Suite composer (4.4):** call `llm_client.chat()` with `model=llama3.1:8b`,
        `expect_json=True` to generate per-test `justification` strings and the final
        `RecommendedSuite` JSON
      - Write result into `context["recommended_suite"]`
- [ ] Write `tests/test_agent4.py` — assert suite duration ≤ budget, no duplicate fingerprints,
      all journeys covered

**Relevant Context:**
- `BUDGET_LIMIT_SECONDS` default: 1800 (30 min)
- `coverage_fingerprint` in `test_cases.json` is a string hash grouping tests by code path

**Status:** [ ] pending

---

### Sub-Task 8 — Agent 5: Test Scenario Generator

**Intent:** Identify user journeys with no test coverage, read acceptance criteria from user
stories, and generate Gherkin BDD feature files and Playwright TypeScript stubs for each gap.

**Expected Outcomes:**
- Given `ImpactMap` + `RecommendedSuite`, `run_scenario_generator(context)` populates
  `context["generated_scenarios"]`
- Each coverage gap produces a Gherkin `.feature` file content and a Playwright stub
- Uses `qwen2.5-coder:7b` for both Gherkin writing and TypeScript scaffolding

**Sub-modules implemented:**
| Sub-Module | Implementation | Model |
|---|---|---|
| 5.1 Gap Detector | Compare impacted journeys against selected test journey IDs | Deterministic |
| 5.2 User Story Interpreter | Extract acceptance criteria from `user_stories.json` | `llama3.1:8b` |
| 5.3 Scenario Writer | Generate Gherkin feature file for each gap | `qwen2.5-coder:7b` |
| 5.4 Script Scaffolder | Convert Gherkin → Playwright TypeScript stub | `qwen2.5-coder:7b` |
| 5.5 Review Gate | In local mode: save files to `output/` and note PR-creation as future step | N/A (future) |

**Todo List:**
- [ ] Write `app/agents/scenario_generator.py`:
      - `run(context: dict) -> dict` — main entry
      - **Gap detection (5.1):** collect `journey_id` values from `recommended_suite["suite"]`;
        find journeys in `impact_map["user_journeys"]` not covered by any selected test
      - **Story interpretation (5.2):** for each uncovered journey, find the linked user story
        in `user_stories.json` by `journey_id`; call `llm_client.chat()` with
        `model=llama3.1:8b` to extract acceptance criteria as a structured list
      - **Gherkin generation (5.3):** for each gap, call `llm_client.chat()` with
        `model=qwen2.5-coder:7b`, `temperature=0.3` to generate a Gherkin feature file;
        include a few-shot example of the project's Gherkin style in the system prompt
      - **Playwright stub (5.4):** call `llm_client.chat()` with `model=qwen2.5-coder:7b`
        to convert the generated Gherkin into a Playwright TypeScript `test()` stub
      - Store generated file contents in `context["generated_scenarios"]`
      - Also write files to `output/generated_tests/` directory (creates it if absent)
- [ ] Write `tests/test_agent5.py` — mock a coverage gap, assert Gherkin output contains
      `Feature:`, `Scenario:`, `Given`, `When`, `Then` keywords

**Relevant Context:**
- Gherkin few-shot example should be hardcoded in the agent (2–3 scenarios from `test_cases.json`)
- Playwright stub template: `import { test, expect } from '@playwright/test';`
- `output/` directory is git-ignored

**Status:** [ ] pending

---

### Sub-Task 9 — Pipeline Orchestrator & Flask App

**Intent:** Wire all 5 agents into a sequential pipeline and expose it through the Flask UI.
The user enters a PR URL, the pipeline runs, and results are shown in a 4-tab dashboard.

**Expected Outcomes:**
- `POST /analyse` runs agents 1→5 in sequence, populating `PipelineContext`
- Results page renders 4 tabs: Impact Map, Risk Scores, Recommended Suite, Generated Tests
- Each tab displays the structured output with appropriate formatting (tables, code blocks)
- Errors from any agent are shown gracefully without crashing the app

**Todo List:**
- [ ] Write `app/pipeline.py`:
      - `run_pipeline(pr_url: str) -> PipelineContext`
      - Initialise empty `PipelineContext` dict with `pr_url`
      - Call agents in order: `change_analyser.run()`, `impact_mapper.run()`,
        `risk_scorer.run()`, `suite_recommender.run()`, `scenario_generator.run()`
      - Each agent receives and returns the full context dict
      - Catch exceptions per agent, append to `context["errors"]`, continue pipeline
- [ ] Update `app/routes.py`:
      - `GET /` → render `index.html`
      - `POST /analyse` → call `pipeline.run_pipeline(pr_url)`, render `results.html`
        with full context
- [ ] Write `app/templates/index.html`:
      - Clean form with PR URL text input and "Analyse PR" submit button
      - Brief description of what the platform does
- [ ] Write `app/templates/results.html`:
      - 4-tab layout (Bootstrap or plain CSS): Impact Map | Risk Scores | Recommended Suite | Generated Tests
      - **Tab 1 — Impact Map:** list of directly + transitively impacted modules,
        user journeys table, browser/env matrix table
      - **Tab 2 — Risk Scores:** sortable table with test name, risk score bar, score breakdown,
        justification
      - **Tab 3 — Recommended Suite:** table of selected tests with browser, environment,
        estimated duration, priority; total duration shown
      - **Tab 4 — Generated Tests:** per-gap section with Gherkin code block and
        Playwright stub code block
      - Display any errors from `context["errors"]` in a warning banner
- [ ] Seed ChromaDB before first run by calling `scripts/seed_chroma.py` in app startup if
      collections are empty

**Relevant Context:**
- `pipeline.py` is the single entry point called by Flask — no agent imports in `routes.py`
- Use `json.dumps(..., indent=2)` in templates via Jinja2 `tojson` filter for raw JSON display
- Bootstrap 5 CDN is sufficient for the tabbed layout (no npm/build step needed)

**Status:** [ ] pending

---

### Sub-Task 10 — End-to-End Validation

**Intent:** Verify the full pipeline works end-to-end with a real (public) GitHub PR URL
and that all outputs are correctly shaped and displayed.

**Expected Outcomes:**
- Flask app starts cleanly after `flask run`
- Submitting a real public GitHub PR URL returns a results page within 60 seconds
- All 4 tabs display correctly formatted, non-empty content
- Unit tests for all 5 agents pass via `pytest tests/`

**Todo List:**
- [ ] Run `scripts/seed_chroma.py` and verify ChromaDB collections are populated
- [ ] Submit a test GitHub PR URL and verify each agent's output shape matches its I/O contract
- [ ] Verify no unhandled exceptions; check `context["errors"]` is empty on happy path
- [ ] Run `pytest tests/` and confirm all 5 agent test files pass
- [ ] Document `README.md` with setup steps: `pip install -r requirements.txt`,
      `ollama pull llama3.1:8b`, `ollama pull qwen2.5-coder:7b`,
      `ollama pull nomic-embed-text`, `python scripts/seed_chroma.py`, `flask run`

**Relevant Context:**
- A suitable public test PR: any open PR on a Python or JavaScript public GitHub repo
- Ollama must be running locally on port 11434 before starting Flask

**Status:** [ ] pending

---

## Key Design Decisions

| Decision | Local Choice | Rationale |
|---|---|---|
| Agent orchestration | Sequential Python function calls | Simplest to debug; easy to trace context mutations |
| Reasoning LLM | `llama3.1:8b` | Best open-source instruction-following; fits 8 GB VRAM |
| Code/Gherkin LLM | `qwen2.5-coder:7b` | Fine-tuned for code tasks; better TypeScript + Gherkin output |
| Embedding model | `nomic-embed-text` | Best open-source embedding in Ollama; 768-dim, works well on code + prose |
| Vector store | ChromaDB (persistent) | Zero-config, file-based, native Python; direct replacement path to Azure AI Search |
| Fixture data | Static JSON in `data/` | No external service dependencies; consistent, repeatable |
| LLM temperature | 0.2 for reasoning, 0.3 for generation | Low temperature = deterministic structured JSON output |
| Context window | 8192 tokens | Sufficient for diff + graph context in llama3.1:8b |
| Web UI | Flask + Jinja2 + Bootstrap 5 CDN | No build toolchain; renders on the server; easy to iterate |

---

## Future Azure Migration Path

When migrating from local to Azure, replace the following components one-for-one:

| Local Component | Azure Equivalent |
|---|---|
| Ollama `llama3.1:8b` / `qwen2.5-coder:7b` | Azure OpenAI GPT-4o |
| Ollama `nomic-embed-text` | Azure OpenAI `text-embedding-3-large` |
| ChromaDB (local file) | Azure AI Search (vector + hybrid search) |
| Sequential function calls | Azure Service Bus topics |
| Static JSON fixtures | Azure AI Search indexes + Azure App Insights + Cosmos DB |
| Flask app | Azure Container Apps or Azure App Service |
| `output/` directory | Azure Blob Storage |
| Manual PR URL input | GitHub/ADO webhook (CI trigger — Agent 6 scope) |
