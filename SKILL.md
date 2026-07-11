---
name: better-plan
description: Project workflow skill for turning product delivery goals into an end-to-end plan with requirements, evidence, implementation checkpoints, and validation. Use when the user asks the agent to follow this project workflow, continue the workflow, inspect project progress, or begin from the workflow entry file.
---

# Better Plan

Follow this workflow in order. Treat this file as the workflow entry point.

## General Rules

- Work from the current project root unless the user gives another root.
- Preserve user changes. Do not revert or overwrite unrelated work.
- Prefer `rg` and `rg --files` for discovery.
- Read before editing. Do not implement changes until the relevant plan files and code paths have been understood.
- Keep notes grounded in file paths, symbols, tests, and observed behavior.
- Do not turn an agent's past implementation mistakes into permanent counterexamples, test cases, gates, or workflow branches. Correct the mistake once, then document and validate only the intended correct structure.
- When writing plans, checkpoints, validators, or acceptance criteria, state the required correct format and checks directly. Do not add "not this previous wrong thing" rules unless the user explicitly defines that case as a real project requirement.
- Organization rule, allowed structure: organize projects only by function, capability, domain, protocol boundary, data structure, runtime responsibility, and validation target.
- Organization rule, forbidden structure: never organize code, directories, tests, documents, registries, reports, APIs, plans, checkpoints, validators, or workflow branches by version number, migration round, historical generation, legacy stage, or compatibility era.
- Organization rule, external version exception: version identifiers are allowed only when the project already provides a mature external service and the identifier is an external protocol label, official release label, changelog/status label, or compatibility label required by that external contract. Such identifiers must not define the internal code, document, plan, checkpoint, test, registry, report, or API structure.
- Organization rule, forbidden compatibility: do not preserve legacy compatibility, old implementations, fallback shims, deprecated paths, versioned wrappers, hollow verifiers, non-current entry points, or duplicate implementations separated by labels such as `v1`, `v2`, `legacy`, or `compat`.
- Organization rule, remediation: when non-current entry points or version-shaped organization are found, refactor directly to the single current implementation organized by function and content. Do not retain compatibility layers unless they are required by an external service contract that is already in force.
- Code design rule, layering: structure implementation into modules with one responsibility per file, grouped into layers by runtime responsibility, such as interface, application or domain logic, and infrastructure. Never let one file accumulate a project's unrelated behaviors.
- Code design rule, decoupling: modules interact only through their declared interfaces, and dependencies point in one direction, from outer layers toward the domain core. Do not reach into another module's internals or share hidden mutable state across module boundaries.
- Code design rule, deliberate patterns: choose design patterns on purpose before implementation and record in `Architecture.md` why each chosen pattern earns its complexity. Do not force patterns onto code that stays simpler without them, and do not skip a pattern where it removes real coupling.
- Code design rule, file splitting: when a file gains a second responsibility, or a change no longer fits the owning module, split the file or module along responsibility boundaries instead of growing it. Keep every module independently testable.
- Plan writing rule, single final state: write plans as a complete convergence target, not as phased optimization, progressive refactoring, or multi-version delivery. The intended outcome is one single final state.
- Plan writing rule, no staged delivery: do not define intermediate phases as acceptable deliverables. Commit-sized Nodes may sequence execution, but they must all converge on the same final implementation.
- Plan writing rule, unique implementation: do not preserve old implementation paths, legacy fallbacks, long-lived compatibility logic, or parallel versions. All changes and optimizations must converge into the only current implementation.
- Validation rule: every fix must include real verification, such as tests, verifier runs, registry validation, generated-artifact consistency checks, or static evidence tied to the changed files and behavior.

## End-To-End Delivery Rules

- Treat each Plan as a product delivery contract, not only an execution task list.
- Define product requirements before implementation. The plan must state the user problem, target users or workflows, functional requirements, non-functional constraints, scope, non-goals, and final acceptance targets.
- Ground delivery decisions in evidence. Requirements, architecture, data structures, algorithms, and product gaps must cite source files, existing behavior, user-provided facts, external product references, or open-source framework practice when relevant. Do not invent product claims or acceptance targets without evidence.
- Design the architecture before implementation. Decide the module and file decomposition, the layer boundaries, the dependency direction, the interface contracts between modules, and the deliberately chosen design patterns with their rationale, before any implementation Node starts. This is what keeps implementation Nodes decoupled and lets independent Nodes proceed in parallel.
- Establish plan-local delivery artifacts before implementation when they do not already exist. Prefer `Requirements.md`, `Evidence.md`, `Architecture.md`, and `Validation.md`, or reuse equivalent project-standard documents inside the plan directory.
- Keep traceability from start to finish. Use stable requirement labels such as `REQ-001` in requirements, implementation Nodes, and validation criteria, and record them in each Node's `requirements` field. Final validation must prove the same requirements defined at the beginning, not a different target discovered later. Use `scripts/manifest_tool.py check-labels` to keep document labels and Node labels consistent whenever either side changes.
- Treat the foundation artifacts as living documents. `Requirements.md`, `Evidence.md`, `Validation.md`, and `Architecture.md` are established by the foundation Nodes but do not freeze afterward: when mid-plan work changes requirements, evidence, validation mapping, or architecture, update the artifact inside the Node that causes the change (or a new maintenance Node with the matching foundation role) rather than letting documents drift from delivery. Later foundation-role maintenance Nodes are valid as long as the first occurrence of each role keeps the required order.
- Match task difficulty to the work. Product requirements, market or product-gap analysis, architecture decisions, complex algorithms, data structures, concurrency, and security-sensitive work require `high` or `deep`; simple mechanical edits such as configuration changes may use `low` or `medium`.
- For a new product or feature plan, product requirements and evidence work must use `deep`. Use `high` only when Step 1 verified that the corresponding artifact already exists and only needs narrow maintenance. The validator enforces the `high`-or-`deep` floor for foundation and validation roles; the `deep` requirement for new-product foundation work is a workflow obligation on top of that floor.
- Do not let implementation silently redefine the product target. If evidence changes the target, update the requirements and validation mapping first, then update dependent Nodes.

