# Architecture

## Runtime

The browser loads React from an external Nginx Container App. Nginx proxies
`/api` to the internal FastAPI Container App with buffering disabled and long
SSE timeouts. FastAPI executes the same compiled LangGraph `StateGraph` used in
local tests. Foundry supplies chat/embedding model inference only.

```text
Browser -> public frontend ACA -> /api proxy -> internal backend ACA
        -> LangGraph -> PostgreSQL
        -> Foundry model deployment
```

No Foundry application-hosting resource participates in the request path.

## State and security

`AsyncPostgresSaver` owns graph checkpoints. Audit tables project workflow
runs, replayable events, approvals, sessions, evaluations, and release
evidence. Administrator scripts own DDL and grant a dedicated runtime role only
the required table DML, sequence usage, schema usage, and database connect.
The server enables Entra and password authentication: Entra owns DDL, while
the application uses a separately rotated least-privilege password role. The
server-creation password is generated into local AZD environment state and is
never used by the application.

User-assigned identities pull backend/frontend images from ACR. The backend
identity also has model-inference access on the Foundry account. The backend
ingress is internal; only the frontend is externally reachable.

This public POC does not claim a private database path. PostgreSQL currently
uses the Azure-services `0.0.0.0` firewall rule because the Container Apps
environment has no deterministic static egress. TLS is mandatory, the runtime
role is restricted, and release verification checks the exact server, dual
authentication, firewall rule, and TLS parameter. **Production stop condition:**
do not promote this topology or increase backend replicas until PostgreSQL uses
private networking or deterministic controlled egress and distributed HITL
admission locking is implemented.

## Observability

Application Insights receives FastAPI, LangGraph, model, tool, checkpoint, and
HITL correlation. Content recording is disabled by default. Health and
long-lived SSE requests remain filtered so workflow signal stays visible.
