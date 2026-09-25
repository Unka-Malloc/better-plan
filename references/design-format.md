# Design.md v1 Format

The Designer writes one structured solution plan in `Design.md`. Python compiles its human names,
prose, outputs, risks, and evidence into canonical v3 codes and fields. The Designer never writes
`REQ-*`, `TASK-*`, `NODE-*`, `OUT-*`, `AC-*`, JSON, lifecycle receipts, or duplicated graph
bookkeeping.

Generate the authoritative skeleton with:

```sh
python3 scripts/manifest_tool.py schema design
```

`open-designer-session` creates this same field-only skeleton at the returned `draft_path` when the
file does not already exist. It contains no example requirement, architecture, Task, Node, or
acceptance semantics. Replace its empty fields with the actual design; an untouched skeleton keeps
the direct-write fallback instead of becoming a draft.

## Document structure

An optional `#` document title may precede these recognized `##`–`####` sections. Section names are
case-insensitive:

- `Requirements`
- `Architecture`
- one or more `Task: <ascii-name>` sections
- `Full regression`

Unknown sections and unrecognized lines become `unmapped`; the compiler never guesses their
meaning. Human names use lowercase ASCII slugs after normalization and must be unique in their own
kind. References use those names, never generated codes.

## Requirements

Write one requirement per list item:

```md
- observable-behavior: The authorized behavior is observable. — source: user-request, repository-contract
```

`source` is optional and defaults mechanically to `Design.md`.

## Architecture

```md
Summary: One bounded design whose Tasks form a single parallel frontier.
Notes:
- Keep dependent implementation steps inside the same Task.
```

## Task fields

Each Task accepts this closed field catalog. `Owns` and `Write paths` are aliases; `Difficulty`
and `Tier` are rejected as unmapped content because no Task is tiered.

```md
## Task: bounded-delivery
Outcome: The requested behavior passes its focused oracle.
Scope in:
- The bounded capability.
Scope out:
- Unrelated behavior.
Outputs:
- verified-result: Verified result — artifact: relative/path — guarantee: The delivery can rely on it.
Owns:
- relative/path
Exclusive:
- build directory — isolated per Node under target/<node>/
- test fixture store — isolated per Node under fixtures/<node>/
Worker: code
Workload: medium
Verification: code
Risks:
- quality
Nodes:
- inspect-contracts: Confirm the affected contracts and boundaries.
- implement-behavior: Implement the bounded behavior. — after: inspect-contracts
- verify-behavior: Prepare focused verification. — after: inspect-contracts
- integrate-result: Integrate implementation and verification. — after: implement-behavior, verify-behavior
Requirements:
- observable-behavior
Design:
approach:
- Use the simplest adequate implementation.
Acceptance:
- Given: State with a known expected result — When: The public entry runs — Then: Its result matches that state — Oracle: Compare the actual entry's result with the independently arranged expectation; unavailable observation fails — Evidence: command: focused regression — Covers: observable-behavior, verified-result
Regression:
Commands:
- python3 -m unittest tests.test_module
Paths:
- relative/path
```

`Scope out` and risks default to empty, `Worker` to `code`, and `Verification` to `code`.

`Worker` names one of two responsibilities, never a strength:

- `code` — the Task writes code and its result is proven by its commands.
- `hybrid` — the Task writes code *and* its result is judged visually, so it owes rendered evidence.

`Verification` repeats that answer as evidence: `code` or `hybrid`. The two must agree, and readiness
rejects a Task that says one thing in each field, because only the hybrid Worker is the role that
produces a rendered result — so a hybrid Task is dispatched to the packaged `hybrid-worker` role,
while a code Task goes to the packaged `worker` role.

One Worker role handles every Task, so do not write a `Difficulty` or `Tier` line: Tasks are not
tiered, no stronger or weaker role exists, and the compiler reports the line as unmapped. Size the
work instead, because readiness judges this Task against the single-session ceiling:

| Dimension | Ceiling |
| --- | --- |
| Nodes in the Task | 8 |
| Nodes on the critical path | 4 |
| Widest ready frontier | 4 |
| Write paths | 8 |
| Acceptance criteria | 8 |
| Focused verification commands | 6 |

