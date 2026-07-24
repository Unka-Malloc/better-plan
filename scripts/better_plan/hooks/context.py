"""Build privacy-safe Better Plan lifecycle context for supported hosts."""

from __future__ import annotations

MAX_CONTEXT_LENGTH = 2048
AUDITOR_REFERENCE = "references/auditor.md"
INTENT_GUIDANCE = (
    "Prioritize the user's request. For planning, coding, or explicit implementation work, "
    "enter Better Plan. Otherwise, follow the user's instructions and perform the requested work "
    "or answer the user's question accordingly."
)


def session_context() -> str:
    return INTENT_GUIDANCE


def prompt_context() -> str:
    return INTENT_GUIDANCE


def agent_completion_context(node_id: str, phase: str, action: str) -> str:
    """Return one bounded parent directive after an Agent tool completes."""
    if action == "dispatch_auditor":
        duty = (
            "Focused regression passed. Dispatch exactly one fresh read-only auditor using "
            f"{AUDITOR_REFERENCE}."
        )
    elif action == "main_correction_decision":
        duty = (
            "Focused regression failed. The native main must classify the evidence: keep an "
            "ordinary implementation defect inside the same Node and frozen acceptance, and "
            "open design repair only for a real design or product-semantics error. Do not "
            "redispatch automatically."
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
            "audit-passed, same-Node implementation correction, design repair only for a real "
            "design or product-semantics error, or pause to defer."
        )
    else:
        duty = "Read next-action and handle the current state in the native main."
    return (
        f"Better Plan agent-complete event: Node {node_id}, phase {phase}, action {action}. "
        f"{duty} Do not continue the stopped child agent."
    )[:MAX_CONTEXT_LENGTH]
