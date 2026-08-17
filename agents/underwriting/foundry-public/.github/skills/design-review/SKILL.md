---
name: design-review
description: Review underwriting changes conservatively and run the applicable local and hosted evidence gates.
---

# Design Review Skill

Use this skill for final review before completion or release handoff.

## Review guardrails

- Review only files touched by the current change.
- Reject broad refactors unless the task explicitly requires them.
- Preserve one LangGraph underwriting workflow path across local, public-wrapper, and hosted execution surfaces.
- Preserve deterministic fan-out/fan-in, checkpoint resume, retry, idempotency, same-origin proxy, and selected-run privacy behavior unless the task explicitly changes them.
- Keep AG-UI additive and CopilotKit allowlisted.

## Required execution

Run the smallest existing applicable gates:

```bash
make test
make quality
```

Add operator-surface validation when applicable:

```bash
make test-e2e
```

Add hosted evidence when public-lane or telemetry surfaces changed:

```bash
make foundry-smoke
make foundry-eval
```

## What to inspect

1. Canonical module ownership and no-shim boundaries.
2. Fan-out/fan-in and deterministic decision correctness.
3. Checkpoint, crash, resume, and idempotency evidence.
4. AG-UI, CopilotKit, run-history, and selected-run privacy contract stability.
5. PostgreSQL boundary separation between checkpointer state and projections.
6. Hosted trace and evaluation evidence for public release surfaces.

## Pass/fail behavior

- Pass when applicable gates succeed and the change preserves repository contracts.
- Fail when broad refactors, boundary violations, missing coverage, or missing release evidence remain.

