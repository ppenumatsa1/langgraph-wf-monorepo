# PRD - Underwriting LangGraph Workflow

## Objective

Build a demo-ready underwriting workflow on **one shared LangGraph `StateGraph`** while preserving the existing underwriting operator and browser contract.

## Core features

- Application-form intake for insurance underwriting scenarios
- Parallel risk, credit, medical, and driving checks with visible fan-in
- Deterministic underwriting decision before any rationale generation
- Crash and resume from durable PostgreSQL checkpoint state
- Separate durable history for runs, events, checkpoints, results, and idempotency evidence
- Stable FastAPI, AG-UI, and CopilotKit contracts for the browser and Playwright suites
- Same-origin public wrapper: the browser calls `/api`; only the internal backend calls Foundry Responses 2.0
- Application Insights-only observability and report-only hosted evaluation evidence
- Strict selected-run assistant allowlist

## Non-goals (v1)

- Browser-direct access to Foundry or PostgreSQL
- Production auth redesign
- Parallel workflow engines or compatibility shims
- LangSmith adoption as a release prerequisite
- Reusing historical MAF deployment identifiers as LangGraph proof

## Acceptance criteria

1. One underwriting request drives all business stages through one LangGraph graph.
2. The browser continues to support the application form, run history, retry, crash, resume, checkpoint timeline, and four-check fan-in display.
3. Resume restores checkpointed state and avoids duplicate side effects.
4. AG-UI remains additive to durable read models.
5. CopilotKit remains selected-run, read only, and allowlisted.
6. Public hosting keeps the browser on a same-origin API and health contract while the internal backend delegates to Foundry Responses 2.0.
7. Telemetry exports to Application Insights with no LangSmith requirement.
8. Release validation enforces least-privilege PostgreSQL access, immutable packaging, safe evaluation evidence, and same-origin proxy correctness.

## Delivery contract

Implementation authority and release evidence expectations are defined in
[engineering-operating-model.md](engineering-operating-model.md). Historical
MAF materials are migration provenance only.
