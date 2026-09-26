# Azure OpenAI-Powered Agentic Testing Platform — Solution Plan

## Problem Summary

Web application regression testing is expensive, slow, and over-broad. Every code change triggers a full regression suite across Chrome, Edge, Firefox, multiple environments, and multiple app-server versions. The goal is an **AI-powered platform** that:

- Analyses source-code diffs, user stories, defect history, telemetry, and past test results
- Identifies *only* the impacted modules
- Prioritises high-risk test cases
- Recommends an optimised subset regression suite
- Generates *new* test scenarios for affected user journeys
- Integrates into the CI/CD pipeline
- Provides end-to-end traceability

---

## Top-Level Architecture Overview

The platform is composed of **six primary modules** that form a pipeline, each implemented as an Azure AI Agent (or Azure Function) and orchestrated by a central Azure AI Foundry project using multi-agent orchestration.

```
[Source Control / CI Trigger]
         |
         v
[Module 1: Change Analyser Agent]
         |
         v
[Module 2: Impact Mapper Agent]
         |
         v
[Module 3: Risk Scorer & Test Prioritiser Agent]
         |
         v
[Module 4: Regression Suite Recommender Agent]
         |
         v
[Module 5: Test Scenario Generator Agent]
         |
         v
[Module 6: CI/CD Integration & Traceability Agent]
         |
         v
[Reporting Dashboard — Azure Static Web Apps]
```

---

## Azure AI Foundry Implementation Steps

### Step 1 — Create Azure AI Foundry Project

1. Navigate to **Azure AI Foundry** portal (ai.azure.com).
2. Create a new **AI Foundry Hub** (resource group, region, storage account, Key Vault).
3. Under the hub, create a new **Project**: `agentic-testing-platform`.
4. Deploy an **Azure OpenAI** model connection: GPT-4o (primary reasoning) and text-embedding-3-large (semantic search).

### Step 2 — Provision Supporting Azure Services

| Service | Purpose |
|---|---|
| Azure AI Foundry Agent Service | Host and run each AI agent |
| Azure AI Search | Vector store for code, tests, defect history |
| Azure Cosmos DB | Store traceability records, run metadata |
| Azure Blob Storage | Store diffs, test results, telemetry logs |
| Azure Service Bus | Async messaging between agents |
| Azure Functions (Python) | Lightweight compute for deterministic sub-tasks |
| Azure DevOps / GitHub Actions | CI/CD trigger & integration |
| Azure Monitor + App Insights | Observability of the platform itself |
| Azure Static Web Apps | Reporting dashboard |
| Azure Key Vault | Secrets, API keys |

### Step 3 — Configure Multi-Agent Orchestration in AI Foundry

1. In AI Foundry project, open **Agents** blade.
2. Create each of the six agents (see Module section below), each backed by GPT-4o.
3. Configure **tool calls** (function tools, code interpreter, file search) per agent.
4. Set up an **Orchestrator Agent** that routes the pipeline sequentially and can retry/branch.
5. Define **shared Azure AI Search index** as a knowledge tool accessible by all agents.

### Step 4 — Build the Azure AI Search Indexes

Create the following indexes:
- `code-corpus-index` — chunked source code with metadata (module, file path, commit hash)
- `test-case-index` — test cases with metadata (module, last run status, browser, environment)
- `defect-history-index` — defects linked to modules, test cases, fix commits
- `telemetry-index` — error rates, usage paths, crash signals per module

### Step 5 — Configure CI/CD Integration

1. Add a **CI/CD webhook/trigger step** as the first pipeline stage in Azure DevOps or GitHub Actions.
2. On every Pull Request or merge, the pipeline calls the **Agentic Platform API** (Azure Function HTTP trigger).
3. The platform returns a **recommended test suite JSON** within a time-bounded SLA.
4. The CI/CD pipeline executes only the recommended tests using Selenium Grid / Playwright on Azure Container Instances.
5. Results are posted back to the platform for feedback loop learning.

### Step 6 — Deploy Reporting Dashboard

