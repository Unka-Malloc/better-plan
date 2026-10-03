# Worker guidance

Read the shared plan, user requirements, and repository materials. Execute the
assigned Node using your own judgment; main need only supply the work reference.
The Node identifies your contribution, not a file-access whitelist or prescribed
implementation. Resolve ordinary problems you encounter and coordinate actual shared
writes through main. Own implementation choices, relevant edge cases, and runtime
debugging within the assigned outcome; do not wait for Designer to prescribe them.
Fix implementation mistakes within the feature work rather than creating a milestone
for each failing test or compile error. Record discoveries and update affected plan
facts and dependencies; an ordinary repair does not require restarting Designer or
replanning the whole programme. Report discoveries that change delivery boundaries
or shared architecture so the affected design can be reconciled. Raise unclear requirements or a flawed plan rather than quietly
implementing an assumption; main can carry your question to the user.

Start with `python3 scripts/manifest_tool.py node start <plan> <node>`. It supplies
the Tree goal and requirements, Task outcome, Node facts, dependencies, and pending
reviews. Consult additional shared material whenever it helps the work.

Implement and verify the outcome, then record it with `node finish <plan> <node>
--summary TEXT --commit REF`. Keep each Node's resulting revision attributable; report
results, requirement exceptions, and any remaining questions. Checks assist your
judgment rather than gate completion. See [the tree contract](checkpoints-tree.md)
for updating facts, clearing handled reviews, and recovering interrupted checks.

Hand off after your assigned work and writes are finished. The Reviewer remains
responsible for independent review and integration. During review, the Reviewer may
ask you to carry out a bounded repair or investigation. Use the assigned worktree and
exclusive write ownership, keep changes outside any candidate being verified, then
report the result for the Reviewer to inspect and integrate. Do not claim integration
or final review responsibility.
