# Design principles

1. **Shared information replaces repeated briefing.** Agents read requirements,
   current plans, repository documents, and evidence directly. Main understands and
   conveys the user's needs and keeps the process continuous.
2. **One design, parallel execution, one accountable Reviewer.** One Designer plans
   the work; Workers maximize useful parallelism. One Reviewer owns independent
   review, repair coordination, source review, integration, and verification. It can
   organize bounded repairs in parallel. Only the exact candidate undergoing a
   stability-sensitive verification needs to be frozen; independent work can continue
   outside it.
3. **Responsibility is not a permission list.** Designer, Worker, and Reviewer use
   their own judgment under user requirements and repository rules. Main corrects
   observed deviations without imposing a technical recipe. Reviewer judgment
   includes the validity of the plan itself.
4. **Uncertainty is shared.** Agents raise material questions through main to the
   user. Dependent work can pause; unanswered questions are not assumed decisions.
5. **Current state is the handoff.** Requirements, dependencies, results, checks,
   and open decisions remain accessible without replaying every conversation.
   Source history is immutable and retrieved when needed.
6. **One fact has one owner.** Shared requirements and checks live at their common
   layer. Tasks describe outcomes, Nodes describe coherent contributions, and PRs
   describe reviewable delivery boundaries. A PR may cover related Tasks, and a
   Node's resulting revision may include multiple commits.
7. **Tools assist judgment.** Local graph operations handle traversal, rewiring,
   review propagation, and affected checks. They are not permission or approval gates.
8. **Changes preserve evidence.** Completed work retains its result while affected
   reviews require judgment and reconfirmation; unrelated work stays untouched.
9. **Local operations stay local.** Build adjacency once, traverse affected edges
   in linear time, and write only changed files. Atomic writes hold a short workspace
   lock; editors and commands run outside it. Interrupted checks require explicit
   recovery, not execution deadlines.
10. **Hosts own execution.** Native tools handle messaging, Agent state, and resumption.
    Better Plan preserves user-owned model, tool, permission, and sandbox settings
    while refreshing maintained prompts. Doctor reports configuration drift.
11. **Every instruction earns its context.** Load the shared workflow and the relevant
    role; read command details when needed. Avoid duplicate briefing, identity
    metadata, and rules that do not help the Agent perform the work.

Refactoring plans keep Task slices buildable, update affected producers and consumers
together, and replace incorrect unpublished implementation without compatibility
layers created solely to preserve a development mistake.
