---
name: design-review
description: Review code changes conservatively and run deterministic backend, eval, e2e, and rubric checks.
---

# Design Review Skill

Use this skill in `/fleet` mode for change reviews that must avoid over-optimization or broad refactors.

## Guardrails

- Review only files touched by the change.
- Reject broad refactors unless explicitly required by the task.
- Keep API/event contracts stable unless the task asks for contract changes.
- Do not alter HITL decision logic unless explicitly requested.

## Required execution

Run the repository entry point:

```bash
./scripts/skills/design-review-skill.sh
```

## What this runs

1. Scope guard against broad refactors.
2. Local backend checks: `make format`, `make lint`, `make test-backend`.
3. Backend eval harness: `make eval-backend`.
4. UI E2E checks: `make test-e2e`.
5. Rubric validation against:
   - `scripts/rubric/e2e-rubric.md`
   - `scripts/playwright/tests/workflow.e2e.spec.ts`

The Playwright suite must include a Workflow History API health assertion that fails on visible `Unexpected token`, `not valid JSON`, or `<!doctype` errors, because those indicate the frontend received HTML instead of API JSON.

## Pass/fail behavior

- Exit code `0`: all checks passed.
- Non-zero exit: review/validation failed. Output includes failing step and rerun command.
