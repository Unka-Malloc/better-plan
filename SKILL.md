---
name: better-plan
description: Design-first orchestration for grouped implementation work with isolated Designer, Worker, Verifier, and Reviewer agents. Do not use it merely to maintain the Better Plan source repository itself.
---

# Better Plan

Better Plan incrementally maps a repository from its observed foundation to the detail currently
being changed, then turns authorized work into small task groups with deterministic state, isolated
role agents, focused verification, and one group-level review. The latest user request is always
authoritative; stored state is a revisable model of that request, never an independent source of
work.

## Activation and self-maintenance

When maintaining the Better Plan source repository itself, use the ordinary native repository
workflow. Do not discover, create, select, mutate, dispatch, regress, or review repository-local
Better Plan state merely to maintain this skill, its installer, templates, documentation, tests, or
releases. Use temporary fixtures only when explicitly testing Better Plan behavior.

For other repositories:

1. Consider Better Plan only for planning, coding, or explicit implementation work.
2. Run `scripts/manifest_tool.py discover <project-root>`.
3. If there is no unique valid workspace, continue with ordinary project handling.
4. Never infer authorization from an existing pending or active Node.
5. Keep secrets, personal or machine identity, backend runtime data, and absolute local paths out
   of Plan state, delegated prompts, evidence, and responses.

On the first Better Plan use after installation, tell the user once that ready-made native role
configurations are bundled for Codex, Claude Code, OpenCode, and Cursor and may be installed or
manually imported from `agents/<host>/`. Do not repeat this notice and do not inject it from Hooks.

## Source-grounded authority

Before creating or revising a Plan, freeze a source-grounded intent spine from the latest user request and relevant
`source_files`: ownership, Purpose, Goal, Description, status, real prerequisites, and explicit
non-dependencies. Purpose must remain distinct from derived Goal and Description.

Directory nesting expresses Plan ownership only. Workspace-wide `prerequisites` are the sole
execution-dependency authority; `next`, prose, Plan ancestry, conditions, and status reasons never
create execution edges. Supporting requirement, architecture, validation, and evidence documents
are projections of the canonical `Manifest.json` plus branch `Checkpoints.json`, not parallel plan
authorities.

For a product-wide model, maintain one canonical workspace and one declared repository capability
root; delivery Plans may remain separate historical groups. Record source-authored readable fields
`kind`, `tree_mode`, `node_status`, and `entry_gate` on Plans and
`code`, `title`, `tags`, and `conditions` on Nodes when the source authority provides them. Never
infer, invent, or abbreviate canonical `code` or `title` from Goal or Description.

Use `tree` for the readable default projection and `tree --details` for the complete details audit
projection. Before handoff, compare the readable projection and details audit projection against the
same source-grounded intent spine and correct lost ownership, fields, status, dependencies, or
explicit non-dependencies.

## Progressive capability facts

Keep durable repository knowledge in the workspace-root `Capabilities.json`, orthogonal to delivery
lifecycle state. Its one parentless `repository` entry is the repository's observed core or designed
foundation; every child uses a stable slash-path key. Unknown capability means no entry. Never
manufacture a complete project model up front.

Treat a mature repository's existing architecture as `basis: "observed"` fact. Accept it without a
Designer, Verifier, Reviewer, acceptance criteria, or retrospective audit. Follow only the path from
the repository root to the detail required by the latest request. When that inspection reveals
sibling modules, interfaces, or features, record bounded stubs as `disclosure: "known"` and
`touch: "untouched"`; do not inspect their internals merely to enrich the map. When later work needs
one of those stubs, use `promote-capability` to make it `examined` and `in_scope`, then disclose only
the additional path and siblings encountered for that work. Mark it `modified` after delivery.

The capability hierarchy is structural context, not an execution graph. Observed ancestors are
already established and never become prerequisite work. When a genuinely new `basis: "designed"`
foundation must be implemented, represent its delivery as an explicit parent task group and make
dependent child Nodes reference its completed Node through `prerequisites`; the foundation runs
first because of that real artifact handoff, not because of tree nesting.

Plans are unlimited historical delivery records, but creation is the last choice. Search the stable
capability key and existing Plan scope first; reuse or extend a matching nonterminal Plan. At most
one nonterminal task group may bind a capability key. Create a new group only for a genuinely
distinct high-cohesion closure or later delivery after the prior group is terminal.

## Task groups

Partition executable work into Plans with `kind: "group"` and bind each nonterminal group to one
`capability_key` whose fact is `examined` and `in_scope` or `modified`. Each group must be
high-cohesion and low-coupling: its Nodes jointly close one related capability, module, or scenario,
while unrelated closures belong in other groups. A task group contains, in order:

1. exactly one `group_design` Node;
2. one or more `implementation` Nodes; and
3. exactly one `final_validation` Node.

Every implementation Node directly depends on the group-design Node. The final-validation Node
directly depends on every non-skipped implementation Node, appears last, uses `critical` difficulty,
and owns the group's full-regression contract. Keep all other sequencing exclusively in
`prerequisites`.