1. Build a React/Vue dashboard deployed to **Azure Static Web Apps**.
2. Dashboard reads from Cosmos DB for traceability records.
3. Shows: code change → impacted modules → risk scores → selected tests → pass/fail results.

---

## Modules, Sub-Modules, and Implementation

---

### MODULE 1 — Change Analyser Agent

**Intent:** Parse incoming source-code diff (PR/commit), extract changed files, functions, and components, and map them to logical application modules.

#### Sub-Modules

| Sub-Module | Description |
|---|---|
| 1.1 Diff Parser | Extracts changed files, added/removed lines from Git diff payload |
| 1.2 AST Analyser | Parses changed files using AST to identify changed functions, classes, components |
| 1.3 Module Mapper | Maps file paths and symbols to logical application module taxonomy |
| 1.4 User Story Linker | Links commit messages / PR descriptions to user stories via Azure DevOps Work Items API |

#### Implementation

- **Trigger:** HTTP POST from CI/CD webhook with Git diff payload (JSON).
- **Azure Function 1.1** (`diff-parser`): Receives raw diff, outputs list of `{file, changed_lines, change_type}`.
- **Azure Function 1.2** (`ast-analyser`): Uses `tree-sitter` (Python) to parse changed files, outputs `{file, functions[], classes[], components[]}`.
- **AI Agent 1.3** (`module-mapper`): Uses GPT-4o with `code-corpus-index` to map file paths to module names. Prompt: *"Given these changed file paths and symbols, identify which logical application modules are affected. Use the module taxonomy in the index."*
- **Azure Function 1.4** (`user-story-linker`): Calls Azure DevOps REST API to fetch linked work items from the PR.
- **Output:** `ChangeContext` object → published to Azure Service Bus topic `change-context`.

---

### MODULE 2 — Impact Mapper Agent

**Intent:** Determine the blast radius of changes — which modules, components, and user journeys are transitively impacted beyond the directly changed files.

#### Sub-Modules

| Sub-Module | Description |
|---|---|
| 2.1 Dependency Graph Builder | Builds/queries a static dependency graph of the application |
| 2.2 Transitive Impact Resolver | Traverses the dependency graph to find all impacted modules |
| 2.3 User Journey Mapper | Maps impacted modules to user journeys / end-to-end flows |
| 2.4 Browser & Environment Filter | Determines which browser/environment combinations are relevant |

#### Implementation

- **Trigger:** Subscribes to Service Bus topic `change-context`.
- **Azure Function 2.1** (`dependency-graph`): Pre-built dependency graph stored in Cosmos DB (updated nightly by a separate batch job that runs `madge` or `webpack-bundle-analyzer`). Queried at runtime.
- **AI Agent 2.2** (`transitive-resolver`): GPT-4o with code-corpus-index. Prompt: *"Given directly impacted modules, traverse the dependency graph and identify all transitively impacted modules and shared utility dependencies."*
- **AI Agent 2.3** (`journey-mapper`): Uses `test-case-index` and `defect-history-index` to map modules to known user journeys. Outputs `{journey_id, journey_name, impacted_modules[]}`.
- **Azure Function 2.4** (`browser-env-filter`): Cross-references impacted modules against a browser-compatibility matrix (stored in Blob Storage) to determine which browser/environment combos need testing.
- **Output:** `ImpactMap` object → published to Service Bus topic `impact-map`.

---

### MODULE 3 — Risk Scorer & Test Prioritiser Agent

**Intent:** Assign a risk score to each impacted module and test case using defect history, code churn, telemetry signals, and semantic similarity.

#### Sub-Modules

| Sub-Module | Description |
|---|---|
| 3.1 Defect History Scorer | Scores modules by historical defect density |
| 3.2 Code Churn Scorer | Scores modules by frequency/volume of recent changes |
| 3.3 Telemetry Signal Scorer | Scores modules by user-traffic volume and error rates |
| 3.4 Semantic Similarity Scorer | Uses embeddings to find test cases semantically similar to changed code |
| 3.5 Composite Risk Ranker | Combines all signals into a final risk score per test case |

#### Implementation

