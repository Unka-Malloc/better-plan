# Host Configuration and Role Visibility

Read this reference for native role
configuration changes, installation/update/Doctor work, or host integration. Ordinary planning and
delivery turns do not load it.

Better Plan supports five targets: Codex, Claude Code, Cursor, Kilo Code, and DeepSeek Harness.
Codex has packaged model presets for Designer, Worker, and Reviewer. The new Verifier
profile has no model or reasoning selector and inherits host configuration. Other
targets likewise inherit model and reasoning settings; DeepSeek Harness uses prompts
instead of native role files.

Better Plan owns the Tree and its CLI. It installs **no Hooks, no dispatch adapter, and no lifecycle
callback**: who spawns which role, how a spawn is correlated with a result, and what the host's
concurrency limit is, all remain native host behaviour. Nothing in this package reads or writes a
host's session state.

## Optional packaged roles

Fresh installations offer four native role profiles. The workflow starts one
persistent Verifier by default alongside Main and parallel Workers; Designer shapes
the work and Reviewer independently closes stable milestones and the final result.
A native profile loads instructions; it does not automatically launch a process:

| Role | Purpose | Codex preset selector |
|---|---|---|
| `designer` | authors current Tasks, Nodes, dependencies, requirements, and scoped checks | `gpt-6-astra / xhigh` |
| `worker` | implements assigned code; no quality/process/integration ownership or required evidence pack | `gpt-6-luna / max` |
| `verifier` | persistently inspects actual code, integrates, checks, and repairs throughout execution | host-inherited; no model or effort pin |
| `reviewer` | independently validates and repairs stable milestone and final code against user requirements, then records conclusions | `gpt-6-astra / xhigh` |

A worker slot (`worker`, `worker-1`, …) is a name, not a person and not a strength tier. The packaged
worker profile handles an assigned Node or bounded repair. Tasks describe outcomes, Nodes describe
coherent contributions, and Draft PRs mark reviewable delivery boundaries. A PR may cover related
Tasks, and a Node's resulting revision may contain multiple commits; record the actual relationships.

Main owns requirements, dispatch, and process. Verifier runs persistently alongside
it, independently inspects and integrates Worker code, and arranges repairs. Main
forwards technical repair assignments unchanged when the host prevents direct
dispatch. Reviewer receives requirements and immutable milestone code while Verifier
continues elsewhere. For whole-plan final takeover, all Workers finish, Verifier
regresses and notifies Main, and Main stops Verifier before final review. No upstream
proof pack is required. See `references/main.md` for the native handoff.

Existing installations preserve their user-owned role files and assignment settings.
A narrow upgrade exception adds the missing packaged Verifier profile and its necessary
receipt entry where ownership is known and no same-name role or destination conflicts.
It never changes existing model, tool, or permission settings, replaces a custom
Verifier, or adopts unrelated files. A collision or uncertain ownership is reported
without overwriting the conflicting configuration. The workflow can use the Verifier
guide with an authorized host agent while the user resolves that host setup.
Host concurrency and lifecycle limitations remain real; report them rather than claim
that installing a profile started a running agent.

Role prompt content identifies the role and loads its maintained guidance. It does
not repeat model, effort, provenance, repository rules, or workflow instructions.
Host configuration and receipts retain configuration facts outside the prompt.

Existing local roles, including older inline workflow instructions, keep their host-owned fields;
install and update refresh their prompt content from the current template. A shared reference or
dispatch brief cannot override host constraints. Report a concrete conflict to the native main when
it affects authorized work; neither recommendation drift nor an update itself creates a new approval
question. Report the conflicting instruction and affected operation before dependent
work. Do not treat a template difference alone as a conflict or as authority to replace
local roles.

## Role matrix per target

| Target | Roles installed as | Selector |
|---|---|---|
| Codex | `$CODEX_HOME/agents/{designer,worker,verifier,reviewer}.toml` | three packaged pins; Verifier host-inherited; existing selectors preserved |
| Claude Code | `~/.claude/agents/{designer,worker,verifier,reviewer}.md` | host-inherited |
| Cursor | `~/.cursor/agents/{designer,worker,verifier,reviewer}.md` | host-inherited |
| Kilo Code | `better-plan.md` primary plus `better-plan-{designer,worker,verifier,reviewer}.md` Subagents under the Kilo agents directory (`KILO_CONFIG_HOME`, default `~/.config/kilo/agents`) | none |
| DeepSeek Harness | no role file at all; roles are prompts | none |

Claude Code and Cursor inherit model and effort from host configuration; no identity
or selector metadata is injected into the working prompt.

