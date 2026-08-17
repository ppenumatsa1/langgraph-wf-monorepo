---
name: quick-validation
description: Run the smallest existing validation set for low-risk underwriting app-only changes.
---

# Quick Validation Skill

Use this skill for low-risk changes where infra, release scripts, workflow semantics, AG-UI/CopilotKit contracts, checkpointing, and PostgreSQL behavior are unchanged.

## Goal

Provide a fast confidence gate for low-risk app-only work without pretending to replace full validation.

## Allowed change shapes

- frontend copy/layout/state changes with stable API and stream contracts
- backend refactors that do not touch workflow, persistence, telemetry, or public contracts
- instruction or skill updates that do not change runnable behavior

## Required checks

Choose the smallest existing command set that covers the changed surface:

```bash
make test-backend
make test-frontend
make test
```

Use only the commands that apply to the files changed.

If a deployed frontend already exists and you need hosted parity smoke, run:

```bash
cd frontend && PLAYWRIGHT_BASE_URL="$WEB_URL" npm run test:e2e
```

## Do not use quick validation when

- files under `backend/app/maf/**`, `backend/foundry/**`, `backend/app/infrastructure/**`, `infra/**`, `scripts/foundry/**`, `backend/eval.yaml`, or `backend/.foundry/**` changed
- fan-out/fan-in, retry, crash/resume, checkpoint, idempotency, PostgreSQL, AG-UI, CopilotKit, or telemetry contracts changed
- public deployment or hosted release evidence is in scope

In those cases, use `local-validation` and, when hosted surfaces are involved, `release-readiness`.
