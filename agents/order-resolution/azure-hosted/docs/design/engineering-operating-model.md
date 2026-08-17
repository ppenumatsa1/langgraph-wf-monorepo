# Engineering Operating Model

## Change model

Product/domain/backend/frontend/tests are inherited from `foundry-public` and
remain aligned unless Azure hosting requires a change. Azure-specific work is
isolated to `infra/azure-apphosted`, `scripts/azure`, deployment profiles,
release contracts, and hosting documentation.

## Lifecycle

1. Local validation and deterministic evaluation.
2. Subscription-scope Bicep build and reviewed bootstrap preview.
3. Explicit one-time bootstrap.
4. Administrator-owned PostgreSQL schema/runtime-role setup.
5. Routine app-only release using immutable backend/frontend digests.
6. Topology/image verification, health smoke, low-risk/HITL domain E2E,
   Playwright, report-only Foundry evaluation, and App Insights correlation.
7. Secret-free evidence aggregation with stage timings.

Routine release never provisions or deletes Azure resources.
