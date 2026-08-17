---
name: order-resolution-frontend-ts
description: Create or update repository-specific frontend TypeScript and React surfaces without weakening strictness, durable workflow contracts, privacy boundaries, or selected-thread assistant safety.
---

# Order Resolution Frontend TypeScript

Use this skill when adding or modifying frontend TypeScript, React components, API clients, E2E selectors, or frontend build configuration.

## Scope

- `frontend/src/**/*`
- `frontend/tsconfig*.json`
- `frontend/eslint.config.js`
- `frontend/tests/e2e/*`

## Invariants

- Preserve strict TypeScript settings. Do not introduce `any`, unsafe casts, compiler suppression comments, or weaker `tsconfig` settings to hide contract errors.
- Prefer explicit shared types for threads, workflow status, events, checkpoints, approvals, and outputs over ad hoc object indexing.
- Keep browser calls same-origin through the frontend proxy. No frontend type or client may create direct Foundry, PostgreSQL, MCP/RAG, or secret-bearing access.
- Preserve native SSE as the stable operator contract. AG-UI and CopilotKit remain optional additive selected-thread projections of durable workflow state.
- Preserve the safe selected-thread allowlist in `frontend/src/copilot.ts`. CopilotKit is the chosen runtime integration; the GitHub Copilot SDK is not an application dependency.
- Do not expose order, policy, MCP/RAG, checkpoint, prompt, model, credential, or secret data through frontend types, logs, errors, or assistant context.

## Required verification

1. `cd frontend && npm run build`
2. `cd frontend && npm run lint`
3. `make test-e2e` when UI, API, AG-UI, CopilotKit, or selected-thread behavior changes