## Status Machine Rules

Better Plan state files are validated as a lightweight workflow state machine. `scripts/manifest_tool.py schema plan` and `scripts/manifest_tool.py schema node` print the canonical object shapes; `references/state-files.md` documents field semantics and examples.

1. Use exactly these statuses for Plans and Nodes:
   - `pending`
   - `in_progress`
   - `blocked`
   - `completed`
   - `skipped`

2. Use these status transitions:
   - `pending` may transition to `pending`, `in_progress`, `blocked`, or `skipped`.
   - `in_progress` may transition to `in_progress`, `pending`, `completed`, `blocked`, or `skipped`.
   - `blocked` may transition to `blocked`, `in_progress`, or `skipped`.
   - `completed` may only remain `completed`.
   - `skipped` may only remain `skipped`.
   - `in_progress` to `pending` is the pause edge: the Node yields honestly so another Node can start. Do not misuse `blocked` for task switching; `blocked` is only for real external dependencies or user decisions.

3. Change Node status only through the manifest tool mutation commands. Do not hand-edit `status` values.
   - `scripts/manifest_tool.py start <node-id> [workspace]` marks a Node `in_progress`.
   - `scripts/manifest_tool.py pause <node-id> [workspace] [--reason "..."]` returns the `in_progress` Node to `pending` so a different Node can start, recording resume notes in `status_reason`.
   - `scripts/manifest_tool.py complete <node-id> [workspace] [--delivered <sha>]` marks a Node `completed` and can record the delivering commit in `commit.delivered`.
   - `scripts/manifest_tool.py block <node-id> [workspace] --reason "..."` and `scripts/manifest_tool.py skip <node-id> [workspace] --reason "..."` record the reason in `status_reason`.
   - `scripts/manifest_tool.py check <node-id> [workspace] --criterion <n> [--evidence "..."] [--evidence-file <path>] [--evidence-cmd "..."]` checks one acceptance criterion and records what verified it. Prefer `--evidence-cmd` (the verification command must exit 0 and is recorded with its exit code) and `--evidence-file` (recorded with a sha256) over prose-only evidence.
   - Mutation commands enforce the transition table and every snapshot rule before writing, and they re-derive the owning Plan's status automatically.

4. Change Node structure through the manifest tool graph commands instead of hand-editing `Checkpoints.json`.
   - `scripts/manifest_tool.py add-node [workspace] --plan <selector> ...` inserts a new pending Node with a generated UUID at a validated position; `--after <id> --splice` inserts it into that Node's outgoing chain and rewires the downstream prerequisites in one step.
   - `scripts/manifest_tool.py rewire <node-id> [workspace] ...` replaces or incrementally edits `prerequisites` and `next` with full validation.
   - `scripts/manifest_tool.py edit-node <node-id> [workspace] ...` updates Node fields through validation. Terminal Nodes are historical snapshots: `edit-node` allows only requirements-label corrections on them, and current truth belongs in the plan documents or new Nodes, never in rewritten history.

5. Validate Checkpoints as a current state snapshot.
   - At most one Node may be `in_progress` in one `Checkpoints.json`. Use `pause` to switch work honestly.
   - A Node may be `in_progress` or `completed` only when every prerequisite Node is `completed`.
   - A Node may be `completed` only when every acceptance criterion is checked.
   - A non-terminal Node whose prerequisite is `skipped` is unstartable and fails validation. Rewire its prerequisites or skip it; skip dependent Nodes before skipping their prerequisite.

