---
name: docs-sync
description: Keep underwriting instruction files and design docs synchronized with code, release, and contract changes.
---

# Docs Sync Skill

Use this skill when a change touches code, infrastructure, release scripts, workflow behavior, AG-UI, CopilotKit, or operator-facing contracts.

## Guardrails

- Review only the code and docs affected by the current change.
- Keep documentation edits surgical; do not rewrite unaffected sections.
- Preserve documented contracts unless the task explicitly changes them.
- Update instruction files when repository governance, skill routing, or release gates change.

## Required docs to consider

- `.github/copilot-instructions.md`
- `agents.md`
- `docs/design/architecture.md`
- `docs/design/schema-io-telemetry.md`
- `docs/design/userflow.md`
- `docs/design/e2e-rubric.md`

## Required execution

1. Map touched code, infra, scripts, or skills to the smallest affected documentation set.
2. Update boundaries, commands, and behavioral contracts only where they would otherwise become stale.
3. Keep AG-UI, CopilotKit, checkpoint/resume, telemetry, and hosted release terminology aligned across the instruction files and design docs.
4. Run existing checks only when documentation changes affect runnable commands or examples.

## Reporting

- List docs updated and the change each update follows.
- If no docs changed, state why.
- Report checks run, skipped checks, and blockers.
