# Private Lane Issues, Changes, and Adopted Learnings

## Ledger purpose

This is the canonical design and documentation ledger for the private
LangGraph order-resolution lane. It records decisions, adopted operational
lessons, current scoped documentation/skill changes, and follow-through items.

It does **not** copy historical resource IDs, endpoints, conversation IDs,
evaluation IDs, release IDs, deployment IDs, or success evidence. Repository
configuration and local validation do not prove live Azure readiness or
deployment success.

## Private architecture decisions

### 1. Isolated BYO VNet

The lane uses a primary isolated BYO VNet with address space `10.74.0.0/16`,
a dedicated Foundry network-injection VNet with address space `10.76.0.0/16`,
and a small `westus3` VNet globally peered for the Search private endpoint.
Reserved subnets are:

| Reservation | CIDR | Purpose |
| --- | --- | --- |
| Foundry integration | `10.76.0.0/24` | Private Foundry integration |
| Foundry dependency endpoints | `10.76.1.0/24` | Hosted-compute endpoints for lane-owned dependencies |
| Container Apps | `10.74.2.0/23` | External frontend and internal wrapper |
| Private endpoints | `10.74.4.0/24` | Foundry, PostgreSQL, and approved application-side services |
| Private runner | `10.74.5.0/27` | Noninteractive validation and approved mutation |
| Search private endpoint | `10.75.0.0/27` | Same-region endpoint for the `westus3` Search service |

Private DNS zones/links and endpoint approval are mandatory. Overlapping
address spaces, unresolved private names, or missing endpoint approval are
fail-closed blockers.

### 2. Deliberate ingress boundary

Only the frontend is externally reachable. The FastAPI wrapper is internal.
Foundry, PostgreSQL, ACR, and the runner remain private. The browser has no
direct path to private dependencies.

### 3. Identity and automation boundary

Managed identity and least-privilege RBAC provide service-to-service access.
Authenticated validation, packaging, and Azure mutation run from the private
runner. Automation is noninteractive and fails closed on unexpected targets,
delete/replace plans, missing DNS, missing endpoint approval, missing RBAC,
readiness failures, or secret-bearing artifacts.

### 4. Observability boundary

Application Insights is the required runtime, release, and evaluation
observability backend. LangSmith is not required. Telemetry evidence must be
correlated to the same private release window and workflow identifiers.

### 5. Workflow and business HITL boundary

The lane retains one shared LangGraph `StateGraph`, native
`interrupt()`/`Command(resume=...)`, durable `AsyncPostgresSaver` checkpoints,
separate idempotent audit projections, and the stable native SSE event
contract. Deployment safety gates do not replace or bypass business approval.

## Adopted lessons

### Runtime ownership

- Production schema DDL remains administrator-owned.
- Production startup uses `DB_SCHEMA_MANAGED_EXTERNALLY=true`.
- Runtime database roles receive only the connect, schema usage, required table
  DML, and required sequence permissions.
- The graph checkpoint is authoritative; approval/history tables are
  projections and must remain idempotent.

### Packaging and release safety

- Generated hosted package context is deployment output, not source of truth.
  Sync it from canonical backend source before packaging.
- Approved Microsoft package feeds remain required for Python, frontend, and
  Playwright dependencies.
- Images must be addressed by immutable digest.
- App-only releases must not reconcile network topology, endpoint exposure,
  database ownership, or broad RBAC.

### Private readiness

- Validate private DNS, endpoint approval, routes, managed identity, RBAC,
  Foundry readiness, PostgreSQL TLS/readiness, and private ACR pulls before
  hosted smoke.
- Never use a public dependency endpoint to work around a private readiness
  failure.
- A frontend HTML response on an `/api` route is a proxy/topology defect, not
  workflow evidence.

### Telemetry and evaluation

- Application Insights workflow, Foundry, model, dependency, and HITL spans
  are the required operational signal.
- Hosted evaluation consumes only fresh E2E conversations after configured
  trace materialization age and requires explicit completion.
- A telemetry row count or local configuration is not deployment proof.

### Privacy

- Browser-facing AG-UI and CopilotKit projections remain selected-thread,
  read-only, and redacted.
- Raw order/customer data, policy and retrieval payloads, prompts, model
  output, checkpoint payloads, credentials, and secrets stay backend/private.

