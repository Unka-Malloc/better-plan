"""Build privacy-safe Better Plan lifecycle context for supported hosts."""

from __future__ import annotations

MAX_CONTEXT_LENGTH = 2048
ACCEPTANCE_REVIEWER_REFERENCE = "references/acceptance-reviewer.md"
AUDITOR_REFERENCE = "references/auditor.md"
INTENT_GUIDANCE = (
    "Prioritize understanding the user's request and follow their direction. Consider Better "
    "Plan only for explicit implementation, align only the relevant Plan before selecting "
    "executable work, and bind one user-visible capability to one lifecycle identified by its "
    "selected Node. A selector refusal returns control to the native main and does not end the user's "
    "task. Completion must not select or start another Node; revisions, failures, findings, "
    "and new scope return to native-main judgment."
)


def session_context() -> str:
    return INTENT_GUIDANCE


def prompt_context() -> str:
    return INTENT_GUIDANCE


def agent_completion_context(node_id: str, phase: str, action: str) -> str:
    """Return one bounded parent directive after an Agent tool completes."""
    if action == "dispatch_acceptance_reviewer":
        duty = (
            "Acceptance design is recorded. Dispatch exactly one fresh read-only acceptance "
            f"reviewer using {ACCEPTANCE_REVIEWER_REFERENCE}."
        )
    elif action == "dispatch_auditor":
        duty = (
            "Focused regression passed. Dispatch exactly one fresh read-only auditor using "
            f"{AUDITOR_REFERENCE}."
        )
    elif action == "main_repair_decision":
        duty = (
            "Focused regression failed. Do not redispatch automatically; the native main "
            "must choose whether and how to repair, or defer."
        )
    elif action == "main_acceptance_decision":
        duty = (
            "Acceptance needs a native-main decision. Inspect the current verdict or drift "
            "and choose whether to revise the same Node, narrow the current capability, "
            "defer it, or proceed when evidence permits. Never select or start another Node "
            "automatically."
        )
    elif action == "main_audit_decision":
        duty = (
            "Code audit returned. The native main must inspect the verdict and choose "
            "audit-passed, audit-failed for repair, or pause to defer."
        )
    else:
        duty = "Read next-action and handle the current state in the native main."
    return (
        f"Better Plan agent-complete event: Node {node_id}, phase {phase}, action {action}. "
        f"{duty} Do not continue the stopped child agent."
    )[:MAX_CONTEXT_LENGTH]
