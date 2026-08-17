---
name: order-resolution-evaluation
description: Run deterministic workflow contracts and optional Foundry report-only evaluation for the Azure-hosted backend API.
---

# Order Resolution Evaluation

Blocking local contracts:

```bash
make eval-backend
```

After Azure domain E2E creates three backend thread IDs, the optional report:

```bash
make azure-eval
```

Foundry evaluation is report-only by default. It evaluates traces produced by
the backend API; it does not invoke or deploy an application-host agent.
Preserve exact HITL/event/status checks for low-risk, high-value, and damaged
item cases.
