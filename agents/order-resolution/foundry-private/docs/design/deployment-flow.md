# Private Foundry Deployment Flow

## Design contract

The private lane is an isolated BYO VNet deployment. It is a target design,
not live deployment evidence.

- Azure mutation runs only from the private runner.
- Automation is noninteractive and fail closed.
- `bootstrap` may create an isolated lane; `reuse` is non-mutating.
- Only the frontend has external ingress.
- The wrapper, Foundry, PostgreSQL, ACR, and runner remain private.
- Private DNS, endpoint approval, managed identity, and RBAC are prerequisites.
- The no-public-IP runner uses outbound-only NAT for required GitHub, package
  feed, Azure control-plane, and extension traffic. Other Internet egress is
  denied.
- The runner clones the exact private GitHub commit through protected Managed
  Run Command parameters. The credential is never embedded in the clone URL,
  AZD state, source, or evidence, and the Run Command resource is removed after
  bootstrap.
- Runner AZD state is retained with mode `0600` under
  `/var/lib/order-resolution/private-runner.env`; source refreshes merge
  protected state instead of replacing runner-generated database credentials.
- PostgreSQL schema creation and runtime credential provisioning remain
  explicit administrator steps.
- Production runtime startup uses `DB_SCHEMA_MANAGED_EXTERNALLY=true`.
- Hosted package generation syncs from canonical source before `azd package`,
  and deployed images use immutable digests.
- Application Insights is required; LangSmith is not required.
- Business HITL continues to use LangGraph `interrupt()` and
  `Command(resume=...)`; deployment gates must not bypass it.

## Network reservations

| Reservation | CIDR | Required use |
| --- | --- | --- |
| BYO VNet | `10.74.0.0/16` | Isolated lane address space |
| Foundry integration | `10.74.0.0/24` | Private Foundry integration |
| Container Apps | `10.74.2.0/23` | External frontend and internal wrapper |
| Private endpoints | `10.74.4.0/24` | Foundry, PostgreSQL, ACR, and approved services |
| Private runner | `10.74.5.0/27` | Validation, packaging, and approved mutation |

Private DNS zones must resolve all private service names from the wrapper and
runner. A public hostname or public administrative ingress is never an
acceptable fallback.

## Deployment stages

### Phase 1: validate and authorize

| Step | Stage | Blocking outcome |
| ---: | --- | --- |
| 1 | Profile selection | Selects a secret-free private profile and resolves only the intended subscription, resource group, location, environment, and name prefix. |
| 2 | Source validation | Runs quick or full validation, design review, packaging checks, and required profile/script tests. |
| 3 | Private runner bootstrap and identity | Clones the exact pushed commit, installs pinned dependencies, hydrates AZD state through protected parameters, then confirms scoped Reader, ACR Push, Container Apps Contributor, Foundry Project Manager, and Log Analytics Reader access. |
| 4 | Infrastructure preview | Reviews create/reuse behavior. Unexpected target drift, delete/replace, public exposure, endpoint, DNS, or RBAC changes stop the run. |

### Phase 2: establish the private platform

| Step | Stage | Blocking outcome |
| ---: | --- | --- |
| 5 | Network and DNS | Confirms the BYO VNet, subnet reservations, private endpoints, DNS zones/links, route policy, and endpoint approvals. |
| 6 | Private services | Creates or confirms private Foundry integration, private ACR, private PostgreSQL, Application Insights, identities, and Container Apps. |
| 7 | Database bootstrap and readiness | Applies canonical administrator schema, creates/rotates the least-privilege runtime credential, and verifies TLS, private hostname, tables, runtime DML, and denied DDL. |
| 8 | Foundry readiness | Confirms private endpoint reachability, model deployment/readiness, monitoring connection, runtime-secret connection prerequisites, and minimum RBAC. |

### Phase 3: deploy the application

| Step | Stage | Blocking outcome |
| ---: | --- | --- |
| 9 | Packaging and source sync | Synchronizes hosted packaging from canonical backend source, uses approved package feeds, runs model/quota preflight, and reruns private PostgreSQL readiness. |
| 10 | Private image deployment | Builds and pushes immutable images locally on the VNet runner through the private ACR endpoint, then deploys the backend/wrapper and frontend revisions. The frontend is externally reachable; the wrapper is internal. |
| 11 | Foundry activation | Activates the private Responses 2.0 host with telemetry configuration and literal runtime-secret placeholders only. |
| 12 | Verification and smoke | Verifies exact revisions, immutable digests, private DNS/IP resolution, endpoint connectivity, identity/RBAC, Application Insights connection, secret placeholder integrity, and same-origin `/api` JSON/SSE behavior. |

### Phase 4: prove the release window

| Step | Stage | Blocking outcome |
| ---: | --- | --- |
| 13 | Hosted HITL E2E | Runs low-risk `ORD-1001`, high-risk `ORD-1009` approval/resume, and damaged-item HITL coverage through the external frontend and private dependency path. |
| 14 | Telemetry and evaluation | Waits for configured trace age, verifies correlated Application Insights records and relevant exceptions, then runs report-only evaluation against fresh conversations. |
| 15 | Final evidence | Aggregates one secret-free, release-window-scoped report and rejects stale, cross-window, incomplete, or secret-bearing artifacts. |

