# Implementation Phases

## Phase 0 (historical provenance only): MAF underwriting prototype

- Established the original underwriting operator contract: happy path, retry, crash, resume, fan-in, checkpoints, idempotency evidence, AG-UI, and selected-run assistance.
- Proved the underwriting domain flow and public-lane topology that the LangGraph migration must preserve.

This phase is lineage only; it is not the approved runtime end state.

## Phase 1 (completed in this change): UI, documentation, and skills migration

- Reframed lane documentation around one shared LangGraph underwriting graph.
- Replaced lane-owned MAF workflow skills with LangGraph, Foundry Responses 2.0, native PostgreSQL checkpointing, and Application Insights guidance.
- Updated the frontend copy, rubric wording, and operator docs to preserve the same product contract while aligning terminology with LangGraph.
- Replaced the delivery ledger with a fresh LangGraph migration ledger that does not reuse historical release IDs or success claims.

## Phase 2 (completed): Runtime migration

- Landed the shared `backend/app/langgraph/*` runtime namespace and graph assembly.
- Wired native PostgreSQL checkpoint persistence as the authoritative workflow-state store.
- Preserved stable run, history, AG-UI, CopilotKit, retry, crash, and resume contracts.
- Preserved safe selected-run privacy and same-origin proxy behavior.

## Phase 3 (completed): Hosted validation and evidence regeneration

- Deployed Foundry hosted agent version 6 from a source-bound immutable image digest.
- Passed hosted smoke, happy/retry/`medical_check` crash-resume E2E, and deployed Playwright.
- Passed Foundry trace evaluation, Application Insights correlation, topology verification, and secret-free evidence aggregation.
- Accepted release: `langgraph-underwriting-20260817T144804Z-final`, sourced
  from commit `ee5f1dbf78be0d9428de1971f5b37050db604836`.

## Next-phase candidates

- Tighten typed AG-UI event payload contracts shared across backend and frontend.
- Add richer run comparison or filtering views in the operations console.
- Expand automation around release-evidence capture without weakening the same-origin or privacy boundary.
