# Python 3.8 Compatibility Validation

## Frozen acceptance cases

### PY38-S01 — Public minimum is explicit

- Path: `tests/test_python_compatibility.py::test_public_guidance_declares_python_38_or_newer`.
- Inspect `README.md`.
- Require an unambiguous Python 3.8-or-newer runtime statement.
- Map to REQ-001 and criterion 0.

### PY38-S02 — CI tests both ends of the supported range

- Path:
  `tests/test_python_compatibility.py::test_ci_exercises_both_lower_bound_platforms_and_current_python`.
- Inspect `.github/workflows/ci.yml` as structured text.
- Require Python 3.8 jobs on both Linux and Windows plus a current `3.x` Linux job.
- Require every matrix job to execute the complete suite and CLI smoke commands.
- Map to REQ-004 and criterion 3.

### PY38-N01 — Complete lower-bound execution

- Paths:
  `tests/test_python_compatibility.py::test_running_interpreter_is_within_the_supported_range` and
  the Node's isolated compile/full-suite regression commands.
- Compile all Python modules under `scripts/` and `tests/` with isolated CPython 3.8.
- Run the complete unittest discovery suite with the same interpreter.
- Reject syntax errors, unavailable standard-library APIs, import failures, skipped compatibility
  behavior, test failures, and process errors.
- Map to REQ-002, REQ-003, and criteria 1 and 2.

### PY38-S03 — Shipped command surfaces remain operational

- Path:
  `tests/test_python_compatibility.py::test_production_has_no_runtime_builtin_generic_aliases`
  plus the existing manifest, installer, Hook, and architecture suites.
- Exercise manifest schema/UUID commands through the existing CI smoke route.
- Exercise installer and Hook behavior through the complete suite.
- Require unchanged command contracts on Python 3.8.
- Map to REQ-002, REQ-003, and criterion 2.

## Focused regression

Run the complete suite and compile probe under isolated CPython 3.8, then validate this Plan and its
requirement labels. The current-runtime full suite runs once only after this Node passes its
independent audit.
