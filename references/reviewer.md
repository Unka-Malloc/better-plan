# Reviewer guidance

Review the current delivery goal, success criteria, Task outcomes, Node results,
pending-review items, and latest scoped check results. Use `tree export` for the
assembled read-only view and `checks list` for check coverage and scheduling.

For each Task with a recorded delivery result, confirm its current Draft PR contains the current commits
of its Nodes and leaves the client buildable and runnable. Review whether Task groups
remain independently implementable and whether cross-Task ordering is explicit. The Task integration owner records `task finish` after integration and verification;
the main Agent records `tree finish` after the overall review. These are engineering
conclusions, with PRs remaining Draft. Later Ready, merge, installation and live
acceptance operations require separate project authorization.

Inspect delivery reviews independently from Node progress. A preserved old result
does not prove the current scope, and Tree confirmation cannot conceal unconfirmed
Tasks. Finish commands acknowledge their own layer only; Node reviews, failed checks
and declared exceptions stay visible.

Do not infer decisions or workflow state from prose. An explicit open decision,
pending review, failed check, or unresolved exception is visible in its structured
field. History is consulted only when the current state requires background.

Whole-Tree review is delivery lifecycle activity, not an empty Node commit. If the
audit finds a real correction, represent that scoped change with a Node and commit.
Better Plan does not require a reviewer Node and does not turn the verdict into an
approval gate.

Report concrete conflicts with host instructions to the main Agent. Role template
differences alone do not establish a conflict or authorize changing local roles.
