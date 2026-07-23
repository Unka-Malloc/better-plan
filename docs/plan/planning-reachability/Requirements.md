# Planning Reachability Requirements

## REQ-001 — Deferred work is not terminal history

An intentionally postponed Node uses `deferred`, remains visible with its reason, and can return
to `pending` only through an explicit activation. It is not eligible for execution while deferred.
`skipped` remains an irreversible terminal waiver for work that is no longer promised.

## REQ-002 — Delivery completion preserves outstanding obligations

A deferred implementation Node remains non-terminal and prevents final validation or Plan
completion from treating its requirements as delivered. If scope is removed from the current
delivery, the native main must explicitly skip it or move the capability into a separately
authored follow-up lifecycle instead of disguising deferral as completion.

## REQ-003 — One structured dependency authority

Every wait on another Better Plan Node is represented by that Node ID in `prerequisites`, including
dependencies across Plans in the same workspace. `status_reason` explains administrative state and
`next` records follow-up navigation only; neither changes execution eligibility.

## REQ-004 — Workspace-wide cycle rejection

Validation, graph mutation, and execution entry reject unknown prerequisites and cycles across all
referenced checkpoint files. Cycle diagnostics identify the complete closed Node-ID path. The graph
algorithm runs in `O(V + E)` time and memory without repeated reachability scans.

## REQ-005 — Global eligibility and safe mutation

Start, dispatch, and `next` resolve prerequisite status from the complete workspace rather than the
owning Plan only. A mutation is validated against an in-memory workspace snapshot before any state
file is replaced, so a rejected cross-Plan edge cannot leave partial state behind.

## REQ-006 — Private, bounded reporting

Status, dependency errors, Plans, and installed guidance use repository-relative labels and bounded
goal/reason summaries. They expose no absolute path, machine identity, credentials, endpoint, or
backend runtime output.

## Acceptance target

The native main can defer a promised capability without losing it, explicitly reactivate it later,
and rely on the manifest tool to reject a cross-Plan deadlock before any executor is authorized.