6. Validate Plans against their referenced Checkpoints.
   - A Plan may be `completed` only when all referenced Nodes are terminal: `completed` or `skipped`.
   - A Plan may be `blocked` only when at least one referenced Node is `blocked`. Status derivation marks the Plan `blocked` only when the blocked Nodes leave nothing startable; a blocked Node with startable siblings keeps the Plan `in_progress`.
   - A Plan may be `skipped` only when no referenced Node is `in_progress`.
   - A Plan may not stay `pending` after Node work has started, and may not stay `in_progress` when every Node is terminal. Use `scripts/manifest_tool.py sync-plan [workspace]` to re-derive Plan statuses from their Nodes.

7. `scripts/manifest_tool.py validate` also compares every Plan and Node status against the file's git HEAD version and rejects changes that no transition path allows, such as `completed` back to `in_progress`. Run it after every state file edit; use `transition <current> <target>` to check a single edge.
   - While working inside one plan, `validate [workspace] --plan <selector>` scopes checking to that plan plus the shared index, so pre-existing issues in sibling plans do not block the current change. The full-workspace `validate` remains the close-out gate, and sibling debt must be scheduled, not ignored.
   - `validate --check-sources` verifies that `source_files` entries still resolve; run it when creating or revising a Plan index.
   - `check-labels [workspace] [--plan <selector>]` cross-checks requirement labels between plan documents and Node `requirements`; run it after editing either side.

## Step 1: Read The Plan

Goal: understand the current project progress before taking action.

1. Locate all plan-related files in the current project.
   - Search filenames and directory names for planning signals such as `plan`, `plans`, `roadmap`, `todo`, `task`, `tasks`, `milestone`, `spec`, `requirements`, `design`, `architecture`, `proposal`, `status`, `progress`, `checklist`, `notes`, `README`, `CHANGELOG`, and `TODO`.
   - Search file contents for progress markers such as `TODO`, `FIXME`, `WIP`, `milestone`, `phase`, `next step`, `done`, `blocked`, `pending`, and `in progress`.
   - Include project-management files even when their names do not contain obvious planning words, if their content describes goals, phases, decisions, or remaining work.

2. Read every relevant plan file closely.
   - Identify the stated goal of the project.
   - Identify explicit product requirements, target users, workflows, constraints, non-goals, and acceptance targets.
   - Extract completed work, current work, blocked work, deferred work, and explicit next steps.
   - Capture any decisions, constraints, invariants, acceptance criteria, or warnings that later workflow steps must respect.
   - Capture requirement labels and validation mappings when they exist. If they do not exist, mark that gap for Step 4 instead of inventing completion.
   - Note contradictions between plan files instead of resolving them silently.

3. Identify plan hierarchy and dependency relationships.
   - Classify plans before creating directories. A plan is a parent plan when it provides a shared foundation, common module, base capability, protocol, data model, runtime, or validation layer that other plans depend on.
   - Treat names such as `common`, `shared`, `base`, `core`, `foundation`, or equivalent project terms as strong hierarchy signals when their scope supports multiple child plans.
   - Treat a business-line, feature-line, product-line, integration, adapter, or customer-specific plan as a child plan when it depends on that parent foundation.
   - Treat platform and runtime targets as hierarchy signals. When delivery must adapt to multiple operating systems, devices, or runtime environments, expect one platform-neutral foundation plan and one child plan per platform, because each platform has its own development direction, constraints, and validation targets.
   - Preserve multi-level hierarchy when discovered. If a parent plan has child plans, and a child plan has more specific sub-plans, keep the same parent-to-child nesting instead of flattening the plan list.
   - Record uncertain relationships explicitly in the progress snapshot instead of silently flattening or inventing dependencies.

4. Trace each plan item into the codebase.
   - For every referenced feature, module, command, API, component, test, data model, configuration file, or script, open and read the involved files.
   - Use symbol and text search to find implementation paths that the plan implies but does not name directly.
   - Read tests, fixtures, migrations, generated configs, and build scripts when they determine whether a plan item is complete.
   - Follow imports and call sites far enough to understand behavior, ownership boundaries, and integration points.

5. Determine the current project state.
   - Compare the plan against the actual code.
   - Mark each important item as complete, partial, missing, unclear, blocked, or contradicted by code.
   - Distinguish evidence from inference. Cite the files or symbols that support each conclusion.
   - Identify whether product requirements, evidence, architecture or scaffold, implementation tasks, and validation targets align end to end.
   - Identify the highest-risk gaps that could affect the next workflow step.

6. Report a concise progress snapshot before continuing.
   - Summarize the project goal.
   - List the plan files read.
   - List the code areas inspected.
   - State any parent plans, child plans, and unresolved hierarchy questions found in Step 1.
   - State whether requirements, evidence, implementation scope, and validation targets are aligned or missing.
   - State what appears complete, what remains, and what is uncertain.
   - Ask only for clarification that is necessary to avoid a risky assumption; otherwise continue with the workflow.

## Step 2: Establish The Better-Plan Workspace

Goal: create or reuse a dedicated workspace for all later Better Plan artifacts.

