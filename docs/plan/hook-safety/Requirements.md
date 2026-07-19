# Hook Safety Requirements

## Problem

A user-level Better Plan Hook searched every structural workspace below a broad repository root, merged unrelated active Nodes, and repeatedly blocked Cursor at Stop. The same delivery path installed Hooks automatically and persisted or printed machine-specific paths and unredacted command identity.

## Requirements

- **REQ-001 — Automatic scoped activation:** a dedicated detector must decide whether the event belongs to one repository that contains exactly one structural Better Plan workspace. Only a positive detection may activate lifecycle Hook behavior.
- **REQ-002 — Fail-open ambiguity:** no workspace, multiple workspaces, multiple active Nodes, malformed state, or an ambiguous multi-root payload must return an empty success response. State-management commands needed to pause or inspect work must remain executable.
- **REQ-003 — Bounded continuation:** Codex and Claude continuation callbacks must honor `stop_hook_active`; Cursor must honor `loop_count`. One Hook chain may request at most one continuation.
- **REQ-004 — Authoritative state machine:** platform eligibility remains a hard `start` gate and regression freshness remains a hard `regress` or `complete` gate even when Hooks are absent.
- **REQ-005 — Private relative evidence:** state files and user-facing output may contain only repository-relative paths, safe summaries, and digests. Command output and concrete machine paths must be discarded.
- **REQ-006 — Automatic safe delivery:** install and update may deliver managed Hook entry points automatically, but every invocation must run the dedicated detector before lifecycle logic. Removal must preserve unrelated host configuration.
- **REQ-007 — Single current interface:** remove the duplicate update entry point, installer aliases, and permanent checks for already-removed fallback scripts.
- **REQ-008 — Current protocol proof:** focused tests must cover current Codex, Cursor, and Claude Hook inputs and the final suite must pass once.

## Non-goals

- Hooks do not choose among concurrent Nodes.
- Hooks do not replace host permissions or the manifest state machine.
- Hooks do not scan parent development directories for unrelated projects.

## Acceptance target

Unrelated and ambiguous projects always proceed without manual configuration, a uniquely active Better Plan Node receives at most one scoped lifecycle continuation, all persisted evidence is path-safe and output-free, managed Hook delivery remains portable and removable, obsolete interfaces are absent, and the complete test suite plus plan validation passes.
