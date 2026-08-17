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

## Upstream implementation skills

The Azure and Foundry skills were selectively refreshed from
[`microsoft/skills`](https://github.com/microsoft/skills) at revision
`e58528db9a006528a5fb0a2c029790fa6a9a7c0e`:

- `microsoft-foundry`
- `azure-ai-projects-py`
- `azure-identity-py`
- `azure-monitor-opentelemetry-py`
- `fastapi-router-py`
- `pydantic-models-py`

`langgraph-docs` was refreshed from `langchain-ai/deepagents` revision
`d01e4ac5bf36752e5c89c1c6645d486282cb611f`.

Generic Agent Framework, duplicate Foundry evaluation, and generic TypeScript
setup/update skills are intentionally excluded. The lane-owned LangGraph,
underwriting evaluation, AG-UI, and release skills are the architectural
authority.

Every top-level skill is recorded in `provenance.lock.json` and validated by
`make validate-skills`.
