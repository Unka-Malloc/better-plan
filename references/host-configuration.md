# Host Configuration and Role Visibility

Read this reference only before the first Better Plan role dispatch in a conversation, native role
configuration changes, installation/update/Doctor work, selector diagnosis, or host integration.
Ordinary planning and delivery turns do not load it.

Better Plan supports four hosts: Codex, Claude Code, Cursor, and Kilo Code. Codex is the only one
with packaged role presets; every other host installs unpinned roles and inherits its model and
reasoning effort from the host and the user's own configuration.

## Stable roles and current workflow guidance

New first-install role templates contain stable identity and permission boundaries plus a reference
to `references/designer.md`, `references/worker.md`, or `references/reviewer.md` in the installed
skill. The native main forwards the dispatch's `role_reference` with its complete brief. The role
reads that reference before acting; detailed workflow and reporting instructions live there so a
skill update can maintain them without changing the host role file.

Existing local roles, including older inline workflow instructions, remain immutable. A shared
reference or dispatch brief cannot override their host constraints. Report a concrete conflict to
the native main when it affects authorized work; neither recommendation drift nor an update itself
creates a new approval question. Only future first installations use the smaller templates.

## Role matrix

Better Plan installs four delivery roles per supported host:

| Role | Purpose | Codex preset selector |
|---|---|---|
| `designer` | one structured solution draft, compiled into the Plan by Python | `gpt-6-astra / max` |
| `worker` | the `worker: code` Task, whose result its own commands prove | `gpt-6-luna / max` |
| `hybrid-worker` | the `worker: hybrid` Task, which writes code and is judged visually | `gpt-6-astra / low` |
| `reviewer` | the sole writable terminal audit after complete regression | `gpt-6-astra / xhigh` |

Codex writes these four selectors once at first installation and never rewrites them afterwards.
Claude Code installs the same four roles as unpinned `~/.claude/agents/*.md` files beside its
plugin, and Cursor installs them as unpinned `~/.cursor/agents/*.md` files. Neither pins a model,
variant, or reasoning effort: each role file carries one static
`source=host-inheritance` assignment line, and the host and the user's own configuration decide what
the session runs on. Kilo Code installs the same four roles as one short primary Agent plus the
namespaced Subagents `better-plan-designer`, `better-plan-worker`, `better-plan-hybrid-worker`, and
`better-plan-reviewer`, and pins no model, variant, or reasoning effort for any of them.

Only Codex keeps a role receipt, because it is the only host whose installed files encode a packaged
choice. Claude Code and Cursor roles are verified by comparing the installed files with the rendered
templates: an edit the user made is reported, never repaired and never used to re-sign anything.

The two Workers are responsibilities, not strength tiers. `worker: code` runs on `worker` because
the Task's own commands prove its result; `worker: hybrid` runs on `hybrid-worker` because its
result is also judged visually and therefore owes rendered evidence. Every Task declares
`worker: code|hybrid`, `Verification` repeats that answer, and readiness rejects a Task that says
one thing in each field. A Plan sealed before the rename may still carry the legacy values `general`
(reads as `code`) and `frontend` (reads as `hybrid`). Dispatch looks for `hybrid-worker` only. No
Task is tiered by difficulty: there is no `Difficulty`/`Tier` field, and `Workload`
(`light|medium|heavy`) is an execution-volume estimate that selects no role.

Codex uses this explicit matrix only for first initialization; it does not import model choices from
unrelated local agents. Any existing same-name native role (identified by its TOML `name`, even
under another filename) or role receipt prevents matrix initialization, and existing role files and
receipts remain unchanged. The 2026-09-23 AA snapshots record Astra Max / XHigh / Low at
Intelligence Index 53 / 52 / 46 and Codex Luna Max at Coding Agent Index 41 ($0.1759 per task).
`designer`, `hybrid-worker` and `reviewer` are pinned to the model row for the effort they use, so
their receipts carry an Intelligence Index proxy with Coding Agent cost unset; `worker` is pinned to
the Codex Coding Agent row. Never
compare the two indices as the same scale, and never read an API benchmark cost as a host's
subscription usage.

Both routing catalogs are derived from the complete
[AA source snapshot](artificial-analysis-snapshot.json): all 673 model rows (275 current, 398
historical) and all 19 Coding Agent configurations, with every published source field preserved.
The model table uses Intelligence Index v4.3.2; the agent table uses Coding Agent Index v1.5.
Historical rows retain reference data for explicitly configured models; inclusion does not prove
local availability. Scores in the compact routing catalogs follow AA's rounded display; original
precision, component results, pricing, latency, throughput, token usage, and run versions remain in
the source snapshot. Load the snapshot only for benchmark research, never ordinary dispatch.