A Task that already began keeps the frozen shape its user authorized and is never re-judged. A Task
that never began is still design work even inside a sealed Plan, so a continuation that adds or
rewrites unstarted Tasks is judged here too. An unsealed Task above any ceiling is rejected before
authorization; split it into more mutually parallel-safe Tasks.

`Workload` is a separate, required execution-volume estimate. Choose `light`, `medium`, or `heavy`
from the breadth and number of touchpoints, amount of inspection and change, critical-path depth,
integration work, and verification volume. It is relative workload, not a clock-time estimate and it
selects nothing. It tells the native main how much observation and how long an adaptive wait a
running Task deserves.

`Exclusive` names the machine resources the Task contends on, including the ones that are not files.
Cover at least: build or artifact directory, version-control index and lock, test database or fixture
store, listening ports, simulators or devices, and package or toolchain cache. Name each resource and
the concrete path the Task uses for it.

A Worker runs its own focused checks in the build, test and cache paths this field assigns it, and
only there: declaring a path is what grants the check, and declaring none tells the Worker to edit
without building and report what the native main must verify. When a Task's Nodes run
concurrently, each one needs its **own** path, so readiness rejects an empty `Exclusive` list when the
frontier is wider than one; narrow the frontier instead when a resource genuinely cannot be separated.
Wording is not judged: only the Reviewer can tell whether the named paths really separate the Nodes.

The canonical focused acceptance is a different stage: the native main runs it serially after the
Workers return, so it needs no declaration of its own.

Python always emits empty `prerequisites` and `inputs`. If one Task needs another Task's result or
ordering, merge that work into one Task; every separate Task must be safe to dispatch concurrently.
One acceptance criterion may omit `Covers`, in which case it covers every requirement and output
owned by that Task. Multiple criteria must state `Covers`. This mapping is structural; only claim
coverage when the scenario actually observes the named guarantee. Use the existing prose fields for
the Designer's reasoning guidance in `references/designer.md`; no additional sections or fields are
required. Acceptance cases are required evidence, not an exhaustive definition of correct behavior.

## Internal Node DAG

Every Task requires one or more `Nodes`. Use one list item per Node:

```md
- human-name: Concrete execution outcome. — after: predecessor-a, predecessor-b
```

`after` is optional and defaults to no prerequisites; `after: none` is equivalent. Independent
Nodes omit dependencies and therefore run together. A branch gives multiple Nodes the same
predecessor; a join lists every branch it waits for. Declare an edge only for a real ordering or data
dependency. Python generates `NODE-*` codes, resolves human names, and rejects unknown references,
self-dependencies, and cycles. Nodes remain inside one Worker session and do not receive separate
state or acceptance. Because they share their Task's ownership, Nodes that run together also share
whatever the Task left unassigned: attribute their build, test and cache paths in `Exclusive`, or
narrow the frontier instead of claiming concurrency the machine cannot give them.

## Full regression

```md
## Full regression
Commands:
- python3 -m unittest discover -s tests -p 'test_*.py'
Paths:
- relative/path
```

If `Requirements`, `Architecture`, or `Full regression` is absent, compilation retains that section
from the current Plan and records it in `sections_from_plan`. A draft without a Task section is a
structure issue.

## Diagnostic contract

Every structure or content issue reports its exact `Design.md` line and canonical `Plan.json.spec`
field. A missing value points to its owning section heading and absent field. An unexpected internal
failure reports the nearest compiler phase, line, and field. Unmapped content reports its exact line
range and digest without persisting the original text. Diagnostics are specific enough for one-pass
repair; an agent must not need to reparse the draft merely to locate or separate compiler errors.

## Exclusion and repair

Place `<!-- better-plan: exclude -->` immediately before the next content block to exclude that
block deliberately. The content remains in the live and pristine drafts; the receipt stores only its
line range, digest, and `excluded` status.

The Designer may use the exclusion marker while authoring. After the Designer returns, `Design.md`
is read-only. Python performs the initial conversion; if it reports an issue, the native main
completes `Plan.json` without changing the draft. Authorization refuses every open structure,
content, or unmapped issue.
The native main maps valid in-scope meaning and records a non-adoption reason in
`spec.architecture.notes` for content conflicting with user decisions, outside scope, or explicitly
rejected alternatives. This resolves the conversion issue without inserting an exclusion marker
into the frozen draft or promoting that content into an implementation requirement. Follow
`references/structure-repair.md`; valid design choices and missing requirements cannot be discarded.