- **Trigger:** Subscribes to Service Bus topic `impact-map`.
- **Azure Function 3.1** (`defect-scorer`): Queries `defect-history-index` for defect count, severity, and recency per module. Returns normalised score 0–1.
- **Azure Function 3.2** (`churn-scorer`): Calls GitHub/Azure DevOps API to get commit frequency for each impacted file over 90 days. Returns normalised score 0–1.
- **Azure Function 3.3** (`telemetry-scorer`): Queries App Insights via REST API for error rate and page-visit frequency for impacted modules. Returns normalised score 0–1.
- **AI Agent 3.4** (`semantic-scorer`): Embeds the diff content using `text-embedding-3-large`, queries `test-case-index` for nearest neighbours. Returns ranked list of test cases by cosine similarity.
- **AI Agent 3.5** (`risk-ranker`): GPT-4o with all four scores as input. Prompt: *"Given defect score, churn score, telemetry score, and semantic similarity score for each test case, compute a weighted composite risk score and rank the test cases. Justify the top 10 rankings."* Weights: defect 35%, telemetry 25%, churn 20%, semantic 20%.
- **Output:** `RiskRankedTestList` object → published to Service Bus topic `risk-ranked-tests`.

---

### MODULE 4 — Regression Suite Recommender Agent

**Intent:** From the risk-ranked test list, recommend the optimal subset of tests that provides maximum defect-detection coverage within acceptable execution time and cost constraints.

#### Sub-Modules

| Sub-Module | Description |
|---|---|
| 4.1 Coverage Analyser | Ensures no critical user journey is left untested |
| 4.2 Budget Constraint Solver | Applies time/cost budget constraints to trim the suite |
| 4.3 Deduplication Filter | Removes redundant tests covering the same code path |
| 4.4 Suite Composer | Produces the final recommended suite with browser/env matrix |

#### Implementation

- **Trigger:** Subscribes to Service Bus topic `risk-ranked-tests`.
- **AI Agent 4.1** (`coverage-analyser`): GPT-4o checks whether all impacted user journeys have at least one test in the ranked list. Flags any coverage gap and adds mandatory tests.
- **AI Agent 4.2** (`budget-solver`): Given an SLA constraint (e.g., "total suite must complete in < 30 minutes on Selenium Grid"), calculates how many tests fit. Uses historical execution-time data from `test-case-index`.
- **Azure Function 4.3** (`deduplication`): Groups tests by code-path coverage fingerprint (stored in test index). Keeps the highest-risk test per group.
- **AI Agent 4.4** (`suite-composer`): Assembles the final suite JSON including test IDs, browser, environment, priority order, and justification notes.
- **Output:** `RecommendedSuite` object → published to Service Bus topic `recommended-suite`.

---

### MODULE 5 — Test Scenario Generator Agent

**Intent:** For affected user journeys not covered by existing tests, automatically generate new test scenarios (in Gherkin/BDD or Playwright script format).

#### Sub-Modules

| Sub-Module | Description |
|---|---|
| 5.1 Gap Detector | Identifies user journeys with no existing test coverage |
| 5.2 User Story Interpreter | Reads linked user stories to understand expected behaviour |
| 5.3 Scenario Writer | Generates Gherkin BDD feature files for new scenarios |
| 5.4 Script Scaffolder | Optionally generates Playwright TypeScript test stubs |
| 5.5 Review & Approval Gate | Flags generated tests for human review before inclusion |

#### Implementation

- **Trigger:** Subscribes to Service Bus topic `recommended-suite`; also receives `ImpactMap`.
- **AI Agent 5.1** (`gap-detector`): Compares impacted user journeys against existing test coverage map in `test-case-index`. Returns list of uncovered journeys.
- **AI Agent 5.2** (`story-interpreter`): Reads linked user story text from Azure DevOps. Extracts acceptance criteria and business rules. Prompt: *"Extract the testable acceptance criteria and edge cases from this user story."*
- **AI Agent 5.3** (`scenario-writer`): GPT-4o generates Gherkin feature files. Prompt: *"Write BDD Gherkin scenarios for the following acceptance criteria, covering happy path, edge cases, and negative cases. Follow the project's existing Gherkin style."* Uses few-shot examples from `test-case-index`.
- **AI Agent 5.4** (`script-scaffolder`): Optionally converts Gherkin to Playwright TypeScript stubs using code-interpreter tool.
- **Azure Function 5.5** (`review-gate`): Creates a Pull Request in Azure DevOps/GitHub with generated test files, assigns to QA team for review. Adds `ai-generated` label.
- **Output:** `GeneratedScenarios` artifact (Gherkin files in Blob Storage + PR link) → metadata published to Service Bus topic `generated-scenarios`.

