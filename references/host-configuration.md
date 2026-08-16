# Host Configuration and Role Visibility

Read this reference only before the first Better Plan role dispatch in a conversation, native role
configuration changes, installation/update/Doctor work, selector diagnosis, or host integration.
Ordinary planning and delivery turns do not load it.

## Role matrix

Better Plan installs four delivery roles per supported host:

| 角色 | 用途 | 推荐选择器 |
|---|---|---|
| `designer` | 单次完成结构化方案草稿，由 Python 编译 Plan | `gpt-5.6-sol / xhigh` |
| `worker-standard` | 经济档：普通有界 Task | `gpt-5.6-luna / max` |
| `worker-complex` | 强力档：高风险或结构耦合 Task | `gpt-5.6-sol / medium` |
| `reviewer` | 全量回归后的唯一可写终审，审计源码、测试、诊断与渲染证据 | `gpt-5.6-sol / max` |

When the local OpenCode runtime exposes the complete curated OpenCode Go selector set, its first
installation pins `designer` and `reviewer` to `opencode-go/kimi-k3 / max`, `worker-standard` to
`opencode-go/deepseek-v4-flash / high`, and `worker-complex` to
`opencode-go/gpt-5.6-luna / max`. The installer reads only the bounded public selector inventory
from `opencode models opencode-go`; it never inspects credentials. It creates no partial matrix when
one of those selectors is unavailable.

A complete valid installed matrix is authoritative. Use it automatically and silently; never ask the
user to choose between installed and recommended matrices, and never pause delivery for that choice.
The package recommendation is only a per-role fallback for an absent, unreadable, unsafe, or
model-less role, and never overrides or mutates an installed role.

Show the installed-versus-recommended comparison only when the matrix is missing or invalid, or when
the user asks about role configuration. Render selectors as `model / effort`; when either side pins a
provider, append `@ provider` and label the other side `@ unpinned`. Mark missing roles explicitly,
never infer a provider, and never inspect credentials. Never inject this table from Hooks.

## Native role immutability

An existing native role file or role receipt is immutable local host configuration. Better Plan may
install its matrix only when no same-name role configuration or receipt exists. After that first
installation, every install, update, migration, repair, and Doctor operation must leave all role
files and receipts byte-identical while updating only skills, Hooks, plugins, and adapters.

Neither a receipt mismatch nor an explicit replacement request authorizes Better Plan to edit,
remove, adopt, re-sign, or regenerate local roles. Doctor reports the integrity finding as a warning
without a repair proposal. If the user wants different native roles, that remains a manual
host-configuration operation outside the Better Plan installer; never describe a local override as
a recommendation change.

## Additive host integration — iron rule

Treat every pre-existing host or user file as immutable. General installation, update, provider,
model, routing, Hook, MCP, or skill requests never authorize replacing, overwriting, renaming,
moving, deleting, taking receipt ownership of, or wholesale rewriting an existing file.

Create a uniquely named Better Plan-owned file, or add only the smallest authorized namespaced entry
when the host format supports a non-destructive merge. A receipt covers only artifacts or entries
Better Plan created and never converts a pre-existing file into a managed file. Uninstall removes
only owned artifacts. On a collision or replacement requirement, fail closed and leave the original
untouched. Only an explicit request naming the exact existing file and mutation can authorize it.

## Selector and generation rules

The current local native role matrix is authoritative whether or not its receipt still matches.
Runtime reads the installed selector and uses the packaged selector only when no local role exists.
Never reselect from conversation memory or leaderboard changes. Normal updates and explicit
requests both preserve every local role byte and receipt byte. Verify that immutability first, then
verify skill structure and the separate Hook, plugin, and adapter Doctor results.

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

## Kilo Task adapter

Kilo installs one short user-selectable `better-plan` primary Agent and four namespaced Subagents:
`better-plan-designer`, `better-plan-worker-standard`, `better-plan-worker-complex`, and
`better-plan-reviewer`. The primary Agent's ordered Task permission map denies every other
Subagent. Dispatch the exact role returned by Better Plan with the matching Kilo
`subagent_type`; never substitute Kilo's generic or explore Subagent.

Each Kilo Task call creates an isolated child session. Preserve its returned opaque task ID exactly
for `bind-agent` and `agent-complete`. When post-repair regression returns `resume_reviewer`, resume
the same Reviewer with task_id unchanged instead of creating another Reviewer. Completion is
parent-driven because Better Plan installs no Kilo completion Hook.

Issue separate Task calls for every independently eligible frontier member in the same primary turn
so Kilo may run them concurrently. The packaged Subagents intentionally omit `model`, `variant`, and
provider-specific reasoning options: each inherits the invoking primary Agent's model and uses that
host selection's default reasoning behavior. Users may manually pin a Kilo-supported model and
variant as local immutable host configuration; install, update, and Doctor never rewrite it.

## Codex collaboration adapter

Codex configured roles require a fresh child context. For every Designer, Worker, or Reviewer
spawn, pass the returned Better Plan `agent_type`, set `fork_turns` to `none`, and give the attempt a
unique lower-snake `task_name`. Never combine `agent_type` with a full-history fork: Codex inherits
the parent role in that mode and rejects the configured child role.

Codex collaboration capacity is bounded and includes the native main. Inspect current capacity
before `dispatch-task`, then dispatch only the eligible Tasks that can be spawned immediately. Keep
the rest pending until a slot opens. Capacity-limited batching is a host constraint, not permission
to merge Tasks, serialize their internal Nodes, or substitute a generic `worker`. If the exact
`worker-standard` or `worker-complex` role cannot start, use the existing `delegation-failed`, retry,
and `main-complete` lifecycle for that same role.

Bind the canonical `task_name` returned by Codex spawn, for example `/root/backend_worker`, without
normalization. It is the sole Better Plan host identity; a UI task/thread UUID is not equivalent.
Wait for the exact final callback from that spawned task, then have the native main invoke
`agent-complete` with the same canonical task name.

Codex may deliver the Task body as encrypted content after a plaintext `Payload:` marker. A Worker
that cannot see an actionable Task after that marker must fail closed with `payload-delivery-failed`;
it must not infer a Task by scanning the workspace or selecting a nearby Plan.

Codex Multi-Agent V2 is not plain OpenAI-compatible message forwarding. It relies on Responses API
extensions that carry an encrypted tool argument into an `agent_message` containing
`encrypted_content`. A provider or model that implements only basic OpenAI-compatible plaintext
Chat Completions or Responses requests is therefore ineligible for Codex role dispatch. Compatibility
must be proven end to end for this exact exchange; an OpenAI-compatible label alone is insufficient.
Better Plan never strips, decrypts, or downgrades this payload to plaintext. When the configured role
cannot consume the exchange, preserve the exact role, fail closed through the normal delegation
lifecycle, and return the Task to the native main after retry exhaustion.

Codex has no Better Plan completion Hook. Its current subagent-stop event identifies the child by a
thread UUID rather than the canonical task name returned by spawn, so a Hook cannot correlate the
two safely—especially for parallel children using the same role. Session-start and prompt-submit
Hooks remain supported; completion stays parent-driven until Codex exposes one stable shared
identity at both boundaries.
