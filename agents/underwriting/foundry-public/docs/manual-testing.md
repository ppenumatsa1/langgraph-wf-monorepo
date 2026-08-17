# Manual Testing Guide

## Local full-stack workflow

```bash
make up
```

Open `http://localhost:5173`, submit a scenario, and verify the selected run timeline.

| Scenario | Expected result |
| --- | --- |
| Happy path | `COMPLETED`; final decision visible |
| Retry | retry events appear; run still completes |
| Crash at `medical_check` | `CRASHED`; checkpoint appears and resume completes |

Verify:

- application form accepts underwriting input
- run history refreshes and lets you reselect prior runs
- four-check fan-in shows risk, credit, medical, and driving progress
- `workflow_start`, retry, fan-in, final-decision, and terminal events appear in order
- checkpoint count increases once work becomes durable
- resume completes without duplicate side effects and surfaces any `idempotency_skip` evidence
- selected-run assistant explains only allowlisted run metadata

## Selected-run privacy checks

After selecting an existing workflow run:

1. Open the CopilotKit panel.
2. Ask about status or progress.
3. Confirm the assistant uses only run id, status, safe event metadata, checkpoint summary, and categorical final decision.
4. Confirm it does **not** reveal applicant details, health disclosures, income, credit score, prompts, raw model output, checkpoint payloads, credentials, or secrets.

## Public hosted workflow and browser

For hosted validation:

```bash
make foundry-release
```

Verify:

- happy, retry, and `medical_check` crash or resume flows
- same-origin frontend `/api` calls return JSON or SSE rather than HTML fallback content
- `/backend-health` succeeds through the frontend origin
- the backend Container App remains internal only
- Application Insights and report-only Foundry evaluation use fresh release-window evidence only

If an API route returns HTML, unexpected text, or the wrong content type, stop and investigate the frontend proxy or wrapper route mapping before treating the result as a workflow regression.
