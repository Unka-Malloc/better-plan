---
name: better-plan
description: Project workflow skill for guiding an agent through a fixed execution process. Use when the user asks the agent to follow this project workflow, continue the workflow, inspect project progress, or begin from the workflow entry file.
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
- Plan writing rule, single final state: write plans as a complete convergence target, not as phased optimization, progressive refactoring, or multi-version delivery. The intended outcome is one single final state.
- Plan writing rule, no staged delivery: do not define intermediate phases as acceptable deliverables. Commit-sized Nodes may sequence execution, but they must all converge on the same final implementation.
- Plan writing rule, unique implementation: do not preserve old implementation paths, legacy fallbacks, long-lived compatibility logic, or parallel versions. All changes and optimizations must converge into the only current implementation.
- Validation rule: every fix must include real verification, such as tests, verifier runs, registry validation, generated-artifact consistency checks, or static evidence tied to the changed files and behavior.

## Status Machine Rules

Better Plan state files are validated as a lightweight workflow state machine.

1. Use exactly these statuses for Plans and Nodes:
   - `pending`
   - `in_progress`
   - `blocked`
   - `completed`
   - `skipped`

2. Use these status transitions:
   - `pending` may transition to `pending`, `in_progress`, `blocked`, or `skipped`.
   - `in_progress` may transition to `in_progress`, `completed`, `blocked`, or `skipped`.
   - `blocked` may transition to `blocked`, `in_progress`, or `skipped`.
   - `completed` may only remain `completed`.
   - `skipped` may only remain `skipped`.

3. Validate Checkpoints as a current state snapshot.
   - At most one Node may be `in_progress` in one `Checkpoints.json`.
   - A Node may be `in_progress` only when every prerequisite Node is `completed`.
   - A Node may be `completed` only when every prerequisite Node is `completed`.
   - A Node may be `completed` only when every acceptance criterion is checked.

4. Validate Plans against their referenced Checkpoints.
   - A Plan may be `completed` only when all referenced Nodes are terminal: `completed` or `skipped`.
   - A Plan may be `blocked` only when at least one referenced Node is `blocked`.
   - A Plan may be `skipped` only when no referenced Node is `in_progress`.

5. Use `scripts/manifest_tool.py transition <current> <target>` to check a single status transition.

## Step 1: Read The Plan

Goal: understand the current project progress before taking action.

1. Locate all plan-related files in the current project.
   - Search filenames and directory names for planning signals such as `plan`, `plans`, `roadmap`, `todo`, `task`, `tasks`, `milestone`, `spec`, `requirements`, `design`, `architecture`, `proposal`, `status`, `progress`, `checklist`, `notes`, `README`, `CHANGELOG`, and `TODO`.
   - Search file contents for progress markers such as `TODO`, `FIXME`, `WIP`, `milestone`, `phase`, `next step`, `done`, `blocked`, `pending`, and `in progress`.
   - Include project-management files even when their names do not contain obvious planning words, if their content describes goals, phases, decisions, or remaining work.

2. Read every relevant plan file closely.
   - Identify the stated goal of the project.
   - Extract completed work, current work, blocked work, deferred work, and explicit next steps.
   - Capture any decisions, constraints, invariants, acceptance criteria, or warnings that later workflow steps must respect.
   - Note contradictions between plan files instead of resolving them silently.

3. Trace each plan item into the codebase.
   - For every referenced feature, module, command, API, component, test, data model, configuration file, or script, open and read the involved files.
   - Use symbol and text search to find implementation paths that the plan implies but does not name directly.
   - Read tests, fixtures, migrations, generated configs, and build scripts when they determine whether a plan item is complete.
   - Follow imports and call sites far enough to understand behavior, ownership boundaries, and integration points.

4. Determine the current project state.
   - Compare the plan against the actual code.
   - Mark each important item as complete, partial, missing, unclear, blocked, or contradicted by code.
   - Distinguish evidence from inference. Cite the files or symbols that support each conclusion.
   - Identify the highest-risk gaps that could affect the next workflow step.

5. Report a concise progress snapshot before continuing.
   - Summarize the project goal.
   - List the plan files read.
   - List the code areas inspected.
   - State what appears complete, what remains, and what is uncertain.
   - Ask only for clarification that is necessary to avoid a risky assumption; otherwise continue with the workflow.

## Step 2: Establish The Better-Plan Workspace

Goal: create or reuse a dedicated workspace for all later Better Plan artifacts.

1. Identify whether the project already has a Better Plan workspace.
   - Use the plan files, directories, and project conventions discovered in Step 1. Do not depend on a fixed list of path variants.
   - Treat a directory as a Better Plan workspace only when it is clearly dedicated to this workflow, such as by explicit `better-plan` naming or existing `Manifest.json` and `Checkpoints.json` files that follow this workflow.
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
   - Every plan must have its own directory under the Better Plan workspace, even when there is only one plan.
   - Reuse an existing plan directory when the plan index or directory contents clearly identify the same plan.
   - For a new plan, create a stable lowercase hyphenated directory name based on the plan title, source filename, or dominant goal. Avoid renaming existing plan directories unless required to fix a collision.
   - Ensure every plan directory contains its own `Checkpoints.json`. Create it as an empty JSON array when it does not exist.
   - Keep all later artifacts for that plan inside its plan directory.