## 2026-08-20 - Current scoped implementation changes

### Documentation and instructions

- Reframed the private lane README, agents guide, parent lane index, and
  Copilot instructions around the isolated BYO VNet and private service
  topology.
- Rewrote architecture, deployment flow, user flow, engineering operating
  model, project structure, tech stack, PRD, HITL conditions, schema/telemetry,
  and manual testing documentation.
- Synchronized embedded Mermaid sources with the private frontend/wrapper/
  Foundry/PostgreSQL flow and the private runner/ACR/telemetry boundary.
- Added explicit no-live-success language and removed copied historical
  release evidence.

### Consolidated lane-local skills

- Refreshed the private provenance manifest to point local skills at this lane
  and updated review metadata.
- Extended existing deployment, validation, telemetry, IaC, LangGraph/Foundry,
  PostgreSQL, local/quick validation, release-readiness, docs-sync,
  evaluation, and E2E skills with private-network guidance.
- Preserved upstream Microsoft Foundry, Azure, FastAPI, PostgreSQL, LangGraph,
  and AG-UI guidance instead of duplicating it.
- Added private DNS, endpoint, runner, managed identity, immutable-image,
  fail-closed automation, Application Insights, and business-HITL boundaries
  where each existing skill owns that concern.

### Integrated implementation and local proof

- Added the private LangGraph runtime, frontend, IaC, release automation,
  evaluation, telemetry, evidence, documentation, and consolidated skills.
- Preserved one shared `StateGraph`, native PostgreSQL checkpoint authority,
  deterministic HITL, the stable event contract, idempotent side effects, and
  redacted selected-thread projections.
- Fixed the private frontend HITL view to derive safe action/order/amount
  metadata from the allowlisted `hitl.request` event when the approval audit
  projection intentionally omits duplicate business state.
- Updated the rejection browser assertion to validate the redacted semantic
  status instead of expecting raw JSON in the private frontend.
- Local workflow Playwright passed 7/7 and selected-thread Playwright passed
  7/7 in 51 seconds. The Docker workflow gate passed 7/7 in 143 seconds.
- Backend tests passed 144/144 and deterministic evaluations passed 11/11.

### Private runner integration fixes

- The first runner design assumed an existing source checkout and dependencies
  but had no bootstrap mechanism. The lane now clones the exact pushed commit
  from a private GitHub repository through protected Managed Run Command
  parameters, uses ephemeral `GIT_ASKPASS`, hydrates AZD state securely, and
  removes the Run Command resource after completion.
- The first packaging design used `az acr build`, whose managed build worker
  cannot reach a public-disabled registry without a private agent pool. Builds
  now execute with Docker on the VNet runner and push through the private ACR
  endpoint without enabling public access.
- The runner now receives scoped Reader, ACR Push, Container Apps Contributor,
  Foundry Project Manager, and Log Analytics Reader roles. Hosted deployment
  relies on Foundry Project Manager's constrained platform identity role
  convergence rather than granting general role-assignment authority.

### Integrated Rubber Duck findings and remediation

The integrated review found six release-blocking defects. All six were fixed
before Azure validation:

1. The no-public-IP runner had no package/control-plane egress. An outbound-only
   NAT Gateway and bounded HTTP/HTTPS NSG egress were added; other Internet
   traffic remains denied.
2. Managed Run Command creation was treated as if it returned terminal
   instance results. Bootstrap now creates asynchronously and polls
   `show --instance-view` to a terminal status.
3. The generated `GIT_ASKPASS` helper was not reliably executable. Bootstrap
   now creates the helper correctly, sets executable permissions, passes the
   token only as a protected parameter, and removes the helper afterward.
4. Container Apps target ports did not match the processes. Backend and
   frontend target ports now match `8000` and `5173`.
5. Immutable source refreshes could overwrite runner-generated AZD secrets.
   Protected state now persists at
   `/var/lib/order-resolution/private-runner.env` with mode `0600` and is
   merged on refresh.
6. The runner lacked deployment and identity permissions. It now receives
   Managed Identity Operator separately on both runtime identities and a
   narrow custom role limited to deployment-record operations, in addition to
   the resource-scoped roles documented above.

The same remediation also bounds Run Command evidence to 2,200 bytes, returns
only a sanitized stderr tail on failure, restricts nginx interception to
`502/503/504`, switches infrastructure mode to `reuse` after successful
bootstrap, and excludes generated pytest scratch content.

