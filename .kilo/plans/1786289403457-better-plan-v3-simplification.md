# Better Plan v3 精简方案（审计结论 + 实施计划）

基线：直接在当前工作区（未提交的 v2，测试 89 项全绿）上实施。schema 标记 `better-plan.*/v2` → `/v3`（形状变更，遵守 fail-closed 代际诚实）。

## 0. 价值主线（必须原样保留的部分）

精简以"各环节高效流转"为目的，以下 10 项是 Better Plan 的真价值，本方案**全部保留**，任何实施取舍与之冲突时以本节为准：

1. **一次问询**：Decision Dossier 合并所有不可发现的用户决策，resolve 恰好一次；授权后任何角色不得再问用户。
2. **唯一 Designer 直写会话**：高级模型一次性完成整个 Plan，不可二次派发。
3. **不间断执行 + 决策优先级**：已选决策 → 授权目标/范围/风险 → 现有公共契约 → 最安全可逆 → 最简足够。
4. **唯一可写 Reviewer 终审**：同会话内修复 + 完整回归，吸收视觉验收职责（真实渲染证据由 Plan 数据驱动）。
5. **可执行验收**：每个需求/产出必须被至少一条含 Given/When/Then + oracle + evidence 的验收覆盖；Task 聚焦回归、终审完整回归都留收据。
6. **真实依赖图与并行安全**：无环、每条 Task 前置边有 input 映射、并行独立 Task 写路径不重叠、独占共享资源不冲突。
7. **断context可恢复**：语义摘要 + 授权绑定 + Checkpoints + Hooks 工作区上下文注入。
8. **精确子代理关联**：bind-agent/agent-complete 关联，spawn 返回≠完成，沉默≠失败。
9. **隐私硬线**：秘密形状数据、绝对本地路径不入状态；命令输出只持久化收据。
10. **通用宿主覆盖**：7 宿主（codex/claude/opencode/cursor/kimi/antigravity/copilot）全部保留，加法式集成铁律、回执管理代际不变。

## 1. 已确认决策

| 决策 | 结论 |
|---|---|
| 范围 | 全面精简：协议 + 角色矩阵 + 安装器/Hooks/模型路由同步瘦身 |
| 角色 | 4 个：`designer`、`worker-standard`（经济）、`worker-complex`（强力）、`reviewer`（兼视觉终审）；删除 `worker-routine`、`worker-critical`、`visual-verifier`、`visual-reviewer` |
| 状态文件 | `Manifest.json` + `Plan.json` + `Checkpoints.json` + 只读渲染 `Plan.md`（单文档）；删除 `Capabilities.json`、`PlanBundle.json`、6–9 文档投影与 managed-block 反向同步 |
| 校验哲学 | 结构最小化：仅稳定短码（无 UUID）、依赖单账本、design 自由字典、覆盖查缺不查集合相等、Dossier 去打包数学、风险收敛为标签 |
| 生命周期 | `draft → designing → ready → authorized (⇄ revising) → completed \| blocked`；readiness 单门（authorize）；Gate 概念整体删除 |
| 宿主 | 7 个全部保留，安装器仅随角色数收缩 |
| 基线/版本 | 不单独提交 v2；schema 升 `/v3` |

## 2. v3 协议形状

### Plan.json（唯一语义源）

