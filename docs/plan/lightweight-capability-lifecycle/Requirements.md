# Lightweight Capability Lifecycle Requirements

## REQ-001 — One capability, one lifecycle

One explicit user-visible capability is represented by one selected implementation Node. The
Node ID is the lifecycle identity. Acceptance revision, implementation repair, regression, and
audit remain inside that lifecycle. Completion ends the lifecycle and must not select or start a
different Node automatically.

## REQ-002 — Main-controlled scope changes

Newly discovered adjacent defects, integrations, optimizations, or follow-up capabilities return
to the native main as findings. Only the native main, after comparing them with the latest user
request, may keep them in the current capability, defer them, or author a different Node. A
review rejection or preparation fingerprint change must not automatically dispatch another
acceptance designer.

## REQ-003 — Risk-based acceptance

Acceptance design selects only dimensions justified by the Node's observable requirements,
interfaces, state transitions, and material risks. Success, boundary, negative, replay, privacy,
and fingerprint are candidate dimensions, not a checklist. Omission of an irrelevant dimension
is neither a coverage defect nor a review failure.

## REQ-004 — Lightweight review

The acceptance reviewer rejects only a concrete missing requirement proof, false-positive oracle,
or material risk gap. It must not expand product scope, demand speculative completeness, or reject
because a candidate acceptance category is absent. Findings return to the native main for a
revise, narrow, defer, or proceed decision.

## REQ-005 — Bounded automation

Automatic routing is limited to correlated actions inside the selected lifecycle: acceptance
design may route to review, approved acceptance may route to execution, executor completion runs
focused regression, and a pass may route to thin audit. Rejection, drift, failure, audit findings,
completion, and any possible new capability return control to the native main.

## REQ-006 — Quiet framework-owned waiting

Agent lifetime remains owned by the host framework. Better Plan does not poll, time, interrupt, or
replace a child. Its guidance recommends no repeated progress message while delegated state is
unchanged; report only completion, blocking, user-decision, or scope-change events. This is
heuristic guidance, not a timer or execution gate.

## REQ-007 — Generic and private operation

The lifecycle contract is repository- and provider-neutral. It contains no product, model,
vendor, client, operating-system, or backend-specific routing policy. Plans, handoffs, context,
and evidence use repository-relative paths and disclose no machine, secret, server, or backend
runtime data.

## Acceptance target

A main agent can align one user-visible capability, run one design/review/execution/regression/
audit lifecycle, and stop after that capability resolves. Acceptance remains proportional to
actual risk, and every possible loop or capability expansion requires a fresh native-main
decision rather than an automatic dispatch.
