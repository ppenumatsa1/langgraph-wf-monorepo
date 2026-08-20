<!-- mermaid-ai-skills:start -->
## Mermaid Diagrams

When the user asks to create, edit, or visualize a diagram, follow the
instructions in `.github/instructions/mermaid.instructions.md`.
<!-- mermaid-ai-skills:end -->

## Project guidance

The active implementation is
`agents/order-resolution/foundry-private`. It uses LangGraph for workflow
orchestration and Microsoft Foundry private-VNet hosted-agent deployment. Use
`agents/order-resolution/foundry-public` as the stable public-lane behavioral
reference.

Before changing LangGraph code, read the lane-local `langgraph-docs` and
`langgraph-foundry-py` skills, plus any other lane-local skills relevant to the
area you are touching. Before changing Foundry deployment, evaluation, or
telemetry behavior, read the lane-local `microsoft-foundry` skill.

For the private lane, preserve separate Foundry-agent, Container Apps,
private-endpoint, and private-runner subnets. The frontend is the only public
application ingress. GitHub Actions remains credential-free and must not
provision or mutate Azure resources.
