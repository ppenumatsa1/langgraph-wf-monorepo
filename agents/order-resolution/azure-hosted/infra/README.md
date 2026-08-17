# Infrastructure

`azure-apphosted/iac/main.bicep` is the only Azure infrastructure path. It is a
subscription-scope entrypoint with exact target assertions and modules for
monitoring, ACR, Foundry models/evaluation, PostgreSQL, and Container Apps.

Bootstrap is explicit and reviewed. Routine app-only releases use
`scripts/azure` and do not run Bicep.
