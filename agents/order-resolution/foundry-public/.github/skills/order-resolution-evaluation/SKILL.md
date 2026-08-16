---
name: order-resolution-evaluation
description: Run deterministic and hosted report-only evaluations for the Order Resolution workflow, using repository datasets/contracts locally and delegating remote Foundry evaluation mechanics to microsoft-foundry.
---

# Order Resolution Evaluation Skill

Use this skill for workflow, HITL, prompt, tool-routing, durable-event, or hosted-runtime changes that need quality evidence.

## Local sources of truth

- Canonical dataset: `backend/.foundry/datasets/order-resolution-hosted-cases.jsonl`
- Deterministic contract runner: `backend/evals/eval_runner.py`
- Hosted report runner: `backend/evals/foundry_eval_runner.py`
- Declarative config: `backend/eval.yaml`

## Execution model

1. Run deterministic contract checks first (blocking):

```bash
make eval-backend
```

2. Run hosted report-only evaluation when runtime, prompts, or telemetry-facing behavior changed:

```bash
make eval-foundry
```

3. Optional combined command:

```bash
make eval-all
```

## Guardrails

- Deterministic contract checks stay blocking and exact for HITL state/event/status contracts.
- Keep one source-controlled golden dataset under `backend/.foundry/datasets/`.
- Treat hosted Foundry evaluation results as report-only unless `FOUNDRY_EVAL_ENFORCE_PASS=true` is intentionally set.
- Defer remote evaluator provisioning, endpoint selection, trace analysis, and Foundry troubleshooting mechanics to the `microsoft-foundry` skill.
- Add or update cases when low-risk, approval/resume, damaged-item, or other operator-critical flows change.
- Add or update cases when admission control, single-pending-interrupt-per-thread behavior, replay-safe event emission, graph-state reconciliation, or approval-projection idempotency changes.

## Required evidence

- `backend/.foundry/results/report.json`
- `backend/.foundry/results/contract_capture.json`
- `backend/.foundry/results/foundry-report.json`
