# Azure Application Hosting

The external frontend Container App serves React and proxies `/api` to the
internal FastAPI Container App. FastAPI runs the shared LangGraph directly.
Foundry is limited to model inference and report-only evaluation.

Build the templates without deploying:

```bash
make azure-iac-build
```

One-time bootstrap:

```bash
AZURE_BOOTSTRAP_APPROVED=true make azure-bootstrap
```

Bootstrap generates `POSTGRES_SERVER_ADMIN_PASSWORD` into local AZD state.
PostgreSQL uses dual Entra/password authentication. Its Azure-services firewall
rule is a public-POC compromise, not private networking; production requires a
private or deterministic-egress design.

Routine releases:

```bash
make azure-release
```
