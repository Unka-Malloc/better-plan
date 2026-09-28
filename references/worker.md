# Worker guidance

Start the assigned Node with:

```sh
python3 scripts/manifest_tool.py node start <root> <node-id>
```

Read the returned Tree goal, Task outcome, shared and Task requirements, Node
contract, dependencies, and pending reviews. Work inside that current scope. History
and unrelated branches are not part of the default context; query them only when the
current facts leave a real question.

Run or record the checks useful to the work. Check state is assistance, not a
completion gate. When the Node outcome is done, record the current result:

```sh
python3 scripts/manifest_tool.py node finish <root> <node-id> \
  --summary "result" --commit <current-ref>
```

The tool prints shared and Task requirements again. Report how they were followed
and any exception in your response. Clear handled upstream-review items with
`node review-done`; do not erase the Node's existing result merely because review was
needed.

One Node owns one scoped commit. Create or record that commit without absorbing work
from another Node. When the final Node completes, report `ready_for_integration` to
the Task's designated `integration_owner`. Completion order does not transfer
ownership. Only act as integration owner when the assignment explicitly gives you
that responsibility.

The integration owner assembles all Node commits, resolves conflicts, verifies the
integrated outcome, maintains and records the Task Draft PR, then uses `task finish`
to record its delivery conclusion and exceptions. Leave the client buildable and
runnable and the PR Draft. The main Agent separately records `tree finish` after
overall review and verification. Ready, merge, installation and live acceptance are
outside the default engineering handoff.

Delivery reviews preserve old results but require reconfirmation after relevant
changes. Passing a check or clearing a Node review does not reconfirm delivery.
If a check executor was interrupted, confirm its leftover commands have ended before
`checks recover`; then rerun or record the check. Never use elapsed time as proof of
failure or termination. Report concrete host-instruction conflicts to the main Agent.
