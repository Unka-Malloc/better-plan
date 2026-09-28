"""Current-state Tree, graph operations, checks, and immutable history."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import base64
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest

from scripts.better_plan.application import tree_workflow
from scripts.better_plan.application.tree_workflow import _overlay_edits, _subtree_nodes
from scripts.better_plan.domain.checkpoints_tree import adjacency, descendants, export_payload, new_tree, new_task, new_node, derived_state
from scripts.better_plan.domain.models import ToolError
from scripts.better_plan.infrastructure.workspace import check_lock
from scripts.better_plan.infrastructure.workspace import CurrentWorkspace, read_json, write_json


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "manifest_tool.py"


class CliWorkspace:
    def __init__(self, testcase: unittest.TestCase, root: Path):
        self.testcase = testcase
        self.root = root
        self.counter = 0

    def run(self, *arguments: str, expected: int = 0) -> subprocess.CompletedProcess:
        result = subprocess.run(
            [sys.executable, str(TOOL), *arguments],
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.testcase.assertEqual(result.returncode, expected, result.stderr)
        return result

    def input(self, value: object) -> str:
        self.counter += 1
        path = self.root / ("input-%d.json" % self.counter)
        path.write_text(json.dumps(value), encoding="utf-8")
        return str(path)

    def init(self) -> None:
        self.run("tree", "init", str(self.root), "--title", "Delivery", "--goal", "Ship it")

    def task(self, code: str, requirements: list[str] | None = None, checks=None) -> None:
        value = {
            "id": code,
            "title": code,
            "outcome": "Outcome for %s" % code,
            "requirements": requirements or [],
            "checks": checks or [],
        }
        self.run("task", "add", str(self.root), "--input", self.input(value))

    def node(
        self,
        code: str,
        task: str,
        after: list[str] | None = None,
        status: str = "pending",
        checks=None,
        contract=None,
    ) -> None:
        value = {
            "id": code,
            "task": task,
            "title": code,
            "outcome": "Outcome for %s" % code,
            "after": after or [],
            "status": status,
            "contract": contract or {},
            "checks": checks or [],
        }
        self.run("node", "add", str(self.root), "--input", self.input(value))


def check(code: str, coverage: dict, pending: bool = False, running: bool = False) -> dict:
    return {
        "id": code,
        "title": code,
        "commands": ['"%s" -c "print(1)"' % sys.executable],
        "coverage": coverage,
        "pending": pending,
        "running": running,
        "dirty": False,
        "result": {"status": "passed"} if not pending else None,
    }


class GraphAlgorithmTests(unittest.TestCase):
    def test_breadth_first_propagation_visits_diamond_and_cycle_once(self) -> None:
        nodes = {
            "A": {"after": ["D"]},
            "B": {"after": ["A"]},
            "C": {"after": ["A"]},
            "D": {"after": ["B", "C"]},
        }
        forward, reverse = adjacency(nodes)
        self.assertEqual(forward["A"], ["B", "C"])
        self.assertEqual(reverse["D"], ["B", "C"])
        self.assertEqual(descendants(nodes, ["A"]), ["A", "B", "C", "D"])

    def test_subtree_preserves_external_join_unless_named_as_exit(self) -> None:
        nodes = {
            "A": {"after": []},
            "B": {"after": ["A"]},
            "X": {"after": []},
            "J": {"after": ["B", "X"]},
            "K": {"after": ["J"]},
        }
        self.assertEqual(_subtree_nodes(nodes, ["A"]), ["A", "B"])
        self.assertEqual(_subtree_nodes(nodes, ["A"], ["J"]), ["A", "B", "J"])

    def test_editor_overlay_preserves_concurrent_fields(self) -> None:
        before = {"title": "old", "contract": {"scope": "a"}, "review": []}
        edited = {"title": "new", "contract": {"scope": "a"}, "review": []}
        latest = {"title": "old", "contract": {"scope": "a"}, "review": [{"source": "x"}]}
        self.assertEqual(
            _overlay_edits(latest, before, edited),
            {"title": "new", "contract": {"scope": "a"}, "review": [{"source": "x"}]},
        )


class SplitWorkspaceTests(unittest.TestCase):
    def test_leaf_field_update_is_local_and_recursively_merges_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cli = CliWorkspace(self, root)
            cli.init()
            cli.task("T")
            cli.node("A", "T", contract={"scope": "old", "design": {"api": "keep"}})
            history = root / "history" / "old.json"
            write_json(history, {"id": "old", "content": "immutable"})
            before = {
                "tree": (root / "Tree.json").read_bytes(),
                "task": (root / "tasks" / "T.json").read_bytes(),
                "history": history.read_bytes(),
            }

            cli.run(
                "node",
                "update",
                str(root),
                "A",
                "--input",
                cli.input({"contract": {"scope": "new"}}),
            )

            node = read_json(root / "nodes" / "A.json")
            self.assertEqual(node["contract"], {"scope": "new", "design": {"api": "keep"}})
            self.assertEqual((root / "Tree.json").read_bytes(), before["tree"])
            self.assertEqual((root / "tasks" / "T.json").read_bytes(), before["task"])
            self.assertEqual(history.read_bytes(), before["history"])

    def test_change_propagates_through_diamond_without_erasing_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cli = CliWorkspace(self, root)
            cli.init()
            cli.task("T1")
            cli.task("T2")
            cli.node("A", "T1")
            cli.node("B", "T1", ["A"])
            cli.node("C", "T2", ["A"])
            cli.node("D", "T2", ["B", "C"], status="completed")
            cli.node("E", "T2")
            cli.run("node", "finish", str(root), "D", "--summary", "kept result")

            cli.run("node", "update", str(root), "A", "--input", cli.input({"outcome": "changed"}))

            workspace = CurrentWorkspace(root)
            _, _, nodes = workspace.load()
            self.assertEqual([item["source"]["id"] for item in nodes["D"]["review"]], ["A"])
            self.assertEqual(nodes["D"]["status"], "completed")
            self.assertEqual(nodes["D"]["result"], {"summary": "kept result"})
            self.assertEqual(nodes["E"]["review"], [])
            next_payload = json.loads(cli.run("tree", "next", str(root), "--json").stdout)
            self.assertIn("D", [item["id"] for item in next_payload["review_needed"]])

            before = {path.name: path.read_bytes() for path in (root / "nodes").glob("*.json")}
            cli.run("node", "update", str(root), "A", "--input", cli.input({"outcome": "changed"}))
            after = {path.name: path.read_bytes() for path in (root / "nodes").glob("*.json")}
            self.assertEqual(after, before)

    def test_local_edit_is_not_blocked_by_an_unrelated_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cli = CliWorkspace(self, root)
            cli.init()
            cli.task("T")
            cli.node("A", "T")
            cli.node("B", "T", ["A"])
            a_path = root / "nodes" / "A.json"
            a = read_json(a_path)
            a["after"] = ["B"]
            write_json(a_path, a)
            cli.run("node", "update", str(root), "B", "--input", cli.input({"title": "still editable"}))
            self.assertEqual(read_json(root / "nodes" / "B.json")["title"], "still editable")

    def test_task_contains_multiple_nodes_in_export(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cli = CliWorkspace(self, root)
            cli.init()
            cli.task("T")
            cli.node("A", "T")
            cli.node("B", "T", ["A"])
            payload = json.loads(cli.run("tree", "export", str(root)).stdout)
            self.assertEqual(len(payload["tree"]["tasks"]), 1)
            self.assertEqual([node["id"] for node in payload["tree"]["tasks"][0]["nodes"]], ["A", "B"])


class StructuralOperationTests(unittest.TestCase):
    def test_insert_and_remove_rewire_without_dropping_extra_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cli = CliWorkspace(self, root)
            cli.init()
            cli.task("T")
            for code in ("A", "X"):
                cli.node(code, "T")
            cli.node("B", "T", ["A"])
            inserted = {
                "id": "N",
                "task": "T",
                "title": "N",
                "outcome": "inserted",
                "after": ["X"],
            }
            cli.run("node", "add", str(root), "--input", cli.input(inserted), "--between", "A", "B")
            self.assertEqual(read_json(root / "nodes" / "N.json")["after"], ["X", "A"])
            self.assertEqual(read_json(root / "nodes" / "B.json")["after"], ["N"])
            cli.run("node", "remove", str(root), "N")
            self.assertEqual(read_json(root / "nodes" / "B.json")["after"], ["X", "A"])

    def test_removing_disconnected_task_groups_reconnects_each_exit_to_its_own_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cli = CliWorkspace(self, root)
            cli.init()
            cli.task("REMOVE")
            cli.task("KEEP")
            cli.node("P1", "KEEP")
            cli.node("P2", "KEEP")
            cli.node("R1", "REMOVE", ["P1"])
            cli.node("R2", "REMOVE", ["P2"])
            cli.node("O1", "KEEP", ["R1"])
            cli.node("O2", "KEEP", ["R2"])
            cli.run("task", "remove", str(root), "REMOVE", "--with-nodes")
            self.assertEqual(read_json(root / "nodes" / "O1.json")["after"], ["P1"])
            self.assertEqual(read_json(root / "nodes" / "O2.json")["after"], ["P2"])

    def test_attach_and_move_use_explicit_boundaries_and_preserve_node_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cli = CliWorkspace(self, root)
            cli.init()
            cli.task("T")
            for code in ("X", "U", "K"):
                cli.node(code, "T")
            cli.node("A", "T", status="completed")
            cli.node("B", "T", ["A"], status="completed")
            cli.node("J", "T", ["U"])
            cli.node("L", "T", ["J"])
            cli.node("Z", "T", ["A", "U"])
            b_path = root / "nodes" / "B.json"
            b = read_json(b_path)
            b["result"] = {"summary": "preserve"}
            write_json(b_path, b)

            attached = json.loads(
                cli.run(
                    "subtree", "attach", str(root), "A", "--exit", "B",
                    "--after", "X", "--before", "J",
                ).stdout
            )
            self.assertIn({"action": "add", "from": "B", "to": "J"}, attached["edges"])
            self.assertEqual(read_json(root / "nodes" / "A.json")["after"], ["X"])
            self.assertEqual(read_json(root / "nodes" / "J.json")["after"], ["U", "B"])
            cli.run("node", "review-done", str(root), "J")
            cli.run("node", "review-done", str(root), "L")

            cli.run(
                "subtree", "move", str(root), "A", "--exit", "B",
                "--after", "--before", "K",
            )
            self.assertEqual(read_json(root / "nodes" / "A.json")["after"], [])
            self.assertEqual(read_json(root / "nodes" / "J.json")["after"], ["U"])
            self.assertEqual(read_json(root / "nodes" / "K.json")["after"], ["B"])
            self.assertEqual(read_json(root / "nodes" / "Z.json")["after"], ["A", "U"])
            self.assertTrue(read_json(root / "nodes" / "J.json")["review"])
            self.assertTrue(read_json(root / "nodes" / "L.json")["review"])
            preserved = read_json(root / "nodes" / "B.json")
            self.assertEqual(preserved["status"], "completed")
            self.assertEqual(preserved["result"], {"summary": "preserve"})


class CheckSchedulingTests(unittest.TestCase):
    def test_only_intersecting_checks_are_invalidated_and_running_check_becomes_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cli = CliWorkspace(self, root)
            cli.init()
            cli.task("T")
            cli.node("A", "T")
            cli.node("E", "T")
            checks = [
                check("CA", {"kind": "nodes", "nodes": ["A"]}, running=True),
                check("CE", {"kind": "nodes", "nodes": ["E"]}),
            ]
            cli.run("tree", "update", str(root), "--input", cli.input({"checks": checks}))
            cli.run("node", "update", str(root), "A", "--input", cli.input({"outcome": "changed"}))
            tree = read_json(root / "Tree.json")
            by_id = {item["id"]: item for item in tree["checks"]}
            self.assertTrue(by_id["CA"]["pending"])
            self.assertTrue(by_id["CA"]["dirty"])
            self.assertFalse(by_id["CE"]["pending"])
            self.assertFalse(by_id["CE"]["dirty"])

    def test_check_can_run_before_covered_node_completes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cli = CliWorkspace(self, root)
            cli.init()
            cli.task("T", checks=[check("C", {"kind": "task"}, pending=True)])
            cli.node("A", "T")
            result = cli.run("checks", "run", str(root), "C", "--owner", "task:T")
            self.assertTrue(json.loads(result.stdout)["passed"])
            stored = read_json(root / "tasks" / "T.json")["checks"][0]
            self.assertFalse(stored["pending"])
            self.assertEqual(stored["result"]["status"], "passed")

    def test_change_during_actual_run_only_dirties_intersecting_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cli = CliWorkspace(self, root)
            cli.init()
            cli.task("T", checks=[check("C", {"kind": "nodes", "nodes": ["A"]}, pending=True)])
            cli.node("A", "T")
            cli.node("E", "T")
            args = SimpleNamespace(root=str(root), owner="task:T", id="C", cwd=None)

            def modify_unrelated(project_root, commands):
                tree_workflow._update_node(root, "E", {"outcome": "unrelated"})
                return True, [{"outcome": "passed"}], []

            with patch.object(tree_workflow, "run_commands_with_diagnostics", modify_unrelated):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(tree_workflow.run_check(args), 0)
            self.assertFalse(read_json(root / "tasks" / "T.json")["checks"][0]["pending"])

            def modify_related(project_root, commands):
                tree_workflow._update_node(root, "A", {"outcome": "related"})
                return True, [{"outcome": "passed"}], []

            with patch.object(tree_workflow, "run_commands_with_diagnostics", modify_related):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(tree_workflow.run_check(args), 0)
            stored = read_json(root / "tasks" / "T.json")["checks"][0]
            self.assertTrue(stored["pending"])
            self.assertTrue(stored["dirty"])
            self.assertEqual(stored["result"]["status"], "passed")


class WorkerAndHistoryTests(unittest.TestCase):
    def test_start_and_finish_print_context_without_check_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cli = CliWorkspace(self, root)
            cli.init()
            cli.run("tree", "update", str(root), "--input", cli.input({"requirements": ["shared"]}))
            cli.task("T", requirements=["task rule"])
            cli.node("A", "T", checks=[check("C", {"kind": "node"}, pending=True)])
            started = json.loads(cli.run("node", "start", str(root), "A").stdout)
            self.assertEqual(started["tree"]["goal"], "Ship it")
            self.assertEqual(started["task"]["outcome"], "Outcome for T")
            self.assertEqual(started["requirements"], {"tree": ["shared"], "task": ["task rule"]})
            finished = json.loads(cli.run("node", "finish", str(root), "A", "--summary", "done").stdout)
            self.assertIn("does not gate", finished["confirmation_prompt"])
            self.assertEqual(read_json(root / "nodes" / "A.json")["status"], "completed")

    def test_node_commit_and_task_draft_pr_are_current_references_with_advisory_reminders(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cli = CliWorkspace(self, root)
            cli.init()
            cli.task("T")
            cli.node("A", "T")
            cli.node("B", "T", ["A"])
            cli.run("task", "update", str(root), "T", "--input", cli.input({"integration_owner":"task-lead"}))

            first = json.loads(
                cli.run("node", "finish", str(root), "A", "--summary", "done", "--commit", "abc123").stdout
            )
            self.assertFalse(first["ready_for_integration"])
            self.assertEqual(first["commit_reference"], "abc123")
            self.assertNotIn("draft_pr_reminder", first)

            cli.run(
                "task",
                "update",
                str(root),
                "T",
                "--input",
                cli.input({"draft_pr": "https://example.invalid/pr/7"}),
            )
            self.assertEqual(read_json(root / "nodes" / "A.json")["review"], [])
            reviews_before = read_json(root / "nodes" / "B.json")["review"]
            self.assertTrue(reviews_before)
            cli.run("node", "update", str(root), "A", "--input", cli.input({"commit": "updated-ref"}))
            self.assertEqual(read_json(root / "nodes" / "A.json")["review"], [])
            self.assertEqual(read_json(root / "nodes" / "B.json")["review"], reviews_before)
            cli.run(
                "tree",
                "update",
                str(root),
                "--input",
                cli.input({"delivery_policy": {"pull_requests": "draft_until_tree_review"}}),
            )
            last = json.loads(
                cli.run("node", "finish", str(root), "B", "--summary", "done", "--commit", "def456").stdout
            )
            self.assertTrue(last["ready_for_integration"])
            self.assertEqual(last["integration_owner"], "task-lead")
            self.assertEqual(last["task"]["draft_pr"], "https://example.invalid/pr/7")
            self.assertIn("designated integration owner", last["integration_reminder"])
            self.assertEqual(last["tree"]["delivery_policy"]["pull_requests"], "draft_until_tree_review")
            self.assertIn("separate authorization", last["integration_reminder"])
            self.assertEqual(read_json(root / "nodes" / "A.json")["commit"], "updated-ref")
            self.assertEqual(read_json(root / "tasks" / "T.json")["draft_pr"], "https://example.invalid/pr/7")

            for command in (("task", "finish", str(root), "T", "--summary", "Integrated"),
                            ("tree", "finish", str(root), "--summary", "Engineering reviewed")):
                cli.run(*command)
            confirmed = json.loads(cli.run("tree", "export", str(root)).stdout)
            self.assertEqual(confirmed["derived"]["delivery_status"], "recorded")
            cli.run("node", "update", str(root), "A", "--input", cli.input({"commit":"repair-ref"}))
            dirty = json.loads(cli.run("tree", "status", str(root), "--json").stdout)
            self.assertEqual(dirty["delivery_status"], "needs_review")
            for command in (("task", "finish", str(root), "T", "--summary", "Repair integrated"),
                            ("tree", "finish", str(root), "--summary", "Repair reviewed")):
                cli.run(*command)
            self.assertEqual(json.loads(cli.run("tree", "export", str(root)).stdout)["derived"]["delivery_status"], "recorded")

            cli.task("T2")
            cli.node("C", "T2")
            missing = json.loads(cli.run("node", "finish", str(root), "C", "--summary", "done").stdout)
            self.assertIn("one scoped commit", missing["commit_reminder"])
            self.assertIn("Hand off", missing["integration_reminder"])

    def test_history_is_append_only_searchable_and_attachment_is_byte_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cli = CliWorkspace(self, root)
            cli.init()
            transcript = root / "conversation.txt"
            transcript.write_text("user said keep history", encoding="utf-8", newline="")
            attachment = root / "legacy.bin"
            original = b"legacy\r\nbytes\x00\xff"
            attachment.write_bytes(original)
            cli.run(
                "history",
                "archive",
                str(root),
                "--input",
                str(transcript),
                "--kind",
                "transcript",
                "--source",
                "chat",
                "--id",
                "H1",
                "--attach",
                str(attachment),
            )
            entry = read_json(root / "history" / "H1.json")
            self.assertEqual(base64.b64decode(entry["attachments"][0]["content"]), original)
            self.assertEqual(json.loads(cli.run("history", "search", str(root), "keep history").stdout)[0]["id"], "H1")
            refused = cli.run(
                "history",
                "archive",
                str(root),
                "--input",
                str(transcript),
                "--kind",
                "summary",
                "--source",
                "chat",
                "--id",
                "H1",
                expected=1,
            )
            self.assertIn("already exists", refused.stderr)


class DeliveryAndCheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.ws = CurrentWorkspace(self.root)
        self.ws.write_tree(new_tree("TREE", "Delivery"))
        for code in ("T", "U", "X", "EMPTY"):
            task = new_task(code, code)
            task["integration_owner"] = "coordinator-" + code
            self.ws.write_task(task)
        for code, owner, after in (("A", "T", []), ("B", "U", ["A"]), ("Z", "X", [])):
            node = new_node(code, owner, code, after=after)
            node["status"] = "completed"
            self.ws.write_node(node)
        self.output = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def args(self, **kwargs):
        return SimpleNamespace(root=str(self.root), **kwargs)

    def finish_all(self):
        for code in ("T", "U", "X", "EMPTY"):
            tree_workflow.finish_delivery(self.args(id=code, result=None, summary="Integrated"))
        tree_workflow.finish_delivery(self.args(result=None, summary="Reviewed; PRs remain Draft"))

    def install_checks(self):
        tree, tasks, nodes = self.ws.load()
        tasks["T"]["checks"] = [check("C", {"kind": "task"}), check("D", {"kind": "task"})]
        self.ws.write_task(tasks["T"])
        return self.args(owner="task:T", id="C", cwd=None)

    def test_explicit_delivery_and_reconfirmation_do_not_erase_child_facts(self):
        self.assertEqual(derived_state(*self.ws.load())["delivery_status"], "unrecorded")
        self.finish_all()
        tree_before, tasks_before, _ = self.ws.load()
        tree_workflow._update_node(self.root, "A", {"commit": "new-commit"})
        tree, tasks, nodes = self.ws.load()
        state = derived_state(tree, tasks, nodes)
        self.assertEqual(state["task_delivery_status"], {"T":"needs_review", "U":"needs_review", "X":"recorded", "EMPTY":"recorded"})
        self.assertEqual(tree["delivery"]["result"], tree_before["delivery"]["result"])
        self.assertEqual(tasks["T"]["delivery"]["result"], tasks_before["T"]["delivery"]["result"])
        self.assertTrue(nodes["B"]["review"])
        tree_workflow.finish_delivery(self.args(result=None, summary="Cannot mask Tasks"))
        self.assertEqual(derived_state(*self.ws.load())["delivery_status"], "needs_review")
        for code in ("T", "U"):
            tree_workflow.finish_delivery(self.args(id=code, result=None, summary="Reconfirmed"))
        tree_workflow.finish_delivery(self.args(result=None, summary="Reconfirmed Tree"))
        self.assertEqual(derived_state(*self.ws.load())["delivery_status"], "recorded")
        self.assertTrue(self.ws.load()[2]["B"]["review"])
        self.assertEqual(self.ws.load()[2]["A"]["status"], "completed")

    def test_management_and_identical_changes_are_noops_for_delivery(self):
        self.finish_all()
        tree_workflow._update_node(self.root, "A", {"title": "Display", "role": "worker"})
        before = (self.root / "Tree.json").read_bytes()
        tree_workflow._update_node(self.root, "A", {"title": "Display"})
        patch_file = self.root / "patch.json"
        write_json(patch_file, {"title": "Display", "integration_owner": "new-owner", "draft_pr": "draft-reference"})
        tree_workflow.update_task(self.args(id="T", input=str(patch_file)))
        self.assertEqual((self.root / "Tree.json").read_bytes(), before)
        self.assertEqual(derived_state(*self.ws.load())["delivery_status"], "recorded")

    def test_membership_changes_cover_old_new_and_downstream_tasks(self):
        self.finish_all()
        tree_workflow._update_node(self.root, "A", {"task": "EMPTY"})
        state = derived_state(*self.ws.load())
        self.assertEqual(set(k for k,v in state["task_delivery_status"].items() if v == "needs_review"), {"T", "U", "EMPTY"})
        self.finish_all()
        tree_workflow.remove_node(self.args(id="A", disconnect=False))
        state = derived_state(*self.ws.load())
        self.assertEqual(state["task_delivery_status"]["EMPTY"], "needs_review")
        self.assertEqual(state["task_delivery_status"]["U"], "needs_review")
        self.finish_all()
        tree_workflow.remove_task(self.args(id="EMPTY", with_nodes=False))
        self.assertEqual(derived_state(*self.ws.load())["delivery_status"], "needs_review")

    def test_empty_task_requirements_and_tree_requirements_invalidate_delivery(self):
        self.finish_all()
        patch_file = self.root / "patch.json"
        write_json(patch_file, {"requirements": ["New requirement"]})
        tree_workflow.update_task(self.args(id="EMPTY", input=str(patch_file)))
        self.assertEqual(derived_state(*self.ws.load())["task_delivery_status"]["EMPTY"], "needs_review")
        self.finish_all()
        tree_workflow.update_tree(self.args(input=str(patch_file)))
        self.assertEqual(set(derived_state(*self.ws.load())["task_delivery_status"].values()), {"needs_review"})

    def test_restart_marks_owner_but_result_change_notifies_downstream(self):
        self.finish_all()
        tree_workflow.start_node(self.args(id="A"))
        state = derived_state(*self.ws.load())
        self.assertEqual(state["task_delivery_status"]["T"], "needs_review")
        self.assertEqual(state["task_delivery_status"]["U"], "recorded")
        tree_workflow.finish_node(self.args(id="A", result=None, summary="new evidence", commit=None))
        self.assertEqual(derived_state(*self.ws.load())["task_delivery_status"]["U"], "needs_review")
        self.finish_all()
        before = (self.root / "Tree.json").read_bytes()
        tree_workflow.finish_node(self.args(id="A", result=None, summary="new evidence", commit=None))
        self.assertEqual((self.root / "Tree.json").read_bytes(), before)

    def test_checks_invalidate_only_coverage_and_pass_does_not_reconfirm(self):
        args = self.install_checks()
        self.finish_all()
        tree_workflow.record_check(self.args(owner="task:T", id="C", result=None, status="failed", summary="failure"))
        state = derived_state(*self.ws.load())
        self.assertEqual(state["task_delivery_status"]["T"], "needs_review")
        self.assertEqual(state["task_delivery_status"]["U"], "recorded")
        tree_workflow.record_check(self.args(owner="task:T", id="C", result=None, status="passed", summary="pass"))
        self.assertEqual(derived_state(*self.ws.load())["task_delivery_status"]["T"], "needs_review")
        self.finish_all()
        patch_file = self.root / "patch.json"
        write_json(patch_file, {"checks": [check("C", {"kind":"nodes", "nodes":["Z"]})]})
        tree_workflow.update_task(self.args(id="T", input=str(patch_file)))
        states = derived_state(*self.ws.load())["task_delivery_status"]
        self.assertEqual(states["T"], "needs_review")
        self.assertEqual(states["X"], "needs_review")
        self.assertEqual(states["U"], "recorded")

    def test_check_lock_prevents_overlaps_but_allows_other_checks(self):
        args = self.install_checks()
        def execute(*unused):
            with self.assertRaisesRegex(ToolError, "already running"):
                tree_workflow.run_check(args)
            with self.assertRaisesRegex(ToolError, "already running"):
                tree_workflow.record_check(self.args(owner="task:T", id="C", result=None, status="passed", summary="external"))
            with self.assertRaisesRegex(ToolError, "already running"):
                tree_workflow.recover_check(args)
            # Prove the lock crosses process boundaries, rather than only protecting this interpreter.
            cli = CliWorkspace(self, self.root)
            result = cli.run("checks", "run", str(self.root), "C", "--owner", "task:T", expected=1)
            self.assertIn("already running", result.stderr)
            tree_workflow.record_check(self.args(owner="task:T", id="D", result=None, status="passed", summary="other"))
            self.assertFalse(tree_workflow._snapshot(self.root)[1]["T"]["checks"][0]["interrupted"])
            return True, [], []
        with patch.object(tree_workflow, "run_commands_with_diagnostics", execute):
            tree_workflow.run_check(args)

    def test_removed_and_recreated_check_rejects_old_execution_result(self):
        args = self.install_checks()
        def execute(*unused):
            patch_file = self.root / "patch.json"
            for definitions in ([], [check("C", {"kind":"task"})]):
                write_json(patch_file, {"checks": definitions})
                tree_workflow.update_task(self.args(id="T", input=str(patch_file)))
            return False, [{"outcome":"failed"}], []
        with patch.object(tree_workflow, "run_commands_with_diagnostics", execute):
            with self.assertRaisesRegex(ToolError, "replaced"):
                tree_workflow.run_check(args)
        stored = self.ws.load()[1]["T"]["checks"][0]
        self.assertEqual(stored["result"], {"status":"passed"})

    def test_node_editor_preserves_active_check_identity_and_marks_definition_dirty(self):
        tree, tasks, nodes = self.ws.load()
        nodes["A"]["checks"] = [check("C", {"kind":"node"})]
        self.ws.write_node(nodes["A"])
        base = self.ws.load()[2]["A"]
        args = self.args(owner="node:A", id="C", cwd=None)
        def execute(*unused):
            edited = json.loads(json.dumps(base))
            edited["checks"][0]["commands"] = ["updated command"]
            tree_workflow._update_node(self.root, "A", edited, replace=True, edit_base=base)
            return True, [], []
        with patch.object(tree_workflow, "run_commands_with_diagnostics", execute):
            tree_workflow.run_check(args)
        stored = self.ws.load()[2]["A"]["checks"][0]
        self.assertTrue(stored["pending"])
        self.assertTrue(stored["dirty"])
        self.assertIsNone(stored["run_id"])
        self.assertEqual(stored["commands"], ["updated command"])

    def test_process_exit_requires_explicit_recovery_and_preserves_result(self):
        args = self.install_checks()
        code = """