### Azure validation and preview remediation

- The official `azure.yaml` schema, required provider registration, inherited
  policy inventory, Bicep build/lint, private-network contracts, release
  contracts, backend `144/144` tests, and frontend typecheck/lint/build passed.
- The first preview found four Azure-side blockers:
  - `gpt-4.1-mini` Standard had only 100K TPM available;
  - `text-embedding-3-small` had only 10K TPM available;
  - `Standard_B2s` was restricted in `eastus2`; and
  - the Container Apps Consumption profile rejected min/max fields.
- The lane now allocates 50K TPM to chat, 50K TPM to evaluation, and 10K TPM
  to embeddings; uses unrestricted `Standard_D2as_v7` (2 vCPU, 8 GiB) for the
  runner; and omits unsupported Consumption min/max fields.
- The final fail-closed preview completed in 31 seconds with planned creates
  only and no delete or replace operations.

### First provisioning attempt

- The first live provisioning attempt created the initial private network,
  monitoring, ACR, PostgreSQL, Cosmos DB, runner, Container Apps environment,
  and several private endpoints, then failed closed before Foundry activation.
- Azure AI Search rejected the template because `authOptions` must be null
  when `disableLocalAuth` is true. The explicit `authOptions` block was
  removed; Entra-only access remains enforced through `disableLocalAuth: true`.
- ARM also reported a dependent network operation still in progress after the
  primary Search failure. No cleanup or destructive retry was attempted.
- Bicep, script contracts, and a fresh preview passed after the fix. The
  retry preview contains creates/modifies only and no delete or replace
  operation.

### Second provisioning attempt

- The retry converged the Foundry account, network injection, account
  capability host, and all three quota-safe model deployments. The account is
  `Succeeded`, public access is disabled, and the Foundry subnet has the
  expected successful `legionservicelink`.
- Azure AI Search S1 then failed with
  `InsufficientResourcesAvailable` in `eastus2`. The project and project
  capability host had not been created, so no capability-host cleanup or
  network replacement was required.
- Microsoft Learn documents Basic as a production-capable dedicated tier and
  confirms inbound Private Link is unavailable only on Free. Standard Agent
  Setup requires a BYO Azure AI Search resource but does not state an S1
  minimum. The isolated single-project lane therefore uses Basic rather than
  changing region, reusing another lane's Search resource, weakening private
  access, or scaling to a substantially more expensive tier.

### Third provisioning attempt and documented region constraint

- Basic also failed with `InsufficientResourcesAvailable`, proving the failure
  was regional rather than S1-specific.
- Current Microsoft Learn region guidance explicitly marks `eastus2` as
  capacity constrained for creation of all new Azure AI Search services and
  scaling operations and instructs customers to choose another region.
- The lane restores the official Standard Agent Setup S1 tier and places the
  lane-owned Search service in unconstrained `westus3`. Foundry, models, the
  primary VNet, non-Search private endpoints, PostgreSQL, ACR, Container Apps,
  runner, and monitoring remain in `eastus2`.
- Azure AI Search private-endpoint guidance requires Search, the endpoint VNet,
  and a test client topology in a common region. The Search private endpoint
  therefore uses a small `westus3` VNet globally peered to the primary
  `eastus2` VNet. The Search private DNS zone links both VNets, preserving a
  private-only route from Foundry, the wrapper, and the runner.
- Repeated monolithic deployments also showed that ARM could complete the
  Foundry account resource while the service still reported `Accepted`,
  allowing the Foundry private endpoint to race and fail with
  `AccountProvisioningStateInvalid`.
- Provisioning is now split into two idempotent, fail-closed phases. Phase one
  converges the account and account capability host; a bounded automatic poll
  requires both to report `Succeeded`; phase two independently previews and
  creates the Foundry endpoint, project, connections, RBAC, and project
  capability host. This removes both blind retries and human approval flags.

### Fourth provisioning attempt: VNet child-resource ordering

- S1 Search and its same-region private endpoint provisioned successfully in
  `westus3`, resolving the external Search capacity blocker.
- ARM attempted both global peerings while the new Search VNet's subnet PUT was
  still `Updating`, and rejected them with
  `ReferencedResourceNotProvisioned`.
