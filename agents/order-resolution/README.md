# Order Resolution

Order Resolution has two documented LangGraph lanes:

- [foundry-public](foundry-public/README.md) - the accepted public Foundry
  baseline.
- [foundry-private](foundry-private/README.md) - the isolated BYO VNet target
  with private Foundry, PostgreSQL, ACR, and runner services.

The private lane preserves the shared LangGraph workflow, FastAPI/SSE contract,
durable PostgreSQL checkpoints, redacted AG-UI/CopilotKit projections,
Application Insights observability, and business HITL. Its deployment
automation is noninteractive and fail-closed. The private lane documentation
does not claim live Azure provisioning or release success.
