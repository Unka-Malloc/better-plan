# 开源 Coding Agent Plan Mode 调研与 Better Plan 改进建议

> 历史研究：全文记录调研时的 v1/v2 方案，不构成当前执行指令。文中的“当前”和“最终”均指当时的研究阶段。执行以 [SKILL.md](../../SKILL.md) 和 [v3 状态协议](../../references/state.md) 为准；不得据本文恢复旧审批、角色或回归步骤。
>
> 调研日期：2026-08-09
> 样本：14 个开源 Agent／编排框架，另对一个仅公开发行资料、未公开当前实现源码的产品作排除说明
> 目标：研究 Plan Mode 的组织、审批、任务拆分、边界与重规划机制，审计 Better Plan v1，并记录已选定的 v2 完整计划协议

## 1. 结论先行

调研开始时的 Better Plan v1 已经是一个很强的**执行控制面**：它拥有规范化 DAG、角色分工、路径所有权、设计契约、精确回调关联、回归指纹、Reviewer／repair 闭环与隐私边界。它的主要问题不在调度，而在调度之前：**计划仍不是一门足够完整、可验证的任务描述语言**。本报告后半部保留 v1 审计证据，并在第 15 节记录最终采用且已经落入代码的 v2 方向；旧候选方案不再代表当前协议。

最关键的判断有五个：

1. `goal`、`description` 和 `acceptance_criteria[].text` 的语义主要依靠文档约定，代码只验证“非空”。因此，一个只有漂亮散文、没有输入输出、边界、失败行为和验收 oracle 的 Node，仍可能通过校验。
2. “独立任务”目前被近似为一句 `Closure:` 声明、路径不重叠和稳定接口，但没有验证上游输出是否真的满足下游输入、每个输出是否有独立验收、共享外部状态是否冲突，也没有验证 Worker 能否在看不到原对话时完成任务。
3. 当前所有非终态 delivery Node 在 Designer 调度前就必须带完整 `design`；Designer 又明确不得修改 Better Plan 状态。于是负责产出设计的角色只能在“设计已经完整存在”后开始工作，形成时序倒置。
4. Better Plan 缺少 Codex、Gemini CLI、Qwen Code 等系统共同强调的“先查事实—再消除决策歧义—再形成正式计划—再显式审批”语义门；其中 Qwen Code 还进一步把确认绑定到计划快照与 approval-mode revision。现在的状态机很擅长证明“执行到了哪一步”，却不能证明“这份计划已经足以开始执行”。
5. 不应把其它 Agent 的 Markdown checklist 原样移植进 Better Plan。它们擅长交互与审批，但多数任务项仍是自由文本。Better Plan 应保留自己的 DAG 和执行证据优势，把它们升级成由 **事实账本、任务契约、设计契约、审批版本、执行状态** 五层组成的可验证协议。

本报告建议采用以下核心定义：

> 一个 Task 是独立任务，当且仅当：在它声明的前置产物全部可用后，一个看不到原对话的 Worker，仅凭冻结的 leaf brief，就能在不补做隐藏产品／架构决策、不读取同级 Task 的未声明内部状态的情况下，完成、验证并在适用时回退一个内聚结果。

“独立”不等于“无依赖”；“可并行”也不是“独立”的同义词。可并行还要求没有依赖路径、文件与共享可变资源互不冲突，并且双方只消费冻结的稳定接口。

## 2. 调研方法与证据边界

### 2.1 方法

本次调研执行了以下步骤：

- 从各仓库远端默认分支取得最新 HEAD，在一次性本地研究工作区中拉取完整或 partial/sparse 源码；对 sparse 仓库直接从同一 commit 读取未 checkout 的 blob。
- 使用 `git ls-remote <origin> HEAD` 与本地 `HEAD` 逐仓比对，确保取证 commit 与调研时的远端默认 HEAD 一致。
- 优先阅读实际系统提示词、工具权限过滤器、Plan 进入／退出工具、任务协议、审批状态机、解析器与恢复逻辑；README 只作补充，不用来代替实现证据。
- 将“Plan Mode”按四类理解：会话权限模式、Planner→Executor 交接、结构化任务协议、执行期 ledger。没有显式 Plan Mode 的项目作为对照样本，不把普通 Todo 误称为完整计划。
- 对 Better Plan 同时审阅技能文档、Node schema 说明、校验器、设计契约、Designer 角色与 leaf payload 生成路径，比较“文档声称的约束”和“代码真正强制的约束”。

### 2.2 最新源码快照

