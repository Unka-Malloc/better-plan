"""Build privacy-safe Better Plan lifecycle context for supported hosts."""

from __future__ import annotations

MAX_CONTEXT_LENGTH = 2048
VERIFIER_REFERENCE = "references/verifier.md"
INTENT_GUIDANCE = (
    "Prioritize the user's request. Maintain the Better Plan source repository with the native "
    "workflow, without entering Better Plan. For planning, coding, or explicit implementation in "
    "other projects, enter Better Plan. Otherwise, follow the user's instructions and act or "
    "answer accordingly."
)


def session_context() -> str:
    return INTENT_GUIDANCE


def prompt_context() -> str:
    return INTENT_GUIDANCE


def agent_completion_context(node_id: str, phase: str, action: str) -> str:
    """Return one bounded parent directive after an Agent tool completes."""
    if action == "dispatch_verifier":
        duty = (
            "The Worker returned. Dispatch the write-capable Verifier using "
            f"{VERIFIER_REFERENCE}; it checks and repairs this Node before the state tool runs "
            "the Node's one focused regression."
        )
    elif action == "main_correction_decision":
        duty = (
            "Focused regression failed. The native main must classify the evidence: keep an "
            "ordinary implementation defect inside the same Node and prefer the same compatible "
            "idle Worker for correction. Escalate to group redesign "
            "only for a real cross-node design or product-semantics error. Do not redispatch "
            "automatically."
        )
    elif action == "main_reviewer_decision":
        duty = (
            "The task group's one Reviewer returned after reviewing and repairing the whole "
            "group. Record every non-autonomous choice in the Plan: report immediate items to "
            "the user now, resolve and apply them before continuing, and retain deferred items "
            "for final handoff. Then submit the exact reviewer-finished event so full regression "
            "verifies the Reviewer's changes."
        )
    else:
        duty = "Read next-action and handle the current state in the native main."
    return (
        f"Better Plan agent-complete event: Node {node_id}, phase {phase}, action {action}. "
        f"{duty} A completed turn is not a failed child lifetime: a successfully completed Worker "
        "may remain idle for a later compatible continuation after its Node reaches acceptance."
    )[:MAX_CONTEXT_LENGTH]
