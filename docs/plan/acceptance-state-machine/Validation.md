# Acceptance State Machine Validation

The focused target is `python3 -m unittest tests.test_acceptance_state_machine -v`.
The tests are intentionally written before the production interface exists. Each
fixture is a complete temporary workspace: root `Manifest.json` is a Plan-object
array using only current Plan fields (`id`, `status`, `title`, `directory`,
`source_files`, `goal`, `description`, and `checkpoints`); its plan-local
`Checkpoints.json` has valid UUID4 identifiers, matching pending Plan and Node
status, all required Node metadata, declared relative regression paths, and the
actual path file. The implementation Node uses the required `Scope`, `Closure`,
`Context`, `Target`, `Design Considerations`, `Design Value`, and `Constraints &
Risks` description sections. Lazy enrollment therefore proves `pending` to
`in_progress` rather than assuming an active Node. Delivery Nodes are automated by
role, not by the incidental presence of an `acceptance` snapshot: every pending or
in-progress `implementation` and `final_validation` Node rejects the old manual
`start`, `regress`, `check`, and `complete` entry points before commands or writes.
Foundation roles retain their legitimate manual evidence workflow. The coarse
`pause`, `block`, and `skip` lifecycle remains available to delivery Nodes, but it
is an administrative cancellation boundary rather than an acceptance verdict.

| Requirement | Phase, event, and guard | Focused / final proof | Audit and failure route | Idempotency and privacy proof |
| --- | --- | --- | --- | --- |
| REQ-001 | `awaiting_executor` accepts `dispatch --role executor` only after test-first enrollment. | Focused tests require the public transition API and a test-designed workspace; final validation uses the same public CLI. | Executors cannot record checks or complete. | No executor prompt, transcript, or identity is retained. |
| REQ-002 | `awaiting_executor` or `repair_required` + executor dispatch enters `executor_running`; matching `executor-exited` is the only exit edge. | Pure transition and `next_action` tests prove deterministic selection. | Invalid role, phase, or dispatch ID is rejected. | Duplicate/stale exits leave the snapshot unchanged. |
| REQ-003 | Matching executor exit immediately performs the Node's focused contract. | Portable Python regression commands prove exit routes automatically without a separate regress command. | Passing receipt becomes `awaiting_auditor`; failing receipt becomes `repair_required`. | The outcome is a bounded class, never command output. |
| REQ-004 | A stable-input failure enters `repair_required` and the completion Hook emits `main_repair_decision`; a fresh executor is legal only if the native main chooses repair. | Regression-fail proves immediate main control; an explicit repair dispatch can then pass, while changing a declared acceptance file proves repair cancellation and fresh acceptance design. | Unchanged input awaits a native-main repair/defer choice; reviewed-input drift selects acceptance redesign. | Replayed dispatch does not increment attempts or rerun regression. |
| REQ-005 | `awaiting_auditor` requires a current regression fingerprint; audit verdict needs matching auditor dispatch and fingerprint. | Fixture changes the declared relative artifact after regression and before verdict; final proof binds the audit to the full receipt. | Implementation audit fail routes to `repair_required`; final audit fail routes to `repair_plan_required`. | Stale verdicts reject without changing state bytes; receipts contain digests only. |
| REQ-006 | `audit-passed` from `auditor_running` atomically enters `accepted` then completes the delivery Node. | Fixture proves fresh implementation pass automatically completes. | `start`, direct `regress`, `check`, and `complete` reject every nonterminal delivery Node even before enrollment, without executing regression. | Duplicate audit pass cannot complete twice or mutate evidence. |
| REQ-007 | Every event validates phase, role, opaque dispatch ID, and current receipt. | Focused duplicate/stale-event and serialized-state tests use a portable Python command that reconstructs synthetic credential, path, and endpoint output only at runtime. | Invalid events return a validation error with no side effect. | Persisted state and CLI response exclude the synthetic sensitive text; duplicate events leave state bytes unchanged. |
| REQ-008 | Host-facing `next-action` is derived from `phase` and role; it performs no transition. | CLI tests cover `next-action` and executor/auditor dispatch commands. | Unsupported or wrong role is rejected; parent submits actual exits. | No host/machine metadata is persisted. |
| REQ-009 | `awaiting_regression` accepts one explicit `regression-requested`; fresh full pass moves to audit. A failed attempt parks final as pending in `repair_plan_required`, and a validated repair registration moves it to `awaiting_repair`. | A portable marker proves one full run per acceptance attempt; the end-to-end fixture creates and automatically accepts a separate repair Node before the final retry. | Full or final-audit failure releases the active slot. Only the bound, completed repair Node can move final back to `awaiting_regression`; completed implementation history stays byte-for-byte unchanged. | Wrong, unfinished, historical, or duplicate repair events leave state unchanged; a repeated regression request in the same attempt does not rerun. |