| 项目 | 默认分支 | 调研 HEAD（提交时间） | Plan 组织类型 |
|---|---|---|---|
| [OpenAI Codex](https://github.com/openai/codex/tree/646f7c0a91b8e327d263335da68ae8ef212895ce) | `main` | `646f7c0`（2026-08-09） | 会话级 Plan Mode；正式计划与 TODO 工具严格分离 |
| [OpenCode](https://github.com/anomalyco/opencode/tree/38e10eb1408feb700021b8e8766fb0ab41bf84e2) | `dev` | `38e10eb`（2026-08-08） | 五阶段 Plan workflow、专用计划文件、显式退出审批 |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli/tree/cf22ac7e86f3dcf528e3ae591fec1c03090a49f8) | `main` | `cf22ac7`（2026-08-07） | 自适应复杂度、策略共识、计划文件、正式审批；可选持久任务 DAG |
| [Qwen Code](https://github.com/QwenLM/qwen-code/tree/f3ba99f545e97cff48ecb6af7ea1ea7971d8a6e4) | `main` | `f3ba99f`（2026-08-09） | 迭代式 pair-planning、显式审批 revision、依赖 Todo DAG |
| [Cline](https://github.com/cline/cline/tree/b3cee3f973ffe9d023a10c5c414deba68cd6e09d) | `main` | `b3cee3f`（2026-08-08） | Plan／Act 双模式、提示词与运行时双重写保护 |
| [Roo Code](https://github.com/RooCodeInc/Roo-Code/tree/b867ec9145750d0ae1ff7f02d35406e9bf2a0b16) | `main` | `b867ec9`（2026-05-15） | Architect Mode、可编辑审批的持久 Todo |
| [Aider](https://github.com/Aider-AI/aider/tree/5dc9490bb35f9729ef2c95d00a19ccd30c26339c) | `main` | `5dc9490`（2026-05-22） | Architect→Editor 两模型、不继承原对话的实施指令交接 |
| [Continue](https://github.com/continuedev/continue/tree/5522c6f44ca0ac3528b37244818fbfa39b5af470) | `main` | `5522c6f`（2026-07-20） | Explore→Analyze→Plan→Verify→Execute，Checklist 辅助 |
| [OpenHands](https://github.com/All-Hands-AI/OpenHands/tree/68de5c58872a6b32dc2a94cce6fd33a410de49ff) | `main` | `68de5c5`（2026-08-08） | 独立规划子会话、固定 PLAN.md、显式 Build 交接 |
| [Goose](https://github.com/block/goose/tree/064244e6bddf641876676f054a006b7da1da5182) | `main` | `064244e`（2026-08-08） | Planner→全新 Executor 会话，自包含计划与多轮澄清 |
| [Crush](https://github.com/charmbracelet/crush/tree/75791b8883df8689bef5d2b0407fa71c93bb5234) | `main` | `75791b8`（2026-08-08） | 无独立 Plan Mode；执行期 mental checklist + Todo |
| [Plandex](https://github.com/plandex-ai/plandex/tree/e2d772072efadbe41d2946d97d79be55532dbab5) | `main` | `e2d7720`（2025-10-03） | 可解析 Subtask 协议、`Uses:` 上下文、显式任务修订语法 |
| [AutoGen / Magentic-One](https://github.com/microsoft/autogen/tree/027ecf0a379bcc1d09956d46d12d44a3ad9cee14) | `main` | `027ecf0`（2026-04-06） | Facts／Task／Progress Ledger、停滞检测与重规划 |
| [SWE-agent](https://github.com/SWE-agent/SWE-agent/tree/3ea751c087f32b16e039a2233dd6eefecef325d5) | `main` | `3ea751c`（2026-07-16） | 无独立 Plan Mode；最小改动闭环与逐步轨迹 |

GitHub Copilot CLI 的公开仓库也被拉取核查，但当前仓库只包含 README、安装脚本、许可证和 changelog，没有可用于本研究的 Plan Mode 实现源码，因此不计入上述 14 个开源源码样本。其公开行为可以作产品参照，但不能与源码证据混为一谈。

## 3. 逐仓实现分析

### 3.1 OpenAI Codex：把“正式计划”与“执行 TODO”分成两种协议

Codex 的 [Plan Mode 模板](https://github.com/openai/codex/blob/646f7c0a91b8e327d263335da68ae8ef212895ce/codex-rs/collaboration-mode-templates/templates/plan.md#L1-L128) 是本次样本中对“计划何时完整”定义最清楚的提示词之一。

它把规划分为三个语义阶段：

1. **Ground in the environment**：先读代码和现状，不能让用户回答仓库里可发现的事实。
2. **Align on intent**：确认目标、成功标准、受众、范围内／外、约束、当前状态与关键取舍。
3. **Make implementation decision-complete**：补齐方案、公共接口、数据流、失败路径、测试、发布、迁移与兼容；高影响歧义未解决时不得输出正式计划。

它还给未知问题做了很实用的分类：可发现事实由 Agent 自己调查；只有偏好、产品取舍和无法从环境推导的约束才问用户。正式输出必须是完整替换，而不是零散补丁。

更重要的是，Codex 明确指出 Plan Mode 与 [`update_plan`](https://github.com/openai/codex/blob/646f7c0a91b8e327d263335da68ae8ef212895ce/codex-rs/core/src/tools/handlers/plan_spec.rs) 不同；[`plan.rs`](https://github.com/openai/codex/blob/646f7c0a91b8e327d263335da68ae8ef212895ce/codex-rs/core/src/tools/handlers/plan.rs) 甚至在 Plan Mode 中硬拒绝 TODO 工具。这个区分非常值得 Better Plan 保留：**计划是决策完整的实施规范，TODO 只是执行进度投影**。

局限也很明确：Codex 的正式计划仍是 Markdown；其 TODO 只包含 step 和 status，不具备 DAG、输入输出或验收映射。因此 Better Plan 应借鉴其规划语义，不能退化到其任务数据结构。

### 3.2 OpenCode：探索、设计、复核、落盘、审批的完整流水线

OpenCode 的 [plan-mode.txt](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/opencode/src/session/prompt/plan-mode.txt#L1-L69) 把流程固定为五阶段：Initial Understanding、Design、Review、Final Plan、`plan_exit`。初始调查可按关注点并行分配至最多三个 Explore Agent；设计阶段提示词要求调用 `general` agent 形成实施方案；主 Agent 必须回读关键文件并复核方案，而不是直接转述子 Agent 输出。不过，当前内置 Plan 默认权限同时拒绝 `task:general`，说明这一步的提示词与默认运行时能力并未完全对齐，不能视为已经落实的独立 Plan Agent 流程。

运行时边界不只写在提示词里：

- [Agent 权限定义](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/opencode/src/agent/agent.ts#L119-L217) 将 Plan 与 Explore 建成独立 Agent。内置默认规则把 Plan 编辑限制在计划目录的 Markdown，但随后会合并 user permissions；Explore 采用 deny-by-default 后开放读取、搜索和 `bash`，本文件本身不能证明该 shell 是只读的。
- [Plan 工具](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/opencode/src/tool/plan.ts#L15-L79) 将用户拒绝保留在 Plan Mode，将批准转成带计划路径的 Build 消息。
- [reminders.ts](https://github.com/anomalyco/opencode/blob/38e10eb1408feb700021b8e8766fb0ab41bf84e2/packages/opencode/src/session/reminders.ts#L26-L89) 在进入 Plan 的首个相关回合注入计划文件位置，并在 Plan→Build 时把已有计划作为显式交接物。

优点是阶段、计划产物和退出审批都很清楚；缺点是默认权限存在上述不一致与可覆盖边界，最终计划也仍只要求关键文件与验证段落，未定义 Node 的输入输出、失败边界和依赖协议。

### 3.3 Gemini CLI：按风险调节计划深度，先达成策略共识再正式审批

Gemini CLI 的 [规划提示词](https://github.com/google-gemini/gemini-cli/blob/cf22ac7e86f3dcf528e3ae591fec1c03090a49f8/packages/core/src/prompts/snippets.ts#L598-L647) 先区分 Inquiry 与 Directive，再根据任务复杂度选择 Simple、Standard、Complex 模板。复杂任务必须写 Background & Motivation、Scope & Impact、Proposed Solution、Alternatives、分阶段实施、Verification、Migration & Rollback；不是把所有任务都塞进同一巨型模板。

它采用两层同意：

1. 先讨论调查结果、候选策略与取舍，取得非正式策略共识；
2. 下一回合才写正式计划并通过 Exit Plan Mode 请求批准。

提示词明确禁止在首次提出策略的同一回合直接形成并批准计划。这一门槛能避免 Agent 刚看到第一个可行方案就把它包装成“已完成计划”。

当启用可选的 persistent task tracker 时，Gemini 还把正式计划与持续任务图连接起来。[任务管理协议](https://github.com/google-gemini/gemini-cli/blob/cf22ac7e86f3dcf528e3ae591fec1c03090a49f8/packages/core/src/prompts/snippets.ts#L578-L595) 要求复杂任务立即拆分、依赖未关闭时只处理 leaf、完成前先验证，并使批准计划与 task graph 双向一致。[Exit Plan Mode](https://github.com/google-gemini/gemini-cli/blob/cf22ac7e86f3dcf528e3ae591fec1c03090a49f8/packages/core/src/tools/exit-plan-mode.ts#L116-L250) 验证计划文件边界、存在性与非空，拒绝后继续规划，批准后记录计划路径供执行读取；它没有冻结文件内容、revision 或 digest。

可借鉴之处是风险自适应和两阶段共识；不能照搬之处是 task description 虽要求详细，仍没有 Better Plan 所需的强类型交付契约。

### 3.4 Qwen Code：批准的是特定 revision，而不是一次模糊的“可以执行”

Qwen Code 的 [Plan reminder](https://github.com/QwenLM/qwen-code/blob/f3ba99f545e97cff48ecb6af7ea1ea7971d8a6e4/packages/core/src/core/prompts.ts#L1133-L1180) 是持续的 Explore→Capture→Ask 循环。它要求先建立相关组件与行为如何组合的全局理解，再决定局部修改；引用应复用的现有函数和路径；不要询问从仓库可发现的事实，只询问需求、偏好、取舍和边缘场景优先级。

Qwen Code 最值得借鉴的是审批并发安全：

- [`exitPlanMode.ts`](https://github.com/QwenLM/qwen-code/blob/f3ba99f545e97cff48ecb6af7ea1ea7971d8a6e4/packages/core/src/tools/exitPlanMode.ts#L131-L283) 冻结计划文本、原模式和 approval revision；收到确认后重新检查当前仍处于同一 Plan revision、请求未取消，陈旧确认会 fail closed。
- [设计文档](https://github.com/QwenLM/qwen-code/blob/f3ba99f545e97cff48ecb6af7ea1ea7971d8a6e4/docs/design/explicit-plan-exit-approval.md#L7-L29) 明确处理并发退出、陈旧确认、非交互宿主与失败转换；自动批准／allow 策略不能代替这次计划的显式批准。
- [Plan shell routing 设计与实现约束](https://github.com/QwenLM/qwen-code/blob/f3ba99f545e97cff48ecb6af7ea1ea7971d8a6e4/docs/design/2026-07-17-plan-mode-shell-routing.md#L50-L84) 采用 read-only／write／unknown 三态；unknown 只允许用户批准一次精确 invocation，不等于批准计划，也不退出 Plan Mode，并把 capability 绑定到参数、工作目录和 approval-mode revision。
- [`todoWrite.ts`](https://github.com/QwenLM/qwen-code/blob/f3ba99f545e97cff48ecb6af7ea1ea7971d8a6e4/packages/core/src/tools/todoWrite.ts#L35-L242) 的 Todo 使用稳定 ID、`blockedBy` 依赖，并拒绝重复、自依赖、未知依赖和环。

在调研样本中，Qwen Code 的“批准版本冻结”与 Better Plan 的规范化状态最互补。Better Plan 应把 plan revision／digest 纳入正式协议，而不是只依赖用户对一段变化中的文本说“继续”。

### 3.5 Cline：提示词、工具集、运行时命令守卫三层边界

Cline 的 [Plan/Act 提示词](https://github.com/cline/cline/blob/b3cee3f973ffe9d023a10c5c414deba68cd6e09d/sdk/packages/shared/src/prompt/cline.ts#L21-L59) 要求计划是有清晰步骤的结构化 outline；展示计划后必须结束当前回合，原始任务请求不能算批准，只有用户后续明确批准才可切换 Act。没有切换工具的宿主使用另一份契约，避免提示词声称有不存在的能力。

边界由代码再次强制：Plan 的工具 preset 移除 Editor；[`command-guard-extension.ts`](https://github.com/cline/cline/blob/b3cee3f973ffe9d023a10c5c414deba68cd6e09d/sdk/packages/core/src/extensions/tools/command-guard-extension.ts#L1-L88) 在审批与执行之前拦截变更命令；[`command-guard.ts`](https://github.com/cline/cline/blob/b3cee3f973ffe9d023a10c5c414deba68cd6e09d/sdk/packages/core/src/extensions/tools/command-guard.ts#L22-L247) 识别文件写入、Git／包管理器变更子命令和重定向，同时承认黑名单不是完整 shell parser。

Better Plan 应采用这种“提示词说明 + 能力过滤 + 运行时校验”三层模型。Cline 的不足是计划内容只到 outline，没有持久 Node、依赖、验收或重规划协议。

### 3.6 Roo Code：把“另一个 Mode 能独立执行”写进 Node 质量要求

Roo Code 的 [Architect Mode](https://github.com/RooCodeInc/Roo-Code/blob/b867ec9145750d0ae1ff7f02d35406e9bf2a0b16/packages/types/src/mode.ts#L168-L180) 明确要求 Todo：具体、可行动、逻辑排序、每项只聚焦一个明确结果，并清晰到另一个 Mode 可以独立执行。这一句是 Better Plan 定义独立 Node 时最直接的外部参照。

Roo 的 Todo 是持久状态而非一次性回答：

- [`update_todo_list`](https://github.com/RooCodeInc/Roo-Code/blob/b867ec9145750d0ae1ff7f02d35406e9bf2a0b16/src/core/prompts/tools/native-tools/update_todo_list.ts#L3-L34) 每次提交完整列表，信息变化时更新，只有完全完成才标记完成。
- [`UpdateTodoListTool`](https://github.com/RooCodeInc/Roo-Code/blob/b867ec9145750d0ae1ff7f02d35406e9bf2a0b16/src/core/tools/UpdateTodoListTool.ts#L19-L218) 先解析和校验，再让用户批准；用户可以直接编辑后批准，修改后的列表才入 Task，并能从历史恢复。辅助状态更新 API 只走 pending→in_progress→completed，但完整列表替换路径只校验状态枚举，没有强制单向迁移或完成项冻结。
- Mode 的工具和文件正则在运行时过滤，Architect 默认只能编辑 Markdown。

局限是 Todo item 仍是自由文本，没有输入、输出、依赖、验收证据、风险与回退字段。Better Plan 应采用其独立执行压力测试和可编辑批准 UX，而不是采用其扁平 checklist schema。

### 3.7 Aider：Architect 输出是 Editor 的唯一实施指令消息

Aider 的 [architect prompt](https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/architect_prompts.py#L6-L17) 把输出接收者定义成另一个 Editor 工程师，要求指令简洁但完整、无歧义；Editor 完全依赖这些指令。Architect 不直接输出整份更新文件，避免规划阶段同时承担精确编辑格式。

[`architect_coder.py`](https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/architect_coder.py#L6-L47) 在用户批准后创建独立 Editor，清空其对话消息，并把 Architect 的完整结果作为唯一实施指令消息。Editor 仍从原 coder 获得仓库、文件和运行配置等环境上下文；Planner 与 Editor 可选不同模型和 edit format。

这给 Better Plan 一个非常有用的 **transcript-zero test**：删除原对话，把 Node 作为唯一任务指令发给仍可访问仓库与工具的 Worker；如果 Worker 仍需猜产品选择、接口保证或验收方式，Node 就不是独立任务。Aider 本身的缺点是计划仍是一次性自然语言消息，没有持久 DAG、状态或细粒度批准。

### 3.8 Continue：完整性检查覆盖业务背景、风险、回滚与成功标准

Continue 的 [Plan Mode guide](https://github.com/continuedev/continue/blob/5522c6f44ca0ac3528b37244818fbfa39b5af470/docs/guides/plan-mode-guide.mdx#L68-L80) 要求高质量计划包含业务背景、技术约束、失败风险、回滚、多个方案与取舍；其[执行就绪清单](https://github.com/continuedev/continue/blob/5522c6f44ca0ac3528b37244818fbfa39b5af470/docs/guides/plan-mode-guide.mdx#L256-L266) 要求步骤、风险缓解、批准和成功标准齐备。官方 [how it works](https://github.com/continuedev/continue/blob/5522c6f44ca0ac3528b37244818fbfa39b5af470/docs/ide-extensions/plan/how-it-works.mdx#L55-L63) 将工作流拆成 Exploration、Analysis、Planning、Verification、Execution。

Continue 内核有[专门 Plan system message](https://github.com/continuedev/continue/blob/5522c6f44ca0ac3528b37244818fbfa39b5af470/core/llm/defaultSystemMessages.ts#L76-L91)；CLI 另有完整覆盖式 Checklist 和 Plan policy。但其权限实现暴露了值得警惕的反例：[`defaultPolicies.ts`](https://github.com/continuedev/continue/blob/5522c6f44ca0ac3528b37244818fbfa39b5af470/extensions/cli/src/permissions/defaultPolicies.ts#L42-L66) 明确留下 Bash 只读控制 TODO，并在末尾允许未过滤的 MCP；文档也承认 MCP 可能修改本地或外部系统。

因此 Better Plan 应采用其就绪清单，不应采用“提示词说只读，但运行时给通配工具”的权限做法。

### 3.9 OpenHands：规划子会话与执行会话物理隔离

OpenHands 在当前仓库前端中将 `code | plan` 建为显式状态。进入 Plan 时，[`use-handle-plan-click.ts`](https://github.com/All-Hands-AI/OpenHands/blob/68de5c58872a6b32dc2a94cce6fd33a410de49ff/src/hooks/use-handle-plan-click.ts#L42-L83) 创建独立 `agentType: "plan"` 子会话；正式产物固定为工作区内 `.agents_tmp/PLAN.md` 并做边界检查；Build 时切回 code 会话并发出读取该计划的固定指令。

任务列表更新也是完整覆盖，恢复时选择最新 `plan` observation。更值得 Better Plan 采用的是 [`child-conversation-launch.ts`](https://github.com/All-Hands-AI/OpenHands/blob/68de5c58872a6b32dc2a94cce6fd33a410de49ff/src/services/child-conversation-launch.ts#L126-L134) 的委派要求：child brief 必须自包含，写明目标、约束和预期输出。

当前 checkout 主要覆盖 Agent Canvas 客户端，规划 Agent 的完整系统提示词不在同一源码树，因此不能从此仓证明它对 Node 内容有更强的语义校验。可确认的优势是会话隔离、文件化计划和显式 Build 交接。

### 3.10 Goose：新会话 Executor 只能看到最终计划

Goose 的 [planner prompt](https://github.com/block/goose/blob/064244e6bddf641876676f054a006b7da1da5182/crates/goose/src/prompts/plan.md#L1-L32) 只允许两种结果：信息充分时输出完整计划；否则一次性输出全部澄清问题。每一步必须说明依赖和条件分支，并重述执行所需背景。

其最强约束是：Executor 在全新会话中只收到 Planner 最终计划，完全看不到原始对话。官方 [creating plans](https://github.com/block/goose/blob/064244e6bddf641876676f054a006b7da1da5182/documentation/docs/guides/context-engineering/creating-plans.md#L16-L43) 说明交互规划与规划／执行模型分离；[审阅与执行门](https://github.com/block/goose/blob/064244e6bddf641876676f054a006b7da1da5182/documentation/docs/guides/context-engineering/creating-plans.md#L82-L114) 在用户审阅后清空历史并执行；[多轮澄清说明](https://github.com/block/goose/blob/064244e6bddf641876676f054a006b7da1da5182/documentation/docs/guides/context-engineering/creating-plans.md#L210-L233) 要求信息充分后再生成并审阅计划。

Goose 的计划仍是编号文本，Todo 也没有 DAG；但“零原始上下文”是本次样本中检验计划是否真正完整的最好机制之一。

### 3.11 Crush：Todo 能闭环执行，但不能替代计划

Crush 没有独立 Plan Mode。它在 [coder prompt](https://github.com/charmbracelet/crush/blob/75791b8883df8689bef5d2b0407fa71c93bb5234/internal/agent/templates/coder.md.tpl#L61-L134) 中规定 Before／While／Before finishing 流程，只在真实业务歧义、重大取舍、数据丢失或外部阻塞时提问；同一提示词的[非平凡任务规则](https://github.com/charmbracelet/crush/blob/75791b8883df8689bef5d2b0407fa71c93bb5234/internal/agent/templates/coder.md.tpl#L217-L238) 要求先枚举模型、逻辑、路由、配置、测试、文档、边界与错误路径。

Todo 是 session 一等状态，[数据结构](https://github.com/charmbracelet/crush/blob/75791b8883df8689bef5d2b0407fa71c93bb5234/internal/agent/tools/todos.go#L17-L102) 为每项同时保存 imperative `Content` 和 present-continuous `ActiveForm`。[工具说明](https://github.com/charmbracelet/crush/blob/75791b8883df8689bef5d2b0407fa71c93bb5234/internal/agent/tools/todos.md#L1) 要求恰好一个 `in_progress`，但实现只校验状态枚举，没有强制该数量。这有助于界面表达和执行闭环，却没有输入、输出、所有权、依赖和验收字段。

这个样本提醒我们：**稳定 Todo 状态不等于完整计划**。Better Plan 不应因已有 Node 状态机就认为计划语义也已经完整。

### 3.12 Plandex：最接近可解析“独立任务”的自然语言协议

Plandex 的 [planning.go](https://github.com/plandex-ai/plandex/blob/e2d772072efadbe41d2946d97d79be55532dbab5/app/server/model/prompts/planning.go#L12-L133) 在提示词层要求整数编号、唯一名称、具体说明和精确 `Uses:` 文件集合，并以 `<PlandexFinish/>` 作为可解析结束标记。`Uses:` 被要求同时列修改文件与执行时需要加载的参考文件，且不能用目录替代文件。

后续[修订提示词](https://github.com/plandex-ai/plandex/blob/e2d772072efadbe41d2946d97d79be55532dbab5/app/server/model/prompts/planning.go#L206-L318) 要求按一个 cohesive functionality 分组、不制造额外任务，并用同名修改与独立 Remove Tasks 表达修订；它还要求不要修改或删除已完成项。实际 [parser](https://github.com/plandex-ai/plandex/blob/e2d772072efadbe41d2946d97d79be55532dbab5/app/server/model/parse/subtasks.go#L10-L120) 会解析成 `Title + Description + UsesFiles`，但不强制 Description 或 Uses 非空；运行时合并／删除路径也没有可靠强制“完成项冻结”。因此应区分提示词期望、可解析结构和运行时不变量。

Plandex 最值得借鉴的不是其具体 Markdown 格式，而是三点：

- 计划文本必须能被确定性解析；
- 提示词把每项任务的文件上下文列成显式 `Uses:`，而不是让 Worker 重新漫游整个仓库；
- 修改与删除有显式语法；Better Plan 应在借鉴该协议时额外用运行时硬化完成项冻结。

它的局限是内容完整性与完成项冻结并未被 parser／合并逻辑充分强制，`Uses:` 也仍无法表示上游保证、失败行为、共享外部状态或验收 oracle；其默认提示词还会在用户未要求时排除测试与文档，不能照搬为 Better Plan 的验收策略。

### 3.13 AutoGen / Magentic-One：先建立事实账本，再规划和重规划

Magentic-One 的 [prompts.py](https://github.com/microsoft/autogen/blob/027ecf0a379bcc1d09956d46d12d44a3ad9cee14/python/packages/autogen-agentchat/src/autogen_agentchat/teams/_group_chat/_magentic_one/_prompts.py#L6-L136) 在计划之前先建立事实账本，严格区分：

1. 请求给定或已经验证的事实；
2. 待查询事实及其具体来源；
3. 需要推导的事实；
4. 记忆、经验猜测和假设。

计划基于团队能力和该事实表生成。执行中每轮 Progress Ledger 通过 schema 约束或显式校验的 JSON 判断是否完成、是否循环、是否前进、下一 speaker／执行代理及给他的具体指令。[orchestrator 状态](https://github.com/microsoft/autogen/blob/027ecf0a379bcc1d09956d46d12d44a3ad9cee14/python/packages/autogen-agentchat/src/autogen_agentchat/teams/_group_chat/_magentic_one/_magentic_one_orchestrator.py#L225-L245) 显式持久化 task、facts、plan、rounds 和 stalls。停滞达到阈值后，不是直接“再试一次”，而是先更新事实，再解释失败根因并生成避免同样错误的[新计划](https://github.com/microsoft/autogen/blob/027ecf0a379bcc1d09956d46d12d44a3ad9cee14/python/packages/autogen-agentchat/src/autogen_agentchat/teams/_group_chat/_magentic_one/_magentic_one_orchestrator.py#L348-L476)。

Better Plan 当前已擅长执行 receipt，但缺一个对等的“事实与假设账本”。把 `observed`、`user_decided`、`defaulted`、`unresolved` 分开，可以阻止 Planner 把猜测写成 Worker 的强制要求。

### 3.14 SWE-agent：以复现—修复—复验限制每个实现闭环

SWE-agent 没有显式 Plan Mode、Planner 或任务 ledger。它的价值在于作为最小执行闭环对照：[default.yaml](https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/config/default.yaml#L6-L63) 要求先读相关代码、写复现、确认错误、修改源码、复验、检查边缘情况；提交前重跑复现、删除临时脚本、恢复测试文件，并检查完整 diff。范围被限制为满足 PR 描述所需的最小非测试文件改动。

每步 action、observation、thought、state 和结果都写入 trajectory，直到明确 done。Better Plan 应把这类闭环吸收到每个 Node 的 acceptance 与 evidence，而不是把“测试”留给最后一个宽泛 Validation Node。

## 4. 跨项目最值得借鉴的共同模式

| 模式 | 最佳参照 | Better Plan 应采用的形式 |
|---|---|---|
| 先查可发现事实，再问用户决策 | Codex、Qwen Code、Goose | 建立问题分类；全部不可推导决策合并成一次、最多十组的 Decision Dossier |
| 规划深度随复杂度／风险变化 | Gemini CLI | Simple／Standard／Complex／Critical 的条件模板；高风险维度不可省略，低风险不填空话 |
| 正式计划前先达成策略共识 | Gemini CLI | Decision Dossier 先冻结关键决策与取舍，再由一次 Designer 完成 canonical Plan |
| 计划与 TODO 分离 | Codex、Gemini CLI | canonical Plan 是完整规范；进度列表仅为从 Task 状态生成的只读投影 |
| 规划与执行硬隔离 | OpenCode、Cline、OpenHands | 默认提示词、工具能力与运行时守卫应对齐；允许计划产物写入时限定固定目录，Cline 则禁止 workspace 写入 |
| Executor 不继承原对话 | Goose、Aider | 每个 Worker brief 通过 transcript-zero test；所有必要实施意图、输入保证和决策都在 Task 中，仓库与工具仍是可用执行环境 |
| 单项任务只交付一个明确结果 | Roo Code、Plandex | 一个 Task 对应一个 capability／module／scenario closure；多个可独立验收结果必须拆分 |
| 正式计划是可解析协议 | Plandex | 用强类型 schema 取代仅靠 Markdown 约定；解析和语义校验失败时 fail closed |
| 执行任务图结构化 | Qwen Code；Gemini CLI（可选 tracker） | 使用稳定 ID、依赖、状态与环检测；它是批准 Plan 的执行投影，不替代正式计划 |
| 批准绑定特定版本 | Qwen Code | 首次审批绑定 revision + digest；只有通过 authority diff 的未开始工作 continuation 才能显式继承授权 |
| 事实、未知与猜测分账 | AutoGen | Plan 级 facts／decisions／assumptions ledger；未决高影响问题不能进入 executable Node |
| 重规划解释失败根因 | AutoGen、Plandex 的修订提示词 | 把完成项冻结实现为硬约束；只修改未完成项；记录触发证据、根因、revision diff 与授权继承 receipt |
| 每项先验证再完成 | Gemini CLI、SWE-agent | 每个输出映射到可执行 oracle 和 evidence；负面边界也有对应验收 |

### 4.1 不应照搬的做法

- 不把 Roo、Crush、Continue 的扁平 Markdown checklist 当成计划 schema。
- 不把“关键文件 + 若干步骤 + 测试”当成完整 Node；它缺少输入保证、输出契约和失败语义。
- 不只靠 system prompt 维持只读；Continue 的 MCP／Bash 缺口说明能力层必须 fail closed。
- 不用文件不重叠代替并行安全分析；两个 Node 可以不改同一文件，却同时迁移同一数据库、生成同一产物、改变同一接口语义。
- 不在每个 Node 中机械填满所有风险段落。应对每个风险维度标记“适用并有内容”或“不适用并有理由”，避免长而空的计划。
- 不让 Planner 自己批准自己的计划，也不把一次 shell 命令审批扩张成整个 Plan 的审批。

## 5. Better Plan v1 做得好的部分

> 本节至第 14 节是对迁移前 v1 的审计和最初候选方案。它解释“为什么必须换代”，但其中 `Node`、只读 Designer、`plan_patch`、Repair Task 和重新审批等候选设计已由第 15 节的最终 v2 协议取代。

在指出缺陷前，需要保留 Better Plan 已经明显优于多数样本的能力：

1. **Canonical DAG**：`prerequisites` 是唯一执行图，能拒绝未知 Node、skipped 链和环；比绝大多数 Markdown 计划更可靠。
2. **组级设计与真实并行前沿**：一个 group design、多个 implementation、一个 final validation；明确禁止用叙事顺序制造依赖。
3. **机器化 design contract**：`owned_paths`、`symbols`、`interfaces`、`dependencies`、`decisions`、`test_seams` 已经为设计和所有权提供了强结构。
4. **执行状态与相关性**：dispatch ID、绑定的真实 child ID、回调去重、尝试上限和 main fallback 构成成熟的执行控制面。
5. **验收与回归生命周期**：每个实现 Node 有 focused regression，组级只有一次 full regression，repair 有明确预算；比“最后跑一下测试”的普通计划可靠。
6. **独立 Reviewer 与视觉证据**：最终审阅、视觉／混合 profile 和真实浏览器证据是高风险交付的重要优势。
7. **隐私和范围控制**：禁止把本机身份、密钥、后端运行数据与绝对路径写入 Plan／delegation，是其它样本常被忽略的边界。

因此本报告不是建议重做整个系统，而是为现有控制面补上一层同等严格的**计划语言与计划编译器**。

## 6. Better Plan v1 的具体缺陷

### P0-1：设计阶段存在时序倒置

迁移前基线 [`validate_node_design_contract`](https://github.com/Unka-Malloc/better-plan/blob/6232a00fc7327a99066466179a08bf8f37ba08d9/scripts/better_plan/domain/validation.py#L213-L224) 要求所有非终态 `group_design`、`implementation`、`final_validation` Node 在可调度前都带完整 `design`。而基线 [`designer.md`](https://github.com/Unka-Malloc/better-plan/blob/6232a00fc7327a99066466179a08bf8f37ba08d9/references/designer.md#L55-L62) 明确禁止 Designer 修改 Better Plan 状态，只能返回设计／验收路径、评估、handoff、风险和 blocker。

结果是：

- native main 必须在 Designer 之前猜出所有 paths、symbols、interfaces、algorithms、state、isolation、concurrency；
- Designer 更像对既有答案作外部润色，不能承担“冻结设计”的真实职责；
- 如果 Designer 发现 Node 拆分、接口或所有权错误，没有原子化结构 patch 进入 canonical Plan 的路径；
- 主提示词所说“Designer freezes handoffs”与运行时 schema 的实际作者不一致。

**最初候选（已被 v2 取代）**：曾考虑让 Designer 返回结构化 `plan_patch`。后续讨论确认这仍然限制了 Designer 的设计自由，也把修补责任推回 native main；v2 改为一次 Designer 会话直接编辑整份 canonical Plan，并用前后 intent／scope diff 守住授权核心。

### P0-2：计划语义没有被代码强制

基线 [`state-files.md`](https://github.com/Unka-Malloc/better-plan/blob/6232a00fc7327a99066466179a08bf8f37ba08d9/references/state-files.md#L185-L194) 对 `description` 给出了 Scope、Context、Target、Design Considerations、Design Value、Constraints & Risks 等丰富说明，但基线 [`validation.py`](https://github.com/Unka-Malloc/better-plan/blob/6232a00fc7327a99066466179a08bf8f37ba08d9/scripts/better_plan/domain/validation.py#L573-L575) 只检查 `goal` 与 `description` 是非空字符串。`Closure:` 也只出现在文档、模板和 CLI 帮助中，没有 parser 验证“恰好一个”“位于开头”“确实可独立验收”。

同样，基线[验收校验](https://github.com/Unka-Malloc/better-plan/blob/6232a00fc7327a99066466179a08bf8f37ba08d9/scripts/better_plan/domain/validation.py#L534-L565) 只检查数组非空、对象字段、`checked` 布尔值和 `text` 非空。它不能证明：

- criterion 有可执行 oracle；
- 每个 output／requirement 都被覆盖；
- 每个 failure mode 有负面验收；
- evidence 的来源、命令、断言和成功阈值明确；
- criterion 能由本 Node 独立满足，而不是依赖最终 Reviewer 补洞。

这使“文档很严格、数据很宽松”。格式合法不等于计划完整。

### P0-3：“独立任务”缺少可判定定义

当前 Planning kernel 说独立 Node 路径互斥、消费稳定接口并可并发，但没有把独立性拆成三种不同性质：

1. **任务自包含**：Worker 不需要原对话或隐藏决策；
2. **验收独立**：该 Node 有自己的 observable outcome 与 oracle；
3. **并行安全**：在没有 prerequisite path 时，不与 sibling 争用文件或共享可变资源。

只看 `owned_paths` 会漏掉数据库 schema、生成器输出、feature flag、外部 API、全局配置、协议版本、缓存 namespace 等语义冲突。只写 `Closure: module - X` 也不能证明该模块交付了一个可观察结果。

### P1-1：没有正式的事实、决策、假设与未知账本

Better Plan 现在要求 source-grounded，但没有像 AutoGen 那样把“observed／to lookup／to derive／guess”变成数据；也没有像 Codex 那样为 discoverable facts 与 user decisions 建立问题分类。`Constraints & Risks` 甚至允许把 unresolved questions 与强制约束写在同一自由文本段落。

后果是：

- 猜测可能被悄悄升级为 Worker 约束；
- 用户已做出的产品选择没有稳定 provenance；
- 代码变化后，不知道哪个 Node 依赖哪条已失效事实；
- executable Plan 中可能仍藏着高影响未决问题。

### P1-2：DAG 边只表示顺序，没有表示交付契约

`prerequisites` 能可靠决定 eligibility，这是优势；但一条边没有说明**为什么存在**。当前无法机器验证：

- producer 的哪个 output 被 consumer 的哪个 input 使用；
- producer 承诺的 interface／artifact／invariant 是什么；
- consumer 是否声明了没有对应上游的输入；
- 一个 handoff 指向的 consumer 是否真的依赖 producer；
- 依赖删除后，是否留下悬空输入。

应该保留 `prerequisites` 作为唯一调度图，同时新增 `inputs[].from_node/output` 和 `handoffs[]` 作为边的语义；校验器从语义映射验证现有图，而不是再创造第二张调度图。

### P1-3：验收是 checkbox，不是 oracle 覆盖模型

当前 criterion 的 `text` 可以写“功能正常”并通过 schema。完整验收至少需要：

- 被覆盖的 requirement、output、invariant 或 failure mode ID；
- setup／Given；触发／When；observable assertion／Then；
- oracle 类型（测试、命令、文件检查、浏览器、人工决策等）；
- repository-relative evidence path 或安全命令；
- 正向／负向／迁移／回滚类别；
- 未执行、失败和不适用的明确状态。

### P1-4：缺少“计划已经可以执行”的语义门与审批 revision

Better Plan 有丰富的执行 transition，却没有一个与 Qwen Code 等价的 Plan revision／digest／approval。当前技能也没有要求：首次策略提案与正式计划必须分开；高影响决策清零；正式计划是完整替换；用户批准绑定一个不可变版本。

这在并发和重规划时尤其危险：用户可能批准的是旧文本，而 main 已经修改 Node；或者某个 Node 已完成后，Planner 又改写其边界，没有明确冻结规则。

### P1-5：leaf brief 仍依赖 native main 的临场写作

基线 [`workflow.py`](https://github.com/Unka-Malloc/better-plan/blob/6232a00fc7327a99066466179a08bf8f37ba08d9/scripts/better_plan/application/workflow.py#L20-L49) 把原始 Node 字段投影到 `work_items`；基线 [`orchestration-main.md`](https://github.com/Unka-Malloc/better-plan/blob/6232a00fc7327a99066466179a08bf8f37ba08d9/references/orchestration-main.md#L174-L196) 再要求 native main 自行选择组织与细节，写明 outcome、背景、范围、产物、风险。

这比直接转发 JSON 好，但仍不是确定性“计划编译”：两个 main 可能从同一 Node 写出信息差异很大的 brief；schema 中隐含在自由文本的内容也无法确保全部被传递。应让结构化 Node 自动编译出 transcript-zero brief，native main 只能增加有来源的补充上下文，不能遗漏必填契约。

### P2-1：`check-plan-readiness` 名称与实际语义不一致

基线 [`readiness.py`](https://github.com/Unka-Malloc/better-plan/blob/6232a00fc7327a99066466179a08bf8f37ba08d9/scripts/better_plan/infrastructure/readiness.py#L16-L105) 运行宿主命令、hash Plan／Node 与声明路径，并证明检查期间输入未变化。这是有价值的 **host preflight／freshness check**，但它并不检查本报告所说的计划语义完整性。

未来若加入真正的 semantic readiness，建议一次性把当前命令改名为 `check-host-readiness`，并让 `check-plan-readiness` 专门运行 facts／decisions／task contracts／design contracts／edge mappings／acceptance coverage／approval revision 校验。按仓库规则应完整迁移，不长期保留同义旧命令。

### P2-2：所有 Node 使用同一自由文本大纲，风险不自适应

一个局部机械改动与跨协议迁移都被要求在同一个 `description` 中判断哪些段落适用。结果通常有两个极端：小任务填大量空话，复杂任务把 migration、rollback、security、concurrency 和 observability 挤在一个 `Constraints & Risks` 段落。

应借鉴 Gemini CLI 的复杂度模板，但用字段 applicability 而非散文长度控制：每个维度要么给出内容，要么 `applicable: false` 并写理由；Critical Node 则必须显式处理更多维度。

## 7. v1 阶段的候选模型：五层计划协议（已被第 15 节取代）

```mermaid
flowchart LR
    A["事实与未知账本"] --> B["用户决策与约束"]
    B --> C["Task Contract：what / why / boundary"]
    C --> D["Designer Plan Patch"]
    D --> E["Design Contract：how / interface / ownership"]
    E --> F["语义就绪校验"]
    F --> G["冻结的 Plan revision + digest"]
    G --> H["确定性 Leaf Brief 编译"]
    H --> I["Worker 执行与 Node 证据"]
    I --> J["Reviewer / repair / regression"]
```

五层的职责应当互不混淆：

1. **Facts & Decisions Ledger**：记录事实的来源、状态和用户决策，不能包含执行状态。
2. **Task Contract**：由 native main 在 Designer 前冻结，描述 what、why、边界、输入、输出和验收意图；不提前猜具体实现。
3. **Design Contract**：由 Designer 通过结构化 patch 形成，描述 paths、symbols、interfaces、算法、状态、并发、test seams 和跨 Node handoff。
4. **Plan Revision & Approval**：冻结上述语义的 canonical digest；批准只对精确 revision 生效。
5. **Execution State & Evidence**：沿用现有 dispatch／acceptance／regression／reviewer 控制面；不能反向偷偷改写已批准意图。

## 8. “独立任务”的正式判定规则

### 8.1 必须同时通过的六个测试

1. **Single-outcome test**：Node 只交付一个 capability、module 或 scenario closure，且 outcome 是用户或下游可观察状态，不是“修改若干文件”。
2. **Transcript-zero test**：Worker 只收到该 Node、已批准设计契约和上游产物，也能开始；不需要原对话来补需求、取舍或接口含义。
3. **Dependency-closure test**：所有输入都来自仓库既有事实、明确外部前置，或 `prerequisites` 中 producer 的命名 output；没有隐藏依赖。
4. **Own-oracle test**：每个 output／requirement／failure mode 都有本 Node 可执行的验收；不能只说“在 final validation 一起看”。
5. **Ownership test**：文件、symbols、生成物和共享可变资源的写所有权明确；与无依赖 sibling 没有冲突。
6. **Handoff test**：对下游暴露稳定 artifact／interface／invariant，consumer 名称和保证明确；Worker 不需要知道 sibling 内部实现。

### 8.2 何时必须拆 Node

出现任一条件就应拆分：

- 包含两个可以分别验收、分别回滚的 observable outcomes；
- 一部分被阻塞时，另一部分仍可独立交付；
- 需要不同 Worker 权限、平台、verification profile 或风险等级；
- 修改所有权不相交，并通过稳定接口交接；
- 失败修复责任落在不同模块／能力所有者；
- 一个“实现”节点同时承担 schema migration、业务消费切换和旧实现删除，而三者需要独立前置或回滚门。

不应拆分的典型情况：同一内聚功能在多个紧耦合小文件中的实现、同一状态机的 model + transition + 最小测试、为了套设计模式而按参与者拆 Node、只有叙事先后但没有真实 handoff 的步骤。

### 8.3 并行安全是额外条件

两个独立 Node 只有同时满足以下条件才是 ready frontier：

- 彼此没有 prerequisite path；
- `owned_paths`、symbols 与 acceptance ownership 不重叠；
- 不写同一数据库对象、schema、锁、全局配置、generated artifact、cache namespace、外部资源或协议版本；
- 只通过已经冻结的 interface 交互；
- 任一 Node 失败或回滚不会让另一个 Node 的验收产生假阳性。

## 9. 建议的新 Node 契约

以下是概念 schema，字段名称可在实施设计中微调，但语义不应再退回一个 `description` 字符串：

```json
{
  "id": "<uuid4>",
  "role": "implementation",
  "goal": "冻结一次只对精确 Plan revision 生效的用户批准",
  "prerequisites": ["<producer-node-id>"],
  "task_contract": {
    "closure": {
      "kind": "capability",
      "subject": "plan revision approval",
      "outcome": "旧 revision 的确认不能启动新 revision 的执行"
    },
    "grounding": [
      {
        "fact": "当前 Plan 没有 revision-bound approval",
        "basis": "observed",
        "source": "scripts/better_plan/domain/validation.py"
      }
    ],
    "scope": {
      "in": ["Plan revision model", "approval transition", "stale-confirmation rejection"],
      "out": ["UI redesign", "execution agent selection", "unrelated receipt formats"]
    },
    "inputs": [
      {
        "name": "canonical plan payload",
        "from_node": "<producer-node-id>",
        "output": "validated_task_graph",
        "guarantee": "schema and semantic readiness have passed"
      }
    ],
    "outputs": [
      {
        "id": "frozen_approval",
        "artifact": "plan approval receipt",
        "guarantee": "receipt binds revision, digest and authorized transition"
      }
    ],
    "invariants": [
      "approval never authorizes a different digest",
      "a shell command approval never counts as Plan approval"
    ],
    "failure_modes": [
      {
        "id": "stale_confirmation",
        "condition": "Plan changes after confirmation is shown",
        "required_behavior": "reject the confirmation and remain non-executable"
      }
    ],
    "assumptions": [
      {
        "statement": "approval is an explicit user action",
        "basis": "user_decided",
        "source": "decision:<decision-id>"
      }
    ],
    "open_questions": [],
    "handoffs": [
      {
        "consumer_node": "<consumer-node-id>",
        "output": "frozen_approval",
        "guarantee": "consumer may dispatch only while digest remains current"
      }
    ]
  },
  "design": null,
  "acceptance_criteria": [
    {
      "id": "AC-stale-confirmation",
      "covers": ["failure:stale_confirmation", "output:frozen_approval"],
      "kind": "negative",
      "given": "revision N is shown for approval",
      "when": "the Plan changes to revision N+1 before confirmation returns",
      "then": "confirmation is rejected and no delivery dispatch is created",
      "oracle": {
        "method": "automated_test",
        "path": "tests/<focused-test-file>",
        "assertion": "stale approval fails closed"
      },
      "checked": false
    }
  ]
}
```

### 9.1 边界维度必须显式适用或不适用

| 维度 | 计划必须回答的问题 |
|---|---|
| Scope | 明确 in／out；哪个相邻能力故意不做；扩张边界是什么 |
| Inputs & preconditions | 开始前必须存在什么；来源与保证是什么；失败时是 blocked 还是 fallback |
| Outputs & handoffs | 交付什么稳定 artifact／interface／invariant；哪个 consumer 使用 |
| Invariants & state | 哪些状态永远不能破坏；重试、幂等、顺序、恢复语义是什么 |
| Failure modes | 触发条件、必须行为、可观察信号、责任 Node 是什么 |
| Compatibility | 是否保留旧协议／格式；若完全迁移，旧实现何时删除、如何证明无残留 |
| Migration & rollback | 数据／schema／配置如何迁移；不可逆点；失败后回到什么安全状态 |
| Privacy & security | 敏感信息、权限边界、外部副作用、审计证据是什么 |
| Performance & concurrency | 复杂度、缓存、锁、竞争、吞吐／延迟阈值是否适用 |
| Observability | 如何检测成功、失败、降级和回滚；哪些日志／指标可安全作为证据 |
| Acceptance | 每个 output／requirement／failure mode 由哪个 oracle 覆盖 |

对不适用的维度应使用结构化 `{ "applicable": false, "reason": "..." }`，不能靠省略让 Reviewer 猜，也不能用“无特殊风险”作为填充。

## 10. 建议的 Plan Authoring 提示词

下面的英文文本可作为未来 `references/planning-author.md` 的核心；它面向实际技能提示词，因此保留命令式表达。

```text
## Canonical Plan authoring protocol

The Plan is an executable specification, not a brainstorming note, file inventory,
or progress checklist. Do not create executable Nodes until repository facts,
user-owned decisions, task boundaries, and acceptance oracles are decision-complete.

### Phase 1 — Ground the request

1. Restate the authorized outcome and observable success.
2. Inspect the smallest repository surface that can establish current behavior,
   existing patterns, affected data/control flow, tests, and delivery constraints.
3. Record every material statement as one of:
   - observed: verified from a repository-relative source;
   - user_decided: explicitly chosen by the user;
   - defaulted: a reversible low-impact default with its rationale;
   - unresolved: a fact to discover or a decision to ask.
4. Never ask the user for a discoverable repository fact. Ask only for requirements,
   preferences, authorization, trade-offs, or edge-case priorities that materially
   change the result.

### Phase 2 — Freeze intent and boundaries

Before decomposition, make the following decision-complete: outcome, audience,
in-scope behavior, explicit non-goals, current state, invariants, compatibility,
migration/rollback needs, security/privacy constraints, performance/concurrency
constraints, and success evidence. If a high-impact item remains unresolved, ask
the user and do not emit an executable Plan.

### Phase 3 — Select and agree on the strategy

Trace the relevant end-to-end flow before choosing local edits. Reuse established
interfaces and patterns. For material alternatives, state the trade-off and record
the selected decision. For complex or critical work, obtain strategy agreement in
a separate turn before producing the formal Plan.

### Phase 4 — Decompose by independently acceptable outcomes

Create one implementation Node per cohesive capability, module, or scenario closure.
A Node is independent only when, after its declared prerequisites are satisfied, a
Worker with no access to the original conversation can complete and verify it from
the frozen Node brief without making a hidden product or architecture decision.

For every Node define: observable outcome; grounding; in/out scope; inputs and their
sources; outputs and guarantees; invariants; failure behavior; assumptions and
provenance; handoffs; applicable boundary dimensions; and acceptance oracles.
Do not create an edge for narrative order. Every prerequisite edge must map a named
producer output to a named consumer input. Parallel Nodes must also have disjoint
write ownership and no shared mutable-resource conflict.

### Phase 5 — Adversarial boundary review

Try to invalidate the decomposition. Check hidden dependencies, two outcomes in one
Node, cross-Node file or state conflicts, negative paths, retries, partial failure,
stale state, migrations, rollback, compatibility removal, security/privacy,
performance/concurrency, observability, and false-positive tests. Split or repair
Nodes before approval; never defer a known planning defect to the Worker.

### Phase 6 — Design, validate, and approve

Dispatch Designer only after task contracts are complete. Designer returns one
structured atomic plan patch containing design contracts, owned paths, interfaces,
cross-Node handoffs, decisions, and test seams. Apply the patch only after schema
and semantic validation. Do not let design silently change authorized outcomes,
scope, requirements, or user decisions; return such conflicts as decision blockers.

The formal Plan is always a complete replacement revision. It is ready only when:
- there are no high-impact open questions;
- every input is grounded or produced by a prerequisite;
- every output and requirement has an acceptance oracle;
- every declared failure mode has negative-path coverage;
- every handoff is mirrored by the canonical prerequisite graph;
- parallel ownership is conflict-free;
- migration/removal/rollback obligations are explicit where applicable; and
- the exact canonical revision and digest are presented for explicit approval.

Approval authorizes only that revision. Any semantic edit invalidates the approval.
The execution tracker is derived from the approved Nodes; it never replaces or
silently edits the Plan.
```

### 10.1 Node 撰写子提示词

```text
Write this Node for a Worker who receives no original conversation and owns exactly
one acceptance boundary. Prefer repository-relative facts and stable contracts over
narrative explanation.

Reject or split the Node if any answer is “yes”:
1. Does it contain two outcomes that can be accepted or rolled back separately?
2. Must the Worker choose an unstated product, API, migration, or architecture policy?
3. Does it consume an artifact or guarantee that no prerequisite produces?
4. Can it be marked complete without observing its stated product outcome?
5. Does a failure mode lack a required behavior and an oracle?
6. Does a parallel sibling write the same file, symbol, generated artifact, schema,
   configuration, external resource, or semantic interface?
7. Does the brief rely on “as discussed”, “etc.”, “handle edge cases”, “works”, or
   another phrase whose meaning exists only in the parent conversation?

Return structured fields, not a prose replacement for missing fields. Keep the
closure cohesive, but include every material fact, constraint, uncertainty, risk,
and acceptance condition needed for independent execution.
```

### 10.2 计划就绪审查提示词

```text
Audit the Plan as an adversarial implementer and verifier. Do not improve wording
unless it changes executability. For each failure, identify the Node, violated rule,
missing or contradictory contract, and the smallest semantic repair.

Fail readiness when a Node has a hidden decision, ungrounded assumption, unmatched
input/output, unverifiable outcome, uncovered failure mode, false parallelism,
scope overlap, stale approval, or migration/removal obligation without proof.
Pass only when every Worker can execute from the compiled transcript-zero brief and
every Node can be accepted from its own declared evidence.
```

## 11. 机器校验应新增的规则

### 11.1 Plan 级

- 每个 fact 有唯一 ID、`basis`、repository-relative source 或 decision reference。
- `unresolved` 高影响事项非空时，Plan 不得进入 designed／approved。
- 每个用户决策保存候选、选择和影响范围；修改关联 Node 时提升 revision。
- formal Plan 保存 monotonically increasing revision、canonical digest 和 explicit approval receipt。
- 任何语义字段、图边或 acceptance 变化使旧 approval 与未开始 dispatch 失效。
- 已完成 Node 冻结；需要改变已交付行为时创建显式 repair／migration Node，不改写历史。

### 11.2 Node 级

- `closure.kind/subject/outcome` 均非空，且每个 implementation 恰好一个 closure。
- `scope.in` 与 `scope.out` 不空且不冲突；outcome 不能只是文件操作。
- `open_questions` 必须为空才能执行。
- 每个 `defaulted` assumption 必须是低影响、可逆并有 rationale；高影响只能 `user_decided`。
- 每个 input 必须是 observed external precondition，或映射一个 prerequisite 的 output。
- 每个 handoff target 必须依赖当前 Node，且 output ID 必须存在。
- 每个 output、requirement、invariant 和 failure mode 至少被一个 criterion `covers`。
- 每个 failure mode 至少有一个 `kind: negative` criterion。
- acceptance oracle 必须声明 method、证据位置／安全命令和明确 assertion。
- refactor／migration Node 若要求完整替换，必须有旧实现删除清单与一次性残留检查。

### 11.3 图与并行级

- 继续以 `prerequisites` 作为唯一 scheduler authority；input/output mapping 只解释并验证边。
- 拒绝没有任何语义 handoff 的人工串行边，除非明确标记为 milestone／authorization gate。
- 拒绝有 input mapping 却没有对应 prerequisite 的隐藏边。
- 除路径 overlap 外，增加 `shared_resources` ownership；检测同一 schema、generated artifact、全局 config、external side effect 的冲突。
- 在 Designer patch 后重新计算最大安全 ready frontier，并输出不能并行的具体原因。

## 12. v1 阶段的候选迁移顺序（历史）

按照仓库“一次性完整迁移、不长期保留旧兼容”的规则，建议分成四个最小可验收闭环，但在一个发布代际内完成：

### 闭环 A：任务语义 schema 与校验器

- 新增 Plan facts／decisions／assumptions／revision schema。
- 用 `task_contract` 取代 `description` 中的 Scope／Context／Target／Constraints 散文协议。
- 升级 acceptance criterion 为 `covers + Given/When/Then + oracle`。
- 增加 input/output/handoff 和 boundary applicability 校验。
- 提供一次性迁移脚本转换仓库内测试 fixture；验证没有旧 `description` 协议后删除迁移脚本与兼容读取。

**最小验收**：语义不完整但格式非空的 Node 必须 fail；一个完整 transcript-zero Node 能通过；未知问题、悬空 input、未覆盖 output 和假并行分别有一个代表测试。

### 闭环 B：修正 Designer 时序

- pre-design gate 只要求 facts、decisions 和 task contracts 完整。
- Designer 返回强类型 `plan_patch`，包含每个 delivery Node 的 design contract、handoff 与 acceptance seam。
- native main 原子验证并应用；patch 不能静默改写用户意图和 scope。
- 只有 designed group 才允许 implementation dispatch。

**最小验收**：无预填 design 的 task-ready group 可以调度 Designer；不完整／越权 patch 不改变状态；完整 patch 一次性使 group design-ready。

### 闭环 C：审批版本与确定性 brief 编译

- formal Plan 生成 canonical revision／digest；显式批准绑定该 digest。
- stale／并发 approval fail closed；一次工具批准不扩张为 Plan 批准。
- 从 task + design + acceptance 自动编译 leaf brief；main 可追加有来源的补充，但不能删必填块。
- 给编译结果增加 transcript-zero snapshot test。

**最小验收**：相同 Plan 产生稳定 digest 与稳定 brief；任一语义编辑使旧批准失效；Worker payload 完整包含 inputs、outputs、scope、failure behavior 和 oracles。

### 闭环 D：技能提示词、就绪命令与文档收口

- 将 `SKILL.md` 的 Planning kernel 扩展为本报告第 10 节流程，并路由到独立 planning-author reference。
- 更新 Designer／Worker／Reviewer contract，使角色分别消费 task contract、design patch 和 readiness rubric。
- 将现有 `check-plan-readiness` 完整改名为 `check-host-readiness`；新 `check-plan-readiness` 执行语义校验。
- 删除旧字段、旧帮助、旧 fixture 和旧命令，不保留 alias／runtime fallback。

**最小验收**：安装产物、模板、帮助、测试和文档只出现新代 schema 与命令；一次性脚本证明旧实现无残留后退出门禁。

完成所有闭环后再运行一次全量回归；每个闭环编辑期间只跑覆盖其契约的最窄测试，避免重复全量测试。

## 13. 改进后的 Plan 就绪定义

一份 Better Plan 只有同时满足以下条件，才可以称为“完整计划”：

- 用户授权目标和成功标准明确，范围内／外清楚；
- 关键现状有源码证据，猜测和默认值有 provenance；
- 所有高影响产品／架构／迁移决策已经解决；
- Node 按独立可验收结果拆分，而不是按文件、角色或叙事阶段拆分；
- 每个 Node 通过 transcript-zero、dependency-closure、own-oracle、ownership 与 handoff 测试；
- 每条 prerequisite 都有真实产物／数据／schema／迁移／行为 handoff，或明确 gate 理由；
- 每个 output、requirement、invariant 和 failure mode 都映射可执行 acceptance oracle；
- scope、失败、兼容、迁移／回滚、隐私／安全、性能／并发、可观测性均显式处理适用性；
- Designer 已通过原子 patch 冻结实现设计，且未越权改变用户意图；
- 并行前沿经过路径与共享可变资源冲突检查；
- 正式计划以完整 revision 呈现，用户批准绑定精确 digest；
- leaf brief 能由机器确定性编译，Worker 不依赖原对话；
- 执行 Todo 只是批准 Plan 的状态投影，不能取代或暗改 Plan。

## 14. 初轮研究建议（历史）

Better Plan 不需要模仿某一个 Agent。最合适的组合是：

- 用 **Codex** 定义计划的语义阶段和“Plan ≠ TODO”；
- 用 **Gemini CLI** 做风险自适应模板和“策略共识→正式计划”两阶段门；
- 用 **Qwen Code** 做 revision-bound 显式审批和 stale confirmation 防护；
- 用 **OpenCode／Cline** 的分层机制设计提示词、工具权限与运行时守卫，并修正其各自的覆盖／一致性缺口；
- 用 **Goose／Aider** 的“不继承原对话”Executor 检验 Node 是否自包含；
- 用 **Roo Code／Plandex** 定义单结果、可独立执行、可解析、显式修订的任务协议，并由 Better Plan 自己硬化完成项冻结；
- 用 **AutoGen** 管理事实、未知、假设、停滞根因与重规划；
- 用 **SWE-agent** 强化每 Node 的复现—变更—复验和最小修改边界；
- 最后保留 Better Plan 自己更强的 DAG、所有权、Designer／Worker／Reviewer、receipt 和 regression 控制面。

这轮研究确立了“计划必须能证明任务独立、边界完整、可验收”的方向，但角色次数、问题交互与修复闭环仍需收敛；最终选择见下节。

## 15. 当时采用的 Better Plan v2 协议（历史）

讨论后的关键判断是：完整计划不能只补字段，还必须减少执行期重新决策的机会。Better Plan v2 因此采用“集中决策—一次设计—精确授权—持续执行—一次复核”的单向协议。

```mermaid
flowchart LR
    A["仓库事实与现有契约"] --> B["一次 Decision Dossier"]
    B --> C["Task 初稿"]
    C --> D["一次可写 Designer"]
    D --> E["语义与宿主就绪门"]
    E --> F["revision seal + authorization"]
    F --> G["连续 Task 波次与 continuation"]
    G --> H["一次可写 Reviewer 或 Visual Reviewer"]
    H --> I["completed 或 blocked"]
```

### 15.1 集中决策，而不是连续追问

native main 先探索仓库，只把无法发现且会改变交付结果的事项放进一次 `Decision Dossier`。一个 Dossier 最多十个 `DecisionSet`；每个集合提供二至四个互斥决策包，一个选择同时冻结范围、兼容、实现偏好、风险、验收和回退。所有集合在同一轮呈现；未显式选择的集合采用已经展示的默认包。解析后写入 `Decisions.md` 和 canonical `Plan.json`，不得开启第二轮澄清。

这吸收了 Codex 的“事实与偏好分类”、Goose 的“一次给出全部问题”和 Gemini CLI 的“先对齐策略”，但比这些自由文本流程多了运行时上限、完整包结构与一次呈现计数。

### 15.2 Designer 只运行一次，并直接拥有 Plan

Designer 不再返回 typed patch，也不再是只读顾问。它在一个完整会话中直接编辑 `Plan.json`，可以增删、拆并、重排 Task／Gate，修改依赖、所有权、接口、schema、算法、数据流、状态、并发、风险与验收。它必须在同一会话自检、渲染和修正；运行时拒绝第二个 Designer session。

自由度的边界不是限制设计手段，而是守住授权核心：用户目标、已选决策包、全局 in／out scope、风险与不可逆权限不能被改写。系统在会话前后计算 immutable intent digest；机械格式问题由 native main 按确定性规则修复，不再重派 Designer 或询问用户。

### 15.3 Reviewer 只运行一次，并直接修复交付

所有 Task 到达终态后，代码交付选择 Reviewer；包含真实 UI／浏览器验收的交付改选 Visual Reviewer，二者互斥。Reviewer 获得计划授权范围内的完整写权限，能够跨原 Worker ownership 修复代码、测试、文档、配置和生成产物，并在同一会话持续运行 focused checks 与唯一一次完整回归。失败时继续在本会话修复复验，不创建 Repair Task，也不派发第二次 Reviewer。

若外部系统、凭据或新增权限构成硬阻塞，Reviewer 在同一会话核实证据并把交付收束为 `blocked`；这不是中途向用户求助，也不会把未完成状态伪装成成功。

### 15.4 授权后不中断

seal 将 semantic digest、renderer bundle digest 和 revision 绑定在一起。用户批准后才创建 `Checkpoints.json`。此后任何角色都不得调用用户提问机制，决策顺序固定为：已选包、授权目标与 scope、仓库公开契约、最安全可逆兼容方案、最简单充分实现。

新事实只允许修改尚未开始的 Task。continuation revision 必须保留所有已开始 Task 的完整契约和证据，并通过 authority diff：不得扩大目标、scope、用户决定、关键风险或不可逆权限。合法 revision 自动继承原授权；越界操作只记为 `blocked_by_authority`，外部不可用只记为 `blocked_by_environment`，独立安全分支继续执行。

## 16. v2 的 canonical 数据与独立 Task 定义

五个状态文件各自只有一个职责：

| 文件 | 职责 |
|---|---|
| `Capabilities.json` | 仓库能力事实 |
| `Manifest.json` | Delivery Plan 索引与 capability 绑定 |
| `Plan.json` | 意图、决策、需求、架构、Task、Gate、风险和验收的语义真源 |
| `PlanBundle.json` | renderer 版本、Markdown 映射、文档 hash 与 bundle digest |
| `Checkpoints.json` | 授权后的派发、状态、证据、视觉验证和回归收据 |

全部文件使用精确 `better-plan.*/v2` schema；v1 顶层数组、Node 生命周期、Designer patch、rewire、repair-plan 和兼容别名直接拒绝。

一个 v2 Task 必须冻结：稳定 UUID／`TASK-*`；单一 closure 与可观察 outcome；in／out scope；读写所有权和共享资源；唯一 prerequisites 图；`OUT-*` 生产者保证与 consumer input；接口、schema、数据流、算法／数据结构、状态、并发、错误和恢复；invariant、failure mode、风险引用；以及 `AC-*` Given／When／Then、oracle、evidence contract 和 focused regression。

因此 Task 的独立性由六个可判定条件组成：

1. transcript-zero：leaf brief 不依赖原对话；
2. dependency closure：每个输入来自已声明前提或上游 output；
3. single outcome：只交付一个可以独立接受的结果；
4. own oracle：输出、需求、不变量和失败模式均有本 Task 验收；
5. ownership safety：路径与共享资源不和可并行 Task 冲突；
6. recovery completeness：失败、重试、回滚或补偿已经冻结。

Gate 只表达人工证据、里程碑和最终验收，不再伪装成实施 Task；Design、approval 和 final review 也不再是 Node。

## 17. 提示词与运行时保证的责任分界

本次调研最重要的证据纪律，是区分“提示词希望 Agent 做什么”和“运行时实际拒绝什么”。v2 对关键原则采用双层或三层保证：

| 原则 | 提示词／文档 | 运行时保证 |
|---|---|---|
| 一次问题集 | 要求先探索再集中提问 | `presented_count` 只能为 0 或 1，集合数不超过 10 |
| 一次 Designer | 要求同会话自检和直接改 Plan | session count 只能为 1；第二次 open 拒绝；intent diff 拒绝越权 |
| 完整 Task | 提供 authoring rubric | schema、coverage、DAG、handoff、collision 和 readiness 校验 |
| revision 授权 | 说明 continuation 决策顺序 | digest／revision／started Task freeze／authority diff |
| 不中断执行 | 所有角色提示词禁止提问 | 执行协议没有问题命令；阻塞只进入显式终态并继续其它前沿 |
| 一次 Reviewer | 要求本会话直接修复与完整回归 | Reviewer 与 Visual Reviewer 互斥；第二次 open 拒绝；回归失败保持原 session |

这种分层吸收了 Cline 的提示词、能力与 command guard 思想，也避开 OpenCode 默认权限与提示词不一致、Continue shell／MCP 权限缺口、Crush 和 Roo 仅在工具说明中描述状态约束等问题。

## 18. 最终结论

Better Plan 最适合的方向不是复制某一个 Agent，而是组合它们最可靠的部分：Codex 的正式 Plan／TODO 分离，Gemini CLI 的风险自适应，Qwen Code 的 revision 审批，Goose／Aider 的无原对话交接，Roo／Plandex 的单结果任务，AutoGen 的事实账本与重规划根因，SWE-agent 的复现—变更—复验，以及 Better Plan 自己更强的 DAG、ownership、receipt、视觉证据和回归控制面。

v2 的最终定义是：**先用一次集中决策和一次完整设计，把每个 Task 编译成边界封闭、依赖明确、可独立验收的执行单元；批准后不再把设计责任退回用户，持续执行到一次最终 Reviewer 给出 completed 或有证据的 blocked。**
