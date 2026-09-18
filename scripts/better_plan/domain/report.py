"""Self-contained HTML report projection over live workspace state."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import json

from .models import ToolError


REPORT_SCHEMA = "better-plan.report/v3"
DATA_MARKER = "__BETTER_PLAN_REPORT_DATA__"
TEMPLATE_RELATIVE_PATH = Path("web") / "plan-report.html"


def default_template_path() -> Path:
    return Path(__file__).resolve().parents[3] / TEMPLATE_RELATIVE_PATH


def report_payload(plans: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Assemble the baked report payload from ``{"plan", "checkpoints"}`` pairs."""

    return {
        "schema": REPORT_SCHEMA,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plans": [
            {"plan": dict(entry["plan"]), "checkpoints": entry.get("checkpoints")}
            for entry in plans
        ],
    }


def render_report_html(payload: Mapping[str, Any], template: str) -> str:
    """Embed the payload in the template, safe against ``</script>`` breakout."""

    if template.count(DATA_MARKER) != 1:
        raise ToolError("report template must contain exactly one data marker")
    embedded = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    return template.replace(DATA_MARKER, embedded)


def load_template(path: Path | None = None) -> str:
    template = path or default_template_path()
    if template.is_symlink() or not template.is_file():
        raise ToolError("report template is missing: %s" % TEMPLATE_RELATIVE_PATH.as_posix())
    return template.read_text(encoding="utf-8")