1. Identify whether the project already has a Better Plan workspace.
   - Use `scripts/manifest_tool.py discover <project-root>` to find existing Better Plan workspaces by structure before relying on directory names or creating anything new.
   - Treat structure as authoritative. A directory is an existing Better Plan workspace when it contains a root `Manifest.json` that indexes Plan objects whose `directory` fields point to plan-local directories and whose `checkpoints` fields point to `<directory>/Checkpoints.json` files.
   - Reuse any structurally valid Better Plan workspace regardless of its directory name. The directory does not need to be named `better-plan`, `plan`, `plans`, or any other expected variant.
   - Treat explicit `better-plan` naming as only a weak fallback when the structure is not established yet, such as an empty workspace being initialized.
   - Do not assume a project-owned planning directory belongs to Better Plan just because it contains plans.

2. Choose the workspace location.
   - If a Better Plan workspace already exists, reuse it.
   - If the project has planning files or planning directories but no Better Plan workspace, create a separate `better-plan` directory inside the most appropriate existing planning area.
   - If the project has no planning area but has a conventional documentation area, create a `plan` directory there and use it as the Better Plan workspace.
   - If the project has neither a planning area nor a documentation area, create `docs/plan/` at the project root and use it as the Better Plan workspace.

3. Protect the workspace boundary.
   - Do not create a marker file solely to identify Better Plan. The workspace is identified by its directory choice, root `Manifest.json`, and plan directory `Checkpoints.json` files.
   - Do not overwrite unrelated project documentation. When a file or directory name would collide, choose a Better Plan-specific subdirectory or filename.

## Step 3: Create Plan Workspaces

Goal: create or reuse a dedicated directory for each plan inside the Better Plan workspace.

1. Open the Better Plan workspace from Step 2 and inspect its root `Manifest.json`.
   - The workspace root `Manifest.json` is the plan index. It records every plan managed by this Better Plan workspace and each plan's current status.
   - If the root `Manifest.json` exists, parse it as JSON and preserve all valid existing plan information.
   - If it does not exist, create it as an empty JSON array before adding plans.
   - The workspace root `Manifest.json` must only contain Plan objects. It must never contain task Node objects.

2. Create one plan directory per plan.
   - Use Step 1's plan reading to decide whether the project has one plan or multiple distinct plans.
   - Split work into separate Plans only when the outcomes can be delivered, validated, and reviewed independently after any shared prerequisites are complete. Independent business lines, product areas, integrations, adapters, or document sets may become separate Plans when they share no direct implementation dependency beyond a stable common foundation.
   - Split platform adaptation at the plan level. When delivery targets multiple operating systems, devices, or runtime environments, do not interleave platform-specific tasks inside one checkpoint graph: create one platform-neutral foundation plan plus one child plan per platform target. Each platform has its own development direction, constraints, toolchain, and validation targets, so consider each platform plan independently, and let platform plans proceed in parallel once the shared foundation is ready.
   - Keep tightly coupled work in one Plan when tasks need one checkpoint graph to express hard prerequisites. Do not rely on the root `Manifest.json` order to imply a dependency that must be enforced by `prerequisites`.
   - Use a directory-tree dependency model when deciding Plan order. The root represents the most general shared prerequisite, directories closest to the root represent common foundations and contracts, deeper branches represent consumers such as product areas, business lines, integrations, adapters, or document sets, and sibling branches represent work that can proceed independently after their shared parent is ready.
   - Record each conceptual directory level by its parent, current responsibility, and children. The parent entry should state the upstream foundation or contract this level needs; the current entry should state the capability, boundary, artifact set, or business area this level owns; the children entry should state which downstream Plans or work branches consume it or fan out from it.
   - Treat this dependency tree as a planning model, not as required filesystem structure. Do not create directories named after dependency levels, phases, or priority bands solely to mirror the tree.
   - When multiple Plans are valid, order the root `Manifest.json` by dependency and unlock value: shared foundations and common contracts first; cross-cutting infrastructure, schemas, protocols, toolchains, or reusable modules next; then independent business-line or feature Plans that can proceed in parallel once the shared base is ready; finally documentation, cleanup, release, or operator follow-up Plans unless those artifacts define a required upfront contract.
   - Every plan must have its own directory under the Better Plan workspace, even when there is only one plan.
   - Reuse an existing plan directory when the plan index or directory contents clearly identify the same plan.
   - For a new plan, create a stable lowercase hyphenated directory name based on the plan title, source filename, or dominant goal. Avoid renaming existing plan directories unless required to fix a collision.
   - Ensure every plan directory contains its own `Checkpoints.json`. Create it as an empty JSON array when it does not exist.
   - Keep all later artifacts for that plan inside its plan directory.
   - Keep top-level planning artifacts thin. The root `Manifest.json` and any plan-level summary should act as navigation and status only, not as the main design document, architecture narrative, task breakdown, or execution guide.
   - Do not create or expand top-level design documents as a substitute for checkpoint Nodes. If source material contains a high-level design, architecture proposal, roadmap, feature list, or business plan, distill it into Plan index fields only at summary level and put the actionable design, dependency, scope, risk, and execution detail into the relevant `Checkpoints.json` Nodes.

