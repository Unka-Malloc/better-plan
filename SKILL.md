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
2. Complete the first-use role confirmation gate below unless it was already completed in this
   conversation.
3. Run `scripts/manifest_tool.py discover <project-root>`.
4. If there is no unique valid workspace, continue with ordinary project handling.
5. Never infer authorization from an existing pending or active Node.
6. Keep secrets, personal or machine identity, backend runtime data, and absolute local paths out
   of Plan state, delegated prompts, evidence, and responses.

### First-use role confirmation gate

On the first Better Plan activation in a conversation, inspect the current host's installed Better
Plan role files and receipt read-only, and compare them with the role matrix recommended by this
skill package. Before discovering or mutating Plan state or dispatching any role agent, show the
user one Markdown table containing every role, its purpose, installed model, reasoning effort,
installed and recommended model provider when explicitly pinned, recommended model and effort, and
whether they differ. Mark missing roles and unpinned providers explicitly; never infer a provider
or inspect credentials.

Ask whether to keep the installed matrix or use the recommended matrix, then stop and wait for an
explicit choice. Treat that choice as authorization only for the selected workflow; it does not
authorize replacing existing files. If no native matrix is installed, show every installed value
as `not installed` and ask whether to install or manually import the recommendation. Also tell the
user that ready-made native role configurations are bundled for Codex, Claude Code, OpenCode, and
Cursor under `agents/<host>/`. Do not repeat this gate in the same conversation and do not inject it
from Hooks.

### Role-change reconfirmation gate

Whenever the user requests any change to a native role configuration, repeat the complete
installed-versus-recommended role table before editing anything, even if the first-use table or an
earlier role-change table was already shown in the same conversation. Include every role, not only
the requested roles, with purpose, installed provider/model/reasoning effort, packaged recommended
provider/model/reasoning effort, and an explicit difference status. Label client-specific overrides
and the package recommendation as separate configuration layers; never describe a local override as
a recommendation change.

After the table, restate the exact requested mutations, ask the user to confirm them, then stop and
wait. Until that fresh confirmation arrives, do not edit role files, provider configuration,
receipts, templates, recommendation matrices, or any other host or repository state. A prior
confirmation never satisfies a later role-change request. This gate always repeats and overrides
the first-use gate's same-conversation non-repetition rule.

### Additive host integration — iron rule

Treat every pre-existing host or user file as immutable during model-provider, agent, Hook, MCP,
skill, or other host adaptation. A request to configure, enable, route, or test an integration never
authorizes replacing, overwriting, renaming, moving, deleting, taking receipt ownership of, or
wholesale rewriting an existing file, including an existing Better Plan native role file.

Integrate additively: create a new uniquely named Better Plan-owned file, or add only the smallest
new namespaced table, key, or list entry when the host format supports a non-destructive merge and
the user authorized that configuration. Preserve every unrelated byte and existing entry. A receipt
may cover only artifacts or entries Better Plan created itself; it never converts a pre-existing
file into a managed file. Uninstall removes only those additive artifacts or entries. If the host
requires replacing an existing file or a same-name collision prevents additive installation, fail
closed, leave the original untouched, and report the blocker. Only an explicit request naming the
specific file and exact mutation can authorize editing that existing file; general installation,
update, provider, model, or routing requests never do.

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
After it returns, dispatch the Verifier without running the frozen regression yet. The Worker may
run only the smallest implementation-local diagnostic needed to avoid an obviously broken handoff.

### Verifier

After a Worker returns, run a fresh Verifier for that Node. Use a high-Intelligence
model tier below the strongest available distinct tier when possible. The Verifier is write-capable:
it finds and directly repairs implementation-local defects, omissions, unsafe assumptions, and
broken paths. The state tool runs the Node's frozen focused regression once after it returns. A
remaining ordinary defect
returns to the same Worker lifecycle; only a real cross-node design or product-semantics error may
require native-main redesign judgment.

Every Node declares `verification_profile: code|visual|hybrid`. `code` uses the code Verifier.
`visual` and `hybrid` use the Visual Verifier and require vision, browser control, and rendered
evidence for every declared viewport and interaction state. Source inspection, DOM text, snapshots,
or a successful build never substitute for exercising the real UI. If the required browser or
rendered state is unavailable, fail closed with a blocker. `hybrid` also performs the complete code
and data-flow review. The final-validation profile must cover every non-skipped implementation
profile; a mixed group uses `hybrid`.

### Reviewer

