# Manual Testing Guide

## Local full-stack workflow

```bash
make up
```

Open `http://localhost:5173`, submit a case, and verify the native SSE
timeline.

| Scenario | Prompt | Expected result |
| --- | --- | --- |
| Low risk | `Order ORD-1001 arrived late by 1 day.` | `completed`; no `hitl.request` |
| High value | `Order ORD-1009 is delayed by 5 days.` | `waiting_approval`, then `completed` after approval |
| Damaged reject | `Order ORD-1001 arrived damaged and broken.` | `waiting_approval`, then `escalated` after rejection |

Verify:

- `workflow.stage` appears for triage, policy, and resolution
- `tool.call` appears without leaking backend-only retrieval content
- `checkpoint.created` and `hitl.request` appear only when expected
- exactly one terminal `workflow.output` is emitted
- while approval is pending, a second normal turn on the same thread is
  rejected or explicitly deferred
- only one pending interrupt exists for the thread

## Selected-thread projections

After selecting an existing workflow thread:

1. Connect `GET /api/chat/stream/{thread_id}/ag-ui`.
2. Load `POST /api/copilotkit`.
3. Confirm both surfaces expose only safe lifecycle, approval, and generic
   terminal state.
4. Confirm neither surface can start a run or submit a HITL decision.
5. Confirm neither surface reveals order details, raw policy, MCP/RAG content,
   prompts, raw model output, checkpoint state, credentials, or secrets.

## Private hosted workflow and browser

For hosted validation:

```bash
make foundry-private-release
```

Run hosted checks from the approved private runner only. Before opening the
external frontend, verify the runner can resolve the private Foundry,
PostgreSQL, and ACR names and that managed identity/RBAC and endpoint approval
are ready. The frontend URL is the only external URL used by the browser.

Verify:

- low-risk `ORD-1001`
- high-risk `ORD-1009` approval and resume
- damaged-item HITL behavior
- same-origin frontend `/api` calls return JSON or SSE rather than HTML fallbacks
- telemetry and evaluation use fresh release-window evidence only
- Application Insights contains correlated workflow, Foundry, and HITL spans
- repeated fresh conversations do not produce `too many connections`, Foundry
  424/500 responses, or a retained hosted-session connection floor
- the wrapper, Foundry, PostgreSQL, ACR, and runner are not browser reachable
- no private dependency check falls back to a public endpoint

If an API route returns HTML, unexpected text, or the wrong content type, stop
and investigate the frontend proxy or wrapper route mapping before treating the
result as a graph regression.

The backend Container App remains internal only. Do not point a browser
directly at Foundry, PostgreSQL, ACR, the runner, or the backend FQDN.

Hosted test success is not implied by this checklist. Record only evidence
from the same private release window, and report missing runner, DNS, endpoint,
identity, or telemetry prerequisites as blockers.