3. Apply hierarchical plan directories when plans have parent-child relationships.
   - A parent plan's directory must be the root of its child plan directories. Use the parent plan slug as the directory path for the parent plan, and put each child plan under that path.
   - Grow the plan directory tree from the top down. Upper directories hold the foundation plans that other work builds on; deeper directories hold progressively more specific branch plans; leaf directories hold the concrete delivery branches, such as one platform target, one business line, one integration, or one document set.
   - Expand the tree gradually. Create a child plan directory when its branch becomes concrete work with its own goal, description, and `Checkpoints.json`, instead of pre-creating empty structure or flattening every plan at the workspace root.
   - The parent plan keeps its own checkpoint file at `<parent-directory>/Checkpoints.json`.
   - A child plan uses `<parent-directory>/<child-directory>` as its `directory` and `<parent-directory>/<child-directory>/Checkpoints.json` as its `checkpoints` value.
   - If `common` is the shared parent plan for child plans `A`, `B`, and `C`, create plan directories `common`, `common/a`, `common/b`, and `common/c`.
   - Platform adaptation is a canonical parent-child split: keep the platform-neutral foundation in the parent plan and give each operating system or runtime target its own child plan directory, such as `core`, `core/macos`, `core/windows`. These are real plans named after real delivery branches, not directories invented to mirror abstract dependency levels.
   - When a shared foundation has multiple child plans, make the foundation the parent directory even if the user described the child plans first.
   - When a plan depends on multiple parent candidates, choose the most direct shared foundation as the directory parent and describe the other dependency in the Plan `description`.
   - Do not create an extra grouping directory unless that grouping is itself a real parent plan with its own goal, description, and `Checkpoints.json`.
   - Keep the root `Manifest.json` flat as an array of Plan objects. Express hierarchy through each Plan object's `directory` and `checkpoints` relative paths.

4. Write Plan objects in the canonical shape.
   - Use the shape printed by `scripts/manifest_tool.py schema plan`. Field semantics and a hierarchical example live in `references/state-files.md`.
   - `checkpoints` must always be `<directory>/Checkpoints.json`.
   - Generate Plan IDs with `scripts/manifest_tool.py uuid`. IDs must be UUID4 values.

5. Validate before continuing.
   - Use `scripts/manifest_tool.py validate <better-plan-workspace-root-or-state-file>` to validate the workspace root `Manifest.json` and the `Checkpoints.json` files referenced by that root index.
   - Treat invalid JSON, duplicate IDs, missing required fields, broken plan directories, or broken `checkpoints` paths as workflow issues to fix before selecting a plan for execution.

## Step 4: Build The Checkpoints

Goal: maintain the selected plan directory's `Checkpoints.json`, the ordered node tree that connects all executable tasks for that plan.

1. Select the current plan from the workspace root `Manifest.json`.
   - Prefer the plan named or implied by the user's request.
   - Otherwise choose the first non-completed, non-skipped plan whose prerequisites and status make progress possible.
   - Open that plan's dedicated directory and inspect its `Checkpoints.json`.
   - If the plan directory `Checkpoints.json` exists, parse it as JSON and preserve all valid existing task information.
   - If it does not exist, create it as an empty JSON array before adding nodes.
   - Treat invalid JSON, duplicate node IDs, missing required fields, or broken node references as workflow issues to fix before choosing an execution task.
   - Generate Node IDs with `scripts/manifest_tool.py uuid`. IDs must be UUID4 values.
   - Prefer the manifest tool's graph commands for incremental maintenance of an existing checkpoint file: `add-node` (with `--after`/`--before`/`--splice`) to insert Nodes, `rewire` to change `prerequisites`/`next`, and `edit-node` to update Node fields. They generate IDs, keep placement topologically valid, and validate before writing. Hand-write JSON only when building a new checkpoint file from scratch, and validate immediately afterward.

2. Treat the plan directory checkpoints file as the execution graph.
   - The top-level JSON value must be an ordered array.
   - Each array item must be a JSON object called a Node, in the shape printed by `scripts/manifest_tool.py schema node`. Field semantics live in `references/state-files.md`.
   - Each Node must represent one commit-sized task: small enough to implement, validate, and commit independently.
   - Use the array order as the default execution order, while using node references to model dependencies and follow-up tasks.

