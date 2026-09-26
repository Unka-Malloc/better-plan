# Host Configuration and Role Visibility

Read this reference only before the first Better Plan role dispatch in a conversation, native role
configuration changes, installation/update/Doctor work, or host integration. Ordinary planning and
delivery turns do not load it.

Better Plan supports five targets: Codex, Claude Code, Cursor, Kilo Code, and DeepSeek Harness.
Codex is the only one with packaged role presets; every other target installs unpinned roles and
inherits its model and reasoning effort from the host and the user's own configuration.

Better Plan owns the Tree and its CLI. It installs **no Hooks, no dispatch adapter, and no lifecycle
callback**: who spawns which role, how a spawn is correlated with a result, and what the host's
concurrency limit is, all remain native host behaviour. Nothing in this package reads or writes a
host's session state.

## Stable roles

A delivery has three role names and no more:

| Role | Purpose | Codex preset selector |
|---|---|---|
| `designer` | authors the Tree: Nodes, order, executor chains, and the commands that check them | `gpt-6-astra / max` |
| `worker` | executes one Node; as many worker slots as the delivery needs dispatch here | `gpt-6-luna / max` |
| `reviewer` | audits the finished delivery against its own evidence | `gpt-6-astra / xhigh` |

A worker slot (`worker`, `worker-1`, …) is a name, not a person and not a strength tier. There is no
second kind of worker, no difficulty tier, and no per-Task role field: a Node declares the slot that
owes its outcome, and every slot is dispatched to the one installed `worker` agent. A Task that
would outgrow one session is split into more Nodes rather than promoted to a different role.

New first-install role templates contain stable identity and permission boundaries plus a reference
to `references/designer.md`, `references/worker.md`, or `references/reviewer.md` in the installed
skill. The native main forwards the dispatch's brief; the role reads that reference before acting,
so a skill update can maintain detailed workflow and reporting instructions without changing the
host role file.

Existing local roles, including older inline workflow instructions, remain immutable. A shared
reference or dispatch brief cannot override their host constraints. Report a concrete conflict to
the native main when it affects authorized work; neither recommendation drift nor an update itself
creates a new approval question. Only future first installations use the smaller templates.

## Role matrix per target

| Target | Roles installed as | Selector |
|---|---|---|
| Codex | `$CODEX_HOME/agents/{designer,worker,reviewer}.toml` | packaged, written once |
| Claude Code | `~/.claude/agents/{designer,worker,reviewer}.md` | `source=host-inheritance` |
| Cursor | `~/.cursor/agents/{designer,worker,reviewer}.md` | `source=host-inheritance` |
| Kilo Code | `better-plan.md` primary plus `better-plan-{designer,worker,reviewer}.md` Subagents under the Kilo agents directory (`KILO_CONFIG_HOME`, default `~/.config/kilo/agents`) | none |
| DeepSeek Harness | no role file at all; roles are prompts | none |

Claude Code and Cursor receive one static
`assignment: agent=<role> | role=<role> | model=host-inherited | reasoning_effort=host-inherited | source=host-inheritance`
line, because the host and the user's own configuration own that choice. Never synthesize a model or
effort for them.

Every Kilo Subagent is a leaf: the packaged files deny the Task and question tools, so a worker
cannot dispatch its own Nodes and nesting cannot recurse. Kilo pins no model, no variant, and no
reasoning effort, so each Subagent inherits the invoking primary Agent's model and the host's
default reasoning behaviour. A user may pin a Kilo-supported model as their own local configuration;
install, update, and Doctor never rewrite it.

DeepSeek Harness installs only the shared skill: it reads the shared scan directory and spawns
subagents from a prompt, so there is no role file, no pin, and no receipt to manage.

## Receipts

Codex and Kilo keep a managed receipt next to — never inside — their role directory
(`$CODEX_HOME/agents.better-plan.json`, `<kilo-config>/agents.better-plan.json`). Codex's receipt
records each file digest plus the assignment it was rendered from; Kilo's records file digests only.
Claude Code and Cursor keep no receipt: their roles are verified by comparing the installed files
with the rendered templates.

A receipt is an integrity record, never an authority. It is read, never rewritten, and a mismatch is
a report-only Doctor warning. Nothing in Better Plan turns current bytes into a fresh receipt, and a
receipt that disagrees with local files never causes a role file to be replaced.

## Codex presets

