# Design principles

1. **Current state is the handoff.** A new Agent can learn the delivery, Task,
   Node, dependencies, pending reviews, and latest results without replaying edits.
2. **History is immutable and optional to read.** Archive available conversation
   before changing the plan; query it only when present facts need background.
3. **Tree structure performs the mechanical work.** Agent intent names a local
   operation. The tool computes graph traversal, rewiring, review propagation, and
   check coverage.
4. **Task and Node have different jobs.** A Task is an independently deliverable
   group represented by one Draft PR. A Node is one scoped change represented by one
   commit in that PR. Ready Nodes may run in parallel. The designated Task integration owner leaves the
   client buildable and runnable, then records delivery independently of Node progress.
5. **One fact has one owner.** Shared requirements, Task requirements, Node facts,
   dependencies, and check definitions are not copied into other layers.
6. **Completion and upstream change coexist.** A completed Node keeps its result
   while a separate pending-review item records current follow-up. Task and Tree
   delivery conclusions likewise preserve their results until explicitly reconfirmed.
7. **Checks follow coverage.** Define a check once at its lowest common owner.
   Relevant changes invalidate it; unrelated branches do not.
8. **Automation assists instead of governing.** Start, finish, check, and report
   commands never become approval or validation gates.
9. **Local work stays local.** Build adjacency once, traverse the affected region in
   linear time, and write only changed files. Full assembly is a read-only export.
10. **Concurrency is brief and explicit.** Atomic writes use a short workspace lock.
    Editors and commands run outside it. Each check has an independent process lock
    and temporary run identity; interrupted execution requires explicit recovery.
    No execution deadline or whole-tree revision decides result validity.
11. **Reports consume semantics.** Structured decision, review, status, and check
    fields drive reports. Prose is not parsed into workflow state.
12. **Host configuration belongs to the user.** Existing native role files and
    receipts remain byte-identical through install, update, repair, and uninstall.
13. **Convergence includes repair.** The Reviewer normally owns direct corrections,
    integration, verification, and Task/Tree conclusions within the approved scope.
    Main has the same artifact authority but normally delegates that complete outcome
    to a launchable Reviewer, rather than splitting audit from ordinary remediation.
    This responsibility does not expand host permissions or protected-effect authority.

These principles reject generation histories in current state, whole-tree rewrites
for local changes, duplicated command lists, role cardinality rules, inferred prose
markers, and compatibility paths for superseded unpublished formats.

Refactoring plans use small behavior-preserving Node commits and buildable Task
slices. They update affected producers and consumers together, remove obsolete
unpublished paths, and express ordering between independently implementable Task PRs
as explicit dependencies. Commit and Draft PR fields hold current references only.
