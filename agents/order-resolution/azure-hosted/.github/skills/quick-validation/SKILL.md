---
name: quick-validation
description: Run fast validation for low-risk app-only redeployments.
---

# Quick Validation Skill

Use this skill for routine redeployments where infra did not change and API/HITL/event contracts are unchanged.

## Goal

Provide a fast confidence gate so small app updates can deploy quickly without running the full local validation stack each time.

## Routing

Use `scripts/skills/deployment-mode-router.sh` first. If it reports:

- `validation_mode=quick`: use this skill.
- `validation_mode=full`: run `local-validation` instead.

## Required checks

Run:

```bash
make validate-quick
```

`validate-quick` runs Playwright and, when `API_URL` is set, hosted smoke checks.

If a hosted frontend URL is available, run Playwright against it:

```bash
PLAYWRIGHT_BASE_URL="$WEB_URL" make test-e2e
```

Treat visible Workflow History parsing errors (`Unexpected token`, `not valid JSON`, `<!doctype`) as a hard fail.

## Do not use quick validation when

- IaC/runtime surfaces changed (`infra/**`, `.azure/**`, container runtime/proxy files, smoke scripts).
- HITL logic or workflow event contracts changed.
- API schemas/routers changed in ways that could affect clients.

In those cases, run full validation.