3. Use this Plan shape in the workspace root `Manifest.json`:

```json
{
  "id": "01234567-89ab-4def-8123-456789abcdef",
  "status": "pending",
  "title": "Plan title",
  "directory": "plan-title",
  "source_files": [
    "docs/plan.md"
  ],
  "goal": "One-sentence plan goal.",
  "description": "Short description of what this plan covers.",
  "checkpoints": "plan-title/Checkpoints.json"
}
```

4. Interpret Plan fields strictly.
   - `id`: globally unique plan ID generated only by this skill's manifest tool `uuid` command.
   - `status`: plan state. Must be exactly one of `pending`, `in_progress`, `completed`, `blocked`, or `skipped`.
   - `title`: concise human-readable plan name.
   - `directory`: relative path from the Better Plan workspace root to this plan's dedicated directory.
   - `source_files`: list of source plan files from Step 1. Use an empty list only when the plan came directly from the user request and has no source file yet.
   - `goal`: brief plan goal.
   - `description`: concrete scope of the plan and any important constraints.
   - `checkpoints`: relative path to this plan directory's checkpoint file. It must point to `<directory>/Checkpoints.json`.

5. Validate before continuing.
   - Use `scripts/manifest_tool.py validate <better-plan-workspace-root-or-state-file>` to validate the workspace root `Manifest.json` and the `Checkpoints.json` files referenced by that root index.
   - Use `scripts/manifest_tool.py uuid` to generate Plan IDs. Do not hand-write IDs or use external generators.
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
   - Use the selected manifest tool's `uuid` command to generate Node IDs. Do not hand-write IDs or use external generators.

2. Treat the plan directory checkpoints file as the execution graph.
   - The top-level JSON value must be an ordered array.
   - Each array item must be a JSON object called a Node.
   - Each Node must represent one commit-sized task: small enough to implement, validate, and commit independently.
   - Use the array order as the default execution order, while using node references to model dependencies and follow-up tasks.

3. Use this Node shape:

```json
{
  "id": "01234567-89ab-4def-8123-456789abcdef",
  "status": "pending",
  "prerequisites": [],
  "platform": "macos",
  "difficulty": "medium",
  "goal": "One-sentence task goal.",
  "description": "Detailed description of the work included in this task.",
  "acceptance_criteria": [
    {
      "checked": false,
      "text": "Describe a concrete check that proves this task is complete."
    }
  ],
  "commit": {
    "repository": ".git",
    "message": "Suggested commit message.",
    "target": "Where the work should be committed or delivered."
  },
  "next": [
    "89abcdef-0123-4567-89ab-cdef01234567"
  ]
}
```

4. Interpret Node fields strictly.
   - `id`: globally unique task ID generated only by this skill's manifest tool `uuid` command. Validators require the tool's canonical UUID format.
   - `status`: task state. Must be exactly one of `pending`, `in_progress`, `completed`, `blocked`, or `skipped`.
   - `prerequisites`: list of earlier Node IDs that must be checked and confirmed completed before this task can run. Each ID must already appear before the current Node in `Checkpoints.json`.
   - `platform`: exactly one required operating system platform, such as `macos`, `linux`, or `windows`; verify the current agent's operating system matches before running the task.
   - `difficulty`: required reasoning effort, such as `low`, `medium`, `high`, or `deep`; only run the task when the agent can use that level or higher.
   - `goal`: brief task goal.
   - `description`: concrete task scope, including files, behavior, constraints, and implementation notes when known.
   - `acceptance_criteria`: non-empty checkbox list. Each item must be an object with `checked` as a boolean and `text` as a non-empty string.
   - `commit`: expected commit or delivery information, including the target Git repository's `.git` entry, message, and delivery target.
   - `next`: list of Node UUIDs that become natural follow-up candidates after this task. Use an empty list only when no follow-up Node exists.

5. Build or update Nodes from the selected plan.
   - Convert the plan items discovered in Step 1 into commit-sized Nodes.
   - Write Nodes toward a single final state, not a phased delivery model. A Node may be small for execution, but its goal and acceptance criteria must not allow multiple versions, old paths, fallback shims, or compatibility wrappers to remain.
   - Link Nodes through `prerequisites` and `next` instead of relying only on prose.
   - Mark already completed work as `completed` only when Step 1 found code or test evidence.
   - Preserve uncertainty in `description` or `acceptance_criteria`; do not silently invent requirements.
   - Run the manifest validator after every manifest edit and fix reported issues before continuing.
