# Design principles

Every Agent makes mistakes. Better Plan separates cheap parallel implementation,
persistent independent verification, and fresh independent review rather than
trusting a chain of success claims. Main keeps user requirements and the process
moving; Designer supplies enough architecture and decomposition for execution.
Verifier independently inspects and integrates throughout the plan; Reviewer judges
stable milestone and final code directly against requirements.

1. **Shared requirements replace repeated interpretation.** Keep user requirements,
   current architecture, open decisions, and source references accessible. Main owns
   faithful requirements and coordination, not implementation details.
2. **Design enough, then execute.** One Designer maps requirements to complete,
   independently deliverable milestones and real dependencies. Leave implementation
   details and discoveries to execution rather than prolong upfront planning.
3. **Workers implement; their claims are untrusted.** Workers owe code, not quality
   assurance, process ownership, cross-task integration, or proof packs. Parallelize
   them as widely as useful within actual host resources and permissions.
4. **Persistent verification is the default.** Start Verifier alongside Main during
   execution. It inspects actual changes, integrates, checks, and repairs independently,
   and remains active across milestone closures. It does not prepare proof for Reviewer.
5. **Independent review closes outcomes.** Reviewer receives requirements and a stable
   code candidate, not upstream process evidence as acceptance proof. It independently
   checks, repairs, and closes milestones promptly. Verifier may continue other work
   without touching that candidate.
6. **The final phase has one owner.** After all Workers finish, Verifier integrates and
   performs final whole-plan regression, notifies Main, then Main stops it before
   Reviewer's final takeover. Reviewer reconciles all recorded user requirements.
   Rework may repeat this cycle with an explicit handoff, never competing owners.
7. **One fact has one owner.** Central requirements retain their identities. Tasks
   describe outcomes, Nodes coherent contributions, and Draft PRs reviewable delivery
   boundaries. A PR may cover related Tasks; a Node's revision may include multiple
   commits. Operational records aid coordination but are not trusted acceptance proof.
8. **Discoveries stay local when possible.** Existing independently deliverable bug
   fixes, necessary refactors, and new features have clear boundaries. Errors introduced
   within feature implementation remain feature work. Update affected facts and edges
   rather than restart the entire design for each issue.
9. **Tools assist judgment.** Graph operations handle traversal, rewiring, and affected
   reviews/checks. Changes preserve earlier results while flagging affected work for
   reconfirmation. No tool result substitutes for independent code inspection.
10. **Hosts own execution and configuration.** Native tools handle dispatch, stopping,
    resumption, and capacity. Better Plan supplies a default Verifier role, not an
    automatic lifecycle runtime or human-approval scheme. Preserve user-owned models,
    reasoning, tools, permissions, and budgets; never assume unlimited free capacity.
11. **Uncertainty is shared.** Raise material questions through Main and pause only
    dependent work. Neither silence nor a declared default supplies an answer or
    authorization. Every role follows the user's actual requirements and repository rules.
12. **Local operations stay local.** Build adjacency once, traverse affected edges in
    linear time, and write only changed files. Atomic writes hold a short workspace
    lock; editors and commands run outside it. Interrupted checks require explicit
    recovery, not execution deadlines.
13. **Every instruction earns its context.** Load the shared workflow and relevant
    role; consult detailed references when needed. Avoid duplicate briefs and
    reporting rituals that do not improve the outcome.

Refactoring plans leave independently deliverable slices buildable, update affected
producers and consumers together, and replace incorrect unpublished implementation
without compatibility layers created solely to preserve a development mistake.

An explicitly assigned **Adversary** adds independent, feedback-only challenge in
any collaboration structure. It investigates actual activity, host capabilities,
applicable rules, and external best practices rather than merely checking a plan.
One or multiple targets are grouped by functional domain where useful, including
coordinators and Reviewers. Direct target messages or unchanged coordinator relay
carry concerns; the role never edits artifacts, repairs, or owns acceptance.