- Both peering resources now explicitly depend on completion of every primary
  and Search VNet subnet resource. Existing successful Search resources are
  converged in place; no deletion or recreation is required.

### Fifth provisioning attempt: phase-two account mutation

- The ordered peerings and complete phase-one deployment succeeded.
- Although the phase-two preview labeled the Foundry account `Skip`, the
  emitted account declaration still caused an asynchronous account PUT. The
  account returned to `Accepted` after the readiness poll, and the private
  endpoint again failed with `AccountProvisioningStateInvalid`.
- Account/network injection and model resources are now emitted only in the
  convergence phase. The endpoint, project, connections, RBAC, and project
  capability host bind to an `existing` Foundry account scope in phase two, so
  the post-readiness deployment cannot issue another account PUT.

### Sixth provisioning attempt: endpoint approval propagation

- Both IaC phases completed successfully, including the Foundry private
  endpoint, project, project connections, project capability host, backend,
  and connected global VNet peerings.
- Reconciliation read the raw private-endpoint connection response at
  `.privateLinkServiceConnectionState` instead of the actual
  `.properties.privateLinkServiceConnectionState` path, incorrectly treating
  an approved connection as missing.
- Reconciliation now polls each endpoint connection for up to 10 minutes,
  parses the actual Azure response shape, succeeds only on `Approved`, and
  fails immediately on `Rejected` or `Disconnected`. Authentication,
  authorization, and CLI failures still propagate rather than being treated
  as pending.

### Private-runner protected parameter transport

- The installed Azure CLI accepted a JSON file for
  `az vm run-command create --protected-parameters` but silently omitted those
  parameters; the runner correctly failed closed because `GITHUB_TOKEN` was
  absent.
- A harmless live probe confirmed shorthand `name=value` works but would place
  secret values in local process arguments.
- Runner bootstrap now sends the complete Managed Run Command REST payload
  from a mode-`0600` file in `/dev/shm`. The process arguments contain only the
  file path, while `GITHUB_TOKEN` and the AZD environment remain in the ARM
  `protectedParameters` collection. A live probe confirmed the protected value
  reaches the VM without appearing in command output.
- The first protected bootstrap then exposed a Git helper-scope defect:
  `GIT_ASKPASS` covered only `clone`, and the helper child was not guaranteed to
  inherit `GITHUB_TOKEN`. The runner now exports and forces the executable
  helper for clone, fetch, and detached checkout, then unsets the token and all
  Git prompt variables immediately after installing the exact source tree.
- Managed Run Command does not define `HOME`; AZD refused to infer a config
  path after dependencies installed. The root-run bootstrap now sets
  `HOME=/root` explicitly before Azure CLI or AZD initialization.
- Every subsequent runner stage starts in a new Run Command process, so the
  same explicit `HOME=/root` contract now lives in the shared stage dispatcher
  used by PostgreSQL, packaging, deployment, smoke, E2E, evaluation, and
  telemetry.
- `az vm run-command invoke` evaluates its launcher with `/bin/sh`; the
  Bash-only outer `set -o pipefail` failed before `runner_stage.sh` could emit
  evidence. The outer launcher now uses POSIX `set -eu`, then `exec`s the Bash
  stage dispatcher where `pipefail` remains enforced.
- PostgreSQL schema bootstrap then passed, while runtime credential bootstrap
  reached ARM and exposed a 65-character deployment name. The connection
  deployment now derives its release suffix from the exact remaining
  `64 - prefix length` budget instead of a fixed slice.
- The first full release reran all local gates successfully but stopped before
  packaging because `release.sh` records `runner_bootstrap` while the evidence
  timing schema omitted that stage. The stage is now part of the authoritative
  timing order between `local_gates` and `runner_preflight`.
- The next release reached private readiness and found that Azure serializes
  quota values as JSON numbers such as `350.0`; the integer-only shell regex
  rejected valid usage. Preflight now validates numeric JSON types and
  `current <= limit`. A fully allocated existing deployment is valid even when
  it has no remaining capacity for a new deployment.
- Immutable packaging then exposed a jq boolean-defaulting defect:
  `false // fallback` selects the fallback, so a correctly disabled ACR admin
  user appeared unset. The registry guard now tests both supported property
  paths for an explicit JSON `false` value.