A complete valid installed matrix is authoritative. Use it automatically and silently; never ask the
user to choose between installed and recommended matrices, and never pause delivery for that choice.
On Codex, resolve a role by its TOML `name`, preferring the delivery project's `.codex/agents` over
personal roles in `$CODEX_HOME/agents`. A role with no model or effort pin inherits the host's
settings; report `host-default` rather than replacing it with a recommendation. Report an unreadable
or invalid requested role without silently substituting a default. The package recommendation is
only an absent-role reference and never overrides or mutates a configured role.

Show the installed-versus-recommended comparison only when the matrix is missing or invalid, or when
the user asks about role configuration. Kilo Code has no packaged selector, so there is nothing to
compare there. Render selectors as `model / effort`; when either side pins a provider, append
`@ provider` and label the other side `@ unpinned`. Mark missing roles explicitly, never infer a
provider, and never inspect credentials. Never inject this table from Hooks.

## Native role immutability

An existing native role file or role receipt is immutable local host configuration. Better Plan may
install its matrix only when no same-name role configuration or receipt exists. After that first
installation, every install, update, uninstall, migration, repair, and Doctor operation must leave all role
files and receipts byte-identical while updating only skills, Hooks, plugins, and adapters.

Neither a receipt mismatch nor an explicit replacement request authorizes Better Plan to edit,
remove, adopt, re-sign, or regenerate local roles. Doctor reports the integrity finding as a warning
without a repair proposal. If the user wants different native roles, that remains a manual
host-configuration operation outside the Better Plan installer; never describe a local override as
a recommendation change. Uninstall removes the selected skills, Hooks, plugins, and adapters while
preserving every native role file and receipt, including when the receipt is invalid or missing.

## Additive host integration — iron rule

Protect host and user files that Better Plan did not create or does not own. General installation,
update, provider, model, routing, Hook, MCP, or skill requests never authorize replacing, overwriting,
renaming, moving, deleting, adopting, or wholesale rewriting those unmanaged files. An installation
or update request does authorize maintenance of Better Plan-owned skills, Hooks, plugins, and
adapters within their existing ownership; it does not require naming each owned file again.

Create a uniquely named Better Plan-owned file, or add only the smallest authorized namespaced entry
when the host format supports a non-destructive merge. A receipt covers only artifacts or entries
Better Plan created and never converts a pre-existing file into a managed file. Uninstall removes
only owned artifacts. On a collision or replacement requirement, fail closed and leave the original
untouched. Only an explicit request naming the exact existing file and mutation can authorize it.
Existing native role files and receipts are always governed by the stricter immutability rule above,
including Better Plan-created roles; neither this update authorization nor the explicit-file
exception permits changing them.

## Selector and generation rules

The current local native role matrix is authoritative whether or not its receipt still matches. On
Codex, runtime reads the installed selector and uses the packaged selector only when no local role
exists; its four presets are written once at first installation and never rewritten. Claude Code,
Cursor, and Kilo have no packaged selector at all, so there is nothing to substitute and nothing to
compare: their roles inherit the host. Never reselect
from conversation memory or leaderboard changes. Normal updates and explicit requests both preserve
every local role byte and receipt byte. Verify that immutability first, then verify skill structure
and the separate Hook, plugin, and adapter Doctor results.

Doctor reports skill structure and source equality separately. Run it from the intended source
checkout, or pass that checkout with `--source`. An installed tree compared with itself cannot prove
that an update occurred; Doctor reports that limitation. Source comparison checks packaged files
once per shared installation and excludes immutable host role files and receipts. A successful
skill comparison does not mean existing native role instructions were updated.

## Framework and adapter boundary

Keep lifecycle truth host-neutral. Exact opaque identity preservation, one-ID-to-one-dispatch
binding, retry ceilings, Task independence, and final-callback reduction are Better Plan framework
rules. Fix defects in those invariants once in the framework; never duplicate them across native
hosts.

A host adapter owns only behavior imposed by that host's API or configuration format: native event
names and payload fields, response encoding, spawn options, capacity semantics, and the identity the
host exposes at each boundary. Each host adapter is isolated; adding or changing one must not alter
another host's event inventory or completion parser. If a new host already satisfies the shared
framework contract, its adapter stays declarative and minimal.

## Claude Code and Cursor adapters

Both hosts install the four delivery roles as unpinned Markdown agent files: Claude Code under
`~/.claude/agents/`, Cursor under `~/.cursor/agents/`. The file names are the dispatch names
(`designer`, `worker`, `hybrid-worker`, `reviewer`), so `--native-host claude` and
`--native-host cursor` return the role name as `agent_type` and the native main spawns that exact
role. Neither host receives a packaged selector: the rendered identity line reports
`model=host-inherited | reasoning_effort=host-inherited | source=host-inheritance`, because the host
and the user's own configuration own that choice. Never synthesize a model or effort for them.

Claude Code loads the skill from its plugin layout (`~/.claude/skills/better-plan`, with
`.claude-plugin/plugin.json` and the payload under `skills/better-plan`). Cursor uses the shared
Agent Skills scan path, or its native `~/.cursor/skills/better-plan` tree when that already exists.

