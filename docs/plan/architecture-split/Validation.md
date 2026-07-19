# Validation

## Acceptance design

- Architecture tests assert dependency direction, thin entrypoints, canonical imports,
  module-size ceilings, and absence of removed top-level implementations.
- The workflow-core oracle maps every declared symbol to exactly one canonical module:
  `WorkflowStateMachine` to `domain.models`, `transition` to `domain.transitions`,
  `validate_design_contract` to `domain.design`, `reference_for_action` to
  `domain.roles`, `validate_checkpoints_data` to `domain.validation`, `NodeLocation`
  to `infrastructure.workspace`, `run_regression_at_location` to
  `infrastructure.regression`, `advance_command` to `application.workflow`, and
  `main` to `adapters.manifest_cli`. Runtime `__module__` checks and AST ownership
  checks reject duplicate definitions and compatibility re-exports.
- Dependency checks cover every workflow package layer and reject upward imports,
  runtime imports, `ImportError` fallback ladders, wildcard cross-layer imports, and
  package-level `sys.path` mutation. Only the direct executable may use one exact,
  fixed repository-root bootstrap before delegating to the CLI adapter.
- The `manifest_tool.py` oracle permits only its docstring, the fixed bootstrap,
  whitelisted imports, and `SystemExit(manifest_cli.main())`; it also executes the
  bounded `--help` contract.
- Fault fixtures prove the oracle detects a misplaced symbol, application-to-adapter
  dependency, business logic in the entrypoint, fallback imports, a legacy module,
  and a module one line beyond the size ceiling.
- Existing manifest, acceptance, Hook, installer, and role suites remain behavioral
  regression oracles after their imports move to the canonical package.
- Agent-completion tests cover correlated role exits, focused regression routing,
  bounded repair attempts, auditor routing, and main-thread decision handoff.
- No Better Plan application component observes Agent elapsed time or owns host
  interruption. Until the host emits Agent completion, the workflow performs no result
  transition.
- Hook architecture tests assign workspace detection and lifecycle handling to unique
  package modules, require a behavior-free executable with a live `--help` contract,
  reject the two removed top-level implementations, and forbid lifecycle imports of
  workflow state-write APIs. Fault fixtures prove both legacy-file and business-entry
  defects are observable.
- Installer architecture tests assign immutable paths and inventory to
  `installation.models`, atomic tree operations to `installation.skills`, platform
  side effects to `installation.targets`, read-only checks to `installation.doctor`,
  use-case composition to `installation.service`, Hook JSON ownership to
  `hooks.config`, and argument/output handling to `adapters.install_cli`. The direct
  `scripts/install.py` executable is limited to one fixed import bootstrap and
  `SystemExit(install_cli.main())`.
- The installer oracle requires `InstallPaths`, `copy_skill_tree`, `install_target`,
  `remove_target`, `doctor`, `install_agents`, `uninstall_agents`, `uninstall_hooks`,
  `install_hook_config`, `uninstall_hook_config`, and the installer `main` to have one
  canonical owner. AST ownership and runtime `__module__` checks enforce those owners
  while preserving the two declared adapter owners of the shared `main` symbol. It
  rejects upward installer dependencies, business logic in the executable, the removed
  top-level Hook configuration module, stale payload inventory entries, and modules
  above the common size ceiling.
- Installer behavior remains covered by temporary-home installation, update,
  uninstallation, Hook-only removal, detector-gated lifecycle execution, diagnostics,
  optional runtime checks, WSL discovery, privacy-safe output, and complete current
  payload inventory tests. Full uninstallation checks both dry-run and applied message
  streams and rejects disclosure of the temporary installation root's absolute path.
- Final architecture acceptance constructs a synthetic source tree containing every
  `CURRENT_SKILL_FILES` entry plus one unlisted runtime marker, installs it through the
  canonical copier, and requires the target file set to equal the allowlist exactly.
- Skill metadata acceptance verifies the `SKILL.md` name and non-empty description plus
  the OpenAI agent display name, short description, default prompt, and `$better-plan`
  invocation without adding a YAML runtime dependency.
- Each implementation Node runs only its focused suite. The final Node runs one complete
  test discovery, workspace/source validation, requirement-label validation, and skill
  metadata validation on the final fingerprint.

Evidence is limited to command digests, exit codes, timestamps, and content
fingerprints. A fresh read-only auditor decides each Node after regression succeeds.
