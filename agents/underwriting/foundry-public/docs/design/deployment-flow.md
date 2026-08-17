# Underwriting Foundry Public Deployment Flow

## Current design

The approved public lane keeps these rules:

- Azure operations run from a locally authenticated operator environment.
- `bootstrap` creates the full lane; `reuse` is non-mutating.
- PostgreSQL remains reachable only under the approved firewall and TLS posture.
- Schema creation and runtime credential provisioning remain explicit administrator steps.
- Production runtime startup uses `DB_SCHEMA_MANAGED_EXTERNALLY=true`.
- The backend receives the runtime URL through an ACA secret; the hosted agent receives only the literal project `CustomKeys` connection placeholder.
- Routine releases are app-only and do not invoke infrastructure reconciliation.
- Hosted package generation must sync from canonical source before `azd package`, and deployed images must be immutable digests.
- The frontend remains external, the backend remains internal, and browser traffic stays same-origin.

## Deployment stages

### Phase 1: validate and authorize

| Step | Stage | Outcome |
| ---: | --- | --- |
| 1 | Profile selection | Selects the secret-free public profile and resolves environment, region, and name prefix. |
| 2 | Source validation | Runs the required validation lane, design review, packaging checks, and script or profile checks. |
| 3 | Local Azure authentication | Confirms Azure CLI and AZD authentication and hydrates retained non-secret outputs into the selected local environment. |
| 4 | Infrastructure preview | Reviews bootstrap creation or non-mutating reuse. Unexpected resource, RBAC, or retained-state mutation is a stop condition. |

### Phase 2: provision the public platform

| Step | Stage | Outcome |
| ---: | --- | --- |
| 5 | Base infrastructure | Creates or confirms Foundry account and project, model deployments, ACR, monitoring, Container Apps, identities, PostgreSQL, and evaluation storage. |
| 6 | Database bootstrap and readiness | Applies canonical schema, creates or rotates the least-privilege runtime credential, and verifies TLS, hostname, firewall, required tables, and denied runtime DDL. |
| 7 | Foundry base connections | Confirms monitoring, evaluation-storage, and runtime-secret connection prerequisites for the public project. |

### Phase 3: deploy the application

| Step | Stage | Outcome |
| ---: | --- | --- |
| 8 | Shared readiness | Re-runs PostgreSQL readiness, performs read-only model or quota preflight, and converges the deterministic runtime-secret project connection. |
| 9 | Immutable image build | Synchronizes hosted packaging from canonical backend source, validates all three Docker contexts, builds backend and hosted images in ACR, builds the frontend locally, resolves digests, and records release-local image inputs. |
| 10 | Hosted activation then app deploy | Activates the hosted agent from the prebuilt digest, persists its exact version, and then deploys the internal backend and external frontend concurrently without mutating the approved topology. |
| 11 | Deployment verification and smoke | Verifies revisions, image digests, wrapper topology, Application Insights connection, runtime-secret placeholder integrity, same-origin health and API behavior, and hosted smoke success. |

### Phase 4: prove the release

| Step | Stage | Outcome |
| ---: | --- | --- |
| 12 | Hosted underwriting E2E | Runs happy, retry, and `medical_check` crash or resume coverage through the frontend origin and validates checkpoint resume, fan-in visibility, and idempotency-skip evidence. |
| 13 | Telemetry and evaluation | Waits for fresh trace materialization, verifies correlated Application Insights records and zero relevant exceptions, then runs report-only Foundry evaluation against the fresh evidence set. |
| 14 | Final evidence | Aggregates one secret-free release-window report and rejects stale, cross-window, incomplete, or secret-bearing artifacts. |

## Command mapping

