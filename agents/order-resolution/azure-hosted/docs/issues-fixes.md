# Issues Ledger

| Item | Status | Resolution / blocker |
| --- | --- | --- |
| Foundry hosted application path | Fixed | Removed; Foundry is inference/evaluation only. |
| Backend exposure | Fixed | Container App ingress is internal. |
| SSE proxy buffering | Fixed | Nginx disables buffering/cache/compression and uses long timeouts. |
| Destructive routine deployment | Fixed | `azure-release` is app-only; bootstrap is separately guarded. |
| PostgreSQL DDL ownership | Fixed | Entra administrator runs schema/checkpointer setup; runtime role has no DDL. |
| PostgreSQL authentication mismatch | Fixed | Flexible Server enables Entra and password auth; bootstrap password is local-AZD-only and runtime uses a separate restricted role. |
| Cross-replica HITL resume race | Mitigated | Atomic PostgreSQL claim plus backend `maxReplicas=1`; production scale-out waits for distributed admission locking. |
| Concurrent release evidence writes | Fixed | Advisory file locking, unique same-directory temp files, fsync, and atomic replace. |
| Unexpected hosted topology | Fixed | Verification requires exactly two named Container Apps and zero Foundry agent applications/versions. |
| PostgreSQL public firewall | POC-only | Azure-services rule retained with TLS, restricted runtime role, exact verification, and a production stop condition for private networking or controlled egress. |
| Immutable releases | Fixed | ACR digests are captured and exact digests are deployed/verified. |
| Azure execution | Not run | Requires authentication, target permissions, PostgreSQL admin values, and model quota. |
