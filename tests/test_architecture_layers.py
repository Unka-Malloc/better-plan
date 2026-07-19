"""Architectural layer enforcement tests for Better Plan workflow code."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import ast
import importlib
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
BETTER_PLAN_DIR = SCRIPTS_DIR / "better_plan"
MANIFEST_TOOL = SCRIPTS_DIR / "manifest_tool.py"
INSTALL_TOOL = SCRIPTS_DIR / "install.py"

MAX_FILE_LINES = 1400

TRY_NODE_TYPES: tuple[type[ast.AST], ...] = (ast.Try,)
if hasattr(ast, "TryStar"):
    TRY_NODE_TYPES += (ast.TryStar,)

REQUIRED_SYMBOLS = {
    "workflow_state_machine": ("WorkflowStateMachine", "scripts.better_plan.domain.models"),
    "transition": ("transition", "scripts.better_plan.domain.transitions"),
    "validate_design_contract": ("validate_design_contract", "scripts.better_plan.domain.design"),
    "reference_for_action": ("reference_for_action", "scripts.better_plan.domain.roles"),
    "validate_checkpoints_data": ("validate_checkpoints_data", "scripts.better_plan.domain.validation"),
    "node_location": ("NodeLocation", "scripts.better_plan.infrastructure.workspace"),
    "run_regression_at_location": ("run_regression_at_location", "scripts.better_plan.infrastructure.regression"),
    "advance_command": ("advance_command", "scripts.better_plan.application.workflow"),
    "manifest_main": ("main", "scripts.better_plan.adapters.manifest_cli"),
    "install_paths": ("InstallPaths", "scripts.better_plan.installation.models"),
    "copy_skill_tree": ("copy_skill_tree", "scripts.better_plan.installation.skills"),
    "install_target": ("install_target", "scripts.better_plan.installation.targets"),
    "doctor": ("doctor", "scripts.better_plan.installation.doctor"),
    "install_agents": ("install_agents", "scripts.better_plan.installation.service"),
    "uninstall_agents": ("uninstall_agents", "scripts.better_plan.installation.service"),
    "uninstall_hooks": ("uninstall_hooks", "scripts.better_plan.installation.service"),
    "remove_target": ("remove_target", "scripts.better_plan.installation.targets"),
    "install_hook_config": ("install_hook_config", "scripts.better_plan.hooks.config"),
    "uninstall_hook_config": ("uninstall_hook_config", "scripts.better_plan.hooks.config"),
    "install_main": ("main", "scripts.better_plan.adapters.install_cli"),
}

LAYER_PREFIXES = {
    "scripts.better_plan.domain": "domain",
    "scripts.better_plan.infrastructure": "infrastructure",
    "scripts.better_plan.application": "application",
    "scripts.better_plan.adapters": "adapters",
    "scripts.better_plan.hooks": "hooks",
    "scripts.better_plan.installation": "installation",
    "scripts.manifest_tool": "manifest_tool",
    "scripts.install": "install_tool",
}

FORBIDDEN_IMPORTS = {
    "domain": {"application", "infrastructure", "adapters", "hooks", "installation"},
    "infrastructure": {"application", "adapters", "hooks", "installation"},
    "application": {"adapters", "hooks", "installation"},
}

MODULE_FORBIDDEN_PREFIXES = {
    "scripts.better_plan.installation.models": (
        "scripts.better_plan.installation.skills",
        "scripts.better_plan.installation.targets",
        "scripts.better_plan.installation.doctor",
        "scripts.better_plan.installation.service",
        "scripts.better_plan.adapters",
        "scripts.better_plan.hooks",
    ),
    "scripts.better_plan.installation.skills": (
        "scripts.better_plan.installation.targets",
        "scripts.better_plan.installation.doctor",
        "scripts.better_plan.installation.service",
        "scripts.better_plan.adapters",
        "scripts.better_plan.hooks",
    ),
    "scripts.better_plan.installation.targets": (
        "scripts.better_plan.installation.doctor",
        "scripts.better_plan.installation.service",
        "scripts.better_plan.adapters",
    ),
    "scripts.better_plan.installation.doctor": (
        "scripts.better_plan.installation.service",
        "scripts.better_plan.adapters",
    ),
    "scripts.better_plan.installation.service": (
        "scripts.better_plan.installation.doctor",
        "scripts.better_plan.adapters",
    ),
}


@dataclass(frozen=True)
class Violation:
    path: Path
    lineno: int
    message: str

    def as_text(self) -> str:
        return f"{self.path}:{self.lineno}: {self.message}"


def module_name_from_path(path: Path, root: Path = ROOT) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    if not parts:
        return ""
    if parts[0] != "scripts":
        return ".".join(parts)
    return ".".join(parts)


def layer_for_module(module: str) -> str:
    if module == "scripts":
        return "scripts"
    for prefix, layer in LAYER_PREFIXES.items():
        if module == prefix or module.startswith(prefix + "."):
            return layer
    if module.startswith("scripts."):
        return "scripts"
    return "external"


def resolve_importfrom_module(node: ast.ImportFrom, current_module: str) -> str | None:
    if node.level == 0:
        return node.module
    current_parts = current_module.split(".")
    if node.level > len(current_parts):
        return node.module
    base = current_parts[: -node.level]
    if node.module:
        return ".".join([*base, node.module])
    return ".".join(base)


def is_sys_path_mutation(node: ast.AST) -> bool:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if _is_sys_path_target(target):
                return True
    if isinstance(node, ast.AugAssign):
        return _is_sys_path_target(node.target)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr not in {"append", "insert", "extend", "pop", "remove", "clear"}:
            return False
        return (
            isinstance(node.func.value, ast.Attribute)
            and isinstance(node.func.value.value, ast.Name)
            and node.func.value.value.id == "sys"
            and node.func.value.attr == "path"
        )
    return False


def _is_sys_path_target(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "path"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    ) or (
        isinstance(node, ast.Subscript)
        and _is_sys_path_target(node.value)
    )


def symbol_ownership_violations(
    trees: dict[Path, ast.AST],
    required: dict[str, tuple[str, str]],
    root: Path,
) -> list[Violation]:
    expected_modules: dict[str, set[str]] = defaultdict(set)
    for symbol, module in required.values():
        expected_modules[symbol].add(module)
    definitions: dict[str, set[Path]] = {name: set() for name in expected_modules}
    reexports: dict[str, set[tuple[Path, int]]] = defaultdict(set)

    for path, tree in trees.items():
        module = module_name_from_path(path, root=root)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in expected_modules:
                definitions[node.name].add(path)
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    public_name = alias.asname or alias.name
                    if public_name in expected_modules and module not in expected_modules[public_name]:
                        reexports[public_name].add((path, node.lineno))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    public_name = alias.asname or alias.name.rsplit(".", 1)[-1]
                    if public_name in expected_modules and module not in expected_modules[public_name]:
                        reexports[public_name].add((path, node.lineno))

    findings = []
    for _, (symbol, canonical_module) in required.items():
        canonical_path = root / f"{canonical_module.replace('.', '/')}.py"
        owners = definitions[symbol]
        if not owners:
            findings.append(
                Violation(canonical_path, 1, f"missing required symbol definition: {symbol}")
            )
            continue
        if canonical_path not in owners:
            findings.append(
                Violation(
                    canonical_path,
                    1,
                    f"{symbol} must be defined in {canonical_module}, found in {[module_name_from_path(p, root=root) for p in owners]}",
                )
            )
        allowed_paths = {
            root / f"{module.replace('.', '/')}.py"
            for module in expected_modules[symbol]
        }
        if owners != allowed_paths:
            findings.append(
                Violation(
                    canonical_path,
                    1,
                    f"{symbol} definition set differs from canonical modules: {sorted(module_name_from_path(p, root=root) for p in owners)}",
                )
            )
        for path, lineno in reexports[symbol]:
            if path not in allowed_paths:
                findings.append(
                    Violation(path, lineno, f"{symbol} is re-exported/aliased outside canonical module")
                )

    return findings


def dependency_and_antipattern_violations(
    trees: dict[Path, ast.AST],
    root: Path,
    layer_forbidden: dict[str, set[str]],
) -> list[Violation]:
    findings: list[Violation] = []

    for path, tree in trees.items():
        module = module_name_from_path(path, root=root)
        module_layer = layer_for_module(module)
        forbidden_import_layers = layer_forbidden.get(module_layer, set())
        forbidden_module_prefixes = MODULE_FORBIDDEN_PREFIXES.get(module, ())

        def check_module_dependency(imported_module: str, lineno: int) -> None:
            if any(
                imported_module == prefix or imported_module.startswith(prefix + ".")
                for prefix in forbidden_module_prefixes
            ):
                findings.append(
                    Violation(path, lineno, f"forbidden module dependency: {module} -> {imported_module}")
                )

        for node in ast.walk(tree):
            if isinstance(node, TRY_NODE_TYPES):
                for handler in node.handlers:
                    if isinstance(handler.type, ast.Name) and handler.type.id == "ImportError":
                        findings.append(Violation(path, node.lineno, "disallow fallback imports with except ImportError"))
                    if isinstance(handler.type, ast.Attribute) and handler.type.attr == "ImportError":
                        findings.append(Violation(path, node.lineno, "disallow fallback imports with except ImportError"))

            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                    findings.append(Violation(path, node.lineno, "disallow __import__"))
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "importlib"
                ):
                    findings.append(Violation(path, node.lineno, "disallow importlib runtime import API"))

            if is_sys_path_mutation(node) and not (
                module in {"scripts.manifest_tool", "scripts.install"}
                and _is_entry_path_bootstrap(node)
            ):
                findings.append(Violation(path, node.lineno, "disallow cross-layer sys.path mutation"))

            if isinstance(node, ast.ImportFrom):
                imported_module = resolve_importfrom_module(node, module)
                if imported_module is None:
                    continue
                imported_layer = layer_for_module(imported_module)
                check_module_dependency(imported_module, node.lineno)
                if node.module is None:
                    for alias in node.names:
                        check_module_dependency(f"{imported_module}.{alias.name}", node.lineno)
                if imported_layer in forbidden_import_layers and module_layer != imported_layer:
                    findings.append(
                        Violation(
                            path,
                            node.lineno,
                            f"forbidden dependency: {module} -> {imported_module}",
                        )
                    )
                if imported_module == "importlib" or imported_module.startswith("importlib."):
                    findings.append(Violation(path, node.lineno, "disallow importlib module import"))
                if any(alias.name == "*" for alias in node.names):
                    if imported_module.startswith("scripts."):
                        findings.append(
                            Violation(path, node.lineno, f"forbidden wildcard import from {imported_module}")
                        )

            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_module = alias.name
                    imported_layer = layer_for_module(imported_module)
                    check_module_dependency(imported_module, node.lineno)
                    if imported_layer in forbidden_import_layers and module_layer != imported_layer:
                        findings.append(
                            Violation(
                                path,
                                node.lineno,
                                f"forbidden dependency: {module} -> {imported_module}",
                            )
                        )
                    if imported_module == "importlib" or imported_module.startswith("importlib."):
                        findings.append(Violation(path, node.lineno, "disallow importlib module import"))

        entry_adapter = {
            "scripts.manifest_tool": "manifest_cli",
            "scripts.install": "install_cli",
        }.get(module)
        if entry_adapter is not None:
            findings.extend(_direct_tool_entry_violations(path, tree, module, entry_adapter))
            # Keep executable import patterns enforceable and deterministic.
            for node in tree.body:
                if isinstance(node, ast.ImportFrom):
                    resolved = resolve_importfrom_module(node, module) or ""
                    allowed_adapter_import = (
                        resolved == f"scripts.better_plan.adapters.{entry_adapter}"
                        or (
                            resolved == "scripts.better_plan.adapters"
                            and {alias.name for alias in node.names} == {entry_adapter}
                        )
                    )
                    if resolved and resolved.startswith("scripts.") and not allowed_adapter_import:
                        findings.append(
                            Violation(
                                path,
                                node.lineno,
                                f"{path.name} must only import its canonical CLI adapter",
                            )
                        )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imported = alias.name
                        if imported.startswith("scripts.") and imported != f"scripts.better_plan.adapters.{entry_adapter}":
                            findings.append(
                                Violation(
                                    path,
                                    node.lineno,
                                    f"{path.name} must only import its canonical CLI adapter",
                                )
                            )

    return findings


def _direct_tool_entry_violations(
    path: Path,
    tree: ast.AST,
    module: str,
    adapter_name: str,
) -> list[Violation]:
    findings: list[Violation] = []
    has_main_import = False
    has_dunder_guard = False
    bootstrap_count = 0

    for index, node in enumerate(tree.body):
        if isinstance(node, ast.Expr):
            is_docstring = (
                index == 0
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
            if _is_entry_path_bootstrap(node.value):
                bootstrap_count += 1
            elif not is_docstring:
                findings.append(
                    Violation(path, node.lineno, f"{path.name} contains a non-bootstrap expression")
                )
        elif isinstance(node, ast.Import):
            if [(alias.name, alias.asname) for alias in node.names] != [("sys", None)]:
                findings.append(
                    Violation(path, node.lineno, f"{path.name} may import only sys directly")
                )
        elif isinstance(node, ast.ImportFrom):
            imported = {(alias.name, alias.asname) for alias in node.names}
            is_path_import = node.level == 0 and node.module == "pathlib" and imported == {("Path", None)}
            is_adapter_import = (
                node.level == 0
                and node.module == "scripts.better_plan.adapters"
                and imported == {(adapter_name, None)}
            )
            if not (is_path_import or is_adapter_import):
                findings.append(
                    Violation(path, node.lineno, f"{path.name} contains a non-whitelisted import")
                )
        elif isinstance(node, ast.If):
            if not _is_dunder_main_guard(node):
                findings.append(Violation(path, node.lineno, f"{path.name} must not contain non-main control flow"))
        else:
            findings.append(
                Violation(path, getattr(node, "lineno", 1), f"{path.name} top-level node is not in thin-wrapper whitelist")
            )

        if isinstance(node, ast.ImportFrom):
            imported_module = node.module or ""
            if imported_module == f"scripts.better_plan.adapters.{adapter_name}" or (
                imported_module == "scripts.better_plan.adapters"
                and {alias.name for alias in node.names} == {adapter_name}
            ):
                has_main_import = True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            findings.append(Violation(path, node.lineno, f"{path.name} contains a business function or class"))
        elif isinstance(node, (*TRY_NODE_TYPES, ast.For, ast.While, ast.With)):
            findings.append(Violation(path, node.lineno, f"{path.name} must stay a thin wrapper"))
        if isinstance(node, (ast.AsyncFor, ast.AsyncWith)):
            findings.append(Violation(path, node.lineno, f"{path.name} must stay a thin wrapper"))

        if isinstance(node, ast.If):
            if _is_dunder_main_guard(node):
                has_dunder_guard = True
                if not _has_system_exit_main(node, adapter_name):
                    findings.append(Violation(path, node.lineno, f"{path.name} __main__ guard must call SystemExit({adapter_name}.main())"))

    if not has_main_import:
        findings.append(Violation(path, 1, f"{path.name} must import {adapter_name}"))
    if not has_dunder_guard:
        findings.append(Violation(path, 1, f"{path.name} must expose __main__ guard for CLI contract"))
    if bootstrap_count != 1:
        findings.append(Violation(path, 1, f"{path.name} must contain exactly one fixed import bootstrap"))
    return findings


def _is_dunder_main_guard(node: ast.If) -> bool:
    if not isinstance(node.test, ast.Compare):
        return False
    if len(node.test.ops) != 1 or not isinstance(node.test.ops[0], ast.Eq):
        return False
    return (
        isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
        and len(node.test.comparators) == 1
        and isinstance(node.test.comparators[0], ast.Constant)
        and node.test.comparators[0].value == "__main__"
    )


def _has_system_exit_main(node: ast.If, adapter_name: str) -> bool:
    if node.orelse or len(node.body) != 1:
        return False
    for statement in node.body:
        if isinstance(statement, ast.Raise):
            if (
                isinstance(statement.exc, ast.Call)
                and isinstance(statement.exc.func, ast.Name)
                and statement.exc.func.id == "SystemExit"
                and len(statement.exc.args) == 1
                and _is_main_call(statement.exc.args[0], adapter_name)
            ):
                return True
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            if (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "sys"
                and call.func.attr == "exit"
                and len(call.args) == 1
                and _is_main_call(call.args[0], adapter_name)
            ):
                return True
    return False


def _is_main_call(node: ast.AST, adapter_name: str) -> bool:
    if not isinstance(node, ast.Call) or node.args or node.keywords:
        return False
    if isinstance(node.func, ast.Name):
        return node.func.id == "main"
    return (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == adapter_name
        and node.func.attr == "main"
    )


def _is_entry_path_bootstrap(node: ast.AST) -> bool:
    """Allow only the direct executable's one repository-root import bootstrap."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    return (
        node.func.attr == "insert"
        and isinstance(node.func.value, ast.Attribute)
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "sys"
        and node.func.value.attr == "path"
        and len(node.args) == 2
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == 0
        and ast.unparse(node.args[1]) == "str(Path(__file__).resolve().parents[1])"
        and not node.keywords
    )


