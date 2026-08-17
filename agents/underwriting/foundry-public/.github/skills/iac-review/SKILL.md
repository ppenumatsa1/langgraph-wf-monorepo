---
name: iac-review
description: Review underwriting Azure, Foundry, PostgreSQL, and deployment assets without mutating cloud resources.
---

# IaC Review Skill

Use this skill to review public-lane deployment assets before validation or deployment. Do not run commands that create, update, or delete Azure resources.

## Scope

Review repository deployment assets, including:

- `infra/foundry-hosted/azure.yaml`
- `infra/foundry-hosted/iac/main.bicep`
- `backend/Dockerfile.hosted`
- `frontend/Dockerfile`
- `scripts/foundry/*.sh`
- `scripts/foundry/*.py`

## Review checklist

- Verify `azure.yaml`, Bicep, bootstrap, provision, deploy, and smoke scripts describe one coherent public deployment path.
- Check hosted-agent, public-backend, and public-frontend deployment responsibilities stay distinct and explicit.
- Review Foundry project/account assumptions, hosted agent version flow, and managed-identity access patterns.
- Review PostgreSQL auth, firewall, schema bootstrap, runtime credential rotation, and the guarded rebuild path.
- Review Container App or hosted runtime environment variables, secret references, OpenTelemetry settings, and model-content capture defaults.
- Review Application Insights and Log Analytics wiring for the public adapter and hosted agent.
- Review least-privilege access across Foundry, PostgreSQL, ACR, App Insights, and supporting Azure resources.
- Flag plaintext secrets, widened origins, direct browser-to-Foundry paths, public admin surfaces, destructive defaults, and missing rebuild confirmations.

## Output

Report only actionable findings with file paths, risk, and recommended fixes. If no issues are found, state that IaC review passed without deployment.