- The ACR packaging and final verification guards retained the same flattened
  private-endpoint approval path already corrected in reconciliation. Both now
  read the live ARM shape under
  `.properties.privateLinkServiceConnectionState.status`, and the script
  contract rejects reintroducing the flattened path.
- ACR packaging built and pushed all three images, but `az acr login --output
  none` still forwarded Docker's `Login Succeeded` text to stdout. Because the
  runner stage reserves stdout for one JSON evidence object, that text made
  the result unparsable. Registry login stdout is now explicitly discarded;
  command failures still propagate under strict shell mode.
- Backend deployment reached its isolation guard and exposed another
  `false // empty` jq check. The deploy and runtime-verification stages now
  require explicit JSON booleans for internal backend and external frontend
  ingress rather than applying a fallback operator to boolean values.
- The first Foundry hosted version reached the service but failed provisioning.
  Its project identity already held both registry-reader roles; live ACR
  inspection showed the required
  `azureADAuthenticationAsArmPolicy` was unset. The private registry now
  enables that policy in Bicep, and packaging fails closed unless the live
  policy is `enabled`. Admin authentication and public network access remain
  disabled.
- Comparison with the known-good MAF private project proved that a
  project-scoped `ContainerRegistry` connection is not required. Foundry pulls
  private images through the project identity's `AcrPull` and Container
  Registry Repository Reader assignments. The speculative ACR connection was
  removed from the live project and from Bicep.
- The MAF baseline uses a project-scoped, non-shared Application Insights
  connection. The lane now follows that scope instead of inheriting an
  account-shared connection.
- Hosted deployment remains bounded at twenty minutes and reuses an active
  version only when immutable image, environment, CPU, memory, and instance
  identity all match. A changed runtime definition still creates and waits for
  a new version.
- Full SDK reads then proved the version-list summary incorrectly reported
  failed versions as active; deployment now normalizes the SDK status enum and
  trusts full version details.
- ACR data-plane diagnostics disproved the subsequent per-version identity
  hypothesis. The Foundry project identity authenticated and pulled the exact
  production and diagnostic digests from private `10.74.0.x` addresses with
  HTTP 200 responses. The per-version identities did not perform those pulls.
  The temporary runner permission to create per-version `AcrPull` assignments
  therefore broadened privilege without affecting activation and has been
  removed from Bicep and deployment automation.
- The live Standard Agent Storage RBAC was compared with Microsoft's current
  private-network template. The lane now grants the project identity
  account-scoped `Storage Blob Data Contributor` before capability-host
  creation and account-scoped `Storage Blob Data Owner` with the official
  workspace-prefix and `*-azureml-agent` ABAC condition. The corrected roles
  were deployed successfully, and the project capability host was reconciled
  in place through the reference `2025-04-01-preview` API.
- A raw HTTP diagnostic version still failed after the Storage correction.
  A second control image used Microsoft's official
  `azure-ai-agentserver-responses` host pattern with no LangGraph,
  PostgreSQL, runtime connection, or application initialization. Its immutable
  image was built and pulled successfully, but versions 4 and 5 both failed
  before a hosted session existed, including after capability-host
  reconciliation.
- A final standalone control removed production-image inheritance and SDK
  drift. It used Microsoft's current sample Docker shape (`python:3.12-slim`)
  and exact sample versions `azure-ai-agentserver-responses==2.0.0b0`,
  `azure-ai-projects==2.0.1`, and `azure-identity==1.25.3`, installed through
  the approved Microsoft package feed. Version 6 failed identically before
  session creation. Private-runner Log Analytics queries confirmed repeated
  pulls of its exact digest by the project identity from `10.74.0.x`
  addresses, so neither the production base image nor stable SDK versions are
  plausible remaining causes.
- The account and project capability hosts remain `Succeeded`; the account
  host references the dedicated Foundry subnet, and the project host references
  the expected private Cosmos DB, Storage, and Search connections. This
  isolates the remaining blocker to Foundry hosted-compute activation or its
  service-side capability-host integration rather than application code,
  container readiness, ACR access, or PostgreSQL.
- Both the working MAF account and the failing LangGraph account have
  `disableLocalAuth: true` and public network access disabled. The inherited
  `MCAPSGovDeployPolicies` assignment therefore explains why account updates
  retain Entra-only authentication, but it does not explain hosted activation.
  No policy exemption is required or justified.
