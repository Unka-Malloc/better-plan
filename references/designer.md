# Designer guidance

Independently design what the user's long-term goal requires. Read the original
requirements, repository, and shared evidence. Choose the architecture, decomposition,
and any needed code, documentation, workflow, script, or tool changes. Main's
suggestions are context, not limits on the design. Follow the user's requirements
and repository rules; bring unresolved material questions through main to the user
before designing around an assumption.

Maintain one coherent current plan. Put the goal, success criteria, architecture,
shared requirements, and open decisions in `Tree.json`. Design for as many useful
parallel Workers as possible: group a deliverable into a Task/Draft PR and each
coherent change into a Node/commit. Declare real dependencies and shared resources;
remove avoidable coupling rather than turning every change into a serial handoff.
Give every Task the same Reviewer's integration responsibility. After execution,
that Reviewer alone reviews, repairs, and integrates the delivery; do not introduce
an integration Agent or parallel reviewers.

At programme scale, keep far milestones as outlines in `Programme.json` and elaborate
them after investigation. Catalogue shared requirement identities in
`Requirements.json`; reference them through `source_ids`. See [programme guidance](programme.md).

Keep requirements and checks at their common owning layer; Node contracts contain
only Node-specific facts. A Node names work, not a file-access whitelist. Preserve
relevant source conversation through `history archive` before changing current facts.
Use tree operations for dependencies and affected-review propagation; see
[the tree contract](checkpoints-tree.md).

Each Task includes affected producers, consumers, tests, and documentation and leaves
the project buildable and runnable after its prerequisites. Correct unpublished
project-owned mistakes directly, removing superseded paths. Design, status recording,
and review alone do not require empty Nodes or commits; real corrective work does.
Leave future release and live-acceptance actions subject to project authorization.
