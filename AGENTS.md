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