Both install managed lifecycle handlers: Claude Code in the nested Hook map of
`~/.claude/settings.json` (`SessionStart`, `UserPromptSubmit`, `SubagentStop`), and Cursor in its
flat `hooks.json` (`version: 1`, `sessionStart`, `beforeSubmitPrompt`, `postToolUse`). The handlers
inject bounded session context and normalize a host-reported subagent completion. The native main
still owns correlation: bind every spawn with `bind-agent` and consume only the exact final callback
with `agent-complete`, exactly as for any other host.

## Kilo Task adapter

Kilo installs one short user-selectable `better-plan` primary Agent and four namespaced Subagents:
`better-plan-designer`, `better-plan-worker`, `better-plan-hybrid-worker`, and
`better-plan-reviewer`. Dispatch the exact role returned by Better Plan with the matching Kilo
`subagent_type`; never substitute Kilo's generic or explore Subagent.

Kilo Agent files pin no model, no variant, and no reasoning effort, so each Subagent inherits the
invoking primary Agent's model and the host's default reasoning behaviour. A user may pin a
Kilo-supported model as their own local configuration; install, update, and Doctor never rewrite it.

Each Kilo Task call creates an isolated child session. Preserve its returned opaque task ID exactly
for `bind-agent` and `agent-complete`. When post-repair regression returns `resume_reviewer`, resume
the same Reviewer with task_id unchanged instead of creating another Reviewer. Completion is
parent-driven because Better Plan installs no Kilo completion Hook.

Issue separate Task calls for every independently eligible frontier member in the same primary turn
so Kilo may run them concurrently.

Every Subagent is a leaf. Better Plan grants no Subagent the Task tool, so a Worker cannot dispatch
its own Nodes and nesting cannot recurse. The native main owns Task and Node dispatch, the single
task-level lifecycle record, and every join; a Worker returns its Nodes' focused evidence to the
native main, which accepts only after all of them are integrated and checked.

## Codex collaboration adapter

Forward the dispatch's `assignment_line` alongside the complete brief. It is generated from the
current resolved selector on every dispatch, not baked into a role prompt. Child roles report
host-provided runtime model and effort when available; otherwise they echo this line with its
configuration source intact, or report unknown when neither source is available. Configuration
selection is not runtime confirmation. Never infer model identity from a benchmark or old transcript.

Codex configured roles require a fresh child context. For every Designer, Worker, Hybrid Worker, or
Reviewer spawn, pass the returned Better Plan `agent_type`, set `fork_turns` to `none`, and give the
attempt a unique lower-snake `task_name`. Never combine `agent_type` with a full-history fork: Codex
inherits the parent role in that mode and rejects the configured child role.

For the Worker frontier, group dispatches by exact returned `agent_type` only to reuse the returned
assignment as a byte-identical prompt prefix. Append each Task's compiled brief afterward. The
stable prefix improves provider prompt-cache hits and Token efficiency without merging Tasks,
serializing the frontier, or reusing one live agent ID. A hybrid Task groups under its own
`hybrid-worker` assignment, so its brief never rides a `worker` prefix.

Use the active host's reported spawn capacity and counting semantics before `dispatch-task`.
Do not infer a fixed limit or whether the primary is counted: Codex's configuration key
`agents.max_concurrent_threads_per_session` excludes the primary, while a live tool may expose
a different capacity contract. The live host controls which eligible Tasks can start; keep the
rest pending until it admits more work. Capacity-limited batching is a host constraint, not permission
to merge Tasks, serialize their internal Nodes, or substitute a generically configured agent. If
the exact returned Worker role cannot start, use the existing `delegation-failed`, retry, and
`main-complete` lifecycle for that same role.

Bind the canonical `task_name` returned by Codex spawn, for example `/root/backend_worker`, without
normalization. It is the sole Better Plan host identity; a UI task/thread UUID is not equivalent.
Wait for the exact final callback from that spawned task, then have the native main invoke
`agent-complete` with the same canonical task name.

A Worker that receives no visible actionable Task must return `payload-delivery-failed`; it must not
infer a Task by scanning the workspace or selecting a nearby Plan. This checks the actual dispatch
payload only and never rejects a provider or conversion layer in advance.

Better Plan does not pre-qualify or reject a configured Codex role based on provider wire format,
conversion layers, or the presence of a particular encrypted message envelope. A locally resolved
role remains eligible for dispatch; its actual runtime result follows the normal delegation
lifecycle.

Codex has no Better Plan completion Hook. Its current subagent-stop event identifies the child by a
thread UUID rather than the canonical task name returned by spawn, so a Hook cannot correlate the
two safely—especially for parallel children using the same role. Session-start and prompt-submit
Hooks remain supported; completion stays parent-driven until Codex exposes one stable shared
identity at both boundaries.
