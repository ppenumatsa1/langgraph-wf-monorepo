# E2E rubric

Playwright rubric source: `frontend/tests/e2e/rubric.ts`.

## Automated criteria

1. Happy path run completes and decision is shown.
2. Retry scenario records retry events and completes.
3. Crash scenario yields `CRASHED` status and a resumable run id.
4. Resume completes from a checkpointed run.
5. Fan-in state includes all required check results.
6. Checkpoint list is populated.
7. Idempotency skip signal is present in replay or resume path.
8. Event payload includes observability context fields.

## Manual and hosted criteria

9. Selected-run assistant behavior remains allowlisted and redacted.
10. Public release smoke confirms browser traffic stays on the frontend origin, `/backend-health` reaches the internal adapter, and direct backend public reachability is denied.
11. Public release smoke confirms the public request, hosted workflow, and report-only Foundry evaluation evidence correlate in Application Insights and Foundry.
12. Public release smoke confirms retry and crash or resume evidence correlate on one durable `workflow_run_id` per run.
13. Hosted release evidence is recorded in `docs/design/issues-changes-fixes.md` before readiness is claimed.
14. Deployment verification proves frontend external and backend internal ingress, ready revisions or images, Application Insights connection, runtime-secret placeholder integrity, and external-schema mode.

Criteria 1-8 are automated Playwright coverage. Criteria 9-14 are hosted or manual checks because they require deployed Azure resources, telemetry materialization, or privacy review. A local rubric pass requires all automated criteria to pass. A full public release pass requires both the automated criteria and the hosted or manual checks.
