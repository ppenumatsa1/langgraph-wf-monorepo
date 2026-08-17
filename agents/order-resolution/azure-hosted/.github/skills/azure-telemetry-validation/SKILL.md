---
name: azure-telemetry-validation
description: Correlate Azure-hosted backend workflow, model, checkpoint, and HITL telemetry in Application Insights.
---

# Azure Telemetry Validation

Run domain E2E first, then:

```bash
make azure-telemetry
```

Require all three current release thread IDs to appear after the E2E timestamp,
with workflow/model/tool/HITL signal and no correlated exceptions. Keep content
recording disabled and write only secret-free counts, IDs, target names, and
timestamps to release evidence.
