---
name: azure-validation
description: Validate Azure Container Apps, Bicep, profiles, images, PostgreSQL, Foundry models, and release gates without mutating Azure.
---

# Azure Validation

Run:

```bash
make test-skills
make test-deployment-profile
make test-scripts
make azure-iac-build
make azure-package
```

Review the subscription/resource-group/location assertions, bootstrap/reuse
separation, two-service `azure.yaml`, internal backend, external frontend,
SSE-safe proxy, probes, non-root images, managed-identity ACR pull, Foundry
model-only RBAC, administrator-owned PostgreSQL DDL, and secret-free profiles.

Use `az deployment sub what-if` only as a reviewed read-only preview. Do not
deploy from validation.