```
schema: better-plan.plan/v3
code (PLAN-*，即身份，无 UUID), title, directory
phase: draft|designing|ready|authorized|revising|completed|blocked
intent: { goal, scope{in[],out[]}, success[], risk_boundary[],
          autonomy{allow_in_scope_revision, allow_reviewer_repairs,
                   forbid_mid_execution_questions, blocked_branch_policy} }  # 四值固定，同 v2
ledger: { observed[], user_decided[], defaulted[], unresolved[] }            # 四类不变
dossier: { status: not_required|draft|resolved,
           questions: [{ id: Q-*, context, options: [{id, label, effects[]}],
                         recommended, default, selected? }] }
spec:
  requirements: [{ code: REQ-*, statement, source_refs[] }]
  architecture: { summary, notes[] }                                          # 自由条目
  tasks: [{
    code: TASK-*, title, outcome, scope{in[],out[]},
    prerequisites: [TASK-*],
    inputs:  [{ from: TASK-*, output: OUT-*, guarantee }],
    outputs: [{ code: OUT-*, title, artifact, guarantee }],   # consumers 由校验器推导，不存储
    ownership: { write_paths[], shared_exclusive[] },          # read_paths 可选
    difficulty: standard|complex,
    verification: code|visual|hybrid,                          # 驱动 Reviewer 渲染证据要求
    requirements: [REQ-*],
    risks: [标签，固定词表],                                    # 含 critical 类标签 ⇒ difficulty 必为 complex
    design: { 自由字符串键 → string[]，整体非空即可 },            # 不再强制 10 维度
    acceptance: [{ code: AC-*, covers[], given, when, then, oracle,
                   evidence{type, source} }],
    focused_regression: { commands[], paths[] }
  }]
  full_regression: { commands[], paths[] }
lifecycle: { sealed{revision, semantic_digest, sealed_at},
             designer_session, reviewer_session,
             authorization{source, reference_digest, semantic_digest,
                           risk_reasons[], autonomy, authorized_at},
             continuation_session?, continuation_receipts[] }
```

删除的记账机制：全部 UUID 与 `uuid` 命令、`outputs.consumers` 双向账本、invariants/failure_modes 独立编码数组（写入 design/notes 或验收 then 即可）、10 设计维度强制非空、Dossier 打包数学（2–4 包×≥2 决策×affects 四分类）、risk_modules 的 applicable/reason/details 结构、Gate 全家、PlanBundle 逐文档收据、working/immutable/bundle 多摘要（保留唯一 `semantic_digest` + designer 会话的不变量摘要）。

### Checkpoints.json（仅执行态，授权时创建）

```
schema: better-plan.checkpoints/v3
plan, revision, semantic_digest, delivery_status
tasks: [{ code, status, dispatch, evidence[], freshness, status_reason? }]   # 无 gates
```

Task 状态五值不变；dispatch 相位收敛为 `worker_running → worker_correction? → awaiting_acceptance`（无 visual-verifier 相位）。

### 校验器保留的硬规则（约 500 行目标）

- schema 标记、相位枚举、未知字段拒绝（防拼写错误，保留）、各命名空间短码唯一；
- 依赖图：前置存在、无自环、无环；每条 Task→Task 前置边至少有一条 input 映射；input.from 必须是直接前置且引用真实上游 output；
- 并行安全：图上互不可达的 Task 写路径不重叠、shared_exclusive 不相交；
- 验收：covers 只能引用本 Task 拥有的 REQ/OUT 码（未知码=拼写错误，报错）；每个拥有的 REQ/OUT 至少被覆盖一次（查缺，不再要求精确集合相等）；每条验收有 G/W/T + oracle + evidence；
- readiness（仅在 authorize 与 close-continuation 执行）：requirements/tasks/full_regression 非空、每个 REQ 有实现 Task、dossier resolved/not_required、ledger.unresolved 为空、designer 会话已完成；
- 风险标签词表固定（沿用 v2 的 critical/complex 两类集合），critical 类标签 ⇒ difficulty=complex；
- 隐私：秘密形状 + 绝对本地路径全局硬失败；网络端点检查**收窄为 localhost/IP:port**（允许公网 https 文档链接——修复正当计划被反复打回的转圈点）；
- 摘要绑定：ready/authorized 相位 sealed.semantic_digest 必须与现算一致；dossier resolve 恰一次；designer/reviewer 会话 count=1。

## 3. 命令面（34 → 约 20）

保留（语义微调见 §4）：`init-plan`、`build-dossier`、`resolve-dossier`、`open-designer-session`、`close-designer-session`、`check-readiness`（咨询性）、`authorize-plan`、`begin-continuation`、`close-continuation`、`next-action`、`dispatch-task`、`bind-agent`、`agent-complete`、`delegation-failed`、`main-complete`、`accept-task`、`block-task`、`open-reviewer-session`、`close-reviewer-session`、`validate`、`status`、`tree`、`schema`。

删除：`init-capabilities`、`upsert-capability`、`promote-capability`、`capability-tree`、`discover`、`uuid`、`task-ready`、`import-plan-edits`、`render-plan`（保存即渲染 Plan.md）、`seal-plan`（并入 authorize）、`check-host-readiness`（并入 authorize 可选参数）、`open-visual-verifier`、`complete-gate`、`block-gate`。

