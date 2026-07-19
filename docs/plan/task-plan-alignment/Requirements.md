# Task–Plan Alignment Requirements

## Problem

A structural Better Plan workspace can be detected deterministically, but a Plan may no longer represent the user's latest task. Tool-level interception cannot solve that semantic mismatch and can prevent the agent from performing recovery work.

## Requirements

- **REQ-001 — Structural scope:** every managed lifecycle callback activates only when the current repository contains exactly one structural Better Plan workspace; absent or ambiguous scope is a no-op.
- **REQ-002 — Session entry:** session start and resume identify Better Plan only as candidate project context. They must not infer a task from the workspace, select an active Node, or instruct the agent to continue existing work without a user request.
- **REQ-003 — Latest-intent authority:** at task submission, one short instruction tells the agent to prioritize understanding and following the latest user request. Candidate Plans never define what the user asked for.
- **REQ-004 — Corrective planning:** only after the user explicitly asks for implementation does the agent consider entering Better Plan. It then uses candidate Plans as revisable references, creates or rewrites a suitable nonterminal Plan when none corresponds, and corrects intent drift before implementation. Completed and skipped history remains immutable, so a terminal Plan is followed by a new Plan.
- **REQ-005 — Host-correct context:** Codex and Claude Code receive session and prompt-submit context through their supported lifecycle responses. Cursor receives the standing rule at session start because its prompt-submit Hook cannot currently inject equivalent nonblocking context.
- **REQ-006 — No generic tool interception:** Better Plan performs no command parsing or permission decision. Context callbacks and ambiguity failures are nonblocking; the only tool-scoped callback matches a completed native Agent call and cannot deny tools or continue a stopped Agent.
- **REQ-007 — Private context:** Hook output contains only static instructions, a bounded data-only Plan inventory, and repository-relative identifiers. It never echoes the submitted prompt, Plan prose, concrete machine paths, secrets, or runtime output.
- **REQ-008 — Managed delivery:** install, update, doctor, and uninstall own exactly the current lifecycle event set for each supported host while preserving unrelated configuration, and focused plus final regression proves the behavior.

## Non-goals

- A deterministic script does not classify semantic similarity by keywords or choose a Plan on the agent's behalf.
- Hooks do not reopen terminal history, choose among concurrent Nodes, or replace manifest state transitions.
- Cursor prompt submission is not converted into a blocking permission gate to emulate missing context injection.

## Acceptance target

Only structural Better Plan projects receive one short lifecycle reminder. The user request remains the sole authority for what work exists, and Better Plan is considered only after an explicit implementation request. Plans are then revisable reference models: nonterminal drift is corrected before implementation, terminal history produces a new Plan, generic tools are not intercepted, and private text is not echoed.
