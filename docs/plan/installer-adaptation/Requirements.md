# Installer Adaptation Requirements

## User problem

The current installer correctly writes adapters for its six supported clients, but a Windows invocation only writes Windows-user paths. It can discover a WSL OpenCode runtime during `doctor`, yet cannot install or verify the WSL-side adapter. Cursor, Copilot, and Gemini verification is configuration-only, and Claude emits a manifest-version warning.

## Target users and workflows

Users run `python scripts/install.py` or `python scripts/install.py update` from Windows and expect the supported clients discovered on that machine to receive one current Better Plan implementation. They then run `doctor` to distinguish a valid configuration from a runtime that has actually loaded the adapter.

## Requirements

- `REQ-001`: On Windows, install and update must deploy Better Plan to each detected WSL distribution that exposes OpenCode, using the same selected Better Plan source and without creating a parallel legacy implementation.
- `REQ-002`: `doctor` must verify WSL OpenCode by querying its agent list after confirming its WSL-side adapter, and must report a failed WSL deployment as a failure rather than treating discovery alone as success.
- `REQ-003`: Cursor, Copilot, and Gemini checks must run their native runtime validation when the corresponding CLI is available, while retaining a non-failing structural check when it is unavailable.
- `REQ-004`: The generated Claude plugin manifest must be warning-free for the installed Claude CLI by supplying a valid semantic version.
- `REQ-005`: Existing path overrides, shared-skill resolution, idempotence, atomic replacement, and duplicate-native-skill removal must remain intact.

## Scope and non-goals

The scope is `scripts/install.py`, its unit tests, and user-facing installation documentation. Docker OpenCode remains diagnostic-only because a container is not a stable user-home installation target. The installer does not add support for unconfigured third-party agents outside its declared supported-client set.

## Acceptance target

The full unit suite passes, a Windows-host test proves WSL OpenCode deployment and runtime validation, and the local supported adapters pass their structural or native runtime checks without the Claude manifest warning.
