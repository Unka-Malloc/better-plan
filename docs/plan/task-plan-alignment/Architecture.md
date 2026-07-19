# Task–Plan Alignment Architecture

## Module boundaries

- `scripts/better_plan/hooks/scope.py` owns structural repository and Better Plan workspace detection.
- `scripts/better_plan/hooks/context.py` owns bounded Plan inventory and static intent-led alignment guidance. It reads no user prompt and executes no workflow mutation.
- `scripts/better_plan/hooks/runtime.py` normalizes lifecycle events, delegates detection and context construction, and invokes the Agent-completion reducer only after a native Agent returns.
- `scripts/better_plan/hooks/protocols.py` and `scripts/better_plan/hooks/config.py` own host response shapes, current event mappings, matchers, and portable managed commands.
- `scripts/install.py` copies the single implementation and delegates managed configuration updates.

Dependency direction is `install -> hooks.config -> hooks.protocols` and `host -> hooks.runtime -> hooks.scope / hooks.context`, with Agent completion additionally calling the application reducer.

## Lifecycle contract

1. Session start or resume runs structural detection. One workspace is exposed only as candidate context; it does not select work or authorize continuation. Every other result is an empty success response.
2. Codex and Claude task submission repeats the same short instruction: prioritize the user's request and consider Better Plan only for an explicit implementation request. The Hook does not receive or echo task text; the host agent already has the submitted task.
3. Cursor receives the same standing instruction at session start. Its `beforeSubmitPrompt` handler returns only the host's explicit nonblocking allowance, so it cannot inject or enforce a different task interpretation.
4. After an explicit implementation request, the agent inspects only plausibly relevant Plan documents and unfinished Nodes. It corrects matching nonterminal state on drift, creates or rewrites planning state when none corresponds, and creates a new Plan when the prior Plan is terminal.
5. `start` is not a host Hook. It is the internal `pending -> in_progress` state transition and authoritative platform/prerequisite gate.
6. Agent completion is correlated only after the host reports return. It may run deterministic regression and return one routing directive, but it never resumes a stopped child or invents work from Plan state.

## Deliberate patterns

- **Functional core with protocol adapters:** context construction and host response shapes are pure functions; structural discovery and regression retain their existing owners.
- **Data minimization:** inventory contains only bounded relative directory/status pairs. Semantic prose stays in canonical Plan files and the latest prompt stays inside the host conversation.
- **Capability fallback:** host event mappings expose only protocol behavior each host can perform without blocking. Session standing context substitutes for missing Cursor prompt context without simulating it through permissions.
- **Immutable history:** Plan correction branches on terminality instead of adding compatibility paths or reopening completed state.

## Failure behavior

Malformed payload, unreadable state, no workspace, or multiple workspaces returns an empty object. Context events never deny execution. Agent-completion ambiguity is a no-op and captured command output is never reported. Managed commands contain no concrete installation path and removal affects only marked handlers.
