                         ┌──────────────────────────┐
                         │     Developer / QA       │
                         │   PR / User Story / UI   │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────┐
                    │       Azure DevOps / GitHub     │
                    │        CI/CD + Source Code      │
                    └────────────────┬────────────────┘
                                     │
                              Code Change / PR
                                     │
                                     ▼
              ┌────────────────────────────────────────────┐
              │             API / Orchestration Layer      │
              │       Azure Container Apps + FastAPI       │
              └────────────────────┬───────────────────────┘
                                   │
                                   ▼
              ┌────────────────────────────────────────────┐
              │          CHANGE IMPACT ENGINE               │
              │                                            │
              │  Git Diff + AST + Dependency Analysis     │
              │                                            │
              │  Changed Code → Module → API → User Flow  │
              └────────────────────┬───────────────────────┘
                                   │
                                   ▼
        ┌─────────────────────────────────────────────────────────┐
        │                    KNOWLEDGE LAYER                      │
        │                                                         │
        │  ┌──────────────┐   ┌──────────────┐   ┌────────────┐ │
        │  │ Azure AI     │   │ Azure SQL    │   │ Blob       │ │
        │  │ Search       │   │              │   │ Storage    │ │
        │  │              │   │ Test History │   │ Reports    │ │
        │  │ RAG / Vector │   │ Defects      │   │ Logs       │ │
        │  │ Search       │   │ Test Cases   │   │ Artifacts  │ │
        │  └──────────────┘   └──────────────┘   └────────────┘ │
        └───────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
              ┌─────────────────────────────────────────┐
              │           AGENTIC AI LAYER              │
              │                                         │
              │       Azure OpenAI + Agent Framework    │
              │                                         │
              │  ┌──────────────┐                       │
              │  │ Impact Agent │                       │
              │  └──────┬───────┘                       │
              │         ▼                               │
              │  ┌──────────────┐                       │
              │  │ Risk Agent   │                       │
              │  └──────┬───────┘                       │
              │         ▼                               │
              │  ┌──────────────┐                       │
              │  │ Test Selection│                      │
              │  │ Agent         │                      │
              │  └──────┬───────┘                       │
              │         ▼                               │
              │  ┌──────────────┐                       │
              │  │ Test Gen      │                      │
              │  │ Agent         │                      │
              │  └──────────────┘                       │
              └───────────────────┬─────────────────────┘
                                  │
                         Optimized Test Suite
                                  │
                                  ▼
              ┌──────────────────────────────────────────┐
              │             TEST EXECUTION               │
              │                                          │
              │              Playwright                  │
              │                                          │
              │       ┌────────┬────────┬────────┐       │
              │       │ Chrome │  Edge  │ Firefox│       │
              │       └────────┴────────┴────────┘       │
              └──────────────────┬───────────────────────┘
                                 │
                                 ▼
              ┌──────────────────────────────────────────┐
              │       RESULT / FEEDBACK ENGINE           │
              │                                          │
              │  Test Results + Logs + Screenshots       │
              │  Failure Analysis + Telemetry            │
              └──────────────────┬───────────────────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │ Application Insights  │
                     │ Azure Monitor         │
                     └───────────┬───────────┘
                                 │
                                 ▼
                       Feedback → Knowledge
                              Layer