3. Build an end-to-end delivery graph.
   - For a new product or feature plan, use this required foundation order before implementation:
     1. Product requirements, `deep`, creates or updates `Requirements.md`.
     2. Evidence and gap analysis, `deep`, creates or updates `Evidence.md`.
     3. Validation matrix, `deep`, creates or updates `Validation.md` before code changes begin.
     4. Architecture and scaffold, `high` or `deep`, creates or updates `Architecture.md` and any initial framework.
   - Implementation Nodes must not appear before these foundation roles unless Step 1 verified the corresponding artifact is already complete. Final validation must not appear before the implementation Nodes that deliver the requirements it validates.
   - For a new product or feature plan, the first Node must be product requirements unless Step 1 confirmed complete requirements already exist. Its goal should be to clarify the product delivery contract, not to design implementation internals. This Node should create or update `Requirements.md` or the project-standard equivalent, define requirement labels such as `REQ-001`, and record users, workflows, scope, non-goals, constraints, and final acceptance targets. Use `deep` difficulty unless the user already supplied complete requirements.
   - The next foundation Node should be evidence and gap analysis unless Step 1 confirmed complete evidence already exists. This Node should create or update `Evidence.md`, cite source files and external references when used, compare relevant existing products or open-source practice when applicable, and explain why each major product, algorithm, data-structure, or architecture decision is grounded. Use `deep` difficulty unless the evidence is already complete and only needs narrow maintenance.
   - Add a validation-matrix Node before architecture, scaffold, or implementation. This Node should create or update `Validation.md`, map every requirement label to one or more tests, verifiers, generated-artifact checks, or manual acceptance checks, and define the final end-to-end acceptance target before code changes begin. Use `deep` difficulty for new product or feature plans.
   - Add an architecture and scaffold Node before feature implementation when the plan needs documents, interfaces, directories, data models, test harnesses, or framework setup. This Node should create or update `Architecture.md` and establish the initial implementation framework without pretending unfinished behavior is complete. Data models, schemas, APIs, and framework choices belong here or in later implementation Nodes, after product requirements and evidence are established.
   - Make the architecture Node answer the design questions before code grows. `Architecture.md` must record the module and directory map with one responsibility per file, the layer boundaries and dependency direction, the interface contracts between modules, and which design patterns were chosen where and why, including which parts deliberately stay pattern-free because simpler code suffices. Its acceptance criteria must check that this design record exists, not only that scaffold files were created.
   - Add implementation Nodes after requirements, evidence, validation matrix, and scaffold prerequisites. Split by product capability, domain boundary, algorithm, data structure, runtime responsibility, or validation target, and align the split with the `Architecture.md` module map: Nodes with no prerequisite path between them must own disjoint modules and files so they can be implemented in parallel, and Nodes that must change the same module must be ordered through `prerequisites`. Assign `low` or `medium` only to simple mechanical work; assign `high` or `deep` to complex logic, algorithmic work, concurrent behavior, product judgment, or security-sensitive changes.
   - Add final validation Nodes near the end with acceptance targets defined from the beginning. A final validation Node should run the mapped checks from `Validation.md` and prove the delivered product matches the initial requirements. Final validation is separate from the earlier validation-matrix Node and must not replace it.
   - Link the chain through `prerequisites` and `next`: architecture and implementation depend on requirements, evidence, and validation matrix; final validation depends on implementation and the validation matrix.
   - Keep all artifact names flexible when the project already has equivalents, but keep the roles mandatory: requirements, evidence, validation matrix, architecture or scaffold, implementation, and final validation.

4. Order Nodes by dependency and unlock value.
   - Build the Node list as a topological execution graph. A Node must appear after every Node it depends on, and those dependencies must be listed in `prerequisites`; `next` should point to the natural downstream work that becomes available afterward.
   - Use a directory-tree dependency model before flattening Nodes into the ordered array. The conceptual root is the most common prerequisite in the selected Plan; Nodes closest to the root are foundational contracts, schemas, data structures, shared modules, tools, validators, or fixtures; child branches are the modules, features, business lines, integrations, or documents that consume those foundations; leaves are specialized behavior, polish, cleanup, or operator-facing follow-up.
   - For each conceptual directory level, record the parent, current responsibility, and children before flattening. `Parent` means the direct upstream Node or capability this level relies on and what it provides. `Current` means the concrete task responsibility, artifact set, module boundary, or design contract owned at this level. `Children` means the downstream Nodes, branches, business lines, features, documents, or integrations that are unblocked by this level.
   - Interpret sibling branches as independent work unless the code or plan proves a hard dependency. Shared prerequisites should appear once near the root and fan out through `next`; do not duplicate the same foundation under each branch.
   - Flatten the dependency tree root-to-leaf into `Checkpoints.json`, preserving topological validity. The tree guides ordering and branch independence, but the persisted checkpoint file must remain the required top-level JSON array of Node objects.
   - Reorder existing Nodes when there is a concrete reason, such as fixing topological invalidity, moving shared prerequisites closer to the conceptual root, separating independent sibling branches, improving unlock value, or aligning the array with newly discovered code or plan dependencies. Preserve existing Node IDs, statuses, acceptance checks, and user-authored content while reordering. Update `prerequisites` and `next` so the graph still matches the new order, and record the reason in the affected Node `description` sections such as `Scope` or `Constraints & Risks`. Do not reorder Nodes for cosmetic neatness, phase-style storytelling, or historical chronology.
   - Put shared foundations before specialized work when they are real prerequisites. Common domain models, data schemas, storage formats, protocol contracts, core services, shared UI components, configuration systems, build/test tooling, validators, fixtures, and reusable libraries should come before business-line, integration-specific, or feature-specific Nodes that consume them.
   - Prefer Nodes that unblock the most downstream work when two tasks are otherwise independent. Use this to prioritize common contracts, APIs, data structures, and cross-cutting correctness or test infrastructure before leaf features.
   - Keep independent business lines, product areas, adapters, or feature slices independent. Do not add fake prerequisites just to force a narrative sequence; represent them as separate Plans or sibling Nodes that depend only on the shared foundation they actually need.
   - Place documentation and operator artifacts after the implementation they describe, unless the document is the source contract, design spec, API definition, schema, or migration plan that later Nodes must follow.
   - Avoid phase-shaped ordering such as "foundation phase", "feature phase", or "cleanup phase" as deliverable labels. The ordering may be foundational-to-specialized, but every Node must still be a concrete commit-sized task converging on the single final state.

