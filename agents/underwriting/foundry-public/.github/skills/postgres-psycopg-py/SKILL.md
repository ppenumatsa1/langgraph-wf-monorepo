---
name: postgres-psycopg-py
description: Maintain underwriting PostgreSQL persistence with psycopg and SQLAlchemy boundaries for checkpoints, run history, events, and idempotent writes.
---

# PostgreSQL and Psycopg for Underwriting

Use this skill for durable underwriting persistence and database boundary reviews.

## Ownership

- backend/app/infrastructure/db/\* owns engine and table definitions.
- backend/app/infrastructure/checkpointing/\* owns checkpoint persistence.
- backend/app/infrastructure/repositories/\* owns run/event projection persistence.
- backend/app/modules/underwriting/\* owns domain contracts and service behavior.

## Guardrails

- Reuse configured database resources; never create per-request pools/engines.
- Keep all writes idempotent where side effects can be retried.
- Use parameterized SQL and safe SQLAlchemy patterns only.
- Preserve separation between checkpoint storage and projection/read-model tables.
- Do not leak DB errors as success-shaped API responses.

## Required verification

1. Validate `backend/tests/test_run_history.py` for persisted run/event surfaces.
2. Validate `backend/tests/test_state_isolation.py` for cross-run isolation.
3. Validate `backend/tests/test_resume.py` for checkpoint durability.
