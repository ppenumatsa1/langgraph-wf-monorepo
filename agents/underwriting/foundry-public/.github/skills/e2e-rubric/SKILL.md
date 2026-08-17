---
name: e2e-rubric
description: Preserve the underwriting operator rubric across happy path, retry, crash/resume, fan-in, checkpoints, idempotency, observability, selected-run privacy, and hosted release smoke.
---

# E2E Rubric Skill

Use this skill when editing UI behavior, API responses, workflow events, AG-UI, CopilotKit, or hosted release criteria.

## Rubric sources

- `frontend/tests/e2e/rubric.ts`
- `frontend/tests/e2e/underwriting.spec.ts`
- `docs/design/e2e-rubric.md`

## Automated criteria

The Playwright rubric must continue to validate:

1. happy path decision
2. retry behavior
3. crash status and resumable run id
4. resume completion
5. fan-in shared state
6. checkpoint visibility
7. idempotency skip visibility
8. observability fields in event output

## Release-only criteria

9. public hosted smoke confirms the public request correlates with hosted workflow/model traces and safe Foundry evaluation evidence.
10. same-origin `/api` and `/backend-health` behavior proves the backend remains internal.
11. selected-run assistant behavior remains on the safe allowlist.

## Guardrails

- Do not weaken rubric coverage without an explicit task.
- Keep rubric terminology aligned across Playwright, design docs, and instruction files.
- If a criterion changes intentionally, update the test, the rubric source, and the relevant docs together.

## Required verification

```bash
make test-e2e
```

For hosted/public-lane changes, also run:

```bash
make foundry-smoke
make foundry-eval
```

