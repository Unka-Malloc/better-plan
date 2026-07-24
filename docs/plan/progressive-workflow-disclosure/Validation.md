# Progressive Workflow Disclosure Validation

## PD-B01 — Entry routes without preloading workflow

- Path and target: `tests/test_hook_tool.py`, `HookToolTests.assert_entry_only_guidance`,
  `test_session_start_injects_only_short_intent_guidance`,
  `test_intent_guidance_contains_only_progressive_entry_routing`, and
  `test_prompt_submit_injects_only_short_intent_guidance`.
- Preconditions: a structurally valid temporary Better Plan workspace and a supported session or
  prompt-submit host event.
- Action: invoke the Hook and observe
  `scripts/better_plan/hooks/context.py::INTENT_GUIDANCE` through the native host response.
- Observable result: the same static, privacy-safe entry text names Better Plan, routes coding and
  explicit implementation to it, and otherwise tells the agent to follow the user's request or
  answer through the native workflow.
- Oracle: the text is at most 50 whitespace-delimited words; positive routing phrases are all
  present; `acceptance`, `Node`, `lifecycle`, focused-test, regression, repair, audit, completion,
  and selector policy terms are all absent; private prompt and Plan sentinels remain absent.
- Mapping: REQ-001, REQ-002, REQ-003; disclosure-boundary interface and static-composition
  decision in `Architecture.md`; Hook context test seam.

## PD-B02 — Skill entry and activated workflow are separated

- Path and target: `tests/test_orchestration_workflow.py`,
  `test_entry_surfaces_route_work_without_disclosing_lifecycle_policy` and
  `test_activated_skill_and_isolated_roles_retain_lifecycle_policy`.
- Preconditions: repository `agents/openai.yaml`, `SKILL.md`,
  `references/orchestration-main.md`, `references/acceptance-designer.md`,
  `references/executor.md`, and `references/auditor.md` are readable.
- Action: inspect the Skill metadata default prompt independently from the activated Skill and its
  isolated role references.
- Observable result: the default prompt exposes only the same coding/implementation versus
  native/user-directed routing boundary; after activation, the canonical Skill and one-role
  references still retain capability lifecycle ownership, acceptance freeze, ordinary build-error
  handling, independent audit, full regression, and terminal routing. Focused regression remains
  cross-phase policy in `SKILL.md` and `references/orchestration-main.md`: it runs after executor
  exit, while `references/executor.md` permits only the smallest implementation-local build or
  static check and prohibits running frozen acceptance.
- Oracle: the entrance surface must satisfy every positive entry phrase and reject every lifecycle
  policy term. Distinct assertions require post-executor focused-regression routing in both
  `SKILL.md` and the native-main reference, the frozen-acceptance prohibition in the executor
  reference, and the corresponding lifecycle duties in the acceptance-designer and auditor
  references. Passing either by deleting policy from the activated workflow or by incorrectly
  assigning acceptance regression to the executor is therefore impossible.
- Mapping: REQ-001, REQ-002, REQ-003; Skill/role disclosure boundary, role-isolation decision, and
  `agents/openai.yaml` plus workflow-reference test seams in `Architecture.md`.

## PD-B03 — Existing Hook protocols remain bounded

- Path and target: existing protocol, detector-gating, no-workspace, unsupported-event, subagent,
  Cursor, Antigravity, Kimi, Codex, and Claude cases in `tests/test_hook_tool.py` and
  `tests/test_orchestration_workflow.py`.
- Preconditions: supported temporary workspace and event fixtures already declared by those tests.
- Action: run `python3 -m unittest tests.test_hook_tool tests.test_orchestration_workflow`.
- Observable result: session and prompt outputs remain equal to `INTENT_GUIDANCE`; payload encoding,
  workspace detection, fail-open/no-op behavior, event inventory, and role isolation do not change.
- Oracle: exact native response shapes and event mappings remain asserted; unsupported, ambiguous,
  unrelated, and subagent events remain empty bounded no-ops.
- Mapping: REQ-003; compatibility and isolation decisions in `Architecture.md`; existing Hook and
  orchestration test seams.

## Validation commands

- Focused acceptance: `python3 -m unittest tests.test_hook_tool tests.test_orchestration_workflow`
- Plan structure: `python3 scripts/manifest_tool.py validate docs/plan`
- This acceptance-design dispatch does not run either command.

## Coverage

| Requirement | Cases |
| --- | --- |
| REQ-001 | PD-B01, PD-B02 |
| REQ-002 | PD-B01, PD-B02 |
| REQ-003 | PD-B01, PD-B02, PD-B03 |
