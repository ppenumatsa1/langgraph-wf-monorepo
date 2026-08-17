# LangGraph Workflow Monorepo

This repository catalogs independent LangGraph workflow agents. Each agent lane
keeps its application, infrastructure, deployment documentation, validation,
evaluation, and telemetry lifecycle self-contained.

## Agent catalog

| Agent | Deployment variant | Start here |
| --- | --- | --- |
| Order resolution | Public Microsoft Foundry hosted agent with React/FastAPI wrapper | [Order-resolution lane](agents/order-resolution/README.md) |
| Underwriting | Public Microsoft Foundry hosted LangGraph workflow with React/FastAPI wrapper | [Underwriting lane](agents/underwriting/foundry-public/README.md) |

Order Resolution and Underwriting are independently deployable lanes. Future
workflow lanes should follow the same `agents/<agent>/<deployment-variant>`
boundary and preserve lane-local application, infrastructure, validation,
evaluation, telemetry, and evidence ownership.

See the [license](LICENSE) and [disclaimer](DISCLAIMER.md) before using this
repository.
