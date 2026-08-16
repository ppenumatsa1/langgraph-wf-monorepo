# Order Resolution Foundry Public Deployment Flow

## Current design

The approved public lane keeps these rules:

- Azure operations run from a locally authenticated operator environment.
- `bootstrap` creates the full lane; `reuse` is non-mutating.
- PostgreSQL remains publicly reachable only under the approved firewall and
  TLS posture.
- Schema creation and runtime credential provisioning remain explicit
  administrator steps.
- Production runtime startup uses `DB_SCHEMA_MANAGED_EXTERNALLY=true`.
- The backend receives the runtime URL through an ACA secret; the hosted agent
  receives only the literal project `CustomKeys` connection placeholder.
- Routine releases are app-only and do not invoke infrastructure reconciliation.
- Hosted package generation must sync from canonical source before
  `azd package`, and deployed images must be immutable digests.

## Deployment stages

### Phase 1: validate and authorize

| Step | Stage | Outcome |
| ---: | --- | --- |
| 1 | Profile selection | Selects the secret-free public profile and resolves subscription, resource group, location, environment, and name prefix. |
| 2 | Source validation | Runs quick or full validation, design review, packaging checks, and any required script or profile tests. |
| 3 | Local Azure authentication | Confirms Azure CLI and AZD authentication and hydrates retained non-secret outputs into the selected local environment. |
| 4 | Infrastructure preview | Reviews bootstrap creation or non-mutating reuse. Any unexpected resource, RBAC, or retained-state mutation is a stop condition. |

### Phase 2: provision the public platform

| Step | Stage | Outcome |
| ---: | --- | --- |
| 5 | Base infrastructure | Creates or confirms Foundry account and project, model deployments, ACR, monitoring, Container Apps, identities, PostgreSQL, and evaluation storage. |
| 6 | Database bootstrap and readiness | Applies canonical schema, creates or rotates the least-privilege runtime credential, and verifies TLS, hostname, firewall, required tables, and denied runtime DDL. |
| 7 | Foundry base connections | Confirms monitoring, evaluation-storage, and runtime-secret connection prerequisites for the public project. |

### Phase 3: deploy the application

| Step | Stage | Outcome |
| ---: | --- | --- |
| 8 | Packaging and source sync | Synchronizes hosted packaging from canonical backend source, runs read-only model and quota preflight, reruns PostgreSQL readiness, and performs `azd package` freshness checks. |
| 9 | Concurrent runtime deployment | Deploys backend, frontend, and hosted-agent legs concurrently. The frontend stays same-origin; the backend stays internal; every leg resolves an immutable image digest. |
| 10 | Hosted-agent completion | Activates the hosted Responses 2.0 container with telemetry config and literal runtime-secret placeholders only. Foundry account RBAC converges to the required minimum. |
| 11 | Deployment verification and smoke | Verifies exact revisions, image digests, wrapper topology, Application Insights connection, runtime-secret placeholder integrity, backend secret parity, and same-origin API health. Also verify `/api/*` routes return JSON or SSE rather than HTML fallback content. |

### Phase 4: prove the release

| Step | Stage | Outcome |
| ---: | --- | --- |
| 12 | Hosted HITL E2E | Runs low-risk `ORD-1001`, high-risk `ORD-1009` approval/resume, and damaged-item HITL coverage in fresh hosted conversations. |
| 13 | Telemetry and evaluation | Waits for the configured trace age, verifies correlated Application Insights records and zero relevant exceptions, then runs report-only evaluation against those fresh conversations. |
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
| `make foundry-model-preflight` | 8 | Confirms the approved model set and quota without mutating live SKUs or capacity. |
| `make foundry-release-deploy` | 8-10 | Performs packaging, source sync, and concurrent runtime deployment. |
| `make foundry-verify` | 11 | Independently verifies the deployed contract. |
| `make foundry-evidence` | 14 | Aggregates one secret-free release-window report. |
| `make foundry-release` | 2-13 | Runs the authenticated app-only release DAG. |

## Release paths

### Fresh bootstrap

1. Apply the bootstrap profile.
2. Validate source and review the bootstrap preview.
3. Provision the public platform.
4. Apply schema, runtime credentials, and readiness.
5. Run the app-only release.
6. Verify exact deployment state, smoke, hosted E2E, telemetry, evaluation,
   and final evidence.

### Routine app-only release

1. Apply the reuse profile.
2. Hydrate the retained environment.
3. Run the selected validation lane and build/package checks.
4. Run model and quota preflight plus PostgreSQL readiness.
5. Converge the runtime-secret project connection.
6. Deploy backend, frontend, and hosted-agent artifacts concurrently.
7. Verify exact deployment state and same-origin proxy behavior.
8. Run hosted E2E, telemetry, evaluation, and aggregate evidence.

`make foundry-release` must stay app-only.

## Timing gate

The release authority rejects app-only-to-telemetry durations above
**15 minutes**. Timing data is valid only when:

- packaging/source-sync start is recorded,
- telemetry success is recorded,
- all intermediate gates are present and ordered,
- hosted E2E evidence is fresh, and
- the final evidence report belongs to the same release window.

Local timing artifacts help operators, but the reviewed release-window report
and ledger entry are the evidence of record.

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
- same-origin `/api` routes return HTML or other unexpected content types
  instead of JSON or SSE;
- hosted E2E, telemetry correlation, or evaluation uses stale evidence;
- final evidence spans multiple release windows or contains secrets.
