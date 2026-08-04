# Better Plan

Better Plan is a design-first orchestration skill for large refactors, complete migrations, and
high-risk grouped implementation work. Small tasks stay on the native main's ordinary repository
fast path: no Plan state, no Better Plan roles, and no orchestration fixed cost. It keeps the
latest user request authoritative, stores a deterministic Plan/Node state machine, and coordinates
the necessary isolated native roles:

```text
task group
  Designer once
    every code Node -> Worker -> focused regression once
    critical visual/hybrid Node -> Worker -> Visual Verifier -> focused regression once
  Reviewer or Visual Reviewer once -> developer decisions -> full regression once
```

Designer and Reviewer close the two ends of a task group. Designer predicts cross-node problems and
plans the progression once. Workers implement individual Nodes. One Visual Verifier obtains rendered
evidence only for visual or hybrid Critical Nodes. Reviewer performs one full-chain review, repairs
all autonomous findings, and returns choices that genuinely need the user.

## Repository self-maintenance

Maintaining the Better Plan source repository does not require Better Plan. Use the ordinary native repository
workflow for its code, documentation, tests, templates, installer, and releases. Do not create or
consult a repository-local `docs/plan` workspace merely to work on Better Plan itself. Temporary
workspaces are appropriate when testing product behavior.

## Progressive repository model

Better Plan separates durable architecture facts from delivery lifecycle:

```text
Capabilities.json                         Manifest.json + Checkpoints.json
observed/designed repository facts        authorized delivery history and execution
unknown -> known/untouched -> examined     pending -> in_progress -> terminal
```

`Capabilities.json` has one repository root and stable slash-path keys. A mature project's existing
root, modules, and interfaces are accepted as observed facts; they do not need retrospective design
or audit. Better Plan follows only the root-to-leaf path needed by the current request. Siblings
encountered on that path are recorded as lightweight `known/untouched` stubs and are not explored.
If a later request touches one, it is promoted to `examined/in_scope` and disclosed further only as
needed. An unknown capability is simply absent from the file.

The capability tree is structural context, not execution order. Existing observed ancestors are
already established. A newly designed foundation runs before dependent work only when delivery
Nodes carry a real `prerequisites` edge for its artifact or interface.

There is no Plan-count limit, but Better Plan searches by stable capability key and reuses or
extends an existing nonterminal Plan before creating one. Only one nonterminal task group may bind
the same capability. Completed Plans remain history; a later genuinely distinct delivery may add a
new group.

## Task-group structure

Executable work belongs in a high-cohesion, low-coupling Plan with `kind: "group"`. A nonterminal
group binds one `capability_key` already promoted to `examined/in_scope` or `modified`. It contains:

- exactly one `group_design` Node;
- one or more `implementation` Nodes; and
- exactly one trailing `final_validation` Node.

Every implementation directly depends on group design. Final validation directly depends on every
non-skipped implementation and owns the full-regression contract. `prerequisites` is the only
execution graph; Plan nesting, `next`, prose, conditions, and status reasons do not create edges.
Plans preserve the widest safe parallel frontier: independent implementation Nodes use disjoint
paths and stable interfaces and never gain an artificial prerequisite merely to serialize work.

## Roles

| role | cadence | authority | model policy |
| --- | --- | --- | --- |
| Designer | once at group opening | predicts risks and writes/refines group design and executable acceptance across multiple Nodes | strongest locally callable model-only Intelligence Index |
| Worker | once or more per implementation Node | implements frozen design and resolves ordinary build/integration defects | cheapest measured LLM + Agent combination above the Node difficulty floor |
| Visual Verifier | once after a Critical visual or hybrid Worker | exercises the real UI with browser and vision, repairs code and presentation defects, and returns rendered evidence | highest locally callable Arena WebDev tier |
| Reviewer | once after all implementation Nodes | reviews the bound capability end to end plus actually impacted shared paths, repairs autonomous issues, and returns developer choices; known untouched branches stay outside scope | strongest locally callable model-only Intelligence Index |
| Visual Reviewer | once when final validation is visual or hybrid | performs the one full-chain code and rendered-UI review and repairs autonomous findings | same Reviewer intelligence tier, in a role that requires vision and browser capability |

