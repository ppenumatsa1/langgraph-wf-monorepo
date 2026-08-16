# LangGraph Workflow Monorepo

This repository catalogs independent LangGraph workflow agents. Each agent lane
keeps its application, infrastructure, deployment documentation, validation,
evaluation, and telemetry lifecycle self-contained.

## Agent catalog

| Agent | Deployment variant | Start here |
| --- | --- | --- |
| Order resolution | Public Microsoft Foundry hosted agent with React/FastAPI wrapper | [Order-resolution lane](agents/order-resolution/README.md) |

The initial milestone intentionally contains only order resolution. Future
workflow lanes should follow the same `agents/<agent>/<deployment-variant>`
boundary instead of introducing shared abstractions before a second concrete
use case exists.

See the [license](LICENSE) and [disclaimer](DISCLAIMER.md) before using this
repository.
