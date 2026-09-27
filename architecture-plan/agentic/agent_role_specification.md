4 Agents + Sub-Modules for each agent.

Module 1 — Change Analyser Agent
Sub-Module	Role
1.1 Diff Parser	Extracts changed files/lines from Git diff
1.2 AST Analyser	Identifies changed functions/classes via tree-sitter
1.3 Module Mapper	Maps file paths to logical app modules using GPT-4o + AI Search
1.4 User Story Linker	Links PR to Azure DevOps user stories

Module 2 — Impact Mapper Agent
Sub-Module	Role
2.1 Dependency Graph Builder	Pre-built static dependency graph in Cosmos DB
2.2 Transitive Impact Resolver	GPT-4o traverses graph for blast radius
2.3 User Journey Mapper	Maps modules → end-to-end user journeys
2.4 Browser & Env Filter	Determines which browser/env combos need testing

Module 3 — Risk Scorer & Test Prioritiser Agent
Sub-Module	Role
3.1 Defect History Scorer	Weights by historical defect density (35%)
3.2 Code Churn Scorer	Weights by recent commit frequency (20%)
3.3 Telemetry Signal Scorer	Weights by user traffic + error rates (25%)
3.4 Semantic Similarity Scorer	Embeddings cosine similarity to changed code (20%)
3.5 Composite Risk Ranker	GPT-4o computes weighted final score with justification

Module 4 — Regression Suite Recommender Agent
Sub-Module	Role
4.1 Coverage Analyser	Ensures all impacted journeys have at least one test
4.2 Budget Constraint Solver	Trims suite to fit time/cost SLA
4.3 Deduplication Filter	Removes redundant tests covering same code path
4.4 Suite Composer	Produces final JSON suite with browser/env matrix

Agent 5 — Test Scenario Generator Agent
Sub-Module	Role
5.1 Gap Detector	Finds user journeys with zero existing test coverage
5.2 User Story Interpreter	Extracts acceptance criteria from user stories
5.3 Scenario Writer	Generates Gherkin BDD feature files (GPT-4o)
5.4 Script Scaffolder	Converts Gherkin → Playwright TypeScript stubs
5.5 Review & Approval Gate	Raises PR for QA team with ai-generated label

Agent 6 — CI/CD Integration & Traceability Agent --> Future scope enhancement
Sub-Module	Role
6.1 Pipeline Trigger	Calls ADO/GitHub API to queue the optimised test run
6.2 Execution Monitor	Polls progress, updates dashboard in real time
6.3 Results Collector	Parses JUnit/Allure XML results
6.4 Traceability Recorder	Writes full chain to Cosmos DB (GPT-4o structured output)
6.5 Feedback Loop Updater	Pushes results back into AI Search to improve future scoring
6.6 Notification Publisher	Teams webhook + email summary