import os, sys
from types import SimpleNamespace
from scripts.better_plan.application import tree_workflow as w
w.run_commands_with_diagnostics = lambda *args: os._exit(7)
w.run_check(SimpleNamespace(root=sys.argv[1], owner='task:T', id='C', cwd=None))
"""
        result = subprocess.run([sys.executable, "-c", code, str(self.root)], cwd=str(ROOT), capture_output=True)
        self.assertEqual(result.returncode, 7)
        self.assertTrue(tree_workflow._snapshot(self.root)[1]["T"]["checks"][0]["interrupted"])
        with self.assertRaisesRegex(ToolError, "checks recover"):
            tree_workflow.run_check(args)
        with self.assertRaisesRegex(ToolError, "checks recover"):
            tree_workflow.record_check(self.args(owner="task:T", id="C", result=None, status="passed", summary="external"))
        recovered = CliWorkspace(self, self.root).run("checks", "recover", str(self.root), "C", "--owner", "task:T")
        self.assertTrue(json.loads(recovered.stdout)["recovered"])
        stored = self.ws.load()[1]["T"]["checks"][0]
        self.assertEqual(stored["result"], {"status":"passed"})
        self.assertTrue(stored["pending"])
        self.assertFalse(stored["running"])
        with patch.object(tree_workflow, "run_commands_with_diagnostics", return_value=(True, [], [])):
            tree_workflow.run_check(args)


if __name__ == "__main__":
    unittest.main()
