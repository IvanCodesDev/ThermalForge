# ThermalForge 完整 Agent 系统增量 PRD

## 1. 项目信息

- **Language**：中文
- **Programming Language**：沿用现有 Python / FastAPI / Pydantic 后端架构；不在本增量中引入新的前端技术栈
- **Project Name**：`thermalforge_agent_system`
- **原始需求复述**：在不覆盖现有 `AgentPipeline`、`EngineeringState`、`ArtifactRegistry` 与 `SimulationHandoffContract` 实现的前提下，完善 ThermalForge Agent 的 Prompt、Skills、工具、最小权限、工程事实源和产物治理；把经人工确认的关节半径、材料、组件接口、热源等工程事实编译为 SpaceClaim V251 可执行协议，再交接 Fluent/Mechanical 仿真并将结果回灌。所有 LLM Agent 必须使用 `gpt-5.6-sol`。Hyper3D 产物必须始终标记为 `concept_mesh`，不得冒充可制造 CAD。

## 2. 产品目标

1. **可信工程事实源**：以版本化 `EngineeringState` 作为唯一工程事实源，使关键数值均具备单位、状态、证据、版本和人工批准记录。
2. **可审计 Agent 编排**：每次 Agent 执行必须可追溯至固定模型、版本化 Prompt、Skills、工具白名单、权限和输入工程 revision。
3. **闭环仿真交付**：从确认规格生成 SpaceClaim V251 几何交接协议，进入 Fluent/Mechanical，并以严格结果契约回灌、验收和登记产物。

## 3. 用户故事

- As a **热设计工程师**, I want 逐项审核关节半径、材料属性、热源和工况 so that 错误假设不会进入几何与仿真。
- As a **CAD 工程师**, I want 获得版本锁定、单位明确、包含接口与 Named Selection 的 SpaceClaim V251 协议 so that 可以稳定生成可复现工程几何。
- As a **仿真工程师**, I want Fluent/Mechanical 接收同一工程 revision 的材料、载荷、接触、网格和求解计划 so that 仿真输入一致且可复核。
- As a **项目审核人**, I want 查看 Agent 使用的模型、Prompt hash、Skills、工具、权限和产物 lineage so that 每个决策都可审计。
- As a **产品使用者**, I want 明确区分 Hyper3D 概念网格、工程代理几何和制造 CAD so that 不会将展示资产用于制造或工程仿真。

## 4. 增量范围与优先级

### P0 — Must have

- 所有 LLM Agent 的有效模型必须固定为 `gpt-5.6-sol`；注册时不匹配必须拒绝启动。
- 扩展现有 Agent Registry，而非建立平行体系：Prompt 必须有 `id/version/sha256`，Agent 必须声明输入/输出 schema、Skills、工具、权限、质量门和重试策略。
- `EngineeringState` 必须作为下游几何与仿真的唯一工程事实源；所有关键字段必须包含值、单位/语义、状态和证据，并通过 optimistic revision 控制。
- 人工确认关键规格、组件分件语义和材料后，才允许编译几何/仿真交接；存在 `unresolved` 或关键值非 `confirmed` 时必须阻断。
- 定义并校验 SpaceClaim V251 交接：单位、坐标系、关节内外半径/轴向长度/壁厚/轴线、分瓣及翅片参数、组件接口、材料、热源、工况、Named Selections、接触及输出路径。
- 仅允许 `engineering_proxy` 或 `manufacturing_cad` 作为仿真几何；`concept_mesh` 必须被程序性拒绝。
- Fluent/Mechanical 结果必须以 `SimulationResultContract` 回灌，核验 project、engineering revision、handoff、模型、case、收敛及验收阈值。
- 所有输入、SpaceClaim 脚本与几何、网格、日志、场数据、报告和图片必须写入 Artifact Registry，记录 hash、producer/version、input revision、provider、fidelity、URI 和 task UUID（如适用）。
- Agent 执行事件必须记录 agent/version、model、prompt id/hash、skills、tools、状态、时间和关联 revision/artifact。

### P1 — Should have

- 按 Agent 定义实施工具级最小权限；默认拒绝 `network`、`filesystem_write`、`shell`、`secrets_read`，仅执行适配器拥有必要写入或外部调用权限。
- SpaceClaim、Fluent、Mechanical 采用隔离适配器：LLM 只编译严格契约，不直接执行任意 shell、脚本或网络请求。
- 支持仿真失败、未收敛或未达阈值后的 review/revision 分支；任何修改产生新的 EngineeringState revision，不覆盖历史。
- 产物 lineage 可从结果反查 handoff、几何、EngineeringState、审批和来源证据。
- 提供人工审核摘要：变更 diff、未解决项、低置信度项、关键假设和影响范围。

### P2 — Nice to have