def file_size_violations(paths: dict[Path, str], limit: int = MAX_FILE_LINES) -> list[Violation]:
    findings = []
    for path in paths:
        if path.name == "__init__.py":
            continue
        lines = len(paths[path].splitlines())
        if lines > limit:
            findings.append(Violation(path, 1, f"module exceeds {limit} lines"))
    return findings


def analyze_architecture(
    sources: dict[Path, str],
    *,
    root: Path = ROOT,
    required: dict[str, tuple[str, str]] = REQUIRED_SYMBOLS,
) -> list[Violation]:
    trees: dict[Path, ast.AST] = {}
    for path, source in sources.items():
        trees[path] = ast.parse(source, filename=str(path))

    findings: list[Violation] = []
    findings.extend(
        symbol_ownership_violations(trees=trees, required=required, root=root)
    )
    findings.extend(
        dependency_and_antipattern_violations(
            trees=trees,
            root=root,
            layer_forbidden=FORBIDDEN_IMPORTS,
        )
    )
    findings.extend(file_size_violations(sources))
    return findings


def collect_current_sources() -> dict[Path, str]:
    source_paths = [MANIFEST_TOOL, INSTALL_TOOL]
    source_paths.extend(
        path
        for path in BETTER_PLAN_DIR.rglob("*.py")
        if path.is_file()
        and "__pycache__" not in path.parts
        and "vendor" not in path.parts
    )
    return {path: path.read_text(encoding="utf-8") for path in source_paths}


