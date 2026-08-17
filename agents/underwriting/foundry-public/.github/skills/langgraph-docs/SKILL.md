---
name: langgraph-docs
description: Fetch and reference LangGraph Python documentation for underwriting graph composition, native PostgreSQL checkpointers, streaming, and resume patterns.
license: MIT
metadata:
  author: LangChain
  package: langgraph
---

# langgraph-docs

## Workflow

### 1. Fetch the documentation index

Use `web_fetch` or `curl` to read: https://docs.langchain.com/llms.txt

### 2. Select relevant documentation

Prioritize:

- shared `StateGraph` composition
- checkpointers and persistence
- streaming and event projection
- recovery or resume behavior

### 3. Fetch and apply

Fetch the selected pages, then answer or implement from the documentation.

If the initial fetch fails or returns empty content, retry once. If it fails
again, direct the reader to https://docs.langchain.com/oss/python/langgraph/.

