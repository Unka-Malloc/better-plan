# Accordingly Fallback Wording Validation

## AF-B01 — Hook and Skill metadata fallback wording

- Path and target: `tests/test_hook_tool.py::HookToolTests.assert_entry_only_guidance` and
  `tests/test_orchestration_workflow.py` test
  `test_entry_surfaces_route_work_without_disclosing_lifecycle_policy`.
- Preconditions: `INTENT_GUIDANCE` is available directly and the quoted
  `agents/openai.yaml::interface.default_prompt` has been extracted independently of other metadata.
- Action: normalize each entry string and inspect its non-Better-Plan fallback clause.
- Observable result: the clause beginning with `otherwise` uses `accordingly` and contains no
  occurrence of `normally`.
- Oracle: `otherwise` and `accordingly` must occur in the same sentence; a word-boundary negative
  assertion rejects `normally`. Existing assertions in the same helpers continue to require
  planning, coding, explicit implementation, user-directed native fallback, short Hook guidance,
  and absence of lifecycle policy.
- Mapping: REQ-001, REQ-002; literal entry-copy replacement, static-string isolation, and entry
  surface vocabulary test seams in `Architecture.md`.

## AF-B02 — Both README entry-routing statements use the new wording

- Path and target: `tests/test_orchestration_workflow.py` test
  `test_readme_entry_routing_uses_accordingly_without_normally`.
- Preconditions: `README.md` contains the prose statement identified by
  `entry guidance activates Better Plan` and the Hook statement identified by
  `Session and prompt duties share one short routing instruction`.
- Action: select exactly those two lines and inspect each statement independently.
- Observable result: both retain planning, coding, and explicit implementation activation, and
  describe the other-request fallback with `accordingly`.
- Oracle: exactly two identified statements must exist; each must contain the three activation
  terms, must place `accordingly` after `otherwise` or `every other request` in the same sentence,
  and must contain no word-boundary occurrence of `normally`. Unrelated README uses of words such
  as `ordinary` are outside the copy-change boundary.
- Mapping: REQ-001, REQ-002; README consumer of the entry fallback-copy interface and existing
  activation/progressive-disclosure test seams.

## AF-B03 — Focused validation

- Action: run `python3 -m unittest tests.test_hook_tool tests.test_orchestration_workflow`, then
  `python3 scripts/manifest_tool.py validate docs/plan`.
- Observable result and oracle: both commands exit successfully, preserving prior Hook protocol,
  activation, progressive-disclosure, and lifecycle-boundary coverage.
- Mapping: REQ-002; unchanged workflow, protocol, and role contracts.

## Coverage

| Requirement | Cases |
| --- | --- |
| REQ-001 | AF-B01, AF-B02 |
| REQ-002 | AF-B01, AF-B02, AF-B03 |

This acceptance-design dispatch does not run the validation commands.