The model-policy column describes benchmark-routed hosts. Codex applies the explicit default matrix
below for any delivery role without a qualifying local override.

Every role is write-capable within its stated artifact boundary except that no leaf may mutate Better
Plan state, criteria, receipts, or decision history. The native main and state tool own those writes.

Designer receives the local [design-pattern decision catalog](references/design-patterns.md), reads
its decision rules and quick index, then loads only categories relevant to concrete pressure. The
catalog is read offline; ordinary design work does not fetch the website. Every material design
records whether a pattern earns its complexity, the concrete benefit, the simpler alternative, the
smallest correct application, and the costs. `none` is valid—patterns may not be used to manufacture
layers, classes, services, Plans, or Nodes.

## Three benchmark tables

The repository packages three complete, versioned, network-free benchmark snapshots:

- [`coding_agent_catalog.json`](scripts/better_plan/domain/coding_agent_catalog.json) is the Worker
  reference. It contains measured model plus coding-harness combinations. Task-difficulty floors
  are `routine: 25`, `standard: 42`, `complex: 55`, and `critical: 64`. Selection first meets the
  floor, then minimizes cost; missing Agent combinations are ignored.
- [`model_catalog.json`](scripts/better_plan/domain/model_catalog.json) is the Designer and Reviewer
  reference. It contains the model-only Intelligence Index, including current Gemini
  Flash rows. Price is not considered for these roles.
- [`webdev_model_catalog.json`](scripts/better_plan/domain/webdev_model_catalog.json) is the Visual
  Verifier and Visual Reviewer reference. It is a complete pinned snapshot of the Arena WebDev
  Overall leaderboard, which ranks models from human pairwise votes on real interactive web-app
  generation. Visual roles choose the highest WebDev score among locally callable selectors;
  price is not considered and the Intelligence Index is not used as fallback.

The tables are not a hard-coded recommendation list. Better Plan first looks for public model and
reasoning selectors in the user's existing native agent configurations. Worker considers only local
selectors whose model and reasoning setting exactly match a measured Coding Agent combination; an
omitted Worker reasoning setting is not guessed. Designer and Reviewer independently
consider local selectors found in the model-only table; Visual Verifier and Visual Reviewer use the
Arena WebDev table. If no local configuration exists, Better Plan considers only combinations
measured for the selected native harness. It never assumes that a host can call every model and
never guesses an unlisted combination.

Codex has one explicit user-preference default matrix for roles without a qualifying local match:

| Codex agent | default selector |
| --- | --- |
| Designer | `gpt-5.6-sol/max` |
| Reviewer | `gpt-5.6-sol/max` |
| Visual Reviewer | `gpt-5.6-sol/xhigh` (Arena WebDev) |
| Worker (`routine` through `critical`) | `gpt-5.6-luna/max` |
| Visual Verifier | `gpt-5.6-sol/xhigh` (Arena WebDev) |

Codex installation also adds two read-only utility agents outside the delivery lifecycle:
`finder` uses `gpt-5.3-codex-spark/xhigh`, while `fallback_finder` uses
`gpt-5.4-mini/xhigh` only when the preferred Finder is unavailable or out of quota. Independent
planning lookups should use multiple Finder instances concurrently.

Cursor has one explicit user-preference default Worker matrix for installations without a
qualifying local match:

| Cursor agent | default selector | benchmark anchor |
| --- | --- | --- |
| Worker (all tiers) | `cursor-grok-4.5-high-fast` | `grok-build-grok-4-5-high` (Coding Agent Index 64, $2.59/task) |

The row anchors to the grok-build measurement of the same model and reasoning setting, the nearest
measured row available; no cursor-cli measurement exists for that combination yet. Other Cursor
delivery roles keep the ordinary rule: a role file is omitted instead of fabricated when no
qualifying measured configuration exists.

## One-time native role creation

The installer includes ready-made role prompt templates for Codex, Claude Code, OpenCode, and
Cursor. At first installation it chooses every role assignment once, renders the host-native files,
and stores a receipt beside the native agent directory. Normal updates preserve pinned delivery-role
assignments even when the packaged tables change; they may append a newly bundled utility agent such
as Finder. To intentionally reselect delivery roles, uninstall the managed native role files and
install again.

