# Hook Safety Evidence

## Observed behavior

- The user supplied repeated Cursor Stop responses listing active Nodes from unrelated work and reported that even corrective pause work could not proceed.
- `scripts/manifest_tool.py` selected the nearest repository root and recursively returned every structural workspace below it.
- `scripts/hook_tool.py` converted multiple active Nodes and inspection failures into mandatory continuation responses.
- `scripts/install.py` installed user-level Hook handlers during every install or update.
- The privacy audit found concrete paths in Hook commands, installer output, CLI workspace output, fixtures, and evidence records.

## Current host contracts

- Codex documents project trust, repository-local Hook configuration, `Stop`, and the `stop_hook_active` continuation signal: <https://learn.chatgpt.com/docs/hooks>.
- Cursor documents `stop`, `followup_message`, and bounded `loop_count` handling: <https://cursor.com/docs/hooks> and <https://cursor.com/blog/agent-best-practices>.
- Claude Code documents `Stop`, `stop_hook_active`, and bounded Stop behavior: <https://code.claude.com/docs/en/hooks>.

## Deductions

1. Global discovery cannot identify which concurrent Node belongs to one agent session, so ambiguity must be a no-op.
2. A Hook adapter must fail open because the manifest commands already own the hard transition gates.
3. Persisted command text is unnecessary for verification; a digest plus exit success identifies the receipt without retaining sensitive arguments.
4. Automatic Hook delivery is safe only when every invocation first passes a dedicated repository-scoped detector; local uninstall remains an independent, scoped operation.
