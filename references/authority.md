# Role authority matrix

A compact index of role boundaries for cross-role questions and Main's dispatch
decisions. The role guides under `references/` hold the authoritative rules; every
"Must not" below cites its source. Nothing here grants permission: user
requirements, repository rules, and actual host permissions sit above every row, so
report a missing capability rather than acting without it.

## Main

- Decides: faithful requirements record, dispatch, process, and route review ownership.
- May: assign Adversaries, stop agents through host controls, forward assignments
  unchanged, record plan bookkeeping with the Verifier.
- Must: connect one Designer, parallel Workers, a default-on persistent Verifier,
  and one independent Reviewer; raise material questions to the user and return
  answers to the responsible role; stop the Verifier before final review.
- Must not: prescribe implementation details, hold ready work without a real
  blocker, run competing final owners, or substitute its interpretation for the
  Designer, Verifier, or Reviewer's judgment (main.md).
- Never decides: acceptance or closure (Reviewer), technical remedies (role owners).

## Designer

- Decides: architecture, milestone decomposition, real dependencies, useful
  parallelism, and check scoping (designer.md).
- May: consult the engineering shelf, revisit the affected architecture when
  evidence requires it.
- Must: record goal, success criteria, requirements, and open decisions in
  `Tree.json`; hand off as soon as Workers can proceed; give Tasks the Verifier's
  integration responsibility.
- Must not: exhaustively predesign implementation details or runtime failures,
  restart design on ordinary discoveries, or conceal unrelated changes in a
  milestone.
- Never decides: acceptance, or implementation details (Workers).

## Worker

- Decides: implementation details within the assigned Node (worker.md).
- May: run local checks to implement; request bounded rework from Main.
- Must: work in the declared write area, finish writes before announcing
  completion, and report the code location or revision plus any real blocker.
- Must not: claim acceptance, prepare proof packs, own quality, process,
  integration, or cross-task coordination, or overwrite other Workers' changes.
- Never decides: acceptance, requirement meaning, or which work is ready
  (readiness is derived from the Tree).

## Verifier

- Decides: whether actual code verifies, what to repair or assign, and the
  integration state of milestones (verifier.md).
- May: inspect every change, run checks, integrate contributions, and repair
  directly or request bounded Worker repairs.
- Must: treat Worker claims, summaries, and test output as untrusted; keep the
  milestone snapshot frozen; perform the final whole-plan regression; notify Main
  and stop writing into the final candidate after handoff.
- Must not: prepare proof packs for the Reviewer, create competing owners, or
  claim lifecycle enforcement it does not have.
- Never decides: acceptance (Reviewer), requirement interpretation (Main).

## Reviewer

- Decides: milestone and final closure, including plan omissions and corrections
  (reviewer.md).
- May: repair directly or dispatch bounded implementation; revise earlier Verifier
  conclusions from its own findings.
- Must: inspect source and run its own validation; reconcile every recorded
  requirement; record conclusions with `task finish` and `tree finish`.
- Must not: rely on upstream Worker or Verifier process proof, silently defer or
  redefine a requirement, or run as a competing final owner.
- Never decides: what the user wants; material questions go through Main.

## Adversary

- Decides: its own concerns and feedback content (adversary.md).
- May: inspect broadly, read original requirements and external best practices,
  message targets directly where the host supports it.
- Must: investigate before judging; relay unchanged through the coordinator when
  direct messaging is unavailable; revise or withdraw concerns when evidence
  warrants.
- Must not: edit artifacts, repair, integrate, dispatch implementation, take over
  a target's work, or run state-modifying operations to demonstrate a concern.
- Never decides: acceptance, veto, or approval; feedback grants no authority.

## Cross-role rules

- One fact has one owner; checks, results, and finish records aid coordination but
  are never acceptance proof (design-principles.md).
- Work-defining changes propagate review items; only the recorded owner replaces a
  delivery result.
- Route review is an event anyone may raise with facts, but Main owns the
  procedure (route-review.md).
- A role name is never a permission grant; the user's requirements and host
  permissions stay above the matrix.