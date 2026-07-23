# Kimi Code Support Requirements

## Requirement

- `REQ-001`: Better Plan must be installable and discoverable by Kimi Code, activate only for
  structurally detected Better Plan workspaces, preserve unrelated Kimi configuration, reduce a
  correlated successful subagent completion, diagnose the installed integration, and uninstall
  only Better Plan-owned files and Hook entries.

## Boundary

The integration uses Kimi Code's current Skill and Hook contracts. It does not add `PreToolUse`,
`Stop`, tool denial, forced continuation, agent polling, or compatibility for retired Kimi paths
or configuration formats.
