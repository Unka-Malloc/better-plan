# Agent Orchestration Architecture

## Design goal

Better Plan coordinates one delivery through four isolated roles. The active host agent is the only orchestrator. Codex and Claude lifecycle command Hooks detect structural Better Plan state, inject the next required obligation, and may run deterministic focused Node regression; they never impersonate an agent dispatcher, approve implementation, or start full regression. Cursor remains skill-only because its lifecycle context and Stop identity are not reliable enough to enforce this contract.

## Lifecycle

1. **Session start or resume**
   - On supported lifecycle hosts, resolve `cwd` and every workspace-root signal together to one repository, then detect one Better Plan workspace structurally.
   - If signals conflict, include multiple roots, name a file or non-repository location, or do not yield one unique workspace, return no context and leave state untouched.
   - If one exists, require the main agent to read and understand the relevant Plan documents, Node graph, current status, constraints, architecture, and acceptance mapping before acting.
   - Cursor installs only the skill and must invoke it explicitly; no automatic lifecycle comprehension is claimed.
2. **User instruction received**
   - Treat the latest instruction as authoritative.
   - Locate the corresponding Plan and Node; create nonterminal planning state when absent, or update the affected Plan documents and `pending` or `in_progress` Nodes when intent has drifted.
   - Preserve terminal history. A terminal Plan is followed by a new Plan rather than reopened.
   - Dispatch a fresh acceptance agent to write or update the acceptance scheme before executable Nodes are finalized.
3. **Plan and Node changes validated**
   - Validate the manifest and requirement mapping.
   - Dispatch a different fresh executor with an exact ordered list of eligible Node IDs.
   - Wait while that one executor starts, implements, runs focused regression for, and completes each assigned Node sequentially.
4. **Main agent attempts to stop**
   - For one focused implementation Node on Codex or Claude, run its declared focused regression when a fresh receipt is absent, then require a fresh read-only auditor.
   - For a final-validation Node without a fresh full receipt, run no command. Require an independent read-only audit PASS first; only then may the main agent manually run the declared full regression exactly once. Repeated explicit calls with the same current fingerprint reuse the receipt without command execution; changed declared content requires renewed audit before a new explicit attempt.
   - Only explicit `regress` may execute a `full` contract; `complete` never executes it and rejects an absent or stale full receipt. With a current receipt, both repeated explicit `regress` and `complete` consume or reuse it without repeating the command. Focused implementation `regress` remains explicitly rerunnable.
   - A new full receipt invalidates the earlier audit snapshot. Require a final fresh read-only acceptance audit before completion; the Hook and receipt never represent audit PASS.
   - Complete or stop only after the applicable auditor reports PASS. Findings return to a fresh focused execution pass and invalidate the previous audit and receipt.

## Roles

### Main agent — orchestrator

- Owns workspace selection, intent alignment, manifest validation, role dispatch, waiting, retries, and final synthesis.
- Supplies each role only the latest instruction, repository-relative artifact paths, exact scope, and expected result needed for that role.
- Never claims a command Hook spawned a subagent.
- Does not use one role result as another role's independent judgment.

### Acceptance agent — acceptance owner

- Uses a fresh context and owns only the Plan's acceptance scheme, normally `Validation.md`.
- Reads the latest instruction plus relevant requirements, evidence, architecture, and current Nodes.
- Maps every requirement to objective focused and final proof before implementation Nodes are finalized.
- Does not edit implementation, execute Nodes, audit delivered code, or delegate further work.

### Execution agent — ordered Node owner

- Uses a fresh context different from the acceptance and audit agents.
- Receives one or more exact eligible Node IDs in dependency order and processes only that list, sequentially.
- Uses `manifest_tool.py` transitions and each Node's declared focused regression as the state authority.
- Stops and reports a scope or state mismatch instead of selecting replacement Nodes, running siblings concurrently, or delegating further work.

### Audit agent — independent judge

- Uses a fresh, read-only context after implementation and focused regression.
- Compares the latest instruction, Requirements, Validation, Architecture, Node acceptance criteria, changed-file scope, and redacted regression receipts with the delivered code.
- Returns either PASS or actionable findings ordered by severity and tied to repository-relative files or symbols.
- Does not edit files, run state transitions, repair findings, or delegate further work.

## Handoff contracts

Every role handoff contains only:

- the role and explicit prohibitions;
- the latest task-local user intent, paraphrased when raw text is unnecessary;
- repository-relative Plan and source paths;
- exact Node IDs or requirement labels in scope;
- the expected artifact or structured result;
- whether the main agent must wait.

Handoffs and evidence exclude secrets, personal or machine identity, backend runtime data, raw command output, transcripts, absolute paths, and unrelated conversation history. A role result that violates its ownership or omits required proof is discarded and retried with a different fresh agent.

## Module map and dependency direction

| Module | Responsibility | May depend on |
| --- | --- | --- |
| `scripts/hook_scope.py` | Structural, single-repository Better Plan event detection and separate relative-label CLI probing | filesystem structure only |
| `scripts/hook_context.py` | Pure, bounded lifecycle orchestration instructions | sanitized manifest inventory |
| `scripts/hook_tool.py` | Codex and Claude event translation, focused Stop regression, and full-regression audit gating | `hook_scope`, `hook_context`, `manifest_tool` |
| `scripts/hook_config.py` | Codex and Claude managed lifecycle configuration | portable launcher construction |
| `scripts/install.py` | Cross-client skill installation plus capability-honest lifecycle setup and diagnosis | `hook_config` and client adapters |
| `scripts/manifest_tool.py` | Authoritative Plan/Node state and regression receipts | state files and declared commands |
| `references/agent-orchestration.md` | Detailed parent and role prompt contracts | this architecture and skill rules |
| `SKILL.md` | Mandatory workflow order and progressive-disclosure routing | orchestration reference and state contracts |

Codex and Claude host configuration calls `hook_tool.py`; the adapter calls scope/context modules and, only for a focused Stop, may call the manifest regression state machine. No scope or context module mutates state. No Hook script imports an agent SDK, starts a model process, executes an arbitrary user tool, or starts a full regression. Cursor installation does not touch its Hook configuration.

The main agent invokes native host delegation directly. Acceptance, execution, and audit agents are leaves: their handoffs explicitly prohibit recursive delegation, and lifecycle context received inside a recognized subagent event is ignored so orchestration is not re-entered.

## Host capability boundary

Codex, Claude Code, and Cursor expose different native delegation and lifecycle surfaces. Better Plan therefore standardizes obligations and role contracts, not one model-launch protocol. Codex and Claude receive managed lifecycle handlers. Cursor receives the skill only: current `sessionStart` additional context may be discarded, and current Stop identifiers cannot reliably isolate the main session, so installer and doctor explicitly report that automatic lifecycle orchestration and Stop audit are unavailable. No prompt-submit, tool-use, permission-denial, or compatibility adapter substitutes for that gap. When any active host cannot create an isolated subagent or the capability is disabled, the main agent reports the missing capability and pauses the affected gate.

## Failure and retry

- Multiple, conflicting, file-valued, non-repository, ambiguous, or malformed event scope fails open with no Hook response or state mutation.
- Invalid planning state is repaired and validated before delegation.
- Acceptance or execution role failure is retried with a different fresh agent; repeated external or capability failure is surfaced to the user.
- Regression failure returns to focused remediation without exposing command output.
- Audit findings return to a fresh executor; every code or Plan change requires a new fresh audit.
- The complete regression suite belongs only to the final-validation Node. After focused checks and an independent audit PASS, the main agent runs it manually exactly once; the resulting receipt then requires final fresh read-only acceptance before completion.