## 4. 转圈点修复（逐条）

1. **双重 readiness 门 → 单门**：`close-designer-session` 只验证 dispatch 关联、`agent_returned`、不变量摘要（goal/scope/user_decided/dossier 未被 Designer 篡改），然后置 `ready`。readiness 只在 `authorize-plan` 一处硬门；主线程修复循环 = 编辑 Plan.json → `check-readiness`（一次列出全部问题）→ authorize。
2. **worker_correction 死端 → 脚本化出口**：`dispatch-task` 对 `status=in_progress ∧ dispatch.phase=worker_correction` 的 Task 允许开新 dispatch（新 id、attempts+1、保留既有证据）；主线程亲自修复后直接重跑 `accept-task` 的路径写入文档。
3. **Dossier 一次性陷阱 → 界限后移**：`build-dossier` 在 `resolve-dossier` 之前可重建覆盖（构建≠呈现）；`resolve-dossier` 恰好一次，"只问一次"纪律锚定在呈现/解决边界。
4. **隐私正则误伤**：见 §2 校验器——允许公网 https，仍拒绝 localhost/IP 与秘密/绝对路径。
5. **DEVNULL 黑箱**：`authorize-plan --verify-command`、`accept-task`、`close-reviewer-session` 运行命令时，失败将输出尾部（有界，如 2000 字符）打印到 stderr 供操作者诊断；持久化仍只存 {command_sha256, outcome, exit_code} 收据（隐私边界不破）。
6. **丢失子代理**：`delegation-failed` 语义扩展并写入文档——主线程确认宿主子代理已终结且无最终回调，即构成"确凿"失败；attempts 达上限走既有 `main_thread_fallback`。
7. **CI 永久红**：`.github/workflows/ci.yml` smoke 步骤删除 `transition` 行，替换为 `validate`/`schema plan`/`schema task` 等现存动词。

## 5. 实施任务清单（顺序执行）

