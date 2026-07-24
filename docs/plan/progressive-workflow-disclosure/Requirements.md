# Progressive Workflow Disclosure Requirements

## REQ-001 — Entrance-only routing

Session, prompt-submit, and skill-entry guidance decides only whether the current request belongs
in Better Plan. Coding and other explicit implementation work enters the workflow. Questions and
non-implementation requests follow the user's instructions through the native workflow.

## REQ-002 — Deferred lifecycle disclosure

Entry guidance does not preload Node lifecycle, acceptance, execution, focused regression, repair,
audit, full regression, completion, or next-Node policy. The complete workflow remains canonical
in `SKILL.md` and is disclosed through the main and exactly one active-role reference after Better
Plan applies.

## REQ-003 — Existing boundaries remain intact

The change preserves structural workspace detection, supported host protocol responses, privacy
boundaries, role isolation, and every existing Better Plan state transition. It changes prompt
placement, not lifecycle semantics.

## Acceptance target

An agent sees a short routing instruction at entry, enters Better Plan when asked to code or
implement, and otherwise answers or performs the user's request normally. Once activated, the
Skill and role references still provide the complete lifecycle.
