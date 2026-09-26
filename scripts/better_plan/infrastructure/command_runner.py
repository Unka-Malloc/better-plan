"""Run declared commands and persist only privacy-safe receipts.

Verification evidence must be produced by the tool, never reported by the caller
that performed the work. This runner owns process execution, receipt shape, and
diagnostic redaction for every Node the tool completes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import subprocess
import sys
import time

from ..domain.models import plain_shell_command, safe_summary_issue


OUTPUT_TAIL_CHARACTERS = 2000


def timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def safe_diagnostic_tail(output: str) -> str:
    """Keep a bounded, deduplicated tail that is safe to show an operator."""

    values: list[str] = []
    for raw in output[-OUTPUT_TAIL_CHARACTERS:].splitlines():
        line = raw.strip()
        if not line:
            continue
        value = (
            line
            if safe_summary_issue(line, max_chars=500) is None
            else "[redacted unsafe diagnostic line]"
        )
        if not values or values[-1] != value:
            values.append(value)
    return "\n".join(values)[-OUTPUT_TAIL_CHARACTERS:]


def run_commands_with_diagnostics(
    project_root: Path, commands: list[str]
) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]]]:
    """Run commands and return persistent receipts plus ephemeral safe diagnostics."""

    receipts: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for index, command in enumerate(commands):
        # Observation windows never impose an execution deadline. A declared
        # command may enforce its own project-required limit; cancellation
        # remains controlled by the caller.
        output_tail = bytearray()
        with subprocess.Popen(
            plain_shell_command(command),
            cwd=str(project_root),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        ) as process:
            assert process.stdout is not None
            while True:
                chunk = process.stdout.read(8192)
                if not chunk:
                    break
                output_tail.extend(chunk)
                del output_tail[:-OUTPUT_TAIL_CHARACTERS * 4]
            exit_code = process.wait()
        outcome = "passed" if exit_code == 0 else "failed"
        output = output_tail.decode("utf-8", "replace")
        receipts.append(
            {
                "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
                "outcome": outcome,
                "exit_code": exit_code,
                "recorded_at": timestamp(),
            }
        )
        if outcome != "passed":
            tail = safe_diagnostic_tail(output)
            print("command %s (%s)" % (outcome, command), file=sys.stderr)
            if tail:
                print(tail, file=sys.stderr)
            diagnostics.append(
                {
                    "command_index": index,
                    "command_sha256": receipts[-1]["command_sha256"],
                    "outcome": outcome,
                    "exit_code": exit_code,
                    "output_tail": tail,
                }
            )
            return False, receipts, diagnostics
    return True, receipts, diagnostics
