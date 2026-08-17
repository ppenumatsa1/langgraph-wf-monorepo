---
name: underwriting-evaluation
description: Run local underwriting validation plus hosted report-only evaluation evidence for workflow, retry, resume, privacy, and telemetry changes.
---

# Underwriting Evaluation Skill

Use this skill for workflow, prompt, telemetry, AG-UI, CopilotKit, or hosted-runtime changes that need quality evidence.

## Local sources of truth

- Canonical dataset: `backend/.foundry/datasets/underwriting-smoke.jsonl`
- Declarative config: `backend/eval.yaml`
- Hosted report runner: `backend/evals/foundry_trace_eval.py`
- Evidence inputs and outputs:
  - `backend/.foundry/results/hosted-smoke-evidence.json`
  - `backend/.foundry/results/foundry-trace-eval.json`

## Execution model

1. Run local behavior gates first (blocking):

```bash
make test
make quality
make test-e2e
```

2. Run hosted report-only validation when runtime, prompts, or telemetry-facing behavior changed:

```bash
make foundry-smoke
make foundry-eval
```

## Guardrails

- Keep one source-controlled underwriting smoke dataset under `backend/.foundry/datasets/`.
- Treat hosted Foundry evaluation results as report-only unless repository policy intentionally changes.
- Defer remote evaluator provisioning, endpoint selection, trace analysis, and Foundry troubleshooting mechanics to the `microsoft-foundry` skill.
- Add or update cases when happy, retry, crash/resume, four-check fan-in, selected-run privacy, idempotency, or observability behavior changes.
- Keep evaluation outputs free of applicant content, checkpoint payloads, and secrets.
- The `foundry.responses.invoke` trace evidence must contain only redacted release summaries rather than application payloads or rationale content.

## Required evidence

- `backend/.foundry/results/hosted-smoke-evidence.json`
- `backend/.foundry/results/foundry-trace-eval.json`

