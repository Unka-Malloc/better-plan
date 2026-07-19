# Requirements

## REQ-001 Canonical package boundary

All reusable Python code must live under `scripts/better_plan/`. Executable files in
`scripts/` may remain only as thin, legitimate command adapters. Imports use one
canonical package path without fallback ladders or duplicated module identities.

## REQ-002 Workflow separation

Manifest schema validation, workspace persistence, acceptance orchestration,
regression execution, and CLI parsing must be separate modules. The acceptance
transition table and design contract remain pure domain code.

## REQ-003 Installer separation

Installation models, skill-tree operations, target/platform adapters, verification,
and CLI parsing must be separate modules. Hook configuration remains a cohesive
installation dependency rather than being embedded in the installer service.

## REQ-004 Event-driven Agent completion

The application boundary may reduce only a correlated Agent-completion event. Agent
lifetime, cancellation, and platform timeout behavior remain owned by the native host;
Better Plan does not poll, time, interrupt, or replace a running Agent.

## REQ-005 Complete migration

Remove the old domain, Hook helper, and installer implementations after consumers and
tests move to the package. Preserve only `manifest_tool.py`, `install.py`, and
`hook_tool.py` as thin current entrypoints; do not retain compatibility shims.

## REQ-006 Skill integrity and privacy

The installed payload inventory, `SKILL.md`, and `agents/openai.yaml` must describe the
new architecture. Persisted commands and evidence remain repository-relative and do
not expose machine, server, secret, or runtime data.