---

### MODULE 6 — CI/CD Integration & Traceability Agent

**Intent:** Execute the recommended suite in CI/CD, collect results, publish traceability records, and feed results back as a learning signal.

#### Sub-Modules

| Sub-Module | Description |
|---|---|
| 6.1 Pipeline Trigger | Triggers CI/CD pipeline stage with recommended suite |
| 6.2 Test Execution Monitor | Monitors real-time execution progress |
| 6.3 Results Collector | Collects pass/fail/flaky results per test |
| 6.4 Traceability Recorder | Writes full traceability chain to Cosmos DB |
| 6.5 Feedback Loop Updater | Updates defect history and test-case indexes with new results |
| 6.6 Notification Publisher | Sends summary report to Teams / email |

#### Implementation

- **Trigger:** Subscribes to Service Bus topic `recommended-suite` and `generated-scenarios`.
- **Azure Function 6.1** (`pipeline-trigger`): Calls Azure DevOps Pipelines REST API or GitHub Actions API to queue the test run with the recommended suite as a parameter.
- **Azure Function 6.2** (`execution-monitor`): Polls pipeline status every 60 seconds. Publishes progress to Cosmos DB for dashboard.
- **Azure Function 6.3** (`results-collector`): On pipeline completion, downloads JUnit/Allure XML results from Blob Storage. Parses pass/fail/flaky/skipped per test.
- **AI Agent 6.4** (`traceability-recorder`): GPT-4o writes a structured traceability record to Cosmos DB: `{commit_hash, pr_id, changed_files, impacted_modules, risk_scores, selected_tests, test_results, generated_scenarios}`.
- **Azure Function 6.5** (`feedback-updater`): Updates `defect-history-index` and `test-case-index` in Azure AI Search with latest execution results (pass rate, newly found defects). This closes the learning loop.
- **Azure Function 6.6** (`notifier`): Posts summary to Microsoft Teams webhook and sends email via Azure Communication Services.
- **Output:** Traceability record in Cosmos DB; dashboard updated; learning indexes refreshed.

---

## Data Flow Between Modules

```
TRIGGER: PR / Commit in Azure DevOps / GitHub
    |
    v
[MODULE 1 - Change Analyser]
  Inputs:  Git diff payload, PR metadata, Azure DevOps Work Items
  Outputs: ChangeContext {changed_files, changed_symbols, module_names, linked_user_stories}
    |
    v (Service Bus: change-context)
[MODULE 2 - Impact Mapper]
  Inputs:  ChangeContext, Dependency Graph (Cosmos DB), Browser Matrix (Blob)
  Outputs: ImpactMap {impacted_modules[], user_journeys[], browser_env_matrix[]}
    |
    v (Service Bus: impact-map)
[MODULE 3 - Risk Scorer]
  Inputs:  ImpactMap, Defect History Index, Telemetry (App Insights), Test Case Index
  Outputs: RiskRankedTestList {test_id, risk_score, score_breakdown, rank}[]
    |
    v (Service Bus: risk-ranked-tests)
[MODULE 4 - Suite Recommender]
  Inputs:  RiskRankedTestList, SLA budget, Execution time data
  Outputs: RecommendedSuite {test_id, browser, environment, priority, justification}[]
    |
    v (Service Bus: recommended-suite)
    |-----> [MODULE 5 - Scenario Generator]
    |         Inputs:  ImpactMap, RecommendedSuite, User Stories
    |         Outputs: GeneratedScenarios (Gherkin files, PR link)
    |                  -> Service Bus: generated-scenarios
    |
    v (Service Bus: recommended-suite + generated-scenarios)
[MODULE 6 - CI/CD Integration & Traceability]
  Inputs:  RecommendedSuite, GeneratedScenarios, Pipeline APIs, Test Results
  Outputs: Traceability Record (Cosmos DB), Updated Indexes, Notification
    |
    v
[REPORTING DASHBOARD - Azure Static Web Apps]
  Reads Cosmos DB traceability records
  Shows: Code Change -> Modules -> Risk -> Tests -> Results
```

