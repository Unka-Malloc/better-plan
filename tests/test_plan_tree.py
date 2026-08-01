"""Frozen acceptance for Better Plan's readable and detailed tree projections."""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from scripts.better_plan.domain.tree import render_workspace_tree
from scripts.better_plan.installation.models import CURRENT_SKILL_FILES
from tests.test_manifest_tool_cli import PYTHON_TOOL, run_command, write_workspace


REPO_ROOT = PYTHON_TOOL.parents[1]


def uuid4(value: int) -> str:
    """Return a deterministic, valid UUID4-shaped fixture identity."""
    return f"{value:08x}-0000-4000-8000-{value:012x}"


def tree_plan(
    plan_id: str,
    *,
    title: str,
    directory: str,
    status: str,
    kind: str,
    tree_mode: str = "show",
    node_status: str = "show",
    entry_gate: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    plan: Dict[str, object] = {
        "id": plan_id,
        "status": status,
        "title": title,
        "directory": directory,
        "source_files": [f"docs/{directory.replace('/', '-')}.md"],
        "purpose": f"Canonical purpose owned by {title}.",
        "goal": f"Canonical raw goal owned by {title}.",
        "description": f"Canonical raw description owned by {title}.",
        "checkpoints": f"{directory}/Checkpoints.json",
        "kind": kind,
        "tree_mode": tree_mode,
        "node_status": node_status,
    }
    if entry_gate is not None:
        plan["entry_gate"] = entry_gate
    return plan


def tree_node(
    node_id: str,
    *,
    status: str,
    code: Optional[str],
    title: Optional[str],
    prerequisites: Optional[Sequence[str]] = None,
    tags: Optional[Sequence[str]] = None,
    conditions: Optional[Sequence[str]] = None,
    role: str = "implementation",
    next_refs: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    node: Dict[str, object] = {
        "id": node_id,
        "status": status,
        "role": role,
        "goal": f"Canonical raw goal for {code or title or node_id}.",
        "prerequisites": list(prerequisites or ()),
        "next": list(next_refs or ()),
    }
    if code is not None:
        node["code"] = code
    if title is not None:
        node["title"] = title
    if tags is not None:
        node["tags"] = list(tags)
    if conditions is not None:
        node["conditions"] = list(conditions)
    return node


def canonical_execution_fixture() -> Tuple[
    List[Dict[str, object]],
    List[List[Dict[str, object]]],
    List[Optional[str]],
]:
    """Build one source-grounded fixture matching the approved BadTower hand tree."""
    plans: List[Dict[str, object]] = []
    checkpoints: List[List[Dict[str, object]]] = []
    node_ids: Dict[str, str] = {}
    next_plan_id = 1000
    next_node_id = 1

    def add_plan(
        *,
        title: str,
        directory: str,
        status: str,
        kind: str,
        nodes: Optional[List[Dict[str, object]]] = None,
        tree_mode: str = "show",
        node_status: str = "show",
        entry_gate: Optional[Dict[str, object]] = None,
    ) -> None:
        nonlocal next_plan_id
        plans.append(
            tree_plan(
                uuid4(next_plan_id),
                title=title,
                directory=directory,
                status=status,
                kind=kind,
                tree_mode=tree_mode,
                node_status=node_status,
                entry_gate=entry_gate,
            )
        )
        checkpoints.append(nodes or [])
        next_plan_id += 1

    def add_node(
        code: str,
        title: str,
        status: str,
        prerequisites: Optional[Sequence[str]] = None,
        tags: Optional[Sequence[str]] = None,
        conditions: Optional[Sequence[str]] = None,
    ) -> Dict[str, object]:
        nonlocal next_node_id
        node_id = uuid4(next_node_id)
        next_node_id += 1
        node_ids[code] = node_id
        return tree_node(
            node_id,
            status=status,
            code=code,
            title=title,
            prerequisites=prerequisites,
            tags=tags,
            conditions=conditions,
        )

    def chain(
        entries: Sequence[Tuple[str, str]],
        *,
        status: str,
        first_prerequisites: Optional[Sequence[str]] = None,
        first_conditions: Optional[Sequence[str]] = None,
        first_tags: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, object]]:
        nodes: List[Dict[str, object]] = []
        previous_code: Optional[str] = None
        for index, (code, title) in enumerate(entries):
            prerequisites = (
                list(first_prerequisites or ())
                if index == 0
                else [node_ids[str(previous_code)]]
            )
            nodes.append(
                add_node(
                    code,
                    title,
                    status,
                    prerequisites,
                    tags=first_tags if index == 0 else None,
                    conditions=first_conditions if index == 0 else None,
                )
            )
            previous_code = code
        return nodes

    add_plan(
        title="BadTower Service-Layer Development Plan",
        directory="badtower",
        status="in_progress",
        kind="root",
    )
    add_plan(
        title="Plan Execution Contract",
        directory="badtower/plan-execution-contract",
        status="completed",
        kind="rule",
    )
    add_plan(
        title="Current Implementation Context",
        directory="badtower/current-implementation",
        status="completed",
        kind="context",
        tree_mode="hide",
        nodes=[
            add_node(
                "C0",
                "Supplemental current-state snapshot",
                "completed",
            )
        ],
    )
    add_plan(
        title="Approved Maturity Order",
        directory="badtower/maturity-order",
        status="in_progress",
        kind="group",
        tree_mode="flatten",
        nodes=[
            add_node(
                "PZ0",
                "Canonical maturity policy",
                "completed",
            )
        ],
    )

    k_entries = (
        ("K0", "Contract freeze"),
        ("K1", "Storage and state kernel"),
        ("K2", "Admission and scheduling"),
        ("K3", "Native API and lifecycle"),
        ("K4", "Packaging and observation"),
        ("K5", "Integrated-path removal"),
    )
    add_plan(
        title="Stage 0: Native Station Core",
        directory="badtower/maturity-order/stage-0-native-core",
        status="pending",
        kind="stage",
        nodes=chain(k_entries, status="pending", first_tags=["DESIGN_ONLY"]),
    )

    s_entries = (
        ("S0", "Candidate and boundary bind"),
        ("S1", "Native process acceptance"),
        ("S2", "Durable-state acceptance"),
        ("S3", "Pressure and performance acceptance"),
        ("S4", "Package and recovery drills"),
        ("S5", "Standalone closure"),
    )
    add_plan(
        title="Stage 1: Standalone Station Instance",
        directory="badtower/maturity-order/stage-1-standalone",
        status="pending",
        kind="stage",
        nodes=chain(
            s_entries,
            status="pending",
            first_prerequisites=[node_ids[code] for code, _ in k_entries],
        ),
    )

    h_entries = (
        ("H0", "Entry audit and freeze"),
        ("H1", "Membership and placement"),
        ("H2", "Replication and ownership safety"),
        ("H3", "Availability and performance"),
        ("H4", "Evolution and recovery"),
        ("H5", "Complete cluster closure"),
    )
    add_plan(
        title="Stage 2: High-Availability Station Cluster",
        directory="badtower/maturity-order/stage-2-ha-cluster",
        status="deferred",
        kind="stage",
        nodes=chain(
            h_entries,
            status="deferred",
            first_prerequisites=[node_ids["S5"]],
            first_conditions=["entry gate"],
        ),
    )

    native_requirements = [
        node_ids[code]
        for code, _ in (*k_entries, *s_entries, *h_entries)
    ]
    native_gate = add_node(
        "Native Excellence Gate",
        "Require every native milestone",
        "pending",
        native_requirements,
    )
    add_plan(
        title="Native Excellence Gate",
        directory="badtower/maturity-order/native-excellence-gate",
        status="pending",
        kind="gate",
        nodes=[native_gate],
    )

    e_entries = (
        ("E0", "Native gate audit"),
        ("E1", "Contract and descriptor"),
        ("E2", "Harness and SDK"),
        ("E3", "Isolation and packaging"),
        ("E4", "Complete extension closure"),
    )
    add_plan(
        title="Stage 3: External Extension Contract",
        directory="badtower/maturity-order/stage-3-extension-contract",
        status="deferred",
        kind="stage",
        nodes=chain(
            e_entries,
            status="deferred",
            first_prerequisites=[node_ids["Native Excellence Gate"]],
        ),
    )

    stage_4_directory = "badtower/maturity-order/stage-4-protocol-compatibility"
    add_plan(
        title="Stage 4: Optional Protocol Compatibility",
        directory=stage_4_directory,
        status="deferred",
        kind="group",
        entry_gate={
            "title": "Explicit selection gate",
            "prerequisites": [node_ids["E4"]],
            "conditions": ["owner", "immutable version"],
        },
    )

    plugin_specs = (
        (
            "LicoArc Plugin",
            "licoarc",
            (
                ("L0", "Admission freeze"),
                ("L1", "External adapter"),
                ("L2", "Isolation and budgets"),
                ("L3", "Core-absence audit"),
                ("L4", "Compatibility candidate"),
            ),
        ),
        (
            "A2A Plugin",
            "a2a",
            (
                ("A0", "Admission freeze"),
                ("A1", "Protocol boundary"),
                ("A2", "State and mapping"),
                ("A3", "Isolation and performance"),
                ("A4", "Independent candidate"),
            ),
        ),
        (
            "ACP Plugin",
            "acp",
            (
                ("P0", "Explicit admission"),
                ("P1", "Protocol boundary"),
                ("P2", "State and mapping"),
                ("P3", "Isolation and budgets"),
                ("P4", "Compatibility candidate"),
            ),
        ),
        (
            "MCP Plugin",
            "mcp",
            (
                ("M0", "Admission freeze"),
                ("M1", "Protocol boundary"),
                ("M2", "State and mapping"),
                ("M3", "Isolation and performance"),
                ("M4", "Independent candidate"),
            ),
        ),
    )
    for title, directory, entries in plugin_specs:
        add_plan(
            title=title,
            directory=f"{stage_4_directory}/{directory}",
            status="deferred",
            kind="branch",
            node_status="hide",
            nodes=chain(entries, status="deferred"),
        )

    # This pending hidden Node would steal CURRENT if visibility were ignored.
    add_plan(
        title="Release 0.2.0",
        directory="badtower/release-0.2.0",
        status="pending",
        kind="release",
        tree_mode="hide",
        nodes=[add_node("R0", "Supplemental release projection", "pending")],
    )
    return plans, checkpoints, [None] * len(plans)


APPROVED_BADTOWER_TREE = """Legend: [E] eligible   [B] blocked   [D] deferred
        [G] gate       [R] rule

Lifecycle:
DEFERRED --activate--> ELIGIBLE --dispatch--> ACTIVE --accept--> ACCEPTED

BadTower Service-Layer Development Plan
|
+-- Plan Execution Contract [R]
|
+-- Stage 0: Native Station Core
|   |
|   +-- K0 Contract freeze [E, DESIGN_ONLY]  <== CURRENT
|   +-- K1 Storage and state kernel [B <- K0]
|   +-- K2 Admission and scheduling [B <- K1]
|   +-- K3 Native API and lifecycle [B <- K2]
|   +-- K4 Packaging and observation [B <- K3]
|   \\-- K5 Integrated-path removal [B <- K4]
|
+-- Stage 1: Standalone Station Instance
|   |
|   +-- S0 Candidate and boundary bind [B <- K0-K5]
|   +-- S1 Native process acceptance [B <- S0]
|   +-- S2 Durable-state acceptance [B <- S1]
|   +-- S3 Pressure and performance acceptance [B <- S2]
|   +-- S4 Package and recovery drills [B <- S3]
|   \\-- S5 Standalone closure [B <- S4]
|
+-- Stage 2: High-Availability Station Cluster
|   |
|   +-- H0 Entry audit and freeze [D <- S5 + entry gate]
|   +-- H1 Membership and placement [D <- H0]
|   +-- H2 Replication and ownership safety [D <- H1]
|   +-- H3 Availability and performance [D <- H2]
|   +-- H4 Evolution and recovery [D <- H3]
|   \\-- H5 Complete cluster closure [D <- H4]
|
+-- Native Excellence Gate [G, B]
|   \\-- requires: K0-K5 + S0-S5 + H0-H5
|
+-- Stage 3: External Extension Contract
|   |
|   +-- E0 Native gate audit [D <- Native Excellence Gate]
|   +-- E1 Contract and descriptor [D <- E0]
|   +-- E2 Harness and SDK [D <- E1]
|   +-- E3 Isolation and packaging [D <- E2]
|   \\-- E4 Complete extension closure [D <- E3]
|
\\-- Stage 4: Optional Protocol Compatibility
    |
    \\-- Explicit selection gate [D <- E4 + owner + immutable version]
        |
        +-- LicoArc Plugin [D]
        |   +-- L0 Admission freeze
        |   +-- L1 External adapter
        |   +-- L2 Isolation and budgets
        |   +-- L3 Core-absence audit
        |   \\-- L4 Compatibility candidate
        |
        +-- A2A Plugin [D]
        |   +-- A0 Admission freeze
        |   +-- A1 Protocol boundary
        |   +-- A2 State and mapping
        |   +-- A3 Isolation and performance
        |   \\-- A4 Independent candidate
        |
        +-- ACP Plugin [D]
        |   +-- P0 Explicit admission
        |   +-- P1 Protocol boundary
        |   +-- P2 State and mapping
        |   +-- P3 Isolation and budgets
        |   \\-- P4 Compatibility candidate
        |
        \\-- MCP Plugin [D]
            +-- M0 Admission freeze
            +-- M1 Protocol boundary
            +-- M2 State and mapping
            +-- M3 Isolation and performance
            \\-- M4 Independent candidate"""


def write_tree_workspace(
    root: Path,
) -> Tuple[Path, List[Path], List[Dict[str, object]], List[List[Dict[str, object]]]]:
    plans, checkpoints, _ = canonical_execution_fixture()
    manifest = root / "Manifest.json"
    manifest.write_text(json.dumps(plans, ensure_ascii=False, indent=2), encoding="utf-8")
    checkpoint_paths: List[Path] = []
    for plan, nodes in zip(plans, checkpoints):
        directory = root / str(plan["directory"])
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "Checkpoints.json"
        path.write_text(json.dumps(nodes, ensure_ascii=False, indent=2), encoding="utf-8")
        checkpoint_paths.append(path)
    return manifest, checkpoint_paths, plans, checkpoints


class ReadablePlanTreeAcceptanceTests(unittest.TestCase):
    def test_plan_schema_requires_privacy_safe_purpose(self) -> None:
        schema = run_command(sys.executable, PYTHON_TOOL, "schema", "plan")
        self.assertEqual(schema.returncode, 0, schema.stderr)
        payload = json.loads(schema.stdout)
        self.assertIn("purpose", payload["required_fields"])
        self.assertEqual(
            payload["template"]["purpose"],
            "Why this Plan exists and what role it serves in the Plan hierarchy.",
        )

        invalid_values: List[Tuple[str, object, str]] = [
            ("missing", None, "purpose: missing required field"),
            ("empty", "", "purpose: must be a non-empty string"),
            ("multiline", "first line\nsecond line", "single line"),
            ("oversized", "x" * 501, "at most 500 characters"),
            ("absolute", "/protected/private-plan", "concrete absolute path"),
        ]
        for label, value, expected in invalid_values:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                write_workspace(root)
                plans = json.loads((root / "Manifest.json").read_text(encoding="utf-8"))
                if label == "missing":
                    plans[0].pop("purpose", None)
                else:
                    plans[0]["purpose"] = value
                (root / "Manifest.json").write_text(json.dumps(plans), encoding="utf-8")

                result = run_command(
                    sys.executable,
                    PYTHON_TOOL,
                    "validate",
                    root,
                    "--no-git",
                )

                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(expected, result.stderr)
                if label == "absolute":
                    self.assertNotIn(str(value), result.stdout + result.stderr)

    def test_default_projection_matches_the_approved_badtower_hand_tree(self) -> None:
        plans, checkpoints, errors = canonical_execution_fixture()

        rendered = render_workspace_tree(plans, checkpoints, errors)

        self.assertEqual(rendered, APPROVED_BADTOWER_TREE)
        self.assertEqual(rendered.count("<== CURRENT"), 1)
        self.assertNotRegex(
            rendered,
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        )
        for raw_label in ("Purpose:", "Goal:", "Description:", "Role:", "Status reason:"):
            with self.subTest(raw_label=raw_label):
                self.assertNotIn(raw_label, rendered)
        for hidden_or_flattened in (
            "Current Implementation Context",
            "Approved Maturity Order",
            "PZ0 Canonical maturity policy",
            "Release 0.2.0",
        ):
            with self.subTest(hidden_or_flattened=hidden_or_flattened):
                self.assertNotIn(hidden_or_flattened, rendered)
        for character in ("├", "─", "└", "│"):
            self.assertNotIn(character, rendered)

    def test_lifecycle_tags_and_current_are_derived_from_visible_canonical_state(self) -> None:
        root = tree_plan(
            uuid4(4000),
            title="Lifecycle Projection",
            directory="lifecycle",
            status="in_progress",
            kind="root",
        )
        nodes = [
            tree_node(uuid4(4010), status="in_progress", code="A0", title="Active work"),
            tree_node(uuid4(4011), status="completed", code="A1", title="Accepted work"),
            tree_node(uuid4(4012), status="skipped", code="A2", title="Skipped work"),
            tree_node(uuid4(4013), status="pending", code="A3", title="Eligible one"),
            tree_node(uuid4(4014), status="pending", code="A4", title="Eligible two"),
        ]

        rendered = render_workspace_tree([root], [nodes], [None])

        self.assertIn("A0 Active work [ACTIVE]", rendered)
        self.assertIn("A1 Accepted work [ACCEPTED]", rendered)
        self.assertIn("A2 Skipped work [SKIPPED]", rendered)
        self.assertIn("A3 Eligible one [E]", rendered)
        self.assertIn("A4 Eligible two [E]", rendered)
        self.assertNotIn("<== CURRENT", rendered)

    def test_ranges_require_a_complete_ordered_consecutive_code_run(self) -> None:
        root = tree_plan(
            uuid4(4100),
            title="Range Projection",
            directory="range",
            status="deferred",
            kind="root",
        )
        target_ids = [uuid4(4110), uuid4(4111), uuid4(4112)]
        nodes = [
            tree_node(target_ids[0], status="completed", code="K0", title="Zero"),
            tree_node(target_ids[1], status="completed", code="K1", title="One"),
            tree_node(target_ids[2], status="completed", code="K2", title="Two"),
            tree_node(
                uuid4(4113),
                status="deferred",
                code="D0",
                title="Ordered complete range",
                prerequisites=target_ids,
            ),
            tree_node(
                uuid4(4114),
                status="deferred",
                code="D1",
                title="Out-of-order dependency list",
                prerequisites=[target_ids[0], target_ids[2], target_ids[1]],
            ),
        ]

        rendered = render_workspace_tree([root], [nodes], [None])

        self.assertIn("D0 Ordered complete range [D <- K0-K2]", rendered)
        self.assertIn(
            "D1 Out-of-order dependency list [D <- K0 + K2 + K1]",
            rendered,
        )
        self.assertNotIn("D1 Out-of-order dependency list [D <- K0-K2]", rendered)

    def test_details_preserves_the_complete_emoji_audit_projection(self) -> None:
        plans, checkpoints, errors = canonical_execution_fixture()

        rendered = render_workspace_tree(plans, checkpoints, errors, details=True)

        for plan_title in (
            "BadTower Service-Layer Development Plan",
            "Current Implementation Context",
            "Approved Maturity Order",
            "Release 0.2.0",
            "Stage 0: Native Station Core",
            "MCP Plugin",
        ):
            with self.subTest(plan_title=plan_title):
                self.assertIn(f"📋 Plan: {plan_title}", rendered)
        for raw_record in (
            "🆔 ID:",
            "🎯 Purpose:",
            "🏁 Goal:",
            "📝 Description:",
            "🔹 Node:",
            "🧩 Role:",
            "🔗 Prerequisite (execution):",
            "🧭 Next (navigation only):",
        ):
            with self.subTest(raw_record=raw_record):
                self.assertIn(raw_record, rendered)
        for readable_record in (
            "Kind: root",
            "Tree mode: flatten",
            "Tree mode: hide",
            "Node status: hide",
            "Entry gate: Explicit selection gate",
            "🔹 Node: Canonical raw goal for PZ0. [✅ completed]",
            "Code: PZ0",
            "Title: Canonical maturity policy",
            "Code: K0",
            "Title: Contract freeze",
            "Tags: DESIGN_ONLY",
            "Conditions: entry gate",
        ):
            with self.subTest(readable_record=readable_record):
                self.assertIn(readable_record, rendered)
        for status in ("pending", "in_progress", "deferred", "completed"):
            with self.subTest(status=status):
                self.assertRegex(rendered, rf"\[[^\]]+ {status}\]")
        native_gate_id = next(
            node["id"]
            for nodes in checkpoints
            for node in nodes
            if node.get("code") == "Native Excellence Gate"
        )
        e0 = next(
            node
            for nodes in checkpoints
            for node in nodes
            if node.get("code") == "E0"
        )
        self.assertIn(f"{e0['id']} <-", rendered)
        self.assertIn(str(native_gate_id), rendered)

    def test_tree_cli_supports_details_subtrees_and_never_mutates_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest, checkpoints, _, _ = write_tree_workspace(root)
            state_paths = [manifest, *checkpoints]
            before = {path: path.read_bytes() for path in state_paths}

            complete = run_command(sys.executable, PYTHON_TOOL, "tree", root)
            details = run_command(
                sys.executable,
                PYTHON_TOOL,
                "tree",
                root,
                "--details",
            )
            selected = run_command(
                sys.executable,
                PYTHON_TOOL,
                "tree",
                root,
                "--plan",
                "badtower/maturity-order/stage-0-native-core",
            )
            selected_hidden = run_command(
                sys.executable,
                PYTHON_TOOL,
                "tree",
                root,
                "--plan",
                "badtower/release-0.2.0",
            )
            selected_flattened = run_command(
                sys.executable,
                PYTHON_TOOL,
                "tree",
                root,
                "--plan",
                "badtower/maturity-order",
            )

            self.assertEqual(complete.returncode, 0, complete.stderr)
            self.assertEqual(complete.stdout, f"{APPROVED_BADTOWER_TREE}\n")
            self.assertEqual(details.returncode, 0, details.stderr)
            self.assertIn("🌳 Better Plan Workspace", details.stdout)
            self.assertIn("📋 Plan: Current Implementation Context", details.stdout)
            self.assertIn("📋 Plan: Approved Maturity Order", details.stdout)
            self.assertIn("📋 Plan: Release 0.2.0", details.stdout)
            self.assertEqual(selected.returncode, 0, selected.stderr)
            self.assertIn("Stage 0: Native Station Core", selected.stdout)
            self.assertNotIn("Stage 1: Standalone Station Instance", selected.stdout)
            self.assertEqual(selected_hidden.returncode, 0, selected_hidden.stderr)
            self.assertIn("Release 0.2.0", selected_hidden.stdout)
            self.assertEqual(
                selected_flattened.returncode,
                0,
                selected_flattened.stderr,
            )
            self.assertIn("Approved Maturity Order", selected_flattened.stdout)
            self.assertIn(
                "PZ0 Canonical maturity policy [ACCEPTED]",
                selected_flattened.stdout,
            )
            for flattened_sibling in (
                "Plan Execution Contract",
                "Current Implementation Context",
                "Release 0.2.0",
            ):
                with self.subTest(flattened_sibling=flattened_sibling):
                    self.assertNotIn(flattened_sibling, selected_flattened.stdout)
            self.assertEqual(
                {path: path.read_bytes() for path in state_paths},
                before,
            )

    def test_guidance_requires_source_grounded_capability_and_delivery_projections(self) -> None:
        documents = {
            "skill": (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8"),
            "readme": (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
            "state": (REPO_ROOT / "references" / "state-files.md").read_text(
                encoding="utf-8"
            ),
        }

        for name, content in documents.items():
            contract = " ".join(content.casefold().split())
            with self.subTest(document=name):
                self.assertIn("source-grounded intent spine", contract)
                self.assertIn("readable", contract)
                self.assertIn("details", contract)
                self.assertIn("audit", contract)
                self.assertIn("one canonical workspace", contract)
                self.assertIn("capabilities.json", contract)
                self.assertRegex(contract, r"(repository.{0,32}root|parentless repository)")
                self.assertRegex(
                    contract,
                    r"(compare|check).{0,240}(readable|default).{0,240}(details|audit).{0,240}intent spine",
                )

        skill_contract = " ".join(documents["skill"].casefold().split())
        for field in (
            "purpose",
            "goal",
            "description",
            "status",
            "prerequisites",
            "non-dependencies",
            "kind",
            "tree_mode",
            "node_status",
            "entry_gate",
            "code",
            "title",
            "tags",
            "conditions",
        ):
            with self.subTest(skill_field=field):
                self.assertIn(field, skill_contract)
        self.assertRegex(
            skill_contract,
            r"(source|canonical).{0,160}(code|title).{0,160}(not|never).{0,120}(infer|invent|abbreviat)",
        )

        state_contract = " ".join(documents["state"].casefold().split())
        self.assertIn("`purpose`: required", state_contract)
        self.assertIn("sole execution-dependency authority", state_contract)
        self.assertIn("do not affect eligibility", state_contract)
        self.assertRegex(state_contract, r"tree.{0,80}--details")

    def test_renderer_is_part_of_the_canonical_installed_payload(self) -> None:
        self.assertIn(
            "scripts/better_plan/domain/tree.py",
            CURRENT_SKILL_FILES,
        )


if __name__ == "__main__":
    unittest.main()
