---
name: azure-ai-projects-py
description: Use the Azure AI Projects Python SDK for the underwriting repo's Foundry project interactions, especially report-only hosted trace evaluation.
license: MIT
metadata:
  author: Microsoft
  version: "1.0.0"
  package: azure-ai-projects
---

# Azure AI Projects Python SDK (Underwriting)

Use this skill when working on repository code that talks to a Foundry project via `azure-ai-projects`. In this repository the primary current use is the report-only hosted trace evaluation in `backend/evals/foundry_trace_eval.py`.

## Repository touchpoints

- `backend/evals/foundry_trace_eval.py`
- `backend/eval.yaml`
- `backend/.foundry/datasets/underwriting-smoke.jsonl`
- `backend/.foundry/results/hosted-smoke-evidence.json`
- `backend/.foundry/results/foundry-trace-eval.json`

## Required environment

```bash
FOUNDRY_PROJECTS_ENDPOINT="https://<resource>.services.ai.azure.com/api/projects/<project>"
FOUNDRY_MODEL_DEPLOYMENT_NAME="underwriting-gpt-4-1-mini"
AZURE_TOKEN_CREDENTIALS=prod
```

Prefer `DefaultAzureCredential` and wrap both the credential and the `AIProjectClient` in context managers.

## Repository execution model

1. Refresh or confirm hosted smoke evidence for safe conversation ids.
2. Run the report-only trace evaluation:

```bash
make foundry-eval
```

`make foundry-trace-eval` is the same gate. `make foundry-native-eval` is diagnostic-only and must not replace the supported report-only flow.

## Guardrails

- Keep evaluation report-only unless the repository explicitly adds an enforcement switch.
- Evaluate only safe hosted conversations referenced by `backend/.foundry/results/hosted-smoke-evidence.json`.
- Do not expand the evaluation flow to capture applicant data, raw prompt content, or secrets.
- Keep outputs written to `backend/.foundry/results/foundry-trace-eval.json`.
- Use project-scoped Foundry operations; do not fall back to ad hoc key-based clients.

## Minimal pattern

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

with (
    DefaultAzureCredential() as credential,
    AIProjectClient(endpoint=project_endpoint, credential=credential) as project_client,
    project_client.get_openai_client() as openai_client,
):
    ...
```

## Required evidence

- `backend/.foundry/results/hosted-smoke-evidence.json`
- `backend/.foundry/results/foundry-trace-eval.json`
