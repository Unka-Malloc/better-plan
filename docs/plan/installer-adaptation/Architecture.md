# Installer Adaptation Architecture

## Module map

- `scripts/install.py`: owns all runtime discovery, installation paths, adapter generation, and doctor checks.
- `tests/test_install_tool.py`: owns isolated tests for install routing and command outcomes.
- `README.md`: owns user-facing supported-runtime behavior and verification instructions.

## Layers and direction

The CLI layer parses arguments and creates `InstallPaths`. The application layer selects install targets, copies the single skill tree, and emits adapters. The infrastructure layer runs local, WSL, and optional client commands. Dependencies flow from CLI to application to infrastructure; generated adapters do not reach back into installer internals.

## Contracts

`RuntimeProbe` represents a discoverable runtime. A WSL-specific probe must supply its distro, executable location, and Linux home directory. Installation returns messages only after it has installed the WSL shared skill and generated the OpenCode adapter. Doctor returns `OK`, `WARN`, or `FAIL`: an unavailable optional client CLI is `WARN`, while a discovered WSL OpenCode runtime with an invalid Better Plan adapter is `FAIL`.

## Chosen patterns

Use a value object for WSL runtime data so discovery, deployment, and validation share one explicit contract. Use a table-driven optional-client validator for Cursor, Copilot, and Gemini because each differs only in command and expected capability; a table avoids three drifting copies of the same availability/error policy. Keep path resolution and copy primitives unchanged to preserve the existing single-current-implementation invariant.