- The same standalone Microsoft Responses control became `active` and created
  a session as version 1 in the existing MAF private account. It then became
  `active` and created a session in a new Foundry account injected into a fresh
  subnet in the MAF VNet. This disproves a subscription-wide or regional
  service outage and proves the image, SDK, ACR pattern, policy state, and
  current account-creation path can work.
- In the LangGraph VNet, the same control failed in the original project, a
  fresh project, a fresh account on a separate delegated `/24`, and a second
  fresh account created after removing global VNet peering. It also failed
  after matching MAF NAT, service endpoint, NSG, project connection, RBAC, and
  Standard Agent dependency settings.
- A recovery project using the exact MAF Storage, Cosmos DB, and Search
  dependencies returned `invalid_configuration` with request IDs
  `1e32f26f360f4fc0573cee5696f0a1df`,
  `b1d31ec65ad691240ea08a83b8754038`, and
  `53075aa912bf7ced00d9405fb0da07ef`. Foundry reported that a
  customer-managed downstream dependency was inaccessible even though the
  same dependencies activate from the MAF VNet.
- The remaining blocker is therefore isolated to Foundry's managed
  network-injection/service-link path for the LangGraph VNet. The account and
  subnet resources report `Succeeded`, so this condition cannot be repaired
  safely by broadening application RBAC or weakening public-network controls.
- The MAF baseline also proved that Storage Blob Data Owner's ABAC condition
  must use the raw 32-character Foundry workspace ID. The lane had formatted
  that value as a hyphenated GUID; Bicep now preserves the raw ID. This was a
  real authorization defect but did not by itself resolve activation.
