---
name: typescript-update
description: Update underwriting frontend TypeScript code or dependencies while preserving strictness, runtime contracts, and operator behavior.
---

# TypeScript Update Skill

Use this skill when changing existing TypeScript code, React components, or frontend TypeScript dependencies.

## Guardrails

- Keep the build clean at every meaningful step.
- Do not reduce strictness, add `// @ts-ignore`, or widen types to `any` just to silence errors.
- Keep `frontend/src/api.ts` aligned with backend response contracts.
- Keep `frontend/src/copilot.ts` aligned with the safe selected-run assistant contract.
- Update Playwright and docs when user-visible behavior changes.

## Required verification

1. `cd frontend && npm run build`
2. `cd frontend && npm run lint`
3. `make test-e2e` for user-visible, API, AG-UI, or CopilotKit changes