- Prompt/Agent 版本对照评估与质量指标面板。
- Fluent/Mechanical 多工况批处理、失败重试和断点续跑。
- Artifact Registry 对接持久化对象存储、签名 URL、保留策略和产物可视化。
- 基于回灌结果提出优化建议，但不得自动修改已批准工程事实或自动重新提交求解。

## 5. Agent 清单与职责

| Agent | 主要职责 | 输入 / 输出 | 允许工具与权限边界 |
|---|---|---|---|
| Intake Agent | 登记数据手册、STEP、图片、文本等来源，建立项目身份 | SourceAsset → 初始项目记录 | 仅来源登记/读取；无执行权限 |
| Specification Agent | 从来源抽取规格与证据，标记假设、置信度和 unresolved | 来源内容 → SpecificationExtractionResult / EngineeringState 草案 | `source_content_reader`；只读 |
| Component Analysis Agent | 提议组件分件、类别、接口、关节语义与材料映射 | EngineeringState 草案 → semantic candidates / review items | `engineering_schema_reader`；只读，不得确认 |
| Human Review Gate | 确认关键规格、分件语义、材料及其证据 | revision + reviewer decision → Approval / 新 revision | 人工身份与审计写入；不得由 LLM 代签 |
| Geometry / SpaceClaim Compiler Agent | 将已批准事实编译为 V251 严格几何参数与脚本计划 | confirmed EngineeringState → SpaceClaim handoff/script artifact | 只读事实源、写协议草案；禁止直接 shell |
| SpaceClaim V251 Adapter | 在隔离环境执行受控脚本，产出工程几何与 Named Selections | 已批准协议 → geometry/script/log artifacts | 限定文件写入与 SpaceClaim V251 调用；禁止开放式命令 |
| Hyper3D Compiler / Adapter | 生成展示用 Rodin 合约并登记结果 | engineering proxy renders → concept mesh | 外部调用仅限适配器；结果强制 `concept_mesh` |
| Simulation Planner Agent | 编译 Fluent/Mechanical 网格、求解、接触、载荷和验收计划 | approved state + geometry → SimulationHandoffContract | 工程/产物只读；禁止执行求解器 |
| Fluent Adapter | 执行 CFD 或热流体求解并收集结果 | CFD handoff → result contract + artifacts | 仅 Fluent 与限定工作区权限 |
| Mechanical Adapter | 执行热/结构 FEA 或耦合求解并收集结果 | FEA handoff → result contract + artifacts | 仅 Mechanical 与限定工作区权限 |
| Result Interpreter Agent | 解释只读结果、形成 findings，不修改原始结果 | SimulationResultContract → ValidationReport / 建议 | `simulation_result_reader`；只读 |
| Artifact Registry Service | 登记、校验和查询所有产物及 lineage | Artifact → immutable registry entry | 服务端受控写入；按 revision 校验 |

## 6. 端到端流程

1. **摄取**：登记来源资产并创建 pipeline/project；保留来源 URI 与证据定位。
2. **抽取**：Specification Agent 使用 `gpt-5.6-sol` 输出严格结构；不确定项进入 `unresolved`，不得补造。
3. **工程状态归一化**：将单位、坐标系、关节、组件、材料、接口、热源、工况写入新的 `EngineeringState revision`。
4. **人工门 A**：审核关键规格、分件语义、接口和材料；拒绝则回到新 revision，批准记录 reviewer、subject、revision、证据与时间。
5. **几何协议编译**：Geometry Agent 基于已批准 revision 生成 SpaceClaim V251 参数/脚本契约；缺少关节扩展、Named Selections 或材料属性时阻断。
6. **SpaceClaim 执行**：受控 Adapter 生成工程代理或制造 CAD、Named Selections、脚本和日志，并登记 Artifact Registry。
7. **可选展示支路**：从工程代理渲染参考图提交 Hyper3D；返回资产仅登记为 `concept_mesh`，不得进入仿真几何输入。
8. **人工门 B**：确认 SpaceClaim 几何 revision、分件、接口/接触区域、材料映射、载荷区域和求解验收阈值。
9. **仿真交接**：Simulation Planner 输出严格 handoff；按模型路由至 Fluent、Mechanical 或耦合流程。
10. **求解与回灌**：Adapter 收集 case 指标、收敛状态、网格、日志、场数据、报告和图片，生成并校验 `SimulationResultContract`。
11. **验收/迭代**：Result Interpreter 只读解释；通过则完成，失败则进入人工 review，并通过新 EngineeringState revision 迭代，禁止覆盖旧事实与产物。

## 7. 关键数据协议

### 7.1 EngineeringState（事实源）

- 身份：`project_id`、`revision`。
- 基准：单位、左右手坐标系、up axis、origin。
- 几何：关节轴线、转角范围、内/外半径、轴向长度、壳厚；组件尺寸与类别。
- 语义：组件、接口父子关系、配合类型、材料引用。
- 热设计：材料完整热/力学属性、组件热功率、环境温度、占空比和工况。
- 溯源：每个关键值包含 `status` 与非空 `evidence`；确认前不得下游编译。