Maximize safe concurrency while authoring the Plan. Independent implementation Nodes must own
disjoint paths, consume stable interfaces, and omit artificial prerequisites. Add an edge only for
a real artifact, data, schema, migration, or behavioral handoff. If two Nodes can execute safely at
the same time, preserve them as one parallel frontier.

A foundation Node or `milestone_gate` may still use the manual `start`, `check`, and `complete`
path. A `milestone_gate` is an aggregate evidence decision, not delegated delivery work, and must
directly depend on a same-Plan non-gate Node tagged `GATE_LEAF` before it starts.
`prerequisites` remains the sole execution authority: a prose task card is not a Node and is
insufficient evidence for a gate.

## Roles and lifecycle

Load exactly one role reference for the active role. Also load every action-specific local knowledge
reference returned by the dispatch payload; this supplements, and never replaces or multiplies,
the role contract. Leaf agents never mutate Plan state, criteria, receipts, or decision history;
the native main and state tool own those writes.

### Designer

Run the strongest locally callable Intelligence Index tier once at the start of a group. Give the
Designer the whole ordered group and its selected root-to-leaf capability scope, not one isolated
implementation Node or any `known/untouched` sibling. It performs predictive design across multiple
Nodes and milestones, anticipates hidden failure modes, and makes successive handoffs coherent.
Before design it must read the complete local
`references/design-patterns.md` catalog supplied in `knowledge_references`; ordinary dispatch never
fetches the source website. For the group and every material Node design, it compares the simplest
direct solution with any suitable catalog pattern, adopts a pattern only when a concrete verifiable
benefit exceeds its added complexity, and records a complete `design_pattern_assessment`. `none` is
a valid result. A pattern must never justify speculative layers or extra Plan/Node decomposition.
The Designer may write design and executable acceptance artifacts, but not production
implementation. Ordinary later defects do not trigger redesign.

### Worker

Run one Worker for one implementation Node. Classify the Node by task difficulty—not reasoning
effort—as `routine`, `standard`, `complex`, or `critical`. The Worker implements the frozen design,
resolves ordinary build and local-integration problems, and does not edit acceptance or Plan state.
After it returns, the state tool runs the Node's focused regression.

### Verifier

After a Worker passes focused regression, run a fresh Verifier for that Node. Use a high-Intelligence
model tier below the strongest available distinct tier when possible. The Verifier is write-capable:
it finds and directly repairs implementation-local defects, omissions, unsafe assumptions, and
broken paths. The state tool reruns focused regression after it returns. A remaining ordinary defect
returns to the same Worker lifecycle; only a real cross-node design or product-semantics error may
require native-main redesign judgment.

### Reviewer

After all implementations complete, run the initial full regression, then run exactly one fresh
Reviewer for the group whether that regression passed or failed. Use the strongest locally callable
Intelligence Index tier. The Reviewer owns the full end-to-end state of the bound capability, its
changed code, and actually impacted shared paths—not unrelated `known/untouched` repository
branches. It repairs every issue that needs no developer trade-off and reports material choices as
structured `decision_issues`. It is never run a second time for that group. After the native main
records its decisions, the state tool reruns full regression; later repair Nodes return directly to
full regression without another Reviewer.

## Model and agent assignment

Better Plan packages two versioned, network-free benchmark snapshots. They are references, not a
per-dispatch recommendation list:

- `coding_agent_catalog.json` contains measured LLM plus coding-harness combinations. Worker
  difficulty floors are `routine: 25`, `standard: 42`, `complex: 55`, and `critical: 64`. For
  hosts using benchmark routing, choose the lowest-cost measured combination in the current native
  harness at or above the Node's floor; break ties by higher coding score and stable variant ID.
  Ignore combinations absent from the table.
- `model_catalog.json` contains the model-only Intelligence Index. Designer and Reviewer choose the
  highest locally callable score without considering price. Verifier chooses the next distinct
  score when available, otherwise the highest callable score.

Codex has a user-preference default matrix: Designer and Reviewer use `gpt-5.6-sol/max`, all four
Worker difficulty agents use `gpt-5.6-luna/max`, and Verifier uses
`gpt-5.6-sol/medium`. A qualifying existing local Codex selector supplies every role whose measured
combination it exactly matches; the fixed matrix fills the remaining roles. This exception is
Codex-only and is not a recommendation for other hosts.

Codex also installs two lifecycle-independent read-only utilities: `finder` uses
`gpt-5.3-codex-spark/xhigh`; `fallback_finder` uses `gpt-5.4-mini/xhigh` only when the preferred
Finder is unavailable, fails, cannot be spawned, or exhausts quota. Use multiple Finder instances
concurrently for independent planning lookups. They never write files or Plan state.

For other native hosts, the installer performs table selection once while creating Better Plan
agents. It restricts Worker selection to measured Agent combinations named by the user's native
configuration, requiring both its model selector and reasoning setting to match exactly, and
independently restricts Designer, Verifier, and Reviewer to locally configured models found in the
model-only table. Only when no local configuration exists does it fall back to combinations measured
for that native harness. An omitted Worker reasoning setting is not guessed. Unknown or unsupported
combinations are omitted.

