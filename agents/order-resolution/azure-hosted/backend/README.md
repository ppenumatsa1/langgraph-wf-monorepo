# Backend

FastAPI runs the single shared LangGraph `StateGraph` directly for local and
Azure-hosted execution. `AsyncPostgresSaver` owns graph durability; application
tables provide replayable audit/history projections.

Foundry model calls use `DefaultAzureCredential` through the LangChain Azure AI
adapter. If the model is unavailable, deterministic triage remains a node-level
fallback in the same graph.

Production sets `DB_SCHEMA_MANAGED_EXTERNALLY=true`; administrators run
`python -m app.sql.bootstrap` and native checkpointer setup before granting the
runtime role least-privilege DML/sequence access.
