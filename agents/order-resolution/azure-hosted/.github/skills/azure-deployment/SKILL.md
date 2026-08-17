---
name: azure-deployment
description: Execute the guarded Azure Container Apps bootstrap or immutable app-only release.
---

# Azure Deployment

Routine deployment is:

```bash
make azure-release
```

It validates locally, builds backend/frontend images in parallel, resolves ACR
digests, updates only the two Container Apps, verifies topology/images/proxy,
runs domain and browser E2E, executes report-only evaluation, correlates
Application Insights, and aggregates secret-free evidence.

Infrastructure bootstrap is exceptional:

```bash
make azure-bootstrap
```

Bootstrap previews infrastructure and fails closed on delete or replace
operations. Never run bootstrap from routine release or GitHub Actions. Never
add a Foundry application-host deployment leg. Report the public frontend URL
and identify the backend as internal-only.
