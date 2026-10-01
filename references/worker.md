# Worker guidance

Read the shared plan, user requirements, and repository materials. Execute the
assigned Node using your own judgment; main need only supply the work reference.
The Node identifies your contribution, not a file-access whitelist or prescribed
implementation. Resolve ordinary problems you encounter and coordinate actual shared
writes through main. Raise unclear requirements or a flawed plan rather than quietly
implementing an assumption; main can carry your question to the user.

Start with `python3 scripts/manifest_tool.py node start <plan> <node>`. It supplies
the Tree goal and requirements, Task outcome, Node facts, dependencies, and pending
reviews. Consult additional shared material whenever it helps the work.

Implement and verify the outcome, then record it with `node finish <plan> <node>
--summary TEXT --commit REF`. Keep each Node's coherent commit attributable; report
results, requirement exceptions, and any remaining questions. Checks assist your
judgment rather than gate completion. See [the tree contract](checkpoints-tree.md)
for updating facts, clearing handled reviews, and recovering interrupted checks.

Hand off after your work and writes are finished. The last Worker does not become an
integrator. After all Workers finish, the single Reviewer independently reviews and
repairs the delivery, then integrates it. Do not keep writing alongside that review.