---

## Sub-Task Breakdown for Implementation

---

### Sub-Task 1 — Azure Infrastructure Provisioning
- **Intent:** Provision all required Azure services
- **Expected Outcomes:** All Azure resources deployed, connections configured in AI Foundry
- **Todo List:**
  - [ ] Create Azure AI Foundry Hub and Project
  - [ ] Deploy GPT-4o and text-embedding-3-large model connections
  - [ ] Provision Azure AI Search with four indexes
  - [ ] Provision Cosmos DB with traceability and metadata collections
  - [ ] Provision Azure Service Bus with six topics
  - [ ] Provision Azure Blob Storage containers
  - [ ] Configure Azure Key Vault with all secrets
  - [ ] Deploy Azure Monitor and App Insights workspace
- **Status:** [ ] pending

---

### Sub-Task 2 — Module 1: Change Analyser Agent
- **Intent:** Build and deploy the Change Analyser agent and supporting functions
- **Expected Outcomes:** Given a PR webhook payload, the agent outputs a valid `ChangeContext` object
- **Todo List:**
  - [ ] Build `diff-parser` Azure Function (Python, `unidiff` library)
  - [ ] Build `ast-analyser` Azure Function (Python, `tree-sitter`)
  - [ ] Create `module-mapper` AI Agent in AI Foundry with code-corpus-index tool
  - [ ] Build `user-story-linker` Azure Function (Azure DevOps REST API)
  - [ ] Define `ChangeContext` schema and publish to Service Bus
  - [ ] Write integration test for full Module 1 flow
- **Status:** [ ] pending

---

### Sub-Task 3 — Module 2: Impact Mapper Agent
- **Intent:** Build the Impact Mapper agent and dependency graph infrastructure
- **Expected Outcomes:** Given a `ChangeContext`, agent returns a valid `ImpactMap`
- **Todo List:**
  - [ ] Build nightly batch job to generate dependency graph (madge/webpack) into Cosmos DB
  - [ ] Build `dependency-graph` Azure Function query layer
  - [ ] Create `transitive-resolver` AI Agent in AI Foundry
  - [ ] Create `journey-mapper` AI Agent in AI Foundry
  - [ ] Build `browser-env-filter` Azure Function with matrix config
  - [ ] Write integration test for full Module 2 flow
- **Status:** [ ] pending

---

### Sub-Task 4 — Module 3: Risk Scorer Agent
- **Intent:** Build all four scorers and the composite risk ranker
- **Expected Outcomes:** Given an `ImpactMap`, agent returns a ranked list of test cases with scores
- **Todo List:**
  - [ ] Build `defect-scorer` Azure Function (AI Search query)
  - [ ] Build `churn-scorer` Azure Function (GitHub/ADO API)
  - [ ] Build `telemetry-scorer` Azure Function (App Insights REST API)
  - [ ] Create `semantic-scorer` AI Agent (embeddings + AI Search vector query)
  - [ ] Create `risk-ranker` AI Agent in AI Foundry with weighted scoring prompt
  - [ ] Write integration test for full Module 3 flow
- **Status:** [ ] pending

---

### Sub-Task 5 — Module 4: Suite Recommender Agent
- **Intent:** Build the suite recommendation logic with coverage and budget constraints
- **Expected Outcomes:** Agent returns a trimmed, optimised test suite JSON
- **Todo List:**
  - [ ] Create `coverage-analyser` AI Agent in AI Foundry
  - [ ] Create `budget-solver` AI Agent with execution time data tool
  - [ ] Build `deduplication` Azure Function (fingerprint grouping logic)
  - [ ] Create `suite-composer` AI Agent in AI Foundry
  - [ ] Define `RecommendedSuite` schema
  - [ ] Write integration test for full Module 4 flow