For hosts whose code and visual models differ, a local selector agent may declare
`better_plan_scope: visual` beside its public `model` and `reasoning_effort` fields. That selector is
considered only for Visual Verifier/Reviewer assignments; ordinary local selectors continue to
supply code roles. The Kimi Claude Code alias `k3-256k` maps to the packaged Kimi K3 identity shared
by the local-capability and Arena snapshots. Codex ranks locally callable visual selectors through
the Arena WebDev snapshot.

Installation output lists every created role with its pinned model, reasoning setting, and selection
basis. Delivery roles also list benchmark score, measured Worker cost when applicable, and
local-or-fallback source; read-only utilities list their fixed selector and mode. Each child repeats
the same injected `assignment:` line so the user can see how Better Plan is actually configured. If
a host has no qualifying measured configuration for a role or difficulty, that role file is omitted
instead of being fabricated.

Templates may also be imported manually from:

- `agents/codex/`
- `agents/claude-code/`
- `agents/opencode/`
- `agents/cursor/`

This availability notice belongs in first-use guidance, not in lifecycle Hooks.

## Install

The installer and state tools support Python 3.8 or newer.

Install every supported adapter:

```sh
python3 scripts/install.py install --agents all
```

Or select hosts:

```sh
python3 scripts/install.py install --agents codex claude opencode cursor
python3 scripts/install.py update --agents codex claude opencode cursor
python3 scripts/install.py doctor --agents codex claude opencode cursor
```

The broader skill adapter also supports Copilot, Antigravity, Pi, Craft, and Kimi where applicable;
those hosts do not currently receive benchmark-pinned native Better Plan role files.

The installer fails closed on same-name native agent files it does not own. Update preserves user
changes outside the Better Plan-owned receipt. Uninstall removes only files whose current digest
still matches that receipt.

### Breaking replacement of older role files

The current native role matrix is the only supported generation. Better Plan does not preserve or
translate older aliases, receipts, role shapes, mixed-generation configurations, or runtime
fallbacks. When the user explicitly authorizes replacement, remove only the older Better Plan setup
from the active agent directory, install the complete current matrix, and create a fresh receipt.
Never displace unrelated local agents.

A displaced copy may be retained only for manual file recovery; the current release never reads or
restores it as configuration. Successful replacement leaves only the current role names active and
passes installer Doctor plus selector/receipt verification. Ordinary install and update still fail
closed on unowned collisions.

## Workspace state

A product-wide model uses one canonical workspace. Its `Capabilities.json` incrementally records
the repository foundation and disclosed capability paths. Its flat `Manifest.json` stores any
number of delivery Plans; each Plan owns a directory and a `Checkpoints.json` containing its Nodes.
Plan directory nesting expresses ownership only.

Useful commands:

```sh
python3 scripts/manifest_tool.py discover <project-root>
python3 scripts/manifest_tool.py validate <workspace>
python3 scripts/manifest_tool.py tree <workspace>
python3 scripts/manifest_tool.py tree <workspace> --details
python3 scripts/manifest_tool.py init-capabilities <workspace> \
  --key repository --title "Repository core" --description "Observed repository foundation."
python3 scripts/manifest_tool.py upsert-capability <workspace> \
  --key repository/module-a --parent repository --title "Module A" \
  --kind module --description "Module selected by the current request." \
  --disclosure examined --touch in_scope
python3 scripts/manifest_tool.py promote-capability repository/module-b <workspace> --touch in_scope
python3 scripts/manifest_tool.py bind-plan-capability <workspace> \
  --plan <group> --capability repository/module-a
python3 scripts/manifest_tool.py capability-tree <workspace>
python3 scripts/manifest_tool.py status <workspace>
python3 scripts/manifest_tool.py schema capability
python3 scripts/manifest_tool.py schema plan
python3 scripts/manifest_tool.py schema node
```

Freeze a source-grounded intent spine from the latest user request and declared `source_files`.
`tree` is the readable default projection. `tree --details` retains hidden and flattened Plans and
prints the complete details audit projection. Before handoff, compare the readable projection and
the details audit projection against that same source-grounded intent spine. State cannot authorize
unrequested work.

## Compact leaf dispatch and Worker continuation

