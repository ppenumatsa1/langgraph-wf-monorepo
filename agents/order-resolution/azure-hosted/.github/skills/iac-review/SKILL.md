---
name: iac-review
description: Review subscription-scope Bicep and Azure Container Apps release assets without deployment.
---

# IaC Review

Confirm:

- exact subscription, resource group, and eastus2 assertions;
- modular bootstrap and non-mutating reuse/app-only release separation;
- stable unique names and no routine deletion/replacement;
- exactly two Container Apps with external frontend/internal backend;
- SSE-safe same-origin proxy and health probes;
- non-root CFS-based images and immutable release digests;
- managed-identity ACR pull and least-privilege Foundry model access;
- PostgreSQL Entra administrator ownership and restricted runtime grants;
- Log Analytics/Application Insights wiring and redacted telemetry;
- secret-free parsed profiles and evidence;
- no cloud-mutating GitHub Actions.
