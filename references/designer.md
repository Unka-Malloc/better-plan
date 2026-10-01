# Designer guidance

Describe the current delivery directly. Put the final goal, success criteria,
architecture context, shared requirements, and explicit open decisions in
`Tree.json`. Design each Task as an independently implementable Draft PR that leaves
the client buildable and runnable. Design each Node as one coherent scoped commit in
that PR. Assign a Task `integration_owner`, normally the Reviewer, before dispatch,
then add explicit dependency edges for real ordering between Tasks and Nodes.

At programme scale, design in a rolling wave. Keep far milestones as planned
outlines in `Programme.json` -- `goal`, `success`, `requirements`, and
`open_decisions` with the shapes they will later take in a Tree -- and elaborate a
milestone only after its own investigation is complete. Never create placeholder
Nodes or empty Trees to represent future work, and do not fully decompose a
milestone whose requirements are not yet understood. Reference catalogue
requirement ids from delivery outlines, Tree requirements, and Task requirements
through `source_ids`; `Requirements.json` owns requirement status.

Before changing an existing plan, archive the relevant conversation available to
you with `history archive`. This is guidance, not a precondition enforced by the
tool. Rewrite current facts as current facts; do not preserve revision stories in
goals, requirements, Tasks, Nodes, or results.

Keep shared requirements at Tree scope and Task requirements at Task scope. Put only
Node-specific facts in `contract`. Define each check once at the lowest owner common
to its coverage. Use the node, edge, and subtree commands so rewiring, review
propagation, and check invalidation follow the graph automatically.

For refactors, prefer small behavior-preserving Node commits and complete each Task
as a working integration slice. Update affected producers, consumers, tests, and
documentation together. Remove obsolete unpublished implementations instead of
preserving them through compatibility layers. Store only the current Node commit and
Task Draft PR references. Default delivery ends at engineering completion with PRs
Draft. The Reviewer normally integrates, directly repairs, verifies, and records Task
results, and the Reviewer assigned whole-delivery convergence records Tree results.
Do not reserve current-plan corrections or conclusions for main: main normally
coordinates scheduling and may publish the Reviewer's conclusion, or perform
convergence when the Reviewer is unavailable or the user explicitly assigns main.
A project's explicit policy may describe later Ready, merge, installation and
acceptance work, but a plan or recorded completion does not grant execution authority.

Create Nodes only for real scoped code, documentation, or configuration changes that
produce commits. Do not invent design-only, audit-only, or status-only Nodes that
would require empty commits. Treat the final Tree audit as lifecycle activity unless
it discovers a concrete correction that needs its own Node.

Parallelize source work and isolated builds when resources do not conflict. Declare
shared runtime, installed client, and real user-data locations as coordinated
resources so only contending operations serialize. Preserve the project's fixed
acceptance scope instead of substituting fake directories or alternate systems.

Roles, executors, and resources are planning hints. Give each Task, Tree, or programme
milestone one continuous Reviewer, which is enough for all of its defects; do not split
one unit across several Reviewers. Parallelize independent units and coordinate
shared-file writers. The Reviewer-first default does not require a particular role
count, a second Reviewer, or a new approval gate. Workers retain initial Node execution.

Design within the supplied scope and authority. Do not execute production work or
the commands being planned. Route missing input and concrete host/skill conflicts
to the main Agent. Do not bind integration ownership to an ephemeral session ID.
