# Scripts

- `foundry/deploy_public_dev.sh`: authenticated local release sequence.
- `infra/foundry-hosted/runtime/launch_backend.py` and
  `launch_hosted_agent.py`: lane-owned stable startup shims that resolve the
  current LangGraph entrypoints (with legacy fallbacks) without editing
  `backend/`.
- `foundry/preflight_models.sh`: read-only validation of the exact
  Order Resolution chat, embeddings, and evaluator deployments plus regional
  quota records; it never changes model SKUs or capacity.
- `foundry/ensure_hosted_agent_rbac.sh`: idempotently converges only
  `Cognitive Services OpenAI User` for the hosted identity at the Foundry
  account scope.
- `foundry/ensure_foundry_azd_defaults.sh`: initializes the selected public
  AZD environment and resets provision-time Container App images to the MCR
  bootstrap image so deleted ACR tags cannot block infrastructure creation.
- `infra/foundry-hosted/runtime/Dockerfile.backend-release`: release-only
  backend image overlay that keeps the approved dependency feed and points the
  Azure backend leg at the stable LangGraph launcher.
- `foundry/hosted_smoke.sh`: direct Responses smoke with secret-free JSON
  evidence.
- `foundry/hosted_e2e.sh`: fresh ORD-1001 low-risk, ORD-1009 HITL
  approval/resume, and damaged-item HITL approval/resume regression.
- `foundry/verify_deployment.sh`: verifies exact active image digests, ACA
  topology, same-origin proxy health, hosted version/image/RBAC, App Insights,
  database URL parity, and externally managed schema mode.
- `foundry/verify_telemetry.sh`: bounded three-conversation Application
  Insights telemetry check.
- `foundry/release_evidence.py`: atomically initializes/finalizes the
  `langgraph-release/v1` record, records lock-safe UTC stage timings under
  `extensions.release_timing`, enforces required gates and successful timing
  completeness, and hashes artifacts under `.artifacts/releases/<release-id>/`.
- `foundry/release_migration.py`: dry-run-only inventory for legacy
  `deployment-report/` and singular `.artifacts/release/` candidates. It never
  copies or deletes sources; future deletion additionally requires live-release
  and durable-archive markers.
- `foundry/check_public_postgres_readiness.sh`: public PostgreSQL readiness.
- `playwright/`: local and hosted same-origin API/SSE browser regression suite.
- `make test-e2e-selected-thread`: focused frontend selected-thread integration
  test; `make test-e2e` runs it in addition to the workflow browser suite.
- `skills/`: operating-model enforcement and deterministic review gates.

GitHub Actions runs only credential-free CI. Use `make foundry-release` from an
authenticated local shell for Azure deployment and hosted validation.

Release v1 is live-validated by
`final-isolated-20260816T025501Z-667e609-public`; its app-only-to-telemetry
interval was 14m 01.1s. Legacy evidence paths are inventory-only and are not
release authority.

Run the UI suite against the public frontend with
`PLAYWRIGHT_BASE_URL="<frontend-url>" make test-e2e`; the internal backend
Container App is not a browser target.

## Release route

`make foundry-release` is always `app_only`: it reuses the existing PostgreSQL
database and retained public-lane dependencies. The router selects quick or
full *local validation*, not a different deployment mode. The release runs the
selected validation and Bicep build in parallel, packages fresh hosted source,
checks live model/quota state and PostgreSQL readiness, securely converges the
project `CustomKeys` runtime connection, then fans out
backend/frontend/hosted-agent deployment. Hosted deployment uses only the
literal connection placeholder. The release then converges hosted-agent RBAC,
verifies the exact deployed contract, and gates on smoke, hosted E2E,
report-only evaluation, correlated telemetry, and aggregate secret-free
evidence.

`make foundry-provision` is not a routine release fallback. It is the explicit
bootstrap/reuse command: bootstrap creates the complete lane, then output
hydration switches the selected local AZD environment to non-mutating reuse.
Run schema, runtime-credential, and readiness targets explicitly before the
first app release.

## Known non-blocking diagnostics

- `make up` may warn that it could not acquire an Azure CLI token (or that the
  CLI is absent) for a locally configured hosted mode; Compose still starts and
  an operator must provide `FOUNDRY_HOSTED_API_KEY` if that mode needs it.
- `foundry-postgres-readiness` may warn that database names could not be listed.
  The gate still requires the server Ready state, Azure-services firewall rule,
  and any supplied URL's TLS/FQDN validation.
- Hosted E2E may continue after an `azd ai agent invoke` nonzero exit only when
  the command produced parseable JSON; all subsequent response assertions still
  gate the run.
- The design-review skill warns when more than 20 files changed. It is a scope
  warning, not a release-gate pass or failure.
