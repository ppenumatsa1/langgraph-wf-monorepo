# Project Structure

```text
azure-hosted/
  azure.yaml
  backend/                 FastAPI, LangGraph, PostgreSQL, evals, tests
  frontend/                React, Nginx proxy, Playwright
  infra/azure-apphosted/
    iac/main.bicep         subscription-scope orchestration
    iac/modules/           monitoring, ACR, Foundry, PostgreSQL, Container Apps
    runtime/               direct FastAPI launcher
  deployment/             parsed secret-free profiles
  scripts/azure/           bootstrap, release, verification, evidence
  scripts/local/           local parity helpers
  docs/                    design and testing contract
  .github/skills/          refreshed skill catalog and provenance
```

There is no `backend/foundry` entrypoint, hosted-agent source mirror, or
`azure.ai.agent` service.
