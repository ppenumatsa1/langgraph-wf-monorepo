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

The lane uses a primary isolated BYO VNet with address space `10.74.0.0/16`
plus a small `westus3` VNet globally peered for the Search private endpoint.
Reserved subnets are:

| Reservation | CIDR | Purpose |
| --- | --- | --- |
| Foundry integration | `10.74.0.0/24` | Private Foundry integration |
| Container Apps | `10.74.2.0/23` | External frontend and internal wrapper |
| Private endpoints | `10.74.4.0/24` | Foundry, PostgreSQL, ACR, and approved services |
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

## Open implementation follow-through

1. Run noninteractive preview and private readiness checks from the private
   runner; stop on any unexpected mutation or missing prerequisite.
2. Run fresh hosted low-risk, approval/resume, damaged-item, telemetry, and
   report-only evaluation checks after runtime and infrastructure work lands.
3. Record release-window-scoped, secret-free evidence only after those checks
   complete.

## Explicit non-claims

- No live Azure deployment, private endpoint, DNS, identity, RBAC, runner,
  smoke, E2E, evaluation, or telemetry success is claimed.
- No historical resource ID, endpoint, conversation ID, evaluation ID, release
  ID, deployment ID, or success report is reused as private-lane evidence.
- No public dependency endpoint is approved as a fallback.
- No deployment approval prompt is a substitute for business HITL.
