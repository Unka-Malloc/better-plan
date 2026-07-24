# Planning Work Activation Validation

## PA-B01 — Consistent positive activation

- Path and target: `tests/test_hook_tool.py::HookToolTests.assert_entry_only_guidance` and
  `tests/test_orchestration_workflow.py` test
  `test_planning_coding_and_implementation_activation_is_consistent`.
- Preconditions: the Hook context module, `agents/openai.yaml`, `SKILL.md`,
  `references/orchestration-main.md`, and `README.md` are readable.
- Action: inspect Hook guidance and the quoted Skill metadata `default_prompt`, then inspect
  normalized paragraphs in the Skill, native-main contract, and README.
- Observable result: all five surfaces identify planning, coding, and explicit implementation as
  Better Plan work.
- Oracle: each surface must contain one activation clause in which Better Plan, `planning`,
  `coding` (or `code`), and `explicit implementation` occur together. The metadata assertion
  extracts `default_prompt` rather than allowing `display_name` or another YAML field to satisfy
  the Better Plan term.
- Mapping: REQ-001, REQ-002; expanded activation predicate and static entry surfaces in
  `Architecture.md`; Hook intent and orchestration-document test seams.

## PA-B02 — Native fallback and progressive disclosure

- Path and target: `tests/test_hook_tool.py::HookToolTests.assert_entry_only_guidance` and
  `tests/test_orchestration_workflow.py` test
  `test_entry_surfaces_route_work_without_disclosing_lifecycle_policy`.
- Preconditions: a structurally valid temporary Better Plan workspace for Hook cases and readable
  entry guidance for the Hook and Skill metadata.
- Action: observe both entry strings after adding planning to the positive activation predicate.
- Observable result: other requests still follow the user's instructions, requested work, normal
  answer path, or native workflow; entry strings remain short and contain no lifecycle policy.
- Oracle: positive fallback phrases remain required; Hook guidance stays within 50 words; both
  entry surfaces reject acceptance, Node, lifecycle, focused-test, regression, repair, audit,
  completion, and selector terms.
- Mapping: REQ-001, REQ-003; routing-only and no-role-contract-change decisions in
  `Architecture.md`; existing progressive-disclosure test seams.

## PA-B03 — Focused regression

- Path and target: `tests/test_hook_tool.py`, `tests/test_orchestration_workflow.py`, and the
  structural Plan validator.
- Action: run `python3 -m unittest tests.test_hook_tool tests.test_orchestration_workflow`, then
  `python3 scripts/manifest_tool.py validate docs/plan`.
- Observable result and oracle: the focused suites and Plan validation exit successfully, retaining
  prior progressive-disclosure, Hook protocol, role-isolation, and lifecycle-boundary coverage.
- Mapping: REQ-002, REQ-003; unchanged Hook protocol and role-contract boundaries in
  `Architecture.md`.

## Coverage

| Requirement | Cases |
| --- | --- |
| REQ-001 | PA-B01, PA-B02 |
| REQ-002 | PA-B01, PA-B03 |
| REQ-003 | PA-B02, PA-B03 |

This acceptance-design dispatch does not run the validation commands.
