# HITL Approval Conditions

The deterministic graph policy is hosting-independent:

- `ORD-1001` late delivery completes without `hitl.request`.
- `ORD-1009` delayed high-value compensation requires approval.
- Damaged-item resolution requires approval.

Only one unresolved interrupt may exist per thread. Approval preparation emits
`checkpoint.created` and `hitl.request` once, outside replayable interrupt node
bodies. Resume must match the currently pending checkpoint and approval
projection. Approval completes the workflow; rejection escalates it; repeated
responses return the prior outcome without repeating side effects.