## Command mapping

| Command or operation | Stages | Purpose |
| --- | --- | --- |
| `make foundry-private-profile-apply` | 1 | Applies the selected private profile from the runner. |
| `make foundry-private-gates` | 2 | Runs the private lane's local/profile gates. |
| `make foundry-private-what-if` | 4 | Reviews private bootstrap or reuse behavior without applying it. |
| `make foundry-private-provision` | 4-8 | Performs approved private bootstrap/reuse provisioning from the runner. |
| `make foundry-private-runner-bootstrap` | 3 | Securely clones the exact private commit, installs dependencies, and hydrates runner AZD state. |
| `make foundry-private-postgres-schema` | 7 | Applies administrator-owned schema. |
| `make foundry-private-postgres-credentials` | 7 | Creates or rotates the least-privilege runtime credential. |
| `make foundry-private-postgres-readiness` | 7, 9 | Validates private PostgreSQL connectivity, grants, TLS, and denied DDL. |
| `make foundry-private-model-preflight` | 8-9 | Confirms the approved model set and quota without mutating live capacity. |
| `make foundry-private-package` | 9 | Performs source sync and private package validation. |
| `make foundry-private-backend-deploy` / `make foundry-private-frontend-deploy` | 10 | Deploys immutable backend/wrapper and frontend images. |
| `make foundry-private-hosted-deploy` | 11 | Activates the private Foundry hosted runtime. |
| `make foundry-private-verify` | 12 | Independently verifies the private deployment contract. |
| `make foundry-private-smoke` / `make foundry-private-hosted-e2e` | 12-13 | Runs private smoke and hosted workflow/HITL checks. |
| `make foundry-private-eval` | 14 | Runs report-only private hosted evaluation. |
| `make foundry-private-telemetry` | 14-15 | Verifies Application Insights and release-window telemetry. |
| `make foundry-private-release` | 2-15 | Runs the authenticated app-only private release DAG. |

The commands above are existing repository commands. This documentation does
not claim that they have been run successfully in Azure.

## Release paths

### Isolated bootstrap

1. Apply the private bootstrap profile from the trusted operator context.
2. Validate source and review the noninteractive preview.
3. Establish the BYO VNet, private DNS, private endpoints, private services,
   identities, and RBAC.
4. Bootstrap the runner from the exact protected private-repository commit.
5. Apply schema, runtime credentials, and PostgreSQL/Foundry readiness.
6. Run the app-only release.
7. Verify exact revisions, private connectivity, smoke, hosted E2E,
   telemetry, evaluation, and final evidence.

### Routine app-only release

1. Apply the private reuse profile from the trusted operator context.
2. Refresh the private runner to the exact pushed release commit and hydrate
   its retained AZD environment through protected parameters.
3. Run selected validation and build/package checks.
4. Run model/quota preflight plus private PostgreSQL and Foundry readiness.
5. Converge the runtime-secret project connection.
6. Publish immutable images to private ACR and deploy the frontend, wrapper,
   and hosted Foundry artifacts.
7. Verify private connectivity and same-origin proxy behavior.
8. Run hosted E2E, telemetry, evaluation, and aggregate evidence.

The app-only path must stay app-only and must not change network topology,
endpoint exposure, RBAC, or database ownership.

## Timing and evidence gate

If a release policy defines a package-to-telemetry threshold, measure only the
same private release window. Timing data is valid only when:

- packaging/source-sync start is recorded;
- private deployment, smoke, and telemetry success are recorded;
- hosted E2E and evaluation are fresh;
- all intermediate gates are present and ordered; and
- the final evidence report belongs to the same release window and contains no
  secrets or resolved connection strings.

Local timing artifacts help operators but do not replace reviewed evidence.

## PostgreSQL security boundary

| Identity | Allowed | Denied |
| --- | --- | --- |
| PostgreSQL administrator | Schema DDL, runtime credential creation/rotation, readiness bootstrap | Application runtime use |
| Runtime role | Private TLS connect, schema usage, required table DML, required sequence usage | DDL, role creation, schema ownership, broad `CREATE` |
| Internal wrapper | Consume runtime URL through secret reference and private DNS | Receive administrator URL |
| Hosted Foundry runtime | Resolve runtime URL only through the project `CustomKeys` placeholder | Persist resolved URL in metadata or evidence |

## Stop conditions

Stop the release if:

- the preview proposes an unexpected resource, network, PostgreSQL, DNS,
  endpoint, or RBAC change;
- any private service is reachable through an unapproved public endpoint;
- the runner is outside the reserved subnet or lacks required identity/RBAC;
- private DNS or endpoint approval is missing;
- runtime startup requires DDL or broader database privileges;
- package acquisition bypasses approved feeds;
- hosted package output is stale relative to canonical source;
- any image is not pinned by immutable digest;
- same-origin `/api` routes return HTML or another unexpected content type
  instead of JSON/SSE;
- hosted E2E, telemetry correlation, or evaluation uses stale evidence; or
- final evidence spans multiple release windows or contains secrets.
