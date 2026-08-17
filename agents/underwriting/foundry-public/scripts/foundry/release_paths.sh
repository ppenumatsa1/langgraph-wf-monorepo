#!/usr/bin/env bash

release_paths_configure() {
  local root_dir="$1"
  [[ -n "${RELEASE_ID:-}" ]] || {
    echo "RELEASE_ID is required for Foundry release execution." >&2
    return 2
  }
  [[ "$RELEASE_ID" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$ ]] || {
    echo "Invalid RELEASE_ID: $RELEASE_ID" >&2
    return 2
  }
  export FOUNDRY_RELEASE_DIR="$root_dir/.artifacts/releases/$RELEASE_ID"
  export FOUNDRY_RELEASE_EVIDENCE_DIR="$FOUNDRY_RELEASE_DIR/evidence"
  export FOUNDRY_RELEASE_LOG_DIR="$FOUNDRY_RELEASE_DIR/logs"
  export FOUNDRY_VERIFY_EVIDENCE_FILE="$FOUNDRY_RELEASE_EVIDENCE_DIR/foundry-verify.json"
  export HOSTED_E2E_EVIDENCE_FILE="$FOUNDRY_RELEASE_EVIDENCE_DIR/hosted-e2e-evidence.json"
  export FOUNDRY_SMOKE_EVIDENCE_FILE="$FOUNDRY_RELEASE_EVIDENCE_DIR/hosted-smoke-evidence.json"
  export FOUNDRY_TRACE_EVAL_OUTPUT_FILE="$FOUNDRY_RELEASE_EVIDENCE_DIR/foundry-trace-eval.json"
  export APPINSIGHTS_EVIDENCE_FILE="$FOUNDRY_RELEASE_EVIDENCE_DIR/appinsights-evidence.json"
  export FOUNDRY_RELEASE_EVIDENCE_FILE="$FOUNDRY_RELEASE_EVIDENCE_DIR/release-evidence.json"
  mkdir -p "$FOUNDRY_RELEASE_EVIDENCE_DIR" "$FOUNDRY_RELEASE_LOG_DIR"
}
