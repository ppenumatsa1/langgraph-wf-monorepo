# Private Foundry Hosted Agent Infrastructure

This directory is the Azure deployment root for the Order Resolution
Foundry-private lane. It deploys the shared LangGraph workflow as a Foundry
Responses 2.0 hosted agent and exposes the application only through an external
React frontend Container App that proxies to an internal FastAPI wrapper.

## Canonical target

- Subscription: `7df95e88-701c-4693-af77-3159f83b558d`
- Resource group: `rg-langgraph-ora-foundry-private`
- Region: `eastus2`
- Azure AI Search region: `westus3` because current Microsoft Learn guidance
  marks `eastus2` unavailable for new Search services and scaling. Search and
  its private endpoint use a small same-region VNet globally peered to the
  primary `eastus2` VNet.
- AZD environment: `order-resolution-foundry-private`
- Agent: `order-resolution-hosted`
- VNet: `10.74.0.0/16`
- Foundry VNet: `10.76.0.0/16`
- Search private-endpoint VNet: `10.75.0.0/24`

The VNet has dedicated, non-overlapping subnets:

| Purpose | CIDR |
| --- | --- |
| Foundry Agent Service delegation | `10.76.0.0/24` |
| Foundry dependency private endpoints | `10.76.1.0/24` |
| Container Apps infrastructure | `10.74.2.0/23` |
| Private endpoints | `10.74.4.0/24` |
| Azure Run Command runner | `10.74.5.0/27` |
| Search private endpoint | `10.75.0.0/27` in the globally peered `westus3` VNet |

The Foundry agent subnet is delegated to `Microsoft.App/environments` and must
not be reused by Container Apps or the runner. The frontend is the only public
application ingress. Foundry, ACR, PostgreSQL, the backend, and the runner stay
on private paths.

## IaC contract

`iac/main.bicep` creates the lane-owned network, private DNS and endpoints,
network-injected Foundry account/project, Standard Agent Setup dependencies,
Premium ACR, PostgreSQL, Azure Monitor resources, VNet-integrated Container
Apps, managed identities, least-privilege RBAC, and a no-public-IP runner VM.
The runner subnet has an outbound-only NAT Gateway for required GitHub,
package-feed, Azure control-plane, and extension traffic; it does not create
public administrative ingress.

Network injection is configured when the Foundry account is created. The
platform creates the account capability host from `networkInjections`; the
template creates the project capability host only after its connections and
RBAC prerequisites exist. A partially failed capability-host deployment can
leave a `legionservicelink` association on the agent subnet. Use the
capability-host-first cleanup target or a new subnet/VNet; do not blindly retry
the contaminated subnet.

Profiles under `../../deployment/profiles` are secret-free target selectors.
PostgreSQL bootstrap credentials and runner source access are supplied outside
those profiles and must never be committed or copied into release evidence.
The runner receives the exact private GitHub commit and AZD environment through
Managed Run Command protected parameters. Git credentials are handled by an
ephemeral `GIT_ASKPASS` process, never written into the repository URL, and the
managed Run Command resource is deleted after bootstrap.
Runner AZD state persists at
`/var/lib/order-resolution/private-runner.env` with mode `0600`. Source
refreshes merge protected values so runner-generated database credentials are
not replaced by operator-side defaults.

The runner receives Reader and Container Apps Contributor at the lane resource
group, ACR Push at the registry, Foundry Project Manager at the project, Log
Analytics Reader at the workspace, Managed Identity Operator separately on
the backend and frontend identities, and a narrow custom role limited to
resource-group deployment records.

## Validation and lifecycle

From the lane root:

```bash
make test-deployment-profile
make test-scripts
make foundry-private-iac-build
FOUNDRY_PRIVATE_INFRASTRUCTURE_MODE=bootstrap make foundry-private-what-if
```

The what-if guard fails on unplanned delete or replace operations. Provisioning
is explicit and separate from routine delivery:

Bootstrap is intentionally two phase. The first preview and deployment
converge the Foundry account, account capability host, network injection, and
dependencies. A bounded readiness poll then requires both Foundry resources to
report `Succeeded`; only the second preview and deployment can create the
Foundry private endpoint, project, project connections, RBAC, and project
capability host. This prevents the private endpoint from racing the account's
transient `Accepted` state.

```bash
make foundry-private-provision \
  FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE=deployment/profiles/foundry-private-bootstrap.env
```

Routine delivery is app-only and runner-mediated:

```bash
make foundry-private-release \
  FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE=deployment/profiles/foundry-private.env
```

The release packages canonical source, pushes to private ACR, resolves immutable
digests, deploys Container App revisions and one immutable hosted-agent
version, then runs verification, smoke, three-conversation HITL E2E, browser
E2E, Foundry evaluation, Application Insights correlation, and atomic
secret-free evidence aggregation.

Image builds execute with Docker on the runner and push through ACR's private
endpoint. `az acr build` is deliberately not used because an Azure-managed ACR
task without a dedicated private agent pool cannot reach this registry.

Every AZD command sets
`AZURE_DEV_USER_AGENT=microsoft_foundry_skill`. GitHub Actions performs
credential-free validation only and never provisions or deploys Azure.

## Package feeds and runtime secrets

Backend and hosted images retain
`PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple`. Frontend and
Playwright dependencies retain the approved Microsoft npm feed.

The hosted agent receives the runtime database value only through the
deterministic project `CustomKeys` connection placeholder. Resolved database
URLs, PostgreSQL credentials, Azure tokens, and connection strings must not
appear in source, metadata, command output, or evidence.
