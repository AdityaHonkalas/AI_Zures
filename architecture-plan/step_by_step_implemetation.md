Step	Action
1	Create AI Foundry Hub + Project agentic-testing-platform at ai.azure.com
2	Deploy GPT-4o (reasoning) + text-embedding-3-large (semantic search) model connections
3	Provision Azure AI Search with 4 indexes: code-corpus, test-cases, defect-history, telemetry
4	Provision Azure Cosmos DB for traceability records
5	Provision Azure Service Bus with 6 topics (one per module boundary)
6	Create 6 AI Agents in AI Foundry Agents blade — each backed by GPT-4o with specific tools
7	Add Azure Functions (Python) for deterministic sub-tasks (parsing, API calls, dedup)
8	Connect CI/CD webhook from Azure DevOps / GitHub Actions to the platform HTTP trigger
9	Deploy React dashboard to Azure Static Web Apps reading from Cosmos DB