1. **domain/models.py**：v3 常量/模板/枚举——删 UUID 模式与 `generate_id` 依赖方、Gate/Capabilities/Bundle 常量、CONDITIONAL_DOCUMENTS；difficulty 收敛 `{standard, complex}`；端点正则收窄；新 `plan_template`/`task_template`/`checkpoints_template`；schema 标记 `/v3`。
2. **domain/validation.py**：按 §2 重写（目标 ≈500 行）；删 capabilities/bundle/gate 校验、dossier 打包校验、10 维度与集合相等检查；保留隐私/图/并行/覆盖/摘要/会话规则。
3. **infrastructure/plan_bundle.py → plan_render.py**：单文档确定性渲染 `Plan.md`（intent、决策、需求、任务表含依赖/产出/验收、回归契约）；删除 managed-block 解析与逐文档收据。
4. **infrastructure/workspace.py**：删 Capabilities 加载/校验与 bundle 路径；`validate_workspace` 覆盖三文件 + Plan/Checkpoints 交叉绑定。
5. **application/workflow.py**：按 §3/§4 改命令语义——`init-plan`（不再要求 capability 参数，`--capability` 删除）、dossier 两动词、designer 开/关（关不再跑 readiness）、`authorize-plan`（readiness + 可选 `--verify-command/--verify-path` + seal revision + 写 Checkpoints）、continuation（关内跑 readiness + revision++）、`dispatch-task`（含 correction 重派）、`agent-complete`/`main-complete`（删 verification 分支）、`accept-task`/`block-task`（阻塞传播只沿 Task 边）、reviewer 开/关（角色恒为 `reviewer`；`open` 载荷含"需渲染证据的 Task 清单"）。删除 gate/visual-verifier/host-readiness/task-ready/import 函数。
6. **adapters/manifest_cli.py + capability_cli.py**：按 §3 收敛子命令；删除 capability_cli.py。
7. **domain/model_routing.py**：designer/reviewer 走智能榜首选择；worker 两档难度地板（standard=达标最廉价，complex=更高地板）；删 `webdev_routing.py`、`webdev_model_catalog.json`；`infrastructure/native_roles.py` 角色名同步。
8. **角色模板**：每宿主目录收敛为 `designer`、`worker-standard`、`worker-complex`、`reviewer` 四件；reviewer 模板并入条件性渲染证据职责（"当交付含 visual/hybrid Task 时，必须用真实浏览器取得渲染证据"）；删 visual-*/worker-routine/worker-critical；`agents/openai.yaml` 同步。
9. **installation/**：`assignments.py` 角色表收敛为 4；`targets.py`/`doctor.py`/`skills.py` 的角色清单、技能文件清单（references 变更）同步；7 宿主分支全部保留；回执/加法式铁律行为不变。
10. **hooks/**：`context.py` 注入文案更新为 v3 命令名与三文件工作区；`scope.py` 工作区探测仍以 `Manifest.json` 为标记；`config.py`/`runtime.py`/`protocols.py` 结构不动。
11. **references/**：`SKILL.md` 重写（≈120 行，吸收 orchestration-main.md：激活门、协议不变量、五步时序、决策优先级、命令表、渐进引用）；`state-files.md` → v3 状态协议（≈90 行）；`designer.md`/`worker.md`（两档合一并注明档位含义）/`reviewer.md`（含渲染证据职责）；`design-patterns.md` 裁剪为决策规则 + 记录格式 + 快速索引（≈100 行），从"必须完整阅读"改为"存在非平凡结构决策时查阅"；`host-configuration.md` 保留加法铁律、选择器代际规则与角色变更再确认门，删除"每会话必展示对照表"仪式（仅在矩阵缺失/无效或用户请求配置变更时展示）。删除 `orchestration-main.md`、`visual-verifier.md`、`visual-reviewer.md`。
12. **README.md**：v3 四保障、三文件工作区、六相位、主命令清单。
13. **tests/**：`test_v2_*` → `test_v3_protocol.py`（校验器不变量：环、写重叠、覆盖缺失、隐私、摘要绑定、dossier 一次）+ `test_v3_workflow.py`（端到端正常路 + worker_correction 重派与 blocked 分支修复路）；`v2_fixtures.py` → `v3_fixtures.py`；`test_agent_templates.py`/`test_install_tool.py`/`test_hook_tool.py`/`test_model_routing.py`/`test_native_role_resolution.py` 随角色矩阵与文件清单收敛；删 `test_webdev_routing.py`。遵守 AGENTS.md：每不变量一个最窄层代表测试，不做同分支多层重复。
14. **CI**：修复 smoke 步骤（§4.7）。
15. **收尾**：全仓一次 `python3 -m unittest discover -s tests -p 'test_*.py'`；grep 确认无 `v2`、`GATE-`、`uuid`、`visual-verifier`、`Capabilities.json` 残留引用（docs/research 历史文档除外，保留不动）。

## 6. 验证

1. 开发中按模块跑聚焦测试；集成后全量套件一次通过。
2. 临时目录 CLI 走查：`init-plan → build-dossier → resolve-dossier → open/close-designer-session → check-readiness → authorize-plan → next-action → dispatch-task → bind-agent → agent-complete → accept-task → open/close-reviewer-session`，确认 `completed`；再走一次 `accept-task` 失败 → correction 重派路径。
3. 安装冒烟：临时 HOME 下 `install.py install --agent codex` + `doctor`，确认 4 角色回执、无 visual/四档残留。
4. Python 3.8 兼容（现有 `test_python_compatibility.py` 覆盖；新代码不引入 3.9+ 运行时语法）。

## 7. 风险与边界

- **规模预估**：Python ≈7,900 → ≈4,500 行；references ≈810 → ≈450 行；模板 34 → ≈21 件；CLI 34 → ≈20 动词。数字是靶子不是硬指标，以 §0 价值主线不受损为先。
- difficulty 枚举收敛会波及模板/路由/测试，须一次性全仓 grep（`routine|critical` 作为难度值）清理，避免半代际状态。
- semantic digest 覆盖 spec，形状变更后所有测试夹具需重新生成，禁止手抄旧摘要。
- Hooks 注入文案与 CLI 动词名必须同步，否则恢复路径会引导已删除命令。
- `docs/research/agent-plan-mode-research.md` 为历史调研记录，保留不改。
- 本仓库自维护走原生工作流（AGENTS.md 豁免），实施本方案不建 Better Plan 工作区。