## REQ-010 到 REQ-017 Design-first acceptance matrix

| 需求 | 公开 oracle | 负向/误通过防护 | 测试文件/命令 | 证据生成者 / 证据审核者 |
| --- | --- | --- | --- | --- |
| REQ-010 主代理设计归属 | 1) `manifest` 中 `design` 有 `owned_paths / scaffold_paths / symbols / interfaces / errors` 且 `scaffold_paths ⊆ owned_paths`；2) `design_digest` 与工件快照可计算。 | `design` 缺失或 `owned_paths`、`scaffold_paths` 空、`symbols` 不完整时，`acceptance` 不能进入 `acceptance_designer_running`。 | `tests/test_acceptance_state_machine.py::test_design_first_fingerprint_and_phase_gates`（或同场景等价测试） | 设计证据生产：Main agent 在 `Architecture` 产物及 `design` 中落库；设计覆盖审核：`acceptance_reviewer`（独立） |
| REQ-011 角色隔离 | `hook_context`/`hook_tool` 在 `next-action` 中仅返回一个 `role_reference`；`references` 仅按当前 role contract 读取。 | 进入 `acceptance_designer` 时不得读取其他角色路径；错角色分发返回错误，禁止多路径合并注入。 | `tests/test_acceptance_state_machine.py::test_next_action_and_phase_binding`（或同类上下文隔离测试） | 生成：`manifest_tool` 与 Hook 上下文；审核：`acceptance_reviewer` |
| REQ-012 独立验收复审 | `acceptance` 快照包含独立 reviewer 签核态并绑定设计+测试指纹；`next_action` 在同一节点内必须按 `awaiting_acceptance_design -> awaiting_acceptance_review -> awaiting_executor` 流转。 | 审核者未通过（`acceptance-rejected`）时不得进入 `dispatch_executor`；`acceptance-approved` 用过期/错误 `dispatch_id` 时拒绝。 | `tests/test_acceptance_state_machine.py::test_reviewer_event_requires_distinct_dispatch_and_executor_gates_before_approval`、`python3 -m unittest tests.test_acceptance_state_machine -v` | 生成：`acceptance_reviewer`（审阅产物）；审核：`acceptance_reviewer` + 主机端状态机 |
| REQ-013 审计瘦身与边界 | `auditor` 阶段仅使用回归指纹和变更路径；`acceptance` 通过审计后由 `accepted` 原子落档。 | 未携带当前回归指纹或审计人未以 `auditor_running` 发起时，`audit-passed`/`audit-failed` 不得触发转移。 | `tests/test_acceptance_state_machine.py` 中审计转移与修复注册相关 case（如 final audit） | 生成：`manifest_tool`；审核：`auditor` 与 state machine |
| REQ-014 准备指纹失效 | `preparation_fingerprints` 分离 design、scaffold、acceptance；执行前校验三者，执行后仅以稳定的 design + acceptance 判断是否重做验收。 | 脚手架在执行前变化必须回退；执行者按计划修改脚手架不得误回退；失败后 validation/test 漂移必须取消 `dispatch_executor` 并返回 `dispatch_acceptance_designer`。 | `tests/test_acceptance_state_machine.py::test_inputs_change_invalidation_returns_to_acceptance_design` 及执行前/执行后漂移场景 | 生成：`state`（`next_action` 与分层指纹）；审核：`acceptance_reviewer` |
| REQ-015 显式工程决策 | `design.decisions` 必须显式填充 `composition`、`algorithms`、`data_structures`、`state`、`isolation`、`concurrency`；并执行路径独占校验。 | 决策字段缺失或路径重叠冲突时 `validate_design_contract` 与接续校验返回问题并拒绝。 | `tests/test_design_contract.py` + `tests/test_acceptance_state_machine.py` 中 ownership/phase 相关 case | 生成：main agent、`design_contract.py`；审核：`acceptance_reviewer` |
| REQ-016 Agent 生命周期归属 | Better Plan 只消费宿主返回的相关 Agent-completion 事件，不轮询、不计时、不主动中断或替换运行中的 Agent。 | Agent 未返回前不产生 Better Plan 状态动作；返回后才按角色执行确定性 reducer。 | 当前 Hook 编排与 Agent-completion 测试 | native agent framework owns lifetime; native main owns post-result decisions |
| REQ-017 当前安装与 Hook-only 卸载 | 安装清单覆盖当前模块和五个角色文件；`uninstall-hooks` 只删除 managed Codex/Claude lifecycle handlers；所有 handler timeout 不超过 30 秒。 | 缺失当前文件、Cursor/tool-use handler、技能或无关配置被删除都必须失败；旧产物使用一次性删除扫描，不保留长期旧名测试。 | `tests/test_install_tool.py` 的 current payload inventory、hook-only uninstall、bounded lifecycle cases + 本迁移 Node 的一次性扫描 | 生成：installer/hook config；审核：acceptance reviewer + final auditor |