- The sanitized reproduction and support handoff are tracked in repository
  issue
  [#1](https://github.com/ppenumatsa1/langgraph-wf-monorepo/issues/1).
- Hosted and wrapper environments now use `foundry-private-hosted` and
  `foundry-private-wrapper`. This activates the lane's TLS, unresolved
  placeholder, and externally managed schema guards instead of misclassifying
  private runtime processes as `aca-private`.

### 2026-08-24 - Fresh Foundry VNet recovery and hosted image contract

- A clean `10.76.0.0/16` Foundry VNet and fresh Foundry account restored
  network-injected hosted activation. The project identity pulled an exact
  known-good digest from the lane-owned private ACR and the control became
  active, proving the new network, private registry endpoint, RBAC, capability
  hosts, model deployments, and lane-owned dependencies.
- The authoritative ACR endpoint is now only in the `10.76.1.0/24` Foundry
  dependency subnet. Primary-VNet clients reach it through peering and shared
  private DNS. Defining a second ACR endpoint in `10.74.4.0/24` produced
  duplicate private DNS names and selected the stale address, so that endpoint
  and its DNS group were removed from live Azure and repository IaC.
- Every newly built diagnostic and production image was pulled successfully
  but failed activation. Artifact comparison found that the active image was
  an OCI image index containing a Linux/amd64 manifest and a BuildKit
  provenance attestation, while rejected runner builds were bare OCI image
  manifests.
- Wrapping a rejected manifest in a one-platform index still failed. Rebuilding
  the same control with `docker buildx build --platform linux/amd64
  --provenance=true --push` produced the expected two-entry OCI index and
  became active as
  `order-resolution-buildx-control:1`. This isolates the blocker to the hosted
  image publication shape rather than application code, package versions,
  local authentication, networking, identity, or dependencies.
- Private packaging now requires Docker Buildx, publishes hosted images with
  provenance, and rejects an artifact unless registry inspection confirms both
  the Linux/amd64 image and the attestation entry. Backend and frontend
  packaging retain their proven single-manifest Docker path.

### 2026-08-24 - Foundry session PostgreSQL connection exhaustion

- The first Azure browser run was initially misread as automatic HITL approval
  because its failure snapshot showed a completed high-risk conversation.
  Application Insights request evidence proved the headless browser had
  explicitly posted `/api/hitl/respond`; a standalone high-risk browser flow
  then passed. HITL parsing, checkpoint matching, and explicit browser approval
  were not the failure.
- Later browser starts returned wrapper HTTP 500 responses backed by Foundry
  `424 Failed Dependency`. A failed hosted session log exposed the actionable
  cause: `FATAL: too many connections for role
  "order_resolution_runtime"`. The least-privilege role correctly retained its
  20-connection limit, while 16 connections were already in use.
- A Foundry Responses conversation can retain an idle hosted compute session.
  The previous defaults kept at least one connection open and allowed up to ten
  in both the synchronous audit repository pool and the LangGraph
  `AsyncPostgresSaver` pool. The internal wrapper owned the same two pools.
  Repeated hosted and browser conversations therefore accumulated idle
  connections across isolated processes.
- The MAF private reference contains no recorded connection-pool exhaustion
  issue and uses one synchronous `ConnectionPool(min_size=1, max_size=10)`.
  Its protected hosted E2E creates only three fresh conversations and retries
  transient 404/409/429/5xx responses for up to twenty 15-second intervals.
  LangGraph adds a second app-lifetime asynchronous checkpoint pool and this
  release ran hosted E2E plus several fresh browser conversations back to
  back. The MAF shape therefore had roughly half the per-session connection
  floor and enough retry/cooling time to avoid exposing this latent lifecycle
  risk; it is not evidence that unbounded idle pools are safe.
- Both LangGraph pools now share one validated configuration contract. Hosted
  sessions use a zero idle floor, one connection maximum per pool, a 15-second
  idle lifetime, and an identifiable PostgreSQL application name. The wrapper
  uses a zero idle floor, two connections maximum per pool, the same idle
  lifetime, and its own application name. Deployment and runtime verification
  fail if these settings drift.
- Browser release execution is explicitly single-worker and paced for hosted
  session turnover. On failure it retains a bounded local log and emits only a
  sanitized tail instead of suppressing all Playwright diagnostics.
- All 36 retained idle diagnostic Foundry sessions were stopped during diagnosis.
  A fresh immutable deployment and complete release rerun remain required
  before claiming the connection remediation or downstream browser,
  evaluation, and telemetry gates as accepted.
- Release `langgraph-order-resolution-private-20260824T204831Z-212460`
  subsequently proved hosted smoke, three-scenario hosted E2E, workflow browser
  7/7, and selected-thread browser 7/7 with the bounded pools. It then stopped
  at evaluation before contacting Foundry because
  `python -m evals.foundry_eval_runner` was launched from the lane root, where
  the `backend/evals` package was not importable.
- The public and Azure-hosted reference scripts both change into `backend`
  before launching the evaluator module. The private runner now follows that
  same module-resolution contract, and its script test rejects removing the
  working-directory change. A fresh release remains required because the
  failed release cannot provide atomic evaluation and telemetry evidence.
- The next release reached Foundry evaluation and failed artifact upload with
  `ResourceMsiTokenDoesntHavePermissionsOnStorage`. The project already had
  unconditioned `Storage Blob Data Contributor` plus the Standard Agent
  workspace-conditioned `Storage Blob Data Owner`, but evaluation artifacts
  are not confined to `*-azureml-agent` containers. Current Microsoft Foundry
  evaluation guidance requires unconditioned `Storage Blob Data Owner` for
  both the Foundry account and project managed identities on the connected
  storage account.
- IaC now grants that resource-scoped owner role to both Foundry identities.
  Runtime verification rejects missing, conditioned, or drifted assignments
  before smoke/E2E/evaluation. Public storage access remains disabled; this
  changes data-plane authorization only and does not weaken private
  networking.

## Open implementation follow-through

1. Build and deploy a fresh production hosted image from the exact committed
   remediation and verify its immutable digest becomes active.
2. Run fresh hosted low-risk, approval/resume, damaged-item, browser,
   telemetry, and report-only evaluation checks.
3. Complete the integrated Rubber Duck review, remove diagnostic agents,
   repositories, and temporary cross-lane roles, then record only fresh
   release-window evidence.

## Explicit non-claims

- Azure infrastructure, private endpoints, DNS, identities, runner,
  PostgreSQL readiness, private ACR packaging/pulls, backend/frontend
  deployment, and Buildx control activation are live and verified. No active
  production LangGraph version, hosted smoke, hosted/browser E2E, Foundry
  evaluation, or release-window telemetry success is claimed yet.
- No historical resource ID, endpoint, conversation ID, evaluation ID, release
  ID, deployment ID, or success report is reused as private-lane evidence.
- No public dependency endpoint is approved as a fallback.
- No deployment approval prompt is a substitute for business HITL.