5. Build or update Nodes from the selected plan.
   - Convert the plan items discovered in Step 1 into commit-sized Nodes.
   - Assign every Node the correct `role` so validators can enforce delivery order and role-specific difficulty.
   - Decompose high-level plans aggressively into Nodes. Every meaningful design decision, dependency layer, module boundary, data shape, algorithm, feature slice, integration branch, documentation contract, migration step, risk mitigation, or validation target from the top-level plan should become a Node or part of a Node description and acceptance criteria.
   - Prefer enriching `Checkpoints.json` over writing standalone top-level design prose. Create or expand a separate design document only when it is itself a required project artifact, external contract, source specification, or user-requested deliverable; even then, represent the work to create or update that document as a Node.
   - Keep Plan and Manifest text thin after decomposition. If a Plan `description` starts carrying implementation details, architecture rationale, dependency ordering, or long narrative context, move that information into the relevant Node `description` sections instead.
   - Write Nodes toward a single final state, not a phased delivery model. A Node may be small for execution, but its goal and acceptance criteria must not allow multiple versions, old paths, fallback shims, or compatibility wrappers to remain.
   - Add missing requirements, evidence, validation-matrix, architecture or scaffold, and final-validation Nodes when the current plan lacks those roles. Requirements, evidence, and validation-matrix Nodes must appear before implementation Nodes.
   - Record requirement labels in each Node's `requirements` field. Every implementation Node must list at least one requirement label, or describe in `description` why it is enabling work for a later requirement. Every final-validation Node must list the requirement labels it proves and cover all labels carried by non-skipped implementation Nodes.
   - Give every implementation Node an explicit module scope. Name in `description` the modules, directories, and files the Node owns, aligned with the `Architecture.md` module map, and the interfaces it consumes from other modules. Keep Nodes that may run in parallel on disjoint files.
   - Write each Node `description` as a structured task design brief with `Scope`, `Context`, `Target`, `Design Considerations`, `Design Value`, and `Constraints & Risks` as documented in `references/state-files.md`. Omit a section only when it truly does not apply.
   - Set `platform` to `any` unless the task genuinely requires one operating system, and match `difficulty` to the reasoning effort the task needs.
   - Keep platform-specific Nodes in their platform's child plan. Inside a platform child plan, set each Node's `platform` to that target; inside the platform-neutral foundation plan, keep Nodes at `any`. If platform-specific tasks start accumulating inside a neutral plan, return to Step 3 and split the platform work into its own child plan instead of mixing development directions in one checkpoint graph.
   - If implementation work reveals a requirement mismatch, update the requirements, evidence, and validation mapping Nodes before continuing implementation.
   - Link Nodes through `prerequisites` and `next` instead of relying only on prose.
   - Mark already completed work as `completed` only when Step 1 found code or test evidence, then run `sync-plan` so the Plan status reflects the pre-completed work.
   - Preserve uncertainty in `description` or `acceptance_criteria`; do not silently invent requirements.
   - Review every Node description before writing `Checkpoints.json`. Reject descriptions that are only a title, only a restatement of `goal`, generic filler, or missing applicable `Scope`, `Context`, `Target`, `Design Considerations`, `Design Value`, or `Constraints & Risks` content. For implementation tasks, also reject descriptions that ignore relevant design patterns, abstractions, data structures, schemas, algorithms, control flow, or error-handling considerations found in the source plan or inspected code. Reject descriptions that propose a new pattern, abstraction, data structure, algorithm, or architecture change without explaining its practical advantage over a simpler local change. A later agent should be able to understand which code or documents to inspect, which modules or feature areas are affected, what to change, why the design is worthwhile, and what to preserve without rereading the whole source plan; ordering belongs in `prerequisites` and `next`, and completion checks belong in `acceptance_criteria`.
   - Run the manifest validator after every manifest edit and fix reported issues before continuing.