## Administrative lifecycle contract

Administrative lifecycle commands never check a criterion, record audit PASS, or
complete a Node. Before changing coarse status, they transactionally invalidate
any outstanding executor or auditor correlation and clear the current or stale
`last_pass`, regression-generated command evidence, and every regression-mapped
criterion check. The retained acceptance snapshot contains no dispatch, audit,
raw output, finding, prompt, transcript, or runtime path.

- `pause` requires an `in_progress` Node and writes `status=pending`.
  Implementation resumes at `awaiting_executor`; final validation resumes at
  `awaiting_regression`. The attempt count is retained and the next action is
  respectively `dispatch_executor` or `run_regression`.
- `block` writes `status=blocked` and a validated safe reason. Ordinary active
  implementation and final phases return to the same role-specific base phase and
  retain the attempt count. `next-action` still exposes the automatic recovery
  entry, and that entry changes status to `in_progress` and removes the stale
  reason. A blocked Node without an acceptance snapshot can likewise enroll only
  through that automatic entry.
- A blocked final Node already in `repair_plan_required` or `awaiting_repair`
  retains its failure outcome and, when present, the exact repair Node binding.
  `repair-registered` and `repair-completed` are legal recovery events from the
  blocked coarse status; each restores final validation to `pending`, clears the
  block reason, and proceeds through the existing repair handoff phase.
- `skip` writes the terminal `status=skipped`, clears all automated proof, and
  removes the acceptance snapshot. This deliberately discards the attempt count:
  the coarse terminal status is the sole persisted source of truth, avoiding a
  duplicate terminal lifecycle inside `acceptance`. `next-action` is `none`, and
  no dispatch, regression, audit, or repair event can resume the Node.

The focused tests cover executor-running and auditor-running implementation
attempts, auditor-running final attempts, both final repair phases, unenrolled
pending and blocked delivery, and terminal skip. After every administrative
cancellation, the prior executor/auditor/repair event is rejected with both state
files byte-for-byte unchanged. Exact repeated `block` and `skip` requests are
idempotent; repeated `pause` after the Node is already pending and commands from an
illegal terminal status fail without mutation. Foundation Nodes continue to use
the unchanged coarse lifecycle because they have no automated acceptance snapshot.

### Current-interface cleanup acceptance subsection

This subsection is the dedicated acceptance for the current-interface cleanup migration.
The durable oracle is the existing focused current installer/role/orchestration suite
(`tests/test_install_tool.py` and related orchestration coverage) with no dedicated legacy
name retention test and no permanent removed-file inventory in the acceptance record.

The migration oracle is node-local: the Node explicitly declares a one-time active-surface
scan for this Node only. Acceptance preparation reviews the command and expected evidence;
the workflow executes it as a declared Node regression command after implementation and
executor exit, before audit. It is not a recurring final gate because the scan validates a
one-off migration boundary and would add redundant terminal friction if repeated on every
final validation cycle.

