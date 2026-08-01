# Repository Development Rules

## Better Plan self-maintenance exemption

- Maintain the Better Plan source repository with the ordinary native repository workflow.
  Maintaining its code, documentation, tests, templates, installer, or releases does not require
  following the Better Plan workflow.
- Do not discover, create, select, update, dispatch, regress, or audit a Better Plan Plan or Node
  merely because work is being performed in this repository.
- Do not create or maintain a repository-local Better Plan workspace such as `docs/plan` for
  ordinary repository development. Use temporary fixtures when product behavior requires one.
- Exercise the Better Plan workflow here only when the user's request explicitly asks to test or
  demonstrate that workflow. Such an exercise is product behavior under test, not a mandatory
  development process.

## Test scope

- Keep one representative test at the narrowest useful layer for each invariant. Do not repeat the
  same lifecycle branch through domain, CLI, hook, and installer tests unless that boundary adds a
  distinct contract.
- End-to-end coverage should prove the normal grouped path and one repair path. Prefer focused tests
  while editing; run the complete repository suite once after the change is integrated.
- Avoid exhaustive permutations of incidental formatting, equivalent invalid inputs, or host
  templates. Add a case only when it protects a user-visible principle or a security/state boundary.

## Native agent replacement

- Treat the current Better Plan native role matrix as the only supported generation and one
  receipt-managed unit. Do not retain legacy aliases, compatibility adapters, translated receipts,
  mixed generations, or runtime fallback to an older role shape.
- Normal install and update remain fail-closed for unowned same-name files. An explicit user request
  to replace an older Better Plan setup authorizes removing only that setup from the active agent
  directory and installing the complete current matrix with a fresh receipt.
- A recoverable copy may be kept solely for manual file recovery; Better Plan must never read,
  import, restore, or treat it as a compatible configuration. Never displace unrelated local agents.
- Verify the resulting selectors, receipt inventory, skill structure, and installer Doctor result
  before reporting success.
