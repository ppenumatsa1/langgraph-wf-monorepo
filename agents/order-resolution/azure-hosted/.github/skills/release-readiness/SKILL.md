---
name: release-readiness
description: Orchestrate local, infrastructure, app-only release, evaluation, telemetry, and documentation gates for the Azure-hosted lane.
---

# Release Readiness

1. Run backend boundary and documentation checks.
2. Run `make test-skills test-deployment-profile test-scripts`.
3. Run `make test eval-backend test-e2e`.
4. Run `make azure-iac-build azure-package`.
5. Confirm PostgreSQL schema/runtime-role setup and exact target readiness.
6. Use `make azure-release` for routine immutable app-only deployment.
7. Require topology/image verification, health smoke, low-risk and HITL domain
   E2E, Playwright, report-only Foundry evaluation, Application Insights
   correlation, evidence, and timings.
8. Run `design-review` last.

GitHub Actions remains credential-free and non-mutating.
