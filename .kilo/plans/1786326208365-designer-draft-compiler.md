# Designer 草稿编译特性：Design.md → Plan.json（设计规划）

昂贵的 Designer 模型不再手写严格 v3 `Plan.json`（精确字段集、`TASK-*`/`OUT-*` 码、交叉引用、
未知字段拒绝全是记账负担）。改为：Designer 写一份结构化 Markdown 草稿，框架用确定性编译器把它
规范化为可执行 Plan；转换异常由主线程接管并补全 Plan。保持 v3 哲学不动摇：
单一 readiness 门（authorize）、会话永远可关、fail-closed、纯 stdlib（Python 3.8+）。

## 0. 已确认决策（与用户逐条对齐）

| # | 决策 | 结论 |
|---|---|---|
| 1 | 草稿格式 | 结构化 Markdown（`Design.md`+ 小型文档化语法，行导向确定性解析器） |
| 2 | 异常接管 | Designer 返回后草稿只读；转换异常由主线程补全 `Plan.json`，不重调 Designer；`compile-design --apply` 只校验并关闭回执 |
| 3 | 内容守恒 | Designer 返回后草稿只读；未映射内容不可静默丢失；隐私红线 > 保真 |
| 4 | 产出模式 | 双模式：有草稿先编译，异常时主线程接管 Plan；无草稿维持现行直写行为；close 永不困死 |
| 5 | 代际 | 留在 `/v3`：全部新增为 lifecycle 可选回执 + 非状态文件，语义载荷与摘要计算不变 |

## 1. 新数据流

```
open-designer-session          payload + draft_path，知识引用 + references/design-format.md
  → Designer 写 <dir>/Design.md（可随时 compile-design --check 自检）
  → agent-complete → close-designer-session：
      correlation + immutable 恢复（现行逻辑不变）
      草稿存在 → 首次编译（无守恒检查：Designer 有权著作内容）
                 归档 <dir>/Design.pristine.md，覆盖 spec，写 compile 回执
      无草稿   → 与今日行为逐字节一致，零编译
      相位 → ready（永不困死）
  → ready 相位循环：
      compile 回执有 open issue → next-action = repair_plan（自包含 brief）
          主线程只补全 Plan.json → compile-design --apply（校验 + 关闭回执）
      无 open issue → check-readiness / 主线程语义修补（现行）→ authorize-plan
  → authorize-plan 新守卫：存在 open structure/content/unmapped → 拒绝
  → 授权后一次性派发 Designer 设计完成的并行 Task 前沿
```

## 2. Design.md v1 语法（定稿于新文件 references/design-format.md）

- 认可的顶层节（大小写不敏感，`##`–`####` 容错）：`Requirements`、`Architecture`、
  `Task: <名称>`（每任务一节）、`Full regression`。其余内容块一律 unmapped，绝不猜测。
- Task 字段标签 + 小型别名表：`Outcome`、`Scope in/out`、`Outputs`（`名称: 标题 —
  artifact: 相对路径 — guarantee: …`）、`Owns|Write paths`、`Exclusive`、`Difficulty|Tier`、
  `Verification`、`Risks`、`Nodes`（`名称: 结果 — after: 前置节点…`）、
  `Requirements`、`Design:`（自由小写子键 → 决策行）、
  `Acceptance`（Given/When/Then + oracle + evidence + covers）、`Regression`（commands/paths）。
- 名称即身份：任务/产出/需求/节点用人类可读名（标题 slug 化，`[a-z0-9-]`）；`REQ/TASK/OUT/NODE/AC`
  码由编译器按文档序铸造（`TASK-001…`）；重名 = structure issue。
- 机械转换目录（框架代劳，Designer 不再记账）：单值/列表自动装箱；缺省默认
  （difficulty=standard、verification=code、risks=[]、scope.out=[]…）；elevated 风险标签 ⇒
  difficulty 自动升 complex；`prerequisites` 和 `inputs` 固定生成为空数组；单 AC 省略
  covers → 覆盖本任务全部自有 REQ/OUT，多 AC 省略 covers → residue。
- 主线程只传递确认后的需求，不预先起草 Task。Designer 必须把相互依赖的实现工作合并进
  同一个 Task，使所有不同 Task 的写入所有权和独占资源互不冲突，并可在授权后同时派发。
  每个 Task 内由 Designer 设计最小 Node DAG：只有真实顺序依赖才连边，独立节点必须分支，
  汇合节点列出全部前置。编译器生成并校验 `NODE-*`；Worker 并行执行全部就绪节点，Node
  不增加角色、审批或独立状态账本。
