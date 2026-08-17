---
name: ag-ui-react-integration-ts
description: Implement and review React TypeScript consumers for AG-UI-compatible workflow streaming, durable run history, CopilotKit context, and resume UX.
---

# AG-UI React Integration (Underwriting)

Use this skill when changing frontend streaming consumption or UI behavior tied to workflow events.

## Official supporting skills

- Use `typescript-setup` for repository TypeScript boundary decisions.
- Use `typescript-update` when upgrading TypeScript or resolving compiler diagnostics.
- Keep AG-UI and CopilotKit runtime behavior guidance in this skill; the TypeScript skills are supporting references.

## Scope

- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/copilot.ts`
- `frontend/src/components/*`
- `frontend/tests/e2e/underwriting.spec.ts`

## Guardrails

- Keep operator state derived from durable APIs plus additive AG-UI stream updates.
- Do not call Foundry, PostgreSQL, or secret-bearing endpoints directly from the browser.
- Keep the CopilotKit runtime pinned to `/api/v1/underwriting/copilotkit` and preserve the strict selected-run allowlist in `frontend/src/copilot.ts`.
- Surface run ids, checkpoint counts, retry visibility, fan-in progress, same-origin recovery behavior, and terminal status clearly.
- Treat malformed or non-JSON history or assistant responses as explicit user-visible errors.

## Required verification

1. `cd frontend && npm run build`
2. `cd frontend && npm run lint`
3. `make test-e2e`
4. Update `docs/design/e2e-rubric.md` and `docs/design/schema-io-telemetry.md` when operator contracts change.

