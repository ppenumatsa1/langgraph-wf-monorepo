# Lane-local skill inventory

This lane uses a LangGraph-first skill baseline.

## Lane-owned authoritative skills

- `langgraph-docs`
- `langgraph-foundry-py`
- `underwriting-evaluation`
- `ag-ui-react-integration-ts`
- `e2e-rubric`
- `docs-sync`
- `local-validation`
- `design-review`
- `backend-boundary-review`
- `release-readiness`

## Selectively vendored Microsoft catalog skills

The following complete Microsoft catalog skill directories were selectively
copied from [`microsoft/skills`](https://github.com/microsoft/skills) at
revision `e58528db9a006528a5fb0a2c029790fa6a9a7c0e`:

- `microsoft-foundry`
- `agent-framework-azure-ai-py`

The vendored Agent Framework skill remains provenance for hosted Azure AI
integration patterns only. The lane-owned LangGraph skills above are the
architectural authority for underwriting workflow, validation, and release
behavior.