The installation receipt pins every created delivery role; normal updates preserve those assignments
rather than following leaderboard changes, while a later release may append a newly bundled utility
agent such as Finder. Installation output and each child's injected assignment line tell the user the
role, model, reasoning setting, and selection basis. Delivery roles also report benchmark score,
measured Worker cost when applicable, and whether the choice came from local configuration or catalog
fallback; read-only utilities report their fixed selector and mode. Runtime dispatch reads the pinned
native role and never reselects a model.

## Isolated dispatch and completion

For every leaf dispatch:

1. call the native child-agent facility with `fork_turns: "none"`;
2. pass only the selected Node—or the full group for Designer and Reviewer—the one matching role
   reference, the bounded `capability_scope`, every action-specific local knowledge reference, and
   necessary repository-relative files; `capability_scope` omits known untouched descendants;
3. bind the real opaque child-agent ID returned by the host with `bind-agent`; and
4. wait for the host's unambiguous final child completion notification.

Spawn return is not completion. Only a final callback whose child-agent
ID matches the bound outstanding dispatch may advance state. Early, unrelated, mismatched, and
replayed callbacks are no-ops. After group design, serialize `dispatch` for every safely eligible
Worker against the latest state, start all corresponding native spawn calls concurrently, and
serialize each `bind-agent` mutation as its host ID returns. Better Plan state mutations remain
serialized; spawn calls and child work do not. Independent Nodes in the same or different groups may be active
together, and correlation uses the bound child ID rather than a singleton. Completion never selects
or starts another Node automatically.

## Developer decisions

Each group Plan may contain `decision_issues`. A Reviewer-raised issue records an ID, `urgency`,
`question`, `context`, at least two `options`, and `status`:

- `immediate`: report to the user as soon as recorded because safe progress needs a choice; resolve
  and apply it before `reviewer-finished` may continue;
- `deferred`: keep working when safe and include it in the final decision report.

Use `record-decision` rather than hand-editing the field and `resolve-decision` after the user
chooses. `status` explicitly labels immediate items `REPORT NOW` and deferred items for final
handoff. Do not manufacture a decision issue for defects the Reviewer can safely repair.

## Native-main behavior

The native main owns scope, grouping, state transitions, user communication, and any redesign
decision. It must:

- derive outcome, constraints, observable acceptance, and non-goals before reading Plan state;
- disclose only the required root-to-leaf capability path, record encountered siblings as
  `known/untouched`, and reuse an existing matching Plan before creating one;
- select execution only when the latest request authorizes implementation;
- maximize safe Plan parallelism and launch every eligible independent Worker without waiting for
  another independent Worker to finish;
- serialize state-tool mutations while allowing bound child executions to overlap;
- run focused checks during Node closure and the full suite only at the group boundary;
- report immediate decisions promptly and deferred decisions at final handoff; and
- never treat completion, adjacent findings, or a pending Node as authority to start more work.

Use `defer` for visible promised future work and `activate` to make it executable again. Reserve
terminal `skipped` for an explicit waiver or not-applicable result.

## Host and Hook boundaries

Hooks provide bounded session/prompt guidance and may reduce one exact final child completion. They
never advertise role templates, choose models, launch agents, continue a stopped child, deny a
prompt, poll work, or select another Node. The native host owns child lifetime and cancellation.

## Commands

- `scripts/manifest_tool.py discover <project-root>`
- `scripts/manifest_tool.py validate [workspace]`
- `scripts/manifest_tool.py tree [workspace] [--plan ...] [--details]`
- `scripts/manifest_tool.py init-capabilities [workspace] --key ... --title ... --description ...`
- `scripts/manifest_tool.py upsert-capability [workspace] --key ... --parent ... --title ... --kind ... --description ...`
- `scripts/manifest_tool.py promote-capability <key> [workspace] --touch in_scope|modified`
- `scripts/manifest_tool.py bind-plan-capability [workspace] --plan ... --capability ...`
- `scripts/manifest_tool.py capability-tree [workspace] [--details]`
- `scripts/manifest_tool.py next-action <node-id> [workspace]`
- `scripts/manifest_tool.py dispatch <node-id> [workspace] --role designer|worker|verifier|reviewer`
- `scripts/manifest_tool.py bind-agent <node-id> [workspace] --dispatch-id ... --agent-id ...`
- `scripts/manifest_tool.py agent-complete <node-id> [workspace] --agent-id ... --final`
- `scripts/manifest_tool.py advance <node-id> [workspace] --event ...`
- `scripts/manifest_tool.py record-decision [workspace] --plan ... --urgency ... --question ... --context ... --option ... --option ...`
- `scripts/manifest_tool.py resolve-decision <decision-id> [workspace] --plan ... --resolution ...`
- `scripts/manifest_tool.py status [workspace]`

## Role references

- Native main: `references/orchestration-main.md`
- Designer: `references/designer.md`
- Designer's mandatory local pattern catalog: `references/design-patterns.md`
- Worker: `references/worker.md`
- Verifier: `references/verifier.md`
- Reviewer: `references/reviewer.md`
