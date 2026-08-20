---
name: postgres-psycopg-py
description: Maintain PostgreSQL persistence, the native LangGraph Postgres checkpointer, and Psycopg v3 pool usage in this Python workflow service. Use for DATABASE_URL, connection pools, checkpoint durability, repository adapters, Azure Database for PostgreSQL Flexible Server, transactions, and idempotent database writes.
---

# PostgreSQL and Psycopg for Order Resolution

Use this skill for the repository's durable PostgreSQL path. PostgreSQL stores workflow runs,
events, conversation messages, checkpoints, approvals, sessions, and evaluation records.

## Ownership and configuration

- `backend/app/core/database.py` owns the shared database configuration and pool lifecycle.
- `backend/app/infrastructure/persistence/*` owns storage adapters and checkpointer wiring. Keep route, service, LangGraph runtime, and persistence responsibilities separated.
- The private Foundry/Container Apps path uses `STORE_PROVIDER=postgres`;
  Azure Database for PostgreSQL is selected through `DATABASE_URL` and is
  reachable only through the private network.
- PostgreSQL is limited to workflow audit/control-plane persistence; do not add vector, document, or retrieval stores to it.

## Safe persistence patterns

- Reuse the shared `psycopg_pool.ConnectionPool` or async equivalent; never create a pool per request, graph node, or repository method.
- Keep the async pool lifecycle singleton-owned by application startup/shutdown or lifespan wiring. Repositories and LangGraph helpers may borrow connections, but they must not create, replace, or close the global pool opportunistically.
- Use parameterized SQL (`cursor.execute(sql, parameters)`) for every dynamic value. Do not interpolate values into SQL strings.
- Keep LangGraph checkpoint DDL administrator-owned. Hosted runtime code must not call schema-creating setup paths when `DB_SCHEMA_MANAGED_EXTERNALLY=true`.
- Use the native LangGraph Postgres checkpointer for durable threads and resume. Preserve stable `thread_id`, `checkpoint_id`, and checkpoint namespace handling needed for audit and recovery.
- Treat checkpoint-backed graph state as authoritative. Approval tables, workflow history rows, and operator-facing summaries must remain idempotent projections rather than a second source of truth for business decisions.
- On resume, reconcile the pending checkpoint, the idempotent approval projection, and the requested action before updating business state or emitting terminal events.
- Enforce one pending interrupt per thread in durable storage. Do not allow concurrent inserts or projections to create two active approval waits for the same thread.
- Give every side-effecting write an idempotency key and preserve existing retry behavior. Do not blindly retry writes after an uncertain connection or transaction outcome.
- Keep checkpoint PII retention minimal and intentional: store only what is required for resume/audit, avoid copying checkpoint payloads into projection tables, and keep raw checkpoint content out of logs or broad analytics stores.
- Surface database failures through the application's established error and telemetry paths; do not hide them with broad exception handling or success-shaped fallback values.
- Use explicit transaction boundaries when an operation must commit multiple changes atomically. Do not change the configured autocommit behavior without reviewing all affected repository methods.

## Azure Database for PostgreSQL

- Prefer Microsoft Entra authentication and managed identity when the Azure deployment's database and RBAC configuration support it. Require TLS for hosted connections.
- Keep PostgreSQL in the private-endpoint subnet (`10.74.4.0/24`) with
  private DNS resolution from the internal wrapper and private runner. Do not
  make the database public to simplify deployment or diagnostics.
- Keep credentials and connection strings in environment/secret configuration, never in source code or logs.
- Preserve the existing Azure deployment boundary: infrastructure does not
  silently provision or rebuild the PostgreSQL server or workflow database;
  application configuration supplies the TLS `DATABASE_URL` as a Container
  Apps secret and backend persistence code remains provider-neutral.
- Validate private DNS, endpoint readiness, managed identity/RBAC, and TLS
  connectivity before a hosted smoke test. A failed preflight must fail
  closed rather than falling back to a public hostname or local store.

## Dynamic guidance

Use first-party documentation for service configuration that changes over time:

| Need | Lookup |
|---|---|
| Python connection and Entra authentication | `microsoft_docs_search(query="Azure Database for PostgreSQL Flexible Server Python psycopg Microsoft Entra authentication")` |
| Networking and TLS | `microsoft_docs_search(query="Azure Database for PostgreSQL Flexible Server networking TLS")` |
| Azure PostgreSQL limits and maintenance | `microsoft_docs_search(query="Azure Database for PostgreSQL Flexible Server limits maintenance")` |
