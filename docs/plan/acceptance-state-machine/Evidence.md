# Acceptance State Machine Evidence

## Repository evidence

- `scripts/acceptance_machine.py` now makes executor, regression, repair, and auditor transitions deterministic, but its implicit implementation entry is still `awaiting_executor`. It has no preparation states for design, acceptance authoring, or acceptance review.
- `scripts/manifest_tool.py` fingerprints declared source and test paths, discards command output, correlates executor and auditor events, and auto completes only after a fresh audit. It does not yet validate a machine-readable design contract or bind an early test-quality approval to the design and test fingerprints.
- `scripts/hook_tool.py` is read-only at Stop, but `scripts/hook_context.py` still concatenates comprehension, alignment, acceptance, execution, audit, and boundary instructions into one standing main-agent context regardless of the current action.
- `references/agent-orchestration.md` stores the acceptance-designer, executor, and auditor prompt templates in one file. Child handoffs may be selective, but loading the reference exposes every role contract and weakens context isolation.
- `SKILL.md` currently orders the validation matrix before architecture. That lets tests define behavior before files, symbols, signatures, dependency direction, algorithms, isolation, and concurrency have been fixed by the plan designer.
- `tests/test_orchestration_workflow.py` explicitly requires three prompt blocks in the combined reference. The test therefore protects co-location instead of role isolation.
- The first fingerprint-bound final audit found that a command receipt claimed an audit-only criterion and omitted relevant installer, Hook-scope, and test files. This proves that executable test success cannot replace early review of the acceptance contract itself.

## User-provided product evidence

- The native main agent should be the plan and framework designer: it fixes files, functions, classes or interfaces, signatures, inheritance or composition, algorithms, data structures, decoupling, isolation, and concurrency before delegating implementation.
- Acceptance cases need an independent validity judgment before execution. The acceptance designer must not approve its own coverage or oracle quality.
- Modern coding agents already understand ordinary read-only review. Context should be spent on design and acceptance preparation; the final auditor needs only bounded inputs and a PASS-or-findings output contract.
- Role prompts should not be injected together. Each delegated agent should receive only its own role contract and the repository-relative artifacts needed for that role.

## New requirement trace

- **REQ-010:** the current skill places validation before architecture and has no symbol-level design gate; the user assigns plan, framework, and interface ownership to the native main agent.
- **REQ-011:** the combined role reference and concatenated Hook context demonstrate that role contracts are not progressively disclosed today.
- **REQ-012:** the transition table has no acceptance-reviewer phase, so a test designer's output can reach execution without an independent oracle and coverage judgment.
- **REQ-013:** the current auditor contract carries detailed procedural teaching even though the user expects a capable read-only auditor and wants context invested upstream.
- **REQ-014:** existing fingerprints bind regression and final audit only; there is no receipt binding requirements, design, scaffold, validation, and tests before executor dispatch.
- **REQ-015:** Node prose asks agents to consider architecture, but no machine-readable structure records files, symbols, interfaces, engineering choices, isolation, or concurrency for validators and child handoffs.

## Open-source practice

- XState defines transitions as deterministic functions of current state and event, with pure synchronous guards. Better Plan should therefore keep phase selection in a pure module and isolate subprocess/file effects in the manifest adapter: <https://stately.ai/docs/transitions> and <https://stately.ai/docs/guards>.
- LangGraph separates state, work Nodes, and conditional edges, and documents evaluator/optimizer loops as predetermined workflows. Better Plan should similarly let executable test outcomes choose the repair or audit edge rather than let an agent choose: <https://langchain-ai.github.io/langgraph/how-tos/state-reducers/> and <https://langchain-ai.github.io/langgraph/agents/tools/>.
- Airflow represents retryable task failure as an explicit intermediate state and models task instances as idempotent work units. Better Plan should persist a bounded repair phase and attempt count instead of treating failure as prose: <https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/tasks.html>.
- Temporal keeps workflow logic deterministic, retries failed workflow tasks without advancing state, and validates replay against recorded history. Better Plan should bind audit approval to the tested content fingerprint and make duplicate events idempotent: <https://github.com/temporalio/sdk-python>.

## Design deductions

1. Move architecture and scaffold before acceptance design. Requirements and evidence establish why; the main agent then freezes the implementation contract; only afterward may a test designer author executable proof.
2. Represent design as machine-readable Node data plus `Architecture.md`: owned paths, symbol operations, interfaces, dependency edges, engineering decisions, and test seams. A prose-only title is not sufficient input for a delegated executor.
3. Add acceptance-designer and acceptance-reviewer phases ahead of `awaiting_executor`. Reviewer approval binds canonical design and declared test fingerprints, and any change invalidates approval.
4. Split main orchestration and every delegated role into separate reference files. Hook output contains a single repository-relative reference pointer, never embedded role templates.
5. Keep the transition table pure and isolate filesystem, subprocess, fingerprint, and atomic-write effects in the manifest adapter. Use composition of small validators instead of an inheritance hierarchy because the roles share data contracts, not substitutable runtime behavior.
6. Keep mutation serialized per Plan state file. Independent Plans may progress concurrently; within one Plan, sibling ownership must be disjoint and dispatch order remains explicit to avoid the multi-active ambiguity already observed.
7. Let the runner choose regression pass or repair, and keep the final auditor minimal. Audit remains a fresh fingerprint-bound verdict, but it is the last guard, not the place where missing architecture or weak tests are repaired conceptually.
8. Preserve completed Nodes as immutable history. Apply the design-first preparation cycle only to new or nonterminal delivery work.