| Command or operation | Stages | Purpose |
| --- | --- | --- |
| `make foundry-profile-apply` | 1 | Applies the selected public profile. |
| `make validate-quick` / `make validate-full` | 2 | Runs the validation lane selected by the deployment router. |
| `make foundry-bootstrap` | 3 | Selects and hydrates the target environment. |
| `azd provision --preview --no-prompt` | 4 | Reviews bootstrap or reuse behavior without applying it. |
| `make foundry-provision` | 3-7 | Performs bootstrap creation or template-defined reuse hydration. |
| `make foundry-postgres-schema` | 6 | Applies administrator-owned schema. |
| `make foundry-postgres-credentials` | 6 | Creates or rotates the least-privilege runtime credential. |
| `make foundry-postgres-readiness` | 6, 8 | Validates PostgreSQL connectivity, grants, and denied DDL. |
| `make foundry-runtime-connection` | 7, 8 | Converges the deterministic runtime-secret project connection. |
| `make foundry-model-preflight` | 8 | Confirms approved model availability or quota without mutating live capacity. |
| `make foundry-release-package` | 9 | Synchronizes and validates the release build contexts. |
| `make foundry-release-build` | 9 | Builds immutable backend, hosted-agent, and frontend images and records digests. |
| `make foundry-release-hosted-activate` | 10 | Activates the hosted agent from the prebuilt digest and persists its exact version. |
| `make foundry-release-app-deploy` | 10 | Deploys the prebuilt backend and frontend digests concurrently. |
| `make foundry-smoke` | 11 | Confirms hosted execution, runtime-secret resolution, and smoke-scenario completion. |
| `make foundry-eval` | 13 | Runs the supported report-only hosted trace evaluation. |
| `make foundry-verify` | 11, 14 | Independently verifies the deployed contract. |
| `make foundry-evidence` | 14 | Aggregates one secret-free release-window report. |
| `make foundry-release` | 2-14 | Runs the authenticated app-only release DAG. |

## Release paths

### Fresh bootstrap

1. Apply the bootstrap profile.
2. Validate source and review the bootstrap preview.
3. Provision the public platform.
4. Apply schema, runtime credentials, and readiness.
5. Run the app-only release.
6. Verify exact deployment state, smoke, hosted E2E, telemetry, evaluation, and final evidence.

### Routine app-only release

1. Apply the reuse profile.
2. Hydrate the retained environment.
3. Run the selected validation lane and packaging checks.
4. Run model preflight plus PostgreSQL readiness.
5. Converge the runtime-secret project connection.
6. Activate the hosted agent and deploy backend and frontend artifacts.
7. Verify exact deployment state and same-origin proxy behavior.
8. Run hosted E2E, telemetry, evaluation, and aggregate evidence.

`make foundry-release` must stay app-only.

## Timing gate

The release authority enforces two separate budgets:

- package/context start through backend/frontend deployment completion: **15 minutes**;
- package/context start through correlated telemetry: **30 minutes**.

The deployment budget measures artifact delivery rather than serial smoke, E2E,
evaluation, and telemetry latency. Timing data is valid only when packaging
start, telemetry success, hosted E2E evidence, evaluation evidence, and final
evidence all belong to the same release window.

## PostgreSQL security boundary

| Identity | Allowed | Denied |
| --- | --- | --- |
| PostgreSQL administrator | Schema DDL, runtime credential creation or rotation, readiness bootstrap | Application runtime use |
| Runtime role | Connect, schema usage, required table DML, required sequence usage | DDL, role creation, schema ownership, broad `CREATE` |
| Backend Container App | Consume runtime URL through secret reference | Receive administrator URL |
| Hosted agent | Resolve runtime URL only through the project `CustomKeys` placeholder | Persist resolved URL in metadata or evidence |

## Stop conditions

Stop the release if:

- preview proposes unexpected resource, PostgreSQL, network, or RBAC changes;
- runtime startup requires DDL or broader database privileges;
- package acquisition bypasses approved Python or npm feeds;
- hosted package output is stale relative to canonical source;
- any deployed image is not pinned by immutable digest;
- same-origin `/api` routes return HTML or other unexpected content types instead of JSON or SSE;
- hosted E2E, telemetry correlation, or evaluation uses stale evidence;
- selected-run assistant surfaces exceed the safe allowlist; or
- final evidence spans multiple release windows or contains secrets.
