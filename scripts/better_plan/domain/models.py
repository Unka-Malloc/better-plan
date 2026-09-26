"""Shared primitives for the Checkpoints Tree tool.

Everything here is Tree-neutral: the error type, the privacy guard used on stored
summaries and diagnostics, and the shell-command normalizer. Delivery semantics live
in `checkpoints_tree.py`.
"""

from __future__ import annotations

from typing import Any
import re


class ToolError(RuntimeError):
    """A caller-fixable condition: report it, never a traceback."""


# Privacy guard. A value that looks like a secret, an absolute local path, a UNC
# share, or a bare endpoint never enters state, evidence, or a diagnostic.
_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?:(?<![A-Za-z0-9])[A-Za-z]:[\\/]|\\\\[^\\/\s]+[\\/]|(?<![\w.])/(?:Users|home|root|private|tmp|var|etc|opt|mnt|media|Volumes)(?:/|\b))"
)
_NETWORK_ENDPOINT_PATTERN = re.compile(
    r"(?:(?:https?|wss?|ftp)://[^\s]+|\b\d{1,3}(?:\.\d{1,3}){3}\b|(?<![\w.-])(?:localhost|127\.0\.0\.1)(?::\d+)?)",
    re.IGNORECASE,
)
_SENSITIVE_TOKEN_PATTERN = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk|pk|ghp|gho|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{16,}\b|\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b|\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password|passwd|bearer)\s*[:=]\s*\S{8,})",
    re.IGNORECASE,
)


def safe_summary_issue(value: Any, max_chars: int = 1000) -> str | None:
    """Return why a summary cannot be stored, or None when it is safe."""

    if not isinstance(value, str):
        return "must be a string"
    text = value.strip()
    if not text:
        return "must not be empty"
    if len(text) > max_chars:
        return "must be at most %d characters" % max_chars
    if "\x00" in text:
        return "must not contain control characters"
    if _ABSOLUTE_PATH_PATTERN.search(text):
        return "must not contain an absolute local path"
    if _NETWORK_ENDPOINT_PATTERN.search(text):
        return "must not contain a network endpoint"
    if _SENSITIVE_TOKEN_PATTERN.search(text):
        return "must not contain secret-shaped data"
    return None


def plain_shell_command(value: str) -> str:
    """Return one command without a Markdown code-span wrapper.

    Designers habitually write ``- `cmake --build build` ``; a literal backtick pair
    handed to the shell becomes command substitution that executes the command's own
    output. The wrapper carries no meaning, so it is removed before execution.
    """

    text = value.strip()
    if len(text) >= 2 and text[0] == "`" and text[-1] == "`" and "`" not in text[1:-1]:
        text = text[1:-1].strip()
    return text
