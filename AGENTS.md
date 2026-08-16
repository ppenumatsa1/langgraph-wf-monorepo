# Coding Agent Instructions

This repository contains LangGraph workflow agents. The active lane is
`agents/order-resolution/foundry-public`.

Before changing LangGraph orchestration, read the lane-local `langgraph-docs`
and `langgraph-foundry-py` skills, plus any other lane-local skills relevant
to the area you are touching. Before changing Microsoft Foundry hosting,
deployment, evaluation, or telemetry, read the lane-local `microsoft-foundry`
skill.

Preserve the stable native API/SSE event contract, durable PostgreSQL audit
projections, deterministic HITL policy, idempotent side effects, and redacted
AG-UI/CopilotKit boundary. Application Insights is the required observability
backend; LangSmith is not required.

Use the lane `Makefile` for validation and release commands. GitHub Actions is
credential-free CI only and must not mutate Azure resources.