After all implementations complete, run exactly one fresh Reviewer for the group before full
regression. Use the strongest locally callable
Intelligence Index tier. The Reviewer owns the full end-to-end state of the bound capability, its
changed code, and actually impacted shared paths—not unrelated `known/untouched` repository
branches. It repairs every issue that needs no developer trade-off and reports material choices as
structured `decision_issues`. It is never run a second time for that group. After the native main
records its decisions, the state tool runs the group's full regression once. Only a failed run may
create a bounded repair Node and trigger a failure-driven rerun; Reviewer is never invoked again.
When final validation is `visual` or `hybrid`, dispatch the Visual Reviewer instead. It retains the
one-Reviewer invariant while adding real-browser, vision, and rendered-evidence obligations.

### Validation budget

Prefer the smallest executable proof that closes the current boundary. Do not duplicate the same
frozen regression before and after a leaf, add a full-suite run between implementation Nodes, or
expand a command matrix merely for reassurance. The normal path is exactly one focused regression
per implementation Node and one full regression per group. Extra runs require new failure evidence,
an explicit release policy, or a direct user request.

## Model and agent assignment

Better Plan packages three versioned, network-free benchmark snapshots. They are references, not a
per-dispatch recommendation list:

- `coding_agent_catalog.json` contains measured LLM plus coding-harness combinations. Worker
  difficulty floors are `routine: 25`, `standard: 42`, `complex: 55`, and `critical: 64`. For
  hosts using benchmark routing, choose the lowest-cost measured combination in the current native
  harness at or above the Node's floor; break ties by higher coding score and stable variant ID.
  Ignore combinations absent from the table.
- `model_catalog.json` contains the model-only Intelligence Index. Designer and Reviewer choose the
  highest locally callable score without considering price. Verifier chooses the next distinct
  score when available, otherwise the highest callable score.
- `webdev_model_catalog.json` contains a complete pinned Arena WebDev Overall snapshot. Visual
  Verifier and Visual Reviewer choose the highest WebDev score among locally callable selectors,
  without considering price and without falling back to the general Intelligence Index. Arena
  WebDev is a frontend implementation benchmark; rendered browser evidence remains the independent
  visual acceptance contract.

Codex has a user-preference default matrix: Designer and Reviewer use `gpt-5.6-sol/max`, all four
Worker difficulty agents use `gpt-5.6-luna/max`, and Verifier uses `gpt-5.6-sol/high`. Visual
Verifier and Visual Reviewer use `gpt-5.6-sol/xhigh`, selected from the packaged Arena WebDev
snapshot. A qualifying existing local Codex selector supplies every role whose measured
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

A non-Codex local selector may declare `better_plan_scope: visual`. The installer considers that
selector only for Visual Verifier and Visual Reviewer, ranks it through Arena WebDev, and keeps it
out of code-role selection. This
supports one provider gateway exposing a rigorous code model and a separate vision-capable model.
Codex does not require scoped selectors and ranks its callable visual candidates through Arena
WebDev.

The installation receipt pins every created delivery role; normal updates preserve those assignments
rather than following leaderboard changes, while a later release may append a newly bundled utility
agent such as Finder. Installation output and each child's injected assignment line tell the user the
role, model, reasoning setting, and selection basis. Delivery roles also report benchmark score,
measured Worker cost when applicable, and whether the choice came from local configuration or catalog
fallback; read-only utilities report their fixed selector and mode. Routine runtime dispatch reads
the pinned native role and does not reselect a model; the child-spawn recovery heuristic below is
the only temporary exception.

### Child-spawn recovery reminder

Apply this heuristic only when a child-agent spawn is refused or fails before a child ID is
returned; do not repeat it in delegated prompts or routine progress updates. First use a bounded,
read-only host check to distinguish remote model-provider reachability from a local policy,
permission, configuration, quota, or role-selection error. Never inspect or expose credentials or
backend runtime data. If the remote provider is unreachable, stop all further work and report the
blocker to the user. If it is reachable, retry the same spawn once. If that retry also fails, retry
once with a locally callable equivalent model that preserves the role's required capabilities and
quality tier; treat this as a temporary spawn fallback, not a mutation of the installed role matrix
or receipt. If no equivalent model is available or the fallback fails, stop all further work and
report the blocker and attempted recovery steps to the user. Never advance or bind the dispatch
without a real child ID.

Treat the current installed role matrix as the only supported generation and one managed unit. If
the user explicitly asks to replace an older Better Plan setup, remove that setup from the active
agent directory and install the complete current matrix with a fresh receipt. Do not recognize or
translate legacy aliases, receipts, or role shapes, and never fall back to them at runtime. A backup
may exist only as an inert manual-recovery copy. Never replace unrelated local agents; ordinary
install and update continue to reject unowned same-name collisions.

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
- Visual Verifier: `references/visual-verifier.md`
- Reviewer: `references/reviewer.md`
- Visual Reviewer: `references/visual-reviewer.md`