def build_fixture_sources(entries: dict[str, str], root: Path) -> dict[Path, str]:
    return {root / relative: textwrap.dedent(source) for relative, source in entries.items()}


class TestWorkflowArchitectureLayers(unittest.TestCase):
    def setUp(self) -> None:
        self.sources = collect_current_sources()

    def test_required_symbols_are_exact_and_unique(self) -> None:
        violations = analyze_architecture(self.sources)
        relevant = [v for v in violations if "required symbol" in v.message or "re-exported" in v.message or "definition set" in v.message]
        self.assertEqual(relevant, [], "Required symbol ownership must be exact and unique:\n" + "\n".join(v.as_text() for v in relevant))
        for key, (symbol, module_name) in REQUIRED_SYMBOLS.items():
            with self.subTest(symbol=key):
                module = importlib.import_module(module_name)
                value = getattr(module, symbol)
                self.assertEqual(value.__module__, module_name)

    def test_import_dependency_direction_and_anti_patterns(self) -> None:
        violations = analyze_architecture(self.sources)
        disallowed = [v for v in violations if "forbidden" in v.message or "disallow" in v.message or "fallback" in v.message]
        self.assertEqual(disallowed, [], "Dependency direction and anti-pattern checks failed:\n" + "\n".join(v.as_text() for v in disallowed))

    def test_manifest_tool_is_thin(self) -> None:
        violations = analyze_architecture(self.sources)
        manifest_violations = [v for v in violations if "manifest_tool" in v.as_text()]
        self.assertEqual(manifest_violations, [], "manifest_tool.py must stay a thin wrapper with minimal --help contract")

        completed = subprocess.run(
            [sys.executable, str(MANIFEST_TOOL), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("usage:", completed.stdout.lower())

    def test_install_tool_is_thin(self) -> None:
        violations = analyze_architecture(self.sources)
        entry_violations = [v for v in violations if str(INSTALL_TOOL) in v.as_text()]
        self.assertEqual(entry_violations, [], "install.py must stay a thin CLI wrapper")

        completed = subprocess.run(
            [sys.executable, str(INSTALL_TOOL), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("usage:", completed.stdout.lower())

    def test_installed_payload_is_exactly_allowlisted(self) -> None:
        from scripts.better_plan.installation.models import CURRENT_SKILL_FILES
        from scripts.better_plan.installation.skills import copy_skill_tree

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "source"
            target = root / "target"
            for relative in CURRENT_SKILL_FILES:
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("payload\n", encoding="utf-8")
            unlisted = source / "runtime" / "unlisted-data.json"
            unlisted.parent.mkdir(parents=True)
            unlisted.write_text("must not ship\n", encoding="utf-8")

            copy_skill_tree(source, target, dry_run=False)

            installed = sorted(
                path.relative_to(target).as_posix()
                for path in target.rglob("*")
                if path.is_file()
            )
            self.assertEqual(installed, sorted(CURRENT_SKILL_FILES))
            self.assertFalse((target / "runtime" / "unlisted-data.json").exists())

    def test_skill_metadata_surface_is_complete(self) -> None:
        skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill_text.startswith("---\n"))
        frontmatter = skill_text.split("---\n", 2)[1]
        metadata = {
            key.strip(): value.strip()
            for line in frontmatter.splitlines()
            if ":" in line
            for key, value in [line.split(":", 1)]
        }
        self.assertEqual(metadata.get("name"), "better-plan")
        self.assertTrue(metadata.get("description"))

        agent_metadata = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        for field in ("display_name:", "short_description:", "default_prompt:"):
            with self.subTest(field=field):
                self.assertIn(field, agent_metadata)
        self.assertIn("$better-plan", agent_metadata)

    def test_workflow_bounded_module_sizes(self) -> None:
        violations = analyze_architecture(self.sources)
        line_violations = [v for v in violations if "exceeds" in v.message]
        self.assertEqual(line_violations, [], "Workflow module line budgets must hold")

class TestArchitectureLayerNegativeFixtures(unittest.TestCase):
    def test_fixture_detects_wrong_layer_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sources = build_fixture_sources(
                {
                    "scripts/better_plan/domain/models.py": "class WorkflowStateMachine:\n    pass\n",
                    "scripts/better_plan/application/workflow.py": "class WorkflowStateMachine:\n    pass\n",
                },
                root=root,
            )
            violations = analyze_architecture(sources, root=root, required={"workflow": ("WorkflowStateMachine", "scripts.better_plan.domain.models")})
            self.assertTrue(any("re-exported" in v.message or "definition set" in v.message for v in violations))

    def test_fixture_detects_application_to_adapter_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sources = build_fixture_sources(
                {
                    "scripts/better_plan/domain/models.py": "class WorkflowStateMachine:...\n",
                    "scripts/better_plan/domain/transitions.py": "def transition(x:str,y:str,z:str):\n    return x\n",
                    "scripts/better_plan/application/workflow.py": "from scripts.better_plan.adapters.manifest_cli import main\n",
                },
                root=root,
            )
            violations = analyze_architecture(sources, root=root, required={
                "workflow": ("WorkflowStateMachine", "scripts.better_plan.domain.models"),
                "transition": ("transition", "scripts.better_plan.domain.transitions"),
            })
            self.assertTrue(any("forbidden dependency" in v.message for v in violations))

    def test_fixture_detects_business_function_in_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sources = build_fixture_sources(
                {
                    "scripts/manifest_tool.py": "def main():\n    return 0\n",
                },
                root=root,
            )
            violations = analyze_architecture(sources, root=root, required={})
            self.assertTrue(any("business function" in v.message for v in violations))

    def test_fixture_detects_business_function_in_install_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sources = build_fixture_sources(
                {"scripts/install.py": "def install_agents():\n    return []\n"},
                root=root,
            )
            violations = analyze_architecture(sources, root=root, required={})
            self.assertTrue(any("business function" in v.message for v in violations))

    def test_fixture_detects_installer_service_to_adapter_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sources = build_fixture_sources(
                {
                    "scripts/better_plan/installation/service.py": (
                        "from scripts.better_plan.adapters.install_cli import main\n"
                    ),
                },
                root=root,
            )
            violations = analyze_architecture(sources, root=root, required={})
            self.assertTrue(any("forbidden module dependency" in v.message for v in violations))

    def test_fixture_detects_fallback_import_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sources = build_fixture_sources(
                {
                    "scripts/better_plan/domain/models.py": "class WorkflowStateMachine:\n    pass\n",
                    "scripts/better_plan/domain/transitions.py": "def transition(x:str,y:str,z:str):\n    return x\n",
                    "scripts/manifest_tool.py": (
                        "try:\n"
                        "    from scripts.experimental_transition import transition\n"
                        "except ImportError:\n"
                        "    from scripts.better_plan.domain.transitions import transition\n"
                    ),
                },
                root=root,
            )
            violations = analyze_architecture(sources, root=root, required={
                "workflow": ("WorkflowStateMachine", "scripts.better_plan.domain.models"),
                "transition": ("transition", "scripts.better_plan.domain.transitions"),
            })
            self.assertTrue(any("fallback" in v.message for v in violations))

    def test_fixture_detects_1401_line_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lines = "\n".join(["pass"] * (MAX_FILE_LINES + 1))
            sources = build_fixture_sources({"scripts/better_plan/domain/models.py": lines}, root=root)
            violations = analyze_architecture(sources, root=root, required={"workflow": ("WorkflowStateMachine", "scripts.better_plan.domain.models")})
            self.assertTrue(any("exceeds 1400 lines" in v.message for v in violations))


if __name__ == "__main__":
    unittest.main()
