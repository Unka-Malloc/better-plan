# Repository Development Rules

## Better Plan self-maintenance exemption

- Maintain the Better Plan source repository with the ordinary native repository workflow.
  Maintaining its code, documentation, tests, templates, installer, or releases does not require
  following the Better Plan workflow.
- Do not discover, create, select, update, dispatch, regress, or audit a Better Plan Tree or Node
  merely because work is being performed in this repository.
- Do not create or maintain a repository-local Better Plan workspace such as `docs/plan` for
  ordinary repository development. Use temporary fixtures when product behavior requires one.
- Exercise the Better Plan workflow here only when the user's request explicitly asks to test or
  demonstrate that workflow. Such an exercise is product behavior under test, not a mandatory
  development process.

## Test scope

- Keep one representative test at the narrowest useful layer for each invariant. Do not repeat the
  same lifecycle branch through domain, CLI, and installer tests unless that boundary adds a
  distinct contract.
- End-to-end coverage should prove the normal grouped path and one repair path. Prefer focused tests
  while editing; run the complete repository suite once after the change is integrated.
- Avoid exhaustive permutations of incidental formatting, equivalent invalid inputs, or host
  templates. Add a case only when it protects a user-visible principle or a security/state boundary.

## Reporting, clarification, and approval

- Promptly report defects found during development and focused testing. Repair ordinary defects
  within the existing authorized outcome, scope, and risk boundary without asking for confirmation
  of each fix. A progress report does not create an approval gate.
- Request a user decision only when material input cannot be discovered or the required action
  exceeds existing authorization. Complete authorized preparation first, present the concrete
  decision or action, and continue independent work while its answer is pending. Silence and
  declared defaults never grant approval.
- Problems found by the complete repository regression are repaired directly when they remain
  within the approved outcome, scope, published contracts, and risk boundary; run the focused checks
  needed to verify those repairs. Ask the developer only when the failure requires a decision that
  changes one of those boundaries. Continue independent authorized work while that decision is
  pending.

## Native role configuration and prompt refresh

- Treat every host-owned role field as user configuration: model, provider, variant, reasoning
  effort, tools, permissions, sandbox, and any local key. Better Plan may create its role matrix
  only when no same-name role configuration or receipt exists.
- Role prompt content — description and instruction body — is maintained by the skill. Install and
  update refresh it from the current packaged template, preserve every host-owned field, and refresh
  the receipt digests to match. A role file without a recognizable prompt structure stays untouched.
- Install, update, uninstall, Doctor, migration, repair, and explicit replacement requests never
  authorize changing host-owned fields, adding or removing role files, or rewriting prompts outside
  that refresh. Update skills, plugins, and adapters around them.
- A receipt mismatch is a report-only Doctor warning. Never recommend replacement as its repair,
  never regenerate a receipt outside a prompt refresh, and never displace unrelated local agents.
- Verify host-owned fields remain byte-identical across every non-initial installation operation,
  then report the separate skill, plugin, and adapter Doctor results.