- 节级回退：草稿缺 `Requirements`/`Architecture`/`Full regression` 节 → 保留 Plan.json 现值
  （回执 `sections_from_plan`）；一个 `Task` 节都没有 → structure issue。
- 排除标记：独立行 `<!-- better-plan: exclude -->` 作用于下一内容块 → 编译忽略并回执
  （unmapped 的唯一合法关闭方式之一；内容仍保存在草稿与 pristine 中，可审计）。
- 骨架经 `schema design` 输出，为权威模板。

## 3. 编译器契约（新 domain/design_compile.py，纯函数、stdlib-only）

- 全函数（total）：任意文本 → `(spec 候选, issues, 回执数据)`；内部异常降级为带最近编译
  阶段、Design 行号和目标字段的 structure issue，绝不抛出（close 永不因编译失败被困）。
- 诊断一次到位：每个 structure/content issue 必须包含精确 `line` 与 canonical `field`；缺失值
  定位到所属节标题与缺失字段；不得把多个缺陷压成宽泛消息。unmapped 使用精确行区间。主线程或
  其它智能体必须能直接按一次编译结果修复，不再手工重读草稿定位或拆解错误。
- Issue 三类：
  - `structure`（→ 主线程补全 Plan）：未知节、重复名、无法解析的字段行、悬空/歧义引用、多产出无
    `Uses`、多 AC 无 covers、无任务节等；
  - `content`（→ 主线程语义修复，允许改写）：映射字段命中隐私模式（复用
    `safe_summary_issue`/`_privacy_issues` 词表）；隐私红线优先于守恒；
  - `unmapped`（→ 主线程映射进 Plan）：仅记行区间 + sha256 摘要，不持久化原文（隐私）。
- 确定性：同一草稿 → 同一 spec；预封板轮次间码可因顺序调整重铸（authorize 后不再编译，
  "码不重编号"约束不受影响）。
- 内容守恒：Designer 返回后 `Design.md` 与 pristine 必须保持同一摘要；主线程对照只读原稿
  审计并补全 Plan，不能通过删除草稿内容关闭问题。
- `compile-design --apply` 不再重编译或覆盖 `spec`；它只校验主线程完成的 Plan、更新回执并渲染。

## 4. 状态与回执（全部加法式，可选，不动语义摘要）

- 新文件（非状态文件，不入 `STATE_FILE_NAMES`，不参与 `semantic_payload`）：
  `<dir>/Design.md`（Designer 返回后只读）、`<dir>/Design.pristine.md`（close 时归档，
  永不再写）。
- `lifecycle.designer_session.compile`（可选对象，实现时冻结确切键并进 validator 白名单）：
  `{pristine_digest, compiled_spec_digest, applied_at, sections_from_plan[],
  issues[{kind, message, line, field, status: open|resolved}], unmapped[{lines, digest,
  status: open|excluded}]}`；
  所有消息经 safe-summary 校验（隐私）。
- workspace 校验（`infrastructure/workspace.py::validate_workspace`）：存在 compile 回执且
  未封板时，`Design.md` 与 pristine 必须在场且两者内容摘要匹配（被改 = 硬错）；
  封板后不再要求文件在场（摘要留痕即可）。

## 5. 命令面（新增 2、修改 4）

| 命令 | 变化 |
|---|---|
| `compile-design --plan X (--check\|--apply)` | 新。`designing` 的 check 预览编译候选；`ready` 的 check/apply 校验主线程补全的 Plan 与只读草稿，apply 只更新回执并渲染 Plan.md |
| `schema design` | 新。输出草稿骨架 |
| `open-designer-session` | payload 增 `draft_path` 与必须原样转发的 `assignment`；`knowledge_references` 增 `references/design-format.md` |
| `close-designer-session` | 草稿存在 → 首次编译 + 归档 pristine + 覆盖 spec + 写回执；输出增 `{compiled, structure_issues, unmapped, content_issues}`。无草稿 → 现行行为不变 |
| `next-action`（ready 相位） | compile 回执有 open issue → `{action: "repair_plan", brief: {plan_path, readonly_design_path, issues[], rules_reference: "references/structure-repair.md"}}`；否则现行 `authorize_plan` |
| `authorize-plan` | 新守卫：compile 回执存在且有 open structure/content/unmapped → 拒绝并逐条列明 |

Hooks 不变（designer 的 agent-complete 关联沿用）。

## 6. 主线程 Plan 修复契约（新 references/structure-repair.md，短文）

输入即 brief；`Design.md` 只读，主线程补全 `Plan.json` 并保留 unmapped 原文语义；改后运行
`compile-design --plan X --apply` 校验并关闭回执。不得重调 Designer。

## 7. 文档与模板同步