## Step 5: Execute The Checkpoints

Goal: deliver the selected plan node by node with enforced status transitions.

1. Choose the execution target.
   - Run `scripts/manifest_tool.py next [workspace]` to list the resumable `in_progress` Node or the eligible pending Nodes for each plan.
   - Prefer the Node named or implied by the user's request; otherwise take the first eligible Node in array order.
   - Confirm the Node's `platform` matches the current operating system (or is `any`) and that the agent can work at the Node's `difficulty` level or higher. Do not run a Node that fails either check; pick another eligible Node or report the mismatch.

2. Start the Node with `scripts/manifest_tool.py start <node-id> [workspace]`.
   - The tool refuses to start a Node whose prerequisites are not completed or when another Node in the same plan is already `in_progress`.
   - When a different Node must run first — for example an urgent insert discovered mid-task — `pause` the running Node with a resume note instead of blocking it with a fake reason: `scripts/manifest_tool.py pause <node-id> --reason "..."`. Resume it later with `start`.
   - Never edit `status` by hand to force progress. If the tool refuses, fix the underlying state instead.

3. Implement the Node scope.
   - Follow the Node `description`, its `requirements` labels, and the plan's `Requirements.md`, `Evidence.md`, `Architecture.md`, and `Validation.md` artifacts.
   - Respect the `Architecture.md` module boundaries: work inside the modules the Node owns, and depend on other modules only through their declared interfaces.
   - Apply the code design rules while writing: keep one responsibility per file, and split a file that gains a second responsibility instead of piling new behavior into it. Do not gather the plan's code into one file for convenience.
   - If the work needs a new module, a new dependency between modules, or a changed interface contract, update `Architecture.md` within this Node before writing the coupled code, and adjust the affected dependent Nodes in the Checkpoints.
   - Keep the work inside the commit-sized scope. If the scope turns out wrong, return to Step 4 to fix the Checkpoints first, then continue.

4. Verify before completion.
   - Run the real verification each acceptance criterion demands: tests, verifier runs, generated-artifact checks, or static evidence tied to the changed files.
   - Mark each satisfied criterion with `scripts/manifest_tool.py check <node-id> --criterion <n> --evidence "<what proved it>"`. Prefer verifiable evidence: `--evidence-cmd "<verification command>"` records the command and requires it to exit 0; `--evidence-file <path>` records the artifact with its sha256.
   - Do not check a criterion without evidence that exists right now.

5. Complete the Node.
   - Commit the task's work per the Node's `commit` metadata.
   - Run `scripts/manifest_tool.py complete <node-id> --delivered <sha>` with the delivering commit, then commit the state file update.
   - The tool refuses to complete a Node with unchecked acceptance criteria or incomplete prerequisites.

6. Handle interruptions honestly.
   - If progress stops on an external dependency or a decision only the user can make, run `scripts/manifest_tool.py block <node-id> --reason "..."` and report what would unblock it.
   - If the Node simply yields to other work and remains executable, run `scripts/manifest_tool.py pause <node-id> --reason "..."` instead of `block`; blocked status is reserved for real dependencies.
   - If the Node is intentionally deferred, run `scripts/manifest_tool.py skip <node-id> --reason "..."`. Skip or rewire dependent Nodes before skipping their prerequisite; the validator rejects non-terminal Nodes whose prerequisites are skipped.

7. Validate and continue.
   - Run `scripts/manifest_tool.py validate [workspace]` after every state change and fix reported issues before continuing. When pre-existing issues in sibling plans block the current change, use `validate [workspace] --plan <selector>` as the per-change gate and schedule the sibling debt explicitly instead of ignoring it.
   - Repeat from item 1 until the plan has no eligible Nodes left.

## Step 6: Close Out The Plan

Goal: prove the delivered plan matches its original requirements and leave the state files consistent.

1. Confirm every Node in the plan is terminal: `completed` or `skipped`. Resolve stragglers through Step 5 instead of editing statuses directly.
2. Confirm the final-validation Node ran the mapped checks from `Validation.md` and that its `requirements` labels cover every label carried by non-skipped implementation Nodes. Every skipped Node must carry a `status_reason` that explains the deferral.
3. Confirm the delivered code still matches the `Architecture.md` module map, layer boundaries, dependency direction, and interface contracts, and that no file accumulated unrelated responsibilities during implementation. Resolve drift before closing: fix the code, or update the architecture decision with its new rationale.
4. Run `scripts/manifest_tool.py sync-plan [workspace]`, then the full-workspace `scripts/manifest_tool.py validate [workspace]` (not the `--plan`-scoped form), then `scripts/manifest_tool.py check-labels [workspace] --plan <selector>` for the closing plan. All must pass cleanly before reporting completion.
5. Report a closing snapshot using `scripts/manifest_tool.py status [workspace]`: what was completed, what was skipped and why, the evidence behind the acceptance targets, and any follow-up work that belongs in a new plan.