### 7.2 SpaceClaim V251 / Simulation Handoff

- 固定 `provider=spaceclaim`、`api_version=V251`，并绑定 `engineering_revision`。
- 包含 joint parameters、材料全属性、热载荷、contacts、operating cases、Named Selections、mesh plan、solver plan、acceptance criteria。
- Geometry Artifact 必须记录脚本 URI、输出几何 URI、hash、fidelity 和 input revision。
- Named Selection 名称必须唯一；载荷与接触引用必须全部可解析。

### 7.3 Simulation Result

- 固定 schema/version，绑定 project、revision、handoff id、model、solver。
- 每个 case 返回 `converged`、最高温度；CFD 必须返回压降；FEA 必须返回最大等效应力和最小安全系数。
- 结果产物包含 role、URI、content hash；不得修改或覆盖原始 solver 输出。

### 7.4 Artifact Registry

- 必填：`id/role/uri/provider/fidelity/content_hash/producer/version/input_revision`。
- fidelity 语义：`source`、`engineering_proxy`、`concept_mesh`、`manufacturing_cad`、`metadata`。
- 强约束：`concept_mesh` 不得登记为 `manufacturing_cad`，也不得用于仿真 handoff。

## 8. 人工门

1. **规格门**：关节半径/长度/壁厚、单位与坐标系必须确认。
2. **语义门**：组件分件、父子关系、接口/配合类型及 Named Selection 语义必须确认。
3. **材料门**：材料牌号及热导率、比热、密度、热膨胀、弹性模量、泊松比、屈服/抗拉强度必须确认并有证据。
4. **载荷与工况门**：热源映射、功率、环境、占空比及求解验收阈值必须确认。
5. **几何/求解门**：SpaceClaim 产物、接触、网格和 solver plan 必须经工程师批准后方可提交 Fluent/Mechanical。
6. **结果门**：未收敛或未达温度、压降、安全系数阈值时，不得自动标记完成或自动修改事实源。

## 9. 非目标

- 不将 Hyper3D concept mesh 转换、包装或宣传为可制造 CAD。
- 不由 LLM 自动批准关键规格、分件语义、材料、载荷或求解计划。
- 不允许 Agent 执行任意 shell、访问任意网络、读取 secrets 或写入非隔离工作区。
- 不在本增量中替换已有 Pipeline、EngineeringState、ArtifactRegistry、Simulation Contract；仅扩展并统一其编排。
- 不承诺全自动制造级建模、自动网格质量修复或无人工监督的闭环优化。

## 10. 验收标准

- 100% 已注册 LLM Agent 的模型字段为 `gpt-5.6-sol`；其他模型注册失败。
- 100% LLM 执行记录包含 agent/version、prompt id/hash、model、skills、tools、时间、状态及输入 revision。
- 任一关键值非 `confirmed`、证据为空、存在 `unresolved` 或缺少人工 Approval 时，SpaceClaim/仿真 handoff 编译必须失败。
- 可用一份已批准 EngineeringState 生成通过 schema 校验的 SpaceClaim V251 handoff，且完整包含关节、材料、接口/接触、热源、工况与 Named Selections。
- Hyper3D concept mesh 作为 `manufacturing_cad` 登记或用于仿真几何时，系统必须拒绝。
- Fluent/Mechanical 回灌结果若 project/revision/model/case 不一致、未收敛或超验收阈值，系统必须拒绝完成并保留错误原因。
- 每个 SpaceClaim/仿真产物均可通过 Registry 追溯至 producer、版本、input revision、content hash 和来源/上游产物。
- 历史 EngineeringState revision、审批、执行事件和 Artifact 不因新一轮迭代被覆盖。
- 现有 Agent Pipeline、EngineeringState 和 Simulation Contract 测试保持通过，并新增上述模型约束、权限门、人工门和闭环路径测试。

## 11. 待确认项

1. `Settings.openai_text_model` 是否统一默认并强制配置为 `gpt-5.6-sol`，以及测试环境是否允许显式替身模型。
2. SpaceClaim V251 的实际执行形态：Windows 本机 API、Workbench/ACT、批处理服务或远程作业队列。
3. Fluent 与 Mechanical 的确切版本、许可方式、执行节点、超时/并发/重试限制。
4. `manufacturing_cad` 的签发主体和判定标准；是否只有人工 CAD 工程师可将 engineering proxy 晋级。
5. 组件接口是否需要扩展紧固件、螺纹、密封、间隙/过盈、公差及热接触参数。
6. CFD 边界条件是否还需入口温度、速度/质量流量、湍流模型、辐射和重力；Mechanical 是否需约束、载荷时序和疲劳指标。
7. Artifact Registry 的持久化后端、对象存储 URI 规范、hash 算法、访问控制和保留周期。
8. 人工审批的身份认证、角色权限、电子签名与审计合规要求。
