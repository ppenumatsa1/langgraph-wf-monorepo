# Underwriting Foundry-public deployment profiles

This lane owns an independent, non-secret deployment profile contract. A
profile identifies only the canonical subscription, resource group, location,
AZD environment, name prefix, and `foundry-public` lane.

Release-authority status: historical `deployment-report/` and singular
`.artifacts/release/` paths are inventory only. Current release execution
writes `.artifacts/releases/<release-id>/release.json`, evidence, and logs.
Release `uw-public-51a8311-20260816140654` live-validated this path.

The canonical profile is `deployment/profiles/foundry-public.env`. Both
checked-in profiles select subscription
`7df95e88-701c-4693-af77-3159f83b558d`, resource group
`rg-maf-underwriting`, and `eastus2`. Apply the reuse profile directly or copy
it to an operator-owned path without adding secrets:

```bash
./deployment/apply-azd-profile.sh /secure/path/underwriting-foundry-public.env
```

The bootstrap profile remains compatible for a new environment but emits an
explicit legacy warning. Apply it, then prepare derived
resource names and the current operator IP:

```bash
./deployment/apply-azd-profile.sh deployment/profiles/foundry-public-bootstrap.env
make foundry-bootstrap-env
```

Bootstrap mode derives application-owned resource names from `NAME_PREFIX` plus
a deterministic hash of the selected subscription and resource group. It
creates the Foundry account/project/model deployment, ACR, monitoring,
Container Apps environment/apps, managed identities, PostgreSQL, and evaluation
storage. The first provision requires `POSTGRES_ADMIN_PASSWORD` in the selected
local AZD environment. After it completes, provision the
least-privilege runtime database credential with
`make foundry-postgres-credentials` before any application deployment. That
command also converges the project-scoped `underwritingruntimesecrets`
`CustomKeys` connection; routine release readiness converges it again
idempotently before hosted deployment.

Reuse mode requires the target AZD environment to already contain the
non-secret identities for the Foundry account/project, ACR, PostgreSQL
server/database, Container Apps, managed identity, Application Insights, and
Log Analytics workspace. It must also retain its existing lane-local secrets,
including the runtime database URL and PostgreSQL credentials.

Profiles never contain secrets, endpoints, generated resource names, operator
IP placeholders, image tags, or resource IDs. Applying a profile does not
authenticate, provision, deploy, or read a secret. Routine
`make foundry-release` is hard-enforced as app-only and rejects
`FOUNDRY_DEPLOY_MODE`. Provisioning and database rebuild/schema operations
remain explicit. Existing environments with a public backend must run the
one-time `make foundry-backend-internalize CONFIRM=INTERNALIZE-<backend>`
migration before routine releases.

See `docs/design/deployment-flow.md` for the canonical 14-stage flow,
command-to-stage mapping, fresh-bootstrap path, routine release path, and
one-time ingress migration sequence.

Release commands require `RELEASE_ID`. The release record is initialized
atomically, evidence is written under `evidence/`, command output is written
under `logs/`, and success fails closed unless every declared gate is current,
secret-free, release-local, and hashed. Its `extensions.release_timing` lane
extension records UTC start/end timestamps and integer milliseconds for
package/context validation, immutable image build, hosted activation, ACA
deployment, smoke, deployed E2E, evaluation, telemetry, deployment
verification, and final evidence. The app-only total runs from package/context
validation through `telemetry_succeeded_at`; concurrent
evaluation, E2E, and telemetry intervals remain overlapping rather than being
summed. Finalization rejects package-to-deployment durations above 900,000 ms
and package-to-telemetry lifecycle durations above 1,800,000 ms.
`migrate_release_history.py` only inventories legacy paths; live copy and
deletion remain disabled.