- **Status:** [ ] pending

---

### Sub-Task 6 — Module 5: Test Scenario Generator Agent
- **Intent:** Build the test generation pipeline including Gherkin and Playwright stub output
- **Expected Outcomes:** New test scenarios are generated as Gherkin files and raised as PRs for review
- **Todo List:**
  - [ ] Create `gap-detector` AI Agent in AI Foundry
  - [ ] Create `story-interpreter` AI Agent in AI Foundry
  - [ ] Create `scenario-writer` AI Agent in AI Foundry (with few-shot Gherkin examples)
  - [ ] Create `script-scaffolder` AI Agent with code interpreter tool
  - [ ] Build `review-gate` Azure Function (GitHub/ADO PR creation API)
  - [ ] Write integration test for full Module 5 flow
- **Status:** [ ] pending

---

### Sub-Task 7 — Module 6: CI/CD Integration & Traceability Agent
- **Intent:** Build the full CI/CD integration, results collection, and feedback loop
- **Expected Outcomes:** After a test run, full traceability record exists in Cosmos DB and indexes are updated
- **Todo List:**
  - [ ] Build `pipeline-trigger` Azure Function (ADO/GitHub Actions API)
  - [ ] Build `execution-monitor` Azure Function (polling + Cosmos DB updates)
  - [ ] Build `results-collector` Azure Function (JUnit XML parser)
  - [ ] Create `traceability-recorder` AI Agent in AI Foundry
  - [ ] Build `feedback-updater` Azure Function (AI Search index push API)
  - [ ] Build `notifier` Azure Function (Teams webhook + Azure Communication Services)
  - [ ] Write integration test for full Module 6 flow
- **Status:** [ ] pending

---

### Sub-Task 8 — Reporting Dashboard
- **Intent:** Build a web dashboard for traceability and visibility
- **Expected Outcomes:** Dashboard shows full chain from code change to test results
- **Todo List:**
  - [ ] Scaffold React app with Azure Static Web Apps
  - [ ] Build traceability view (code change → modules → risk → tests → results)
  - [ ] Build run history and trend charts
  - [ ] Configure Cosmos DB data API connection
  - [ ] Deploy to Azure Static Web Apps
- **Status:** [ ] pending

---

### Sub-Task 9 — End-to-End Integration & Validation
- **Intent:** Wire all modules together and validate the full pipeline end-to-end
- **Expected Outcomes:** A sample PR in the test app triggers the full pipeline and produces correct output
- **Todo List:**
  - [ ] Create sample web app with known module structure for testing
  - [ ] Seed AI Search indexes with sample data
  - [ ] Run full pipeline with a sample PR diff
  - [ ] Validate ChangeContext, ImpactMap, RiskRankedTestList, RecommendedSuite outputs
  - [ ] Validate generated Gherkin scenarios
  - [ ] Validate Cosmos DB traceability record
  - [ ] Performance test: pipeline must return RecommendedSuite within SLA
- **Status:** [ ] pending

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Agent orchestration | Azure AI Foundry multi-agent with Service Bus | Decoupled, independently scalable, retryable |
| Primary LLM | GPT-4o | Best reasoning for code analysis and test generation |
| Embedding model | text-embedding-3-large | Best semantic search accuracy for code and test similarity |
| Vector store | Azure AI Search (with vector fields) | Native Azure integration, hybrid search capability |
| Async messaging | Azure Service Bus | Reliable, ordered, decoupled between agents |
| State/traceability | Cosmos DB | Flexible schema, global distribution, query capability |
| Test format output | Gherkin BDD + Playwright stubs | Human-readable, compatible with most web test frameworks |
| CI/CD integration | REST API trigger (both ADO and GitHub supported) | Platform-agnostic |
| Feedback loop | AI Search index push after each run | Continuously improves scoring accuracy over time |
