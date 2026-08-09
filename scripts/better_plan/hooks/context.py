"""Build privacy-safe Better Plan lifecycle context for supported hosts."""

from __future__ import annotations

MAX_CONTEXT_LENGTH = 2048
# Protected compatibility contract: keep lifecycle policy in SKILL.md. Change
# this entry guidance only in a developer-authorized change that also updates
# the independent contract fixture in tests/test_hook_tool.py.
INTENT_GUIDANCE = (
    "Understand the user's request. Handle simple tasks directly; only enter the Better Plan "
    "workspace for complex tasks, large migrations, or long-term planning."
)


def session_context() -> str:
    return INTENT_GUIDANCE


def prompt_context() -> str:
    return INTENT_GUIDANCE


def agent_completion_context(target: str, phase: str, action: str) -> str:
    """Return one bounded parent directive after an Agent tool completes."""

    if action == "close_designer_session":
        duty = (
            "The sole Designer returned after directly editing Plan.json. Close that same session, "
            "then use check-readiness to list any remaining issue; never dispatch another Designer."
        )
    elif action == "accept_task":
        duty = (
            "The Worker returned. Run this Task's focused acceptance. If it fails, repair it in the "
            "native main and rerun accept-task, or dispatch-task once more for a correction Worker."
        )
    elif action == "close_reviewer_session":
        duty = (
            "The sole write-capable Reviewer returned. Run the final regression inside this same "
            "Reviewer session; never dispatch a second Reviewer."
        )
    else:
        duty = "Read next-action and handle the current state in the native main."
    return (
        f"Better Plan agent-complete event: target {target}, phase {phase}, action {action}. "
        f"{duty} Do not turn an implementation detail into a mid-execution user question."
    )[:MAX_CONTEXT_LENGTH]