Every Kilo Subagent is a leaf: the packaged files deny the Task and question tools, so a worker
cannot dispatch its own Nodes and nesting cannot recurse. Kilo pins no model, no variant, and no
reasoning effort, so each Subagent inherits the invoking primary Agent's model and the host's
default reasoning behaviour. A user may pin a Kilo-supported model as their own local configuration;
install, update, and Doctor never rewrite it.
Do not add dispatch-time model, provider, variant, or effort overrides to enable
Verifier or Reviewer delegation: Kilo uses the invoking host's current selection. Model capability,
artifact authority, and tool permission are separate concerns. The packaged Kilo
Verifier and Reviewer remain leaves because their `task: deny` fields are host
configuration. Main forwards bounded repair assignments and code locations; Verifier
or Reviewer independently inspects the returned code according to the current phase.

DeepSeek Harness installs only the shared skill: it reads the shared scan directory and spawns
subagents from a prompt, so there is no role file, no pin, and no receipt to manage.

## Receipts

Codex and Kilo keep a managed receipt next to — never inside — their role directory
(`$CODEX_HOME/agents.better-plan.json`, `<kilo-config>/agents.better-plan.json`). Codex's receipt
records each file digest plus the assignment it was rendered from; Kilo's records file digests only.
Claude Code and Cursor now keep a Verifier-only ownership receipt at
`<host-home>/agents.better-plan.json`: schema version 1, the target host, and a `files`
map containing only `verifier.md` and its SHA256 digest. Older three-role installations
had no such receipt. This narrow record distinguishes the new managed profile from
a same-name custom role without adopting the other files; role templates are still
compared independently. Missing or invalid ownership records never authorize replacing
an existing Verifier.

A receipt is an integrity record, never an authority. A prompt refresh rewrites the digests of the
files it maintained and keeps the recorded assignment provenance; a mismatch outside that refresh is
a report-only Doctor warning. Doctor never turns current bytes into a fresh receipt, and a receipt
that disagrees with local files never causes a role file to be replaced.

## Codex presets

Codex writes its three pinned selectors once at first installation and never rewrites
them afterwards. The fourth Verifier profile has no selector; it inherits host defaults.
Role prompt content is refreshed by install and update.
Every pin is evaluated on one standard basis: the Intelligence Index row for the model and effort it
selects. The packaged catalog records those rows at 52 for `designer` and `reviewer` and 37 for
`worker`, each with the task cost the same table publishes (`gpt-6-astra-xhigh` $2.31, `gpt-6-luna`
$0.07). No second index, harness comparison, or cross-index comparison is
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

## Native role configuration and prompt refresh

An existing native role file is split by ownership. Model, provider, variant, reasoning effort,
tool, permission, and sandbox fields are host configuration: install, update, uninstall, migration,
repair, and Doctor leave them byte-identical. Description and instruction text are skill-owned:
install and update refresh them from the current packaged template, preserve every host-owned field,
and refresh the receipt digests to match. A role file without a recognizable prompt structure is
left untouched. After first installation, Better Plan never removes role files; the
only addition allowed is the narrow missing-Verifier upgrade described above.

Neither a receipt mismatch nor an explicit replacement request authorizes changing host-owned fields
or rewriting prompts outside install and update. Doctor reports the integrity finding as a warning
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
Existing native role files and receipts are always governed by the native-role rule above,
including Better Plan-created roles; neither this update authorization nor the explicit-file
exception permits changing host-owned fields or rewriting prompts outside install and update.

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
| Codex | local role names, receipt integrity, role template comparison, installed skill structure, source comparison |
| Claude Code | local role files, Verifier receipt, plugin manifest, `claude plugin validate` when the CLI is present |
| Cursor | local role files, Verifier receipt, installed skill structure, the Cursor CLI version when it is present |
| Kilo | Agent matrix against the packaged sources, installed skill structure, `kilo agent list` when the CLI is present |
| DeepSeek Harness | installed skill structure |

Source comparison checks the shared payload once per selected install; it excludes native host
role files and receipts, so a successful skill comparison never means those were updated. Run Doctor
from the intended source checkout, or pass that checkout with `--source`. An installed tree compared
with itself cannot prove that an update occurred, and Doctor reports that limitation. A `FAIL` exits
non-zero; a `WARN` — drift that Better Plan must not repair, or a host CLI that is simply not
installed — does not.

Role receipt integrity and current template consistency are independent Doctor results.
An old unmodified role can match its original receipt while differing from current
templates. A user-edited role can match current instructions while differing from the
original receipt. Neither result causes replacement; only an install or update prompt
refresh rewrites receipt digests. Codex template comparison uses native role names and
instruction fields, not model selectors.