Observed PASS criteria:

- The focused suite proves installer payload, role contract, and orchestration behavior end-to-end.
- The Node run contains exactly one executed active-surface scan and records only a bounded digest/result.
- A passing path leaves terminal-plan history excluded from the acceptance snapshot and unmodified.
- Re-runs rely on the standard existing suite only; legacy artifacts are not revalidated as names.
- Any future terminalization (`completed`/`skipped`/`failed` family) keeps history immutable and
  does not retroactively invoke the one-time migration oracle.

### Lifecycle-vocabulary repair acceptance

This repair is accepted by two independent, non-self-approving oracles. The durable
oracle is the focused Hook/configuration suite: it exercises a generic unknown stage,
asserts exact equality with the allowed lifecycle-key set, and proves every configured
handler is bounded to 30 seconds. The executor can produce this evidence but cannot
approve it.

The migration oracle is a Node-local, one-time active-surface scan. It runs after the
executor exits and before audit, and must prove that deleted tool-call event vocabulary
is absent from current source, tests, and user-facing references. This scan is migration
evidence only: it is not retained as a recurring test or final gate. Terminal Plan
history is outside its scan boundary and remains immutable. Uninstalling managed Hooks
from an external local installation is a separate operator action and is not inferred
from either oracle.

## Final validation oracle

The final-validation Node binds all evidence to its declared final content
fingerprint and runs the following contract in order:

1. Complete `unittest` discovery executes exactly once for that fingerprint.
2. After the suite, workspace validation confirms that current source paths resolve,
   and label validation confirms the canonical requirement mapping.
3. The passing suite proves that a generic unknown stage is rejected with a
   nonzero exit and empty stdout; the allowed handler inventory is exactly
   `SessionStart`, `UserPromptSubmit`, and `Stop`; and every handler timeout is at
   most 30 seconds. It then proves the current-only installer payload,
   repository-relative managed Hook commands, runtime-data redaction, isolated
   role contracts, and the acceptance state machine.

The final-validation Node does not repeat the lifecycle-vocabulary repair Node's
one-time deleted-vocabulary scan; that scan is migration evidence, while the
repaired current-only tests are the durable final oracle. These command results
prepare bounded evidence; they do not approve the Node. A fresh auditor bound to
the same fingerprint must review that evidence before an audit PASS can complete
final validation. Repository tests do not prove that a local external Hook
installation has been uninstalled; that remains a separate operator action and is
not inferred from this oracle.

## Repair registration contract

The state tool never invents semantic repair work. After final regression or audit
failure it clears the obsolete regression proof and writes `status=pending`,
`phase=repair_plan_required`, and action `create_repair_plan`, releasing the
one-active-Node slot. A planning/acceptance role
must first create a new pending `implementation` Node and add that Node ID to the
original final Node's prerequisites. The public event contract is then:

- `advance <final> --event repair-registered --repair-node <repair> <workspace>`
  validates that the referenced Node exists, is a pending implementation, and is a
  prerequisite of that final Node. It binds only the opaque Node ID and enters
  `awaiting_repair`; next action is `await_repair_completion`.
- The repair Node follows its own unchanged
  `dispatch → executor-exited → regression → auditor → audit-passed` cycle.
- `advance <final> --event repair-completed --repair-node <repair> <workspace>`
  accepts only the same bound ID after that Node is `completed`, clears the binding,
  and restores `awaiting_regression`; next action is `run_regression`.

Final acceptance runs the declared `full` contract once per acceptance attempt,
followed by a separate fresh auditor dispatch. A retry is permitted only after the
registered repair Node completes. All state assertions inspect only safe, bounded
serialized metadata: phase, attempt, bounded outcome, opaque Node/dispatch IDs, and
receipt digests/timestamps—never prompts, findings, paths, or runtime output.

## Design-first preparation acceptance

Acceptance design is a contract gate only: a fresh acceptance designer must produce
`tests/test_design_contract.py` and a reviewed `Validation.md` entry that is derivable
from the frozen design. The next action cannot move to execution until both
`acceptance_designer` and `acceptance_reviewer` transitions are replay-consistent,
and any test or design drift requires fresh re-enrollment before dispatch.
