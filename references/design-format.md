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

Each Task accepts this closed field catalog. `Owns`/`Write paths` and `Difficulty`/`Tier` are
aliases.

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
- shared resource name
Difficulty: standard
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
- Given: A valid state — When: The behavior runs — Then: The result occurs — Oracle: The command exits zero — Evidence: command: focused regression — Covers: observable-behavior, verified-result
Regression:
Commands:
- python3 -m unittest tests.test_module
Paths:
- relative/path
```

`Scope out` and risks default to empty, `Difficulty` to `standard`, and `Verification` to `code`.
The Designer chooses `Difficulty` holistically, not by matching risk names or counting files. Use
`standard` when the path is clear, invariants are local, and failures are easy to detect and recover.
Use `complex` when stronger reasoning is materially useful because one dominant factor or several
combined factors create broad causal coupling, important unknowns, non-obvious tradeoffs, latent or
hard-to-reverse failure, or demanding verification. Risk tags and surface size are evidence, not
automatic triggers: a bounded, reversible, strongly tested migration may be `standard`, while an
untagged but coupled or hard-to-verify Task may be `complex`.

`Workload` is a separate, required execution-volume estimate. Choose `light`, `medium`, or `heavy`
from the breadth and number of touchpoints, amount of inspection and change, critical-path depth,
integration work, and verification volume. It is relative workload, not a clock-time estimate and
does not select the Worker tier. A broad repetitive change may be `heavy` but `standard`; a small
subtle change may be `light` but `complex`.

Python always emits empty `prerequisites` and `inputs`. If one Task needs another Task's result or
ordering, merge that work into one Task; every separate Task must be safe to dispatch concurrently.
One acceptance criterion may omit `Covers`, in which case it covers every requirement and output
owned by that Task. Multiple criteria must state `Covers`.

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
state or acceptance.

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
