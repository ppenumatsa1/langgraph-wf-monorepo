# Scripts

- `local/`: PostgreSQL-backed local parity helpers.
- `manual/`: deterministic order/HITL matrix.
- `playwright/`: browser/domain E2E.
- `azure/`: exact-target preflight, guarded bootstrap, PostgreSQL admin setup,
  immutable image build/deploy, verification, evaluation, telemetry, evidence.
- `skills/`: skill and operating-model validation.

Azure scripts never source deployment profiles; profiles are parsed as data.
Routine `scripts/azure/release.sh` is app-only.
