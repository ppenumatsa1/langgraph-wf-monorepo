# Infrastructure

The only Azure deployment path is
[Foundry hosted](foundry-hosted/README.md). It provisions the public Foundry
account, project, model deployments, ACR, and shared observability/data
dependencies from an empty resource group, deploys an external frontend
Container App and an internal FastAPI wrapper Container App, and hosts the
Responses-native LangGraph agent.

Browser traffic is same-origin through the frontend's `/api` proxy. The internal
backend uses managed identity to call Foundry and shares PostgreSQL durable
workflow state with the hosted agent. Local Docker remains the API/SSE/UI
development environment.