For the first turn of each role, the native main spawns exactly the named installed agent with
`fork_turns: "none"`. The state tool returns transcript-free structured facts: the selected
`work_items`—the whole group for Designer and Reviewer—the matching role reference, bounded
capability scope, action-specific knowledge references, and necessary repository-relative paths.
The native main remains the orchestrator: it applies the primary role reference and writes a focused complete
child brief in the form best suited to the
task, emphasizing the concrete outcome, context, artifacts, constraints, risks, and acceptance
evidence that matter. It may summarize and add source-grounded observations; it must not send only
opaque IDs or selector metadata. Progressive disclosure is based on relevance rather than prompt
size: every material fact, constraint, uncertainty, dependency, risk, and acceptance condition is
disclosed honestly; only irrelevant or redundant context is omitted. A leaf may inspect the complete
Better Plan skill, orchestration or role references, repository files, and other accessible local
guidance whenever useful. Known untouched descendants remain omitted. Designer's dispatch
names `references/design-patterns.md` and requires a `design_pattern_assessment` without requiring
network access.

Each Worker turn still owns exactly one Node. After its one Visual Verifier when required, focused
regression, and acceptance close, the native main dispatches the next authorized eligible Node. If
its `worker_continuation_key` matches an idle Worker's prior key, continue the same child with the
new compact brief and bind the same agent ID; on Codex use `followup_task`. Reuse the same Worker for
ordinary correction too. Spawn only when no compatible idle Worker exists or continuation is
refused or unsafe. Independent ready Nodes remain concurrent; reuse must never serialize the ready
frontier.

Every Node declares `verification_profile: code|visual|hybrid`. `code` routes from Worker directly
to focused regression and the group Reviewer. `visual` and `hybrid` route Critical Nodes through
one Visual Verifier and add explicit `vision`,
`browser`, and rendered-evidence requirements. Source inspection, DOM text, snapshots, and build
success never substitute for exercising the real rendered UI. A final-validation Node must cover
all non-skipped implementation profiles: mixed code and visual work requires `hybrid`.

```sh
python3 scripts/manifest_tool.py next-action <node-id> <workspace> --native-host codex
python3 scripts/manifest_tool.py dispatch <node-id> <workspace> --role designer --native-host codex
python3 scripts/manifest_tool.py dispatch <node-id> <workspace> --role worker --native-host codex
python3 scripts/manifest_tool.py dispatch <node-id> <workspace> --role visual-verifier --native-host codex
python3 scripts/manifest_tool.py dispatch <node-id> <workspace> --role reviewer --native-host codex
```

For Codex, the payload resolves the exact installed role TOML first and freezes its model, reasoning
effort, and public provider selector. A missing or invalid installed role falls back to the packaged
Codex recommendation. The native main passes the returned explicit model and effort to the spawn;
it never relies on stale host metadata. If neither configuration exists, the payload enters
`main_thread_fallback` without attempting a child.

A complete valid installed matrix always wins automatically. First-use reporting may compare it
with the packaged defaults for visibility, but must never ask the user to choose between them or
pause dispatch for such a choice. Packaged defaults are only per-role fallbacks for a missing or
invalid installed selector and never replace the installed matrix.

After a real native spawn, bind its opaque child-agent identity:

```sh
python3 scripts/manifest_tool.py bind-agent <node-id> <workspace> \
  --dispatch-id <better-plan-dispatch-id> --agent-id <native-child-id>
```

A short wait, temporary lack of output, elapsed wall-clock time, missing artifacts, or context
compaction is not a failure. Concrete ongoing progress means the role is still working. Never
interrupt or cancel a bound child to accelerate delivery or manufacture recovery evidence; a
main-initiated `interrupted` or `cancelled` status cannot consume an attempt. Keep waiting unless a
new user request supersedes the work. When the host conclusively refuses a spawn or independently
reports the exact child as terminally failed, record the failure:

```sh
python3 scripts/manifest_tool.py delegation-failed <node-id> <workspace> \
  --dispatch-id <better-plan-dispatch-id> --spawn-refused
python3 scripts/manifest_tool.py delegation-failed <node-id> <workspace> \
  --dispatch-id <better-plan-dispatch-id> --terminal-failed-agent-id <failed-child-id>
```

Use `--unavailable` instead only when the host or provider conclusively reports that delegation is
unavailable. A bare failure record is rejected, so silence or a bounded wait expiry cannot consume
an attempt.