Codex writes its three selectors once at first installation and never rewrites them afterwards.
Every pin is evaluated on one standard basis: the Intelligence Index row for the model and effort it
selects. The packaged catalog records those rows at 53 for `designer`, 37 for `worker`, and 52 for
`reviewer`, each with the task cost the same table publishes (`gpt-6-astra` $3.26, `gpt-6-luna`
$0.07, `gpt-6-astra-xhigh` $2.31). No second index, harness comparison, or cross-index comparison is
used, and an API benchmark cost is never a host's subscription usage.

The catalog (`scripts/better_plan/domain/model_catalog.json`) is read for that provenance only, at
first installation, and it is the sole source of those rows: Better Plan ships no separate benchmark
dataset. A row is reference data for the pinned model and effort, not proof that a host can run it.

A role is identified by the TOML `name` in a Codex role file, never by its filename, so a renamed
file still counts as the same role and an unrelated file never does. Better Plan's installer reads
those names only to decide whether a same-name role already exists; it does not resolve, recommend,
or adopt a selector, and no command prints an installed-versus-recommended comparison. If a local
role exists, the host uses it; if none exists, the host decides what to run, and the packaged
presets above are only what a first installation writes.

## Native role immutability

An existing native role file or role receipt is immutable local host configuration. Better Plan may
install its matrix only when no same-name role configuration or receipt exists. After that first
installation, every install, update, uninstall, migration, repair, and Doctor operation must leave
all role files and receipts byte-identical while updating only skills, plugins, and adapters.

Neither a receipt mismatch nor an explicit replacement request authorizes Better Plan to edit,
remove, adopt, re-sign, or regenerate local roles. Doctor reports the integrity finding as a warning
without a repair proposal. If the user wants different native roles, that remains a manual
host-configuration operation outside the Better Plan installer; never describe a local override as a
recommendation change. Uninstall removes the selected skills, plugins, and adapters while preserving
every native role file and receipt, including when the receipt is invalid or missing.

## Additive host integration — iron rule

Protect host and user files that Better Plan did not create or does not own. General installation,
update, provider, model, routing, skill, or plugin requests never authorize replacing, overwriting,
renaming, moving, deleting, adopting, or wholesale rewriting those unmanaged files. An installation
or update request does authorize maintenance of Better Plan-owned skills, plugins, and adapters
within their existing ownership; it does not require naming each owned file again.

Create a uniquely named Better Plan-owned file, or add only the smallest authorized namespaced entry
when the host format supports a non-destructive merge. A receipt covers only artifacts or entries
Better Plan created and never converts a pre-existing file into a managed file. Uninstall removes
only owned artifacts. On a collision or replacement requirement, fail closed and leave the original
untouched. Only an explicit request naming the exact existing file and mutation can authorize it.
Existing native role files and receipts are always governed by the stricter immutability rule above,
including Better Plan-created roles; neither this update authorization nor the explicit-file
exception permits changing them.

## Skill layout

One shared payload is published per host:

- **Codex, Cursor, Kilo, and DeepSeek Harness** read the shared scan directory
  (`~/.agents/skills/better-plan`, overridable with `BETTER_PLAN_SHARED_HOME`). When that directory
  already exists it is the install target; otherwise a host's own existing skill path is refreshed,
  and on a fresh machine the shared path is created. A native duplicate left over from that choice
  is reported and removed by the installer so a host never loads two copies of the skill.
- **Claude Code** loads the skill from its plugin layout (`~/.claude/skills/better-plan`, with
  `.claude-plugin/plugin.json` and the payload under `skills/better-plan`).

Skill and plugin updates prepare a complete tree before publishing it. If publishing fails, the
installer restores the previous tree; if the filesystem prevents restoration, it retains that tree
in its staging directory for recovery. Successful updates leave no previous-version directory.

## Doctor

Doctor is read-only and reports each selected target separately:

| Target | Checks |
|---|---|
| Codex | local role matrix, installed skill structure, source comparison |
| Claude Code | local role files, plugin manifest, `claude plugin validate` when the CLI is present |
| Cursor | local role files, installed skill structure, the Cursor CLI version when it is present |
| Kilo | Agent matrix against the packaged sources, installed skill structure, `kilo agent list` when the CLI is present |
| DeepSeek Harness | installed skill structure |

Source comparison checks the shared payload once per selected install; it excludes immutable host
role files and receipts, so a successful skill comparison never means those were updated. Run Doctor
from the intended source checkout, or pass that checkout with `--source`. An installed tree compared
with itself cannot prove that an update occurred, and Doctor reports that limitation. A `FAIL` exits
non-zero; a `WARN` — drift that Better Plan must not repair, or a host CLI that is simply not
installed — does not.
