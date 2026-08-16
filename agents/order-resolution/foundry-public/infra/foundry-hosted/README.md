# Public Foundry Hosted Agent

`infra/foundry-hosted` is the only Azure deployment path in this branch. It
deploys the shared LangGraph workflow as a public Foundry Responses agent, an external
React frontend Container App, and an internal FastAPI Responses-wrapper
Container App.

## IaC ownership boundary

The Bicep template has two explicit modes. `bootstrap` creates the complete
lane: Foundry account/project/models, ACR, monitoring, Container Apps
environment/apps, separate app identities, PostgreSQL, evaluation storage,
connections, and resource-scoped RBAC. `reuse` resolves deterministic existing
names and creates no resources, connections, or role assignments.

Evaluation storage is reachable by Foundry through the validated
selected-network/trusted-service posture: public network access is enabled,
the default network action is deny, and only the `AzureServices` bypass is
configured. Blob public access and shared-key authorization remain disabled.
Do not change storage to fully public access or disable networking without a
private endpoint.

Reuse hydration writes every required Bicep output into the selected local AZD
environment, including project/model values, monitoring and Container Apps
resource IDs, PostgreSQL FQDN, and `API_BASE_URL`/`WEB_URL`.

PostgreSQL administration is an explicit post-provision sequence. The canonical
schema is applied with the local administrator credential, a dedicated runtime
login receives DML-only grants, the runtime URL is stored only in the local AZD
environment, and readiness verifies TLS, dual authentication, database and
firewall state before an app release.

Foundry supplies and operates the agent session, file, and vector-store services.
This deployment configures none of the shared resources for those capabilities.

There are no customer-managed networking or runner resources.

## Public target

- Subscription: `7df95e88-701c-4693-af77-3159f83b558d`
- Resource group: `rg-langgraph-ora-foundry-public`
- Location: `eastus2`
- Bootstrap/reuse environments: `order-resolution-bootstrap` /
  `order-resolution-foundry-public`
- Agent: `order-resolution-hosted`

The profiles describe the canonical target but do not prove current live state.
Use the bootstrap profile only for explicitly approved creation and the reuse
profile for routine app-only releases. Review `azd provision --preview` before
infrastructure mutation. `make foundry-model-preflight` is the read-only live
model/quota gate; it validates the agent-specific chat, embeddings, and
evaluator set while recording, not changing, live SKU and capacity.

## Authenticated local release

```bash
make foundry-profile-apply \
  FOUNDRY_DEPLOYMENT_PROFILE=../deployment/profiles/foundry-public.env
make foundry-bootstrap
make foundry-release
```

The release script uses the change-aware deployment router, runs its selected
local validation concurrently with Bicep compilation, and always takes the
app-only route. It fresh-syncs and packages the hosted
context, checks the existing PostgreSQL target once, and deploys the backend,
frontend, and hosted agent independently by immutable ACR digest. Before hosted
deployment it converges the deterministic project `CustomKeys` connection by
streaming secure Bicep parameters over stdin; the runtime URL is not written to
disk or command arguments. The hosted definition contains only the literal
project-connection placeholder, never the resolved URL. Hosted-agent deployment obtains the
platform identity from the active version and
idempotently converges only the account-scoped `Cognitive Services OpenAI User`
role. `make foundry-verify` then checks active revisions/images, external
frontend/internal backend ingress, frontend and same-origin backend health,
hosted version/image and placeholders, App Insights, backend database-secret
parity, and externally managed schema mode. After smoke, the evaluator waits
for fresh three-conversation hosted-E2E evidence and its configured HITL trace
age; telemetry begins only after that evidence exists. `make foundry-evidence`
closes the release with one secret-free JSON report.

The backend release image now uses the lane-owned
`infra/foundry-hosted/runtime/Dockerfile.backend-release` overlay and
`launch_backend.py` stable launcher so Azure automation can follow the
LangGraph startup contract without editing `backend/`. Hosted packaging copies
`launch_hosted_agent.py` into the synced source and overrides the container CMD
to the same stable launcher path.

`make foundry-package` is a local-only gate. It seeds the dedicated
`order-resolution-package-validation` AZD environment from
`deployment/profiles/foundry-public-package-validation.env`, derives the
deterministic non-secret names locally, and runs `azd package` against that
environment without calling `az`, hydrating reuse outputs, or provisioning a
resource group.

Infrastructure creation/reuse is a separate `make foundry-provision`
operation. Apply the bootstrap profile and run `make foundry-bootstrap-env`
before first creation. After successful provisioning, output hydration switches
the local environment to reuse mode.

Before an authenticated release, follow the non-mutating validation recipe and
proof template in `.azure/deployment-plan.md`. After deployment, run hosted
browser validation:

```bash
PLAYWRIGHT_BASE_URL="$(azd env get-value WEB_URL --cwd infra/foundry-hosted)" \
make test-e2e
```

## Foundry evaluation configuration

From the repository root, `make eval-foundry` resolves its evaluator endpoint
and deployment names through this nested AZD project's selected environment.
It uses an allow-list of non-secret values and does not source or display the
environment `.env` file. Check resolution without contacting Foundry:

```bash
make eval-foundry-config
```

To evaluate against another existing local environment without running
`azd env select`, use:

```bash
FOUNDRY_AZD_ENV_NAME=<environment> make eval-foundry
```

`make foundry-up` verifies the deployed project still has an
`ApplicationInsights` connection targeting the configured component. The same
check is part of `make foundry-verify`, which fails before hosted
E2E/evaluation if that prerequisite is absent or drifted.

Telemetry-reader access remains an operational prerequisite. The release path
mutates only the Order-owned runtime-secret project connection and the hosted
identity's required account-scoped role; it does not add shared monitoring
roles.

For the explicit PostgreSQL sequence:

```bash
make foundry-postgres-schema
make foundry-postgres-credentials
make foundry-postgres-readiness
make foundry-runtime-connection
```

Compile before a deployment:

```bash
az bicep build --file infra/foundry-hosted/iac/main.bicep
```

Bootstrap uses public placeholder images only for initial Container App
creation. The app-only release scripts build uniquely tagged images, resolve
their ACR digests, deploy those immutable digest references, persist safe
gitignored component metadata, rotate the backend database secret, preserve the
internal backend/external frontend ingress boundary, and replace the
placeholders.

## Container dependency feed

The backend and hosted-agent Dockerfiles set
`PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple`, the approved
CFS package feed. Keep that feed unchanged for release-image dependency
installation; a package-feed change is a full-validation surface, not a
routine app-only edit.
