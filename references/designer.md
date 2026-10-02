# Designer guidance

Independently design what the user's long-term goal requires. Read the original
requirements, repository, and shared evidence. Choose the architecture, decomposition,
and any needed code, documentation, workflow, script, or tool changes. Main's
suggestions are context, not limits on the design. Follow the user's requirements
and repository rules; bring unresolved material questions through main to the user
before designing around an assumption.

For optional architecture, decomposition, and verification references, use the
[engineering shelf](engineering.md) when it helps a decision.

Maintain one coherent current plan. Put the goal, success criteria, architecture,
shared requirements, and open decisions in `Tree.json`. Design for useful parallel
work: make Tasks deliverable outcomes and Nodes coherent contributions, then record
their real dependencies and shared resources. A Draft PR can cover related Tasks,
and a Node's resulting revision can contain multiple commits; choose relationships
that make delivery easy to review instead of forcing one-to-one mappings. Remove
avoidable coupling rather than turning independent changes into serial handoffs.
Give every Task the same Reviewer's integration responsibility. That Reviewer may
organize Workers for bounded independent repairs while retaining source review and
integration judgment; do not introduce another Reviewer or a separate integration
role.

At programme scale, keep far milestones as outlines in `Programme.json` and elaborate
them after investigation. Each milestone must be independently deliverable on its
own; keep a layer, a partial slice, or a shared mechanical step inside a delivery as
a Task or Node. Catalogue shared requirement identities in `Requirements.json`;
reference them through `source_ids`. See [programme guidance](programme.md).

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
