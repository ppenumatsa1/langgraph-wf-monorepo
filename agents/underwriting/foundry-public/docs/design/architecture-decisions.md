# Architecture Decisions

## Purpose

This record captures the architecture decisions that define the underwriting Foundry public lane after the LangGraph UI, documentation, and skill migration.

Historical MAF decisions are retained only as provenance so the migration path stays understandable.

## Historical provenance

### ADR-001: Original MAF workflow lineage - superseded

**Historical decision:** Use a Microsoft Agent Framework underwriting workflow to prove checkpointing, fan-out/fan-in, retry, crash, and resume.

**Why it matters now:** It explains the preserved operator contract and existing file lineage, but it is no longer the target runtime authority.

**Status:** Superseded by ADR-003 through ADR-008.

## Current decisions

### ADR-002: Keep the underwriting policy deterministic

**Decision:** Compute the underwriting decision and score breakdown from deterministic policy rules before generating any model rationale.

**Why:** Explanation quality must not alter approval, conditional approval, referral, or decline outcomes.

**Result:** The model enriches the decision with rationale only; it cannot override policy.

### ADR-003: Use one shared LangGraph underwriting graph

**Decision:** Model underwriting as one shared LangGraph `StateGraph` with `init_context`, parallel risk/credit/medical/driving checks, `fan_in_aggregator`, deterministic `final_decision`, and optional rationale generation.

**Why:** One graph provides a single source of workflow sequencing for local validation, hosted execution, retry, crash, and resume behavior.

**Result:** The lane preserves one business workflow path and avoids shadow orchestrators or hosted-only logic.

### ADR-004: Make the native PostgreSQL checkpointer authoritative for resume

**Decision:** Treat the native LangGraph PostgreSQL checkpointer as the authoritative workflow-state store for resume.

**Why:** Crash recovery must rehydrate true graph state rather than reconstructed browser projections.

**Result:** Resume uses checkpointed graph state keyed to the underwriting run identity. Browser `/checkpoints` routes expose safe checkpoint summaries rather than authoritative checkpoint payloads.

### ADR-005: Keep audit projections separate from checkpoint state

**Decision:** Maintain separate PostgreSQL projections for workflow runs, workflow events, checkpoint summaries, underwriting results, idempotency evidence, and release evidence.

**Why:** Operator history, replay, and release evidence need durable read models, but they must not become a second authority for workflow state.

**Result:** The browser and CopilotKit use redacted projections; checkpoint state remains backend only.

### ADR-006: Preserve same-origin public browser topology

**Decision:** Keep the public lane as external frontend -> same-origin `/api` proxy -> internal backend -> Foundry Responses 2.0 -> PostgreSQL.

**Why:** The browser must not receive Foundry or database credentials, and backend-only routes must stay private.

**Result:** `/backend-health` remains the public verification path for the internal hop; direct backend public reachability remains a release blocker.

### ADR-007: Require strict selected-run privacy

**Decision:** CopilotKit and AG-UI remain additive, read-only selected-run surfaces with a strict allowlist.

**Why:** Operators need explanations of execution state without exposing applicant data, raw checkpoint payloads, prompts, model output, or secrets.

**Result:** Only safe run metadata and a categorical final decision may cross the bridge.

### ADR-008: Use Application Insights as the required observability backend

**Decision:** Application Insights is the required workflow, Foundry, model, retry, checkpoint, and resume telemetry sink.

**Why:** Release readiness requires one supported operational backend with correlated request and hosted traces.

**Result:** LangSmith is not required for runtime, evaluation, or release gating.

### ADR-009: Make release claims evidence driven

**Decision:** Treat repository configuration as intent only. Claim hosted readiness only from fresh smoke, Playwright, evaluation, telemetry, and ledger evidence.

**Why:** Underwriting public-lane correctness depends on deployment topology, telemetry, and privacy validation, not documentation alone.

**Result:** Historical release identifiers and success claims are not reused as LangGraph proof.