Visual Verifier permits one child attempt before native-main fallback. Every other dispatch permits
at most three delegation attempts: pinned role, one same-role retry, and one capability-equivalent
temporary fallback. At the ceiling, the native main performs the same role
contract from the bounded payload and records completion without inventing a child identity:

```sh
python3 scripts/manifest_tool.py main-complete <node-id> <workspace> \
  --dispatch-id <better-plan-dispatch-id> --role designer|worker|visual-verifier|reviewer
```

This preserves all acceptance, visual evidence, regression, and one-Reviewer boundaries while
preventing endless redispatch or task interruption caused solely by delegation failure.

Spawn return is not completion. State advances only when the host sends
an unambiguous final callback for that exact bound child:

```sh
python3 scripts/manifest_tool.py agent-complete <node-id> <workspace> \
  --dispatch-id <better-plan-dispatch-id> --agent-id <native-child-id> --final
```

Early, unrelated, unbound, mismatched, and replayed callbacks are no-ops. A completion may advance
only its current Node and never auto-selects another Node. The native main serializes `dispatch`
state writes, starts every safely eligible native Worker spawn concurrently, and serializes
`bind-agent` writes as host IDs return. Spawn calls and child executions overlap; state writes do not.
Multiple implementation Nodes in one group, and multiple groups, may have active children because
correlation uses the bound child ID rather than a singleton.

## Implementation and group closure

Every code-profile Worker completion runs the declared focused regression directly, including
Critical code Nodes. Only a Critical visual or hybrid Node routes through one Visual Verifier, which
repairs rather than merely reports and must exercise the real UI with browser and vision. A stale
regression contract is corrected and rerun directly without another Visual Verifier. A passing run
completes the implementation Node; failure returns `main_correction_decision`. Exceptional security
review is an explicit implementation Node executed by a Worker, not a universal role stage.

After all implementation Nodes complete, dispatch the code or visual Reviewer selected by final
validation directly. That Reviewer runs once, repairs
the whole group, and returns structured choices. After those choices are recorded, the native main
submits:

```sh
python3 scripts/manifest_tool.py advance <final-node-id> <workspace> \
  --event reviewer-finished --dispatch-id <reviewer-dispatch-id>
```

The state tool runs full regression once. It aggregates every command failure, retains privacy-safe
diagnostic summaries, and can reuse successful command receipts when `command_paths` prove their
inputs are unchanged. If it fails, `repair-plan` atomically adds and registers a bounded repair
Node; completing that repair triggers only the necessary failure-driven rerun. Reviewer is not
invoked again.

The normal validation budget is therefore one focused regression per implementation Node and one
full regression per task group. Leaf agents may run small diagnostics while repairing, but Better
Plan does not duplicate frozen regressions or insert extra full-suite runs without failure evidence,
an explicit release rule, or a direct user request.

## User decisions

Reviewer choices belong to the owning group Plan:

```sh
python3 scripts/manifest_tool.py record-decision <workspace> --plan <group> \
  --urgency immediate --question "..." --context "..." \
  --option "..." --option "..."

python3 scripts/manifest_tool.py resolve-decision <decision-id> <workspace> \
  --plan <group> --resolution "..."
```

`immediate` means the native main reports the issue to the user now; every immediate item must be
resolved and applied before `reviewer-finished` may continue. `deferred` means work may close safely
first, but the item must appear in final handoff. `status` labels both timings explicitly.

## Hooks

Supported Hooks add bounded guidance for session start and prompt submission and reduce an exact
final child completion. They do not advertise templates, choose models, start agents, treat spawn
return as completion, continue a stopped child, poll work, or select another Node. Host-native child
lifetime and cancellation remain outside Better Plan.

## References

- [State files](references/state-files.md)
- [Host configuration](references/host-configuration.md)
- [Native main](references/orchestration-main.md)
- [Designer](references/designer.md)
- [Design-pattern decision catalog](references/design-patterns.md)
- [Worker](references/worker.md)
- [Visual Verifier](references/visual-verifier.md)
- [Reviewer](references/reviewer.md)
- [Visual Reviewer](references/visual-reviewer.md)

## Development

Run focused tests while changing one subsystem. Run the complete suite once after all changes are
integrated:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```
