---
name: typescript-setup
description: Set up or extend underwriting frontend TypeScript surfaces without weakening runtime or contract safety.
---

# TypeScript Setup Skill

Use this skill when adding or restructuring frontend TypeScript files in the underwriting console.

## Scope

- `frontend/src/**/*`
- `frontend/src/api.ts`
- `frontend/src/copilot.ts`
- `frontend/src/components/*`
- frontend TypeScript configuration files

## Guardrails

- Preserve strict TypeScript settings; do not weaken `tsconfig` or introduce `any`/suppression comments to hide contract errors.
- Keep browser integrations limited to the public FastAPI adapter. No direct Foundry, PostgreSQL, or secret-bearing calls from browser code.
- Keep the CopilotKit runtime contract and selected-run allowlist in `frontend/src/copilot.ts`.
- Prefer explicit shared types for run status, checkpoints, events, and outputs over ad hoc object indexing.

## Required verification

1. `cd frontend && npm run build`
2. `cd frontend && npm run lint`
3. `make test-e2e` when UI, API, AG-UI, or CopilotKit behavior changes
