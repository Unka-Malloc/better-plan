# Hook Safety Architecture

> Completed delivery record. The current session/task alignment contract is defined by `../task-plan-alignment/`; this Plan's terminal Nodes are not reopened.

## Boundaries

- `scripts/hook_scope.py` owns the single automatic decision: whether one host event belongs to a repository that already uses Better Plan.
- `scripts/manifest_tool.py` owns structural workspace validation, state transitions, regression execution, safe evidence records, and relative presentation.
- `scripts/hook_tool.py` owns host payload normalization and response translation. It delegates activation to `hook_scope` and remains a fail-open advisory adapter.
- `scripts/hook_config.py` owns managed handlers and portable command construction.
- `scripts/install.py` owns automatic skill and managed Hook delivery.

Dependency direction remains `install -> hook_config` and `host -> hook_tool -> hook_scope -> manifest_tool`.

## Activation contract

1. Every managed Hook invocation calls `hook_scope` before loading active Nodes or choosing a regression.
2. The detector prefers the event `cwd`; if absent, it accepts `workspace_roots` only when it contains one unique root.
3. The detector resolves the nearest repository boundary and activates only when exactly one structural Better Plan workspace belongs to it. A direct structural Manifest input is also explicit.
4. `hook_tool` activates lifecycle enforcement only when that detected workspace has exactly one active Node.
5. Every absent, ambiguous, or invalid detection returns an empty object without asking an agent to configure or select anything.

The platform predicate protects the unique active Node at the manifest `start` transition and again before Stop-time regression.

## Continuation contract

Stop may request one continuation only. A true `stop_hook_active` or positive Cursor `loop_count` returns an empty response. Regression failure responses contain a safe summary and never interpolate captured output or exception text.

## Evidence contract

- File evidence accepts a repository-relative path confined to the project root and stores that path plus a digest.
- Command evidence discards output and stores a SHA-256 digest of the command, exit success, and timestamp.
- Free-form evidence is one-line, bounded, and rejected when it resembles a concrete absolute path or secret-bearing value.
- CLI paths are rendered relative to the relevant repository or search root; installer and doctor messages use logical target names instead of concrete locations.

## Installation contract

Skill installation and update may write one managed Stop handler per selected supported host. The handler always enters through the automatic scope detector, and managed commands use portable environment-based location rather than concrete machine paths. Uninstall removes only handlers carrying the Better Plan ownership marker. The user's current local handlers remain uninstalled while this repair is developed and verified.
