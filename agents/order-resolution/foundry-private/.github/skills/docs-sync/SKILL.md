---
name: docs-sync
description: Keep private-lane documentation synchronized with focused code and IaC changes while preserving contracts.
---

# Docs Sync Skill

Use this skill when a change touches code, infrastructure as code, scripts, examples, or behavior that may affect repository documentation.

## Guardrails

- Review only the code, IaC, scripts, examples, and docs affected by the current change.
- Keep changes surgical and simplicity-first; do not rewrite unaffected documentation.
- Preserve documented API, event, HITL, validation, and deployment contracts unless the task explicitly changes them.
- Keep the private topology synchronized across README, agents.md, design docs,
  Mermaid source, manual testing, and the issues ledger: external frontend,
  internal wrapper, private Foundry, private PostgreSQL, private ACR, private
  runner, and Application Insights.
- Use the fixed BYO VNet reservations (`10.74.0.0/16`, Foundry `10.74.0.0/24`,
  Container Apps `10.74.2.0/23`, private endpoints `10.74.4.0/24`, runner
  `10.74.5.0/27`) consistently. Do not invent public endpoints or historical
  resource evidence.
- Preserve business HITL (`interrupt()` / `Command(resume=...)`) separately
  from noninteractive deployment safety gates.
- Update only docs whose instructions, examples, diagrams, or behavior descriptions would become stale.
- Do not introduce new validation tooling or broad documentation structure changes.

## Required execution

1. Identify changed code/IaC/scripts/examples and map them to affected docs.
2. Update the smallest relevant documentation sections.
3. Preserve stable contracts called out in repository guidance and update required contract docs when behavior intentionally changes.
4. Run existing relevant checks only when documentation affects runnable scripts, commands, examples, or generated artifacts.
5. Check local Markdown links and Mermaid source consistency. Skill/frontmatter
   validation is run by the existing repository validator; do not edit that
   validator to make a stale document pass.

## Reporting

- List docs updated and the code/IaC change each update follows.
- If no docs needed changes, state why.
- Report any checks run, skipped checks, and blockers.
