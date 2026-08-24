# HITL Approval Trigger Conditions

This document defines the exact conditions that trigger human approval
(`hitl.request`) in the approved LangGraph workflow contract.

## Shared execution contract

- Local FastAPI runs the shared LangGraph `StateGraph`.
- Private Foundry-hosted execution runs the same graph through Responses 2.0.
- The external frontend keeps the same stable API and SSE contract through the
  internal wrapper.

The trigger behavior below is the business contract across local and private
hosted surfaces. Network or deployment safety gates do not alter it.

Only one unresolved interrupt may exist per thread. While approval is pending,
new normal turns on that thread are rejected or explicitly deferred.

## Rule summary

HITL is required if any of these are true:

1. Amount or risk is `>= 100`
2. Issue type is `damaged_item`
3. Policy contains `manual_review`

If none are true, the workflow completes without human approval.

## LangGraph runtime rule

The approved rule remains:

```text
requires_hitl = order.total_amount >= 100
  or issue_type == "damaged_item"
  or "manual_review" in policy
```

Implementation details:

- Triage identifies the issue type from the message.
- Policy retrieval derives the order ID and applicable policy.
- Resolution decides the action.
- If `requires_hitl` is true, the resolution node pauses with `interrupt()`
  only after the graph state and audit projection context are durable.
- `checkpoint.created` and `hitl.request` are emitted during approval
  preparation before the interrupt is returned; they are not replayed from the
  resumed interrupt node.
- Approval or rejection resumes the same thread with `Command(resume=...)`.

## Value derivation

- Issue classification:
  - contains `damage` or `broken` -> `damaged_item`
  - contains `wrong` -> `wrong_item`
  - otherwise -> `late_delivery`
- Order mapping in the baseline scenarios:
  - message containing `1009` -> `ORD-1009` with amount `185.0`
  - otherwise -> `ORD-1001` with amount `79.0`
- Policy mapping:
  - `late_delivery` -> `refund_allowed_if_delay_exceeds_3_days`
  - `damaged_item` -> `replacement_or_full_refund_with_photo_proof`
  - `wrong_item` -> `free_replacement_and_return_label`
  - unknown issue types -> `manual_review_required`

## Test matrix

1. High amount approval trigger
   - Input: `Order ORD-1009 is delayed by 5 days. I need compensation.`
   - Expected: `hitl.request`
2. Damaged item approval trigger
   - Input: `Order ORD-1001 arrived damaged and broken.`
   - Expected: `hitl.request`
3. Low-risk no-approval path
   - Input: `Order ORD-1001 arrived late by 1 day. What can you do?`
   - Expected: no `hitl.request`; terminal `workflow.output.status=completed`
4. Wrong item no-approval path
   - Input: `Order ORD-1001 has the wrong item in the box.`
   - Expected: no `hitl.request`; terminal `workflow.output.status=completed`

## What to assert

For HITL scenarios:

- `checkpoint.created` exists with `reason=approval_required`
- `hitl.request` contains the checkpoint identifier and action summary
- a second normal turn submitted before approval is rejected or deferred, and
  no second pending interrupt is created
- approval produces one `hitl.response` and one terminal
  `workflow.output.status=completed`
- rejection produces one `hitl.response` and one terminal
  `workflow.output.status=escalated`
- duplicate decisions for the same checkpoint remain idempotent

For non-HITL scenarios:

- no `hitl.request`
- one terminal `workflow.output.status=completed`

## Privacy and projection rule

The native timeline remains the operator contract. AG-UI and CopilotKit may
show pending or resolved approval state, but they must not expose raw order,
policy, MCP/RAG, prompt, reviewer-comment, or checkpoint-state payloads.

Hosted approval requests travel through the internal wrapper and private
PostgreSQL projections. The browser never calls private Foundry or PostgreSQL
directly. A waiting approval may outlive active hosted compute; zero-idle
database pools release connections without changing the durable checkpoint or
the requirement to resume only the matching pending checkpoint.