- 新：`references/design-format.md`（语法+别名表+转换目录+exclude+守恒规则+骨架）、
  `references/structure-repair.md`。
- 改写 `references/designer.md`：产出 `Design.md`；随时 `compile-design --check` 自检；
  返回后草稿冻结；无草稿时直写仍是合法出路。
- 更新 `references/state.md`（工作区文件表、命令表、close 语义、回执）、`SKILL.md`
  （§3 设计一次、命令清单、工作区要点）、`README.md`。
- 4 宿主 designer 模板（`agents/{codex,claude-code,opencode,cursor}/designer.*`）指令文本
  改为草稿产出，保持 `ASSIGNMENT_PLACEHOLDER` 与现有 frontmatter/TOML 结构不动。
- `installation/models.py::CURRENT_SKILL_FILES` 增 2 个新 references 文件（Doctor 的
  `check_skill_tree` 自动覆盖）。

## 8. 实施任务清单（顺序执行）

1. `scripts/better_plan/domain/models.py`：增 `DESIGN_NAME = "Design.md"`、
   `DESIGN_PRISTINE_NAME = "Design.pristine.md"` 常量（及 slug 助手若需）。
2. 新建 `scripts/better_plan/domain/design_compile.py`：解析器、名称→码铸造、机械转换目录、
   三类 issue、守恒校验、exclude、骨架文本；纯函数，不做文件 IO。
3. `scripts/better_plan/domain/validation.py`：`designer_session.compile` 回执键白名单与
   形状校验（未知字段拒绝原则不变）。
4. `scripts/better_plan/infrastructure/workspace.py`：`validate_workspace` 增 pristine
   一致性检查（未封板期）。
5. `scripts/better_plan/application/workflow.py`：`close_designer_session` 编译集成；
   新 `compile_design`（相位规则、锁、只读草稿校验、回执、渲染）；`next_action` ready
   分支 + brief；`authorize_plan` 守卫；`status` 小改。
6. `scripts/better_plan/adapters/manifest_cli.py`：接线 `compile-design`、`schema design`。
7. 文档：两个新 references + designer.md 改写 + state.md/SKILL.md/README.md 更新。
8. 4 宿主 designer 模板文本 + `tests/test_agent_templates.py` 断言同步。
9. `installation/models.py` 清单 + 受影响安装测试同步。
10. 测试（见 §9）；全仓 `python -m unittest discover -s tests` 收尾（遵守 AGENTS.md：
    编辑期聚焦测试，集成后全量一次）。

## 9. 测试计划（每不变量一处、最窄层，遵守 AGENTS.md 测试范围规则）

- domain 单元（design_compile）：完整语法快乐路径 → 精确 spec；别名/装箱/默认值/风险自动升档
  各一例；歧义引用、多产出无 Uses、多 AC 无 covers、重名与未知节各一例；缺失语义只报问题、
  不生成替代散文；exclude、确定性与 content 分类各一例；所有错误带 line/field、兜底异常带
  最近阶段定位各一例。
- workflow e2e（`tests/test_v3_workflow.py` 风格）：
  1) 草稿快乐路径：open → 写 Design.md → close 编译覆盖 spec + pristine 归档 → authorize；
  2) 修复路径：含 residue 草稿 → close → next-action=repair_plan → 主线程补全 Plan →
     apply → authorize；并证明 Design.md 改动会被拒绝、unmapped 原文进入 Plan。
- 无草稿路径不加新 e2e：既有套件全绿即证明现行为未变。
- 模板/安装：`test_agent_templates.py` 断言新 designer 文本；skill 清单测试同步。

## 10. 风险与护栏

- 语法蔓延 → v1 识别目录封闭，未识别一律 residue，绝不启发式猜测；异常由主线程直接补全
  Plan，不扩张草稿语法。
- 内容遗漏 → Draft 摘要锁定，主线程在关闭转换问题前对照完整原稿审计 Plan。
- 诊断返工 → compiler issue 强制 line/field，unmapped 强制行区间；笼统错误无法进入回执。
- close 变重 → 编译器全函数、异常降级为 issue，close 永不失败于编译。
- 人工补全被覆盖 → ready 相位不再重编译草稿。
- 双模式漂移 → 有草稿先编译、异常才由主线程接管；无草稿维持现行直写。
- 省钱目标做定性验证（Designer 不再书写 JSON 语法/码/交叉引用/固定值），不做量化基准。

## 11. 范围外（本次不做）

- 续订（continuation）沿用直改 Plan.json；封板后不再编译草稿。
- 可派发的 structurer 安装角色（brief 已为任意代理留好接口，未来加角色不改协议）。
- YAML/JSON 草稿变体、`ledger.observed` 草稿节、token 消耗量化基准。
