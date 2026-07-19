# Agent Orchestration Requirements

## Problem

Better Plan currently injects plan-alignment guidance and runs deterministic Stop regression, but it leaves planning, implementation, and acceptance judgment in the same agent context. The workflow needs explicit role separation so the implementation agent cannot define its own acceptance target or approve its own work.

## Requirements

- **REQ-001 — Plan comprehension:** when a session starts or resumes in a structural Better Plan project, the main agent must locate the workspace, read the relevant Plan documents and Nodes, and understand their goal, constraints, architecture, status, and acceptance mapping before acting.
- **REQ-002 — Instruction alignment:** when a user submits an instruction, the main agent must find the corresponding Plan and Node. If none exists, create the required nonterminal planning state; if the latest user intent differs, update the Plan documents and affected `pending` or `in_progress` Nodes before execution. Preserve terminal history and create a new Plan instead of reopening it.
- **REQ-003 — Independent acceptance design:** during user-instruction handling, dispatch one fresh subagent with no implementation responsibility. Give it the user's instruction and relevant Plan artifacts, and require it to write or update the Plan's acceptance scheme in `Validation.md` or the project-standard equivalent. It must map requirements to objective checks before execution Nodes are finalized.
- **REQ-004 — Sequential delegated execution:** after Plan and Node changes validate, dispatch a different fresh execution subagent. Assign one or more exact eligible Node IDs and require it to execute them in dependency order, using manifest transitions and each Node's focused regression. The main agent remains the orchestrator and waits for the delegated sequence to finish.
- **REQ-005 — Independent stop audit:** when the main agent is about to stop, dispatch another fresh read-only audit subagent. Give it the latest user instruction, relevant Plan artifacts, changed-file scope, acceptance scheme, and regression evidence. It must inspect the delivered code and report pass or actionable findings against the acceptance criteria without editing implementation files.
- **REQ-006 — Role isolation and handoff:** acceptance, execution, and audit must use distinct fresh agents. Each prompt must state ownership, prohibited work, required artifacts, expected result, and whether the main agent must wait. Subagents must not recursively delegate; the main agent owns sequencing, retries, and synthesis.
- **REQ-007 — Private bounded context:** delegation prompts and persisted evidence must use repository-relative paths and minimum task-local context. Never pass or persist secrets, personal or machine identity, backend runtime data, raw command output, transcripts, or unrelated conversation history.
- **REQ-008 — Capability honesty:** Hooks may inject orchestration obligations but must not pretend to spawn agents on hosts where command Hooks cannot do so. The current host agent performs delegation through its native subagent capability. If unavailable or disabled, report the capability gap instead of silently executing all roles in one context or introducing tool-use interception.
- **REQ-009 — Verifiable lifecycle:** focused tests must prove the session, prompt, execution-handoff, and Stop-audit instructions; final validation must prove the current host mappings, privacy boundary, state consistency, and complete regression once.

## Non-goals

- Do not install tool-use Hooks, parse arbitrary commands, or use permissions as an orchestration substitute.
- Do not let an acceptance or audit agent implement fixes.
- Do not run independent sibling Nodes concurrently in this workflow; the assigned execution subagent processes its exact Node list sequentially.
- Do not make command Hook scripts launch nested model processes directly.

## Acceptance target

In every structural Better Plan project, the main agent first understands current planning state, aligns the latest instruction, obtains a separately authored acceptance scheme, delegates exact Nodes to a fresh sequential executor, and obtains a fresh read-only acceptance audit before stopping. Each role remains isolated, host capability is represented honestly, state transitions remain authoritative, and no sensitive or machine-specific data is exposed.
