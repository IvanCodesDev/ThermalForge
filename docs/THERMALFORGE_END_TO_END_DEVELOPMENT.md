# ThermalForge 全链路开发文档

状态：执行基线  
版本：1.0  
日期：2026-07-11  
适用范围：`thermalforge-studio` 前端、`thermalforge-api` 后端、Hermes Agent、图像生成与 Hyper3D Rodin

## 1. 文档目标

本文档把 ThermalForge 从当前 Phase 0 前端演示骨架，推进到真实可用的工程设计 Agent。

最终必须跑通以下完整链路：

> 工程文档与设计描述 → 文档解析 → LLM 约束理解 → 热设计计算与方案筛选 → 概念结构图 → 第二轮 LLM 优化 → 一致多视图 → 质量门禁 → Hyper3D Rodin → GLB 归一化与装配 → 中央 3D 检视 → 爆炸拆解 → 部件说明与报告

“跑通”必须同时满足：

- 每一阶段使用真实输入和真实产物，不能用定时 Mock 冒充。
- 每一阶段产物可保存、追溯、重试和恢复。
- 外部服务失败时只重试失败阶段，不重跑全部流程。
- LLM 输出必须通过结构化 Schema 和确定性规则校验。
- 图像和 3D 产物必须通过质量门禁后才能进入下一阶段。
- 页面刷新后能从服务端任务状态恢复。
- 最终模型可旋转、缩放、爆炸和选择部件。
- 最终报告能说明来源、假设、风险和未验证项。

## 2. 当前真实基线

### 已完成

- [x] 极简 Agent 单页入口。
- [x] 中央 React Three Fiber 3D 场景。
- [x] 程序化关节基座、导热界面和热增强外壳。
- [x] 爆炸、合并、部件选择和设计说明。
- [x] 最近两条对话与完整历史抽屉。
- [x] Mock 阶段状态机、取消和本地恢复。
- [x] 前端测试、Lint 和生产构建。
- [x] FastAPI、持久化任务状态机、SSE、ARQ、ArtifactStore 和 OpenAPI 契约。
- [x] 工程文件流式上传、内容校验、解析、OCR 与可追溯 DocumentBundle。
- [x] EngineeringBrief Schema、官方 Anthropic SDK 适配器、来源校验和补充问答闭环。
- [x] 本地无 Redis 模式使用进程内队列执行与 ARQ 相同的 `PipelineRunner`，上传后可继续推进。
- [x] OpenAI-compatible 结构化输出适配器，可通过环境变量配置服务地址、模型和密钥。
- [x] Agent 完成态加载工程摘要、热分析、热设计、模型清单，并展示设计依据与脱敏输出。
- [x] 中央模型支持整体/分件切换、自动旋转、线框、节点选择和有清单依据的爆炸偏移。
- [x] 当前可运行集成使用受控 GLB 参考资产完成 `ready` 状态，资产按任务复制、校验并追溯。

### 尚未完成

- [ ] 使用项目级 Anthropic 凭据完成真实 LLM 调用与结构化约束抽取评测。
- [ ] 新 Agent 链路调用现有热分析引擎。
- [ ] 概念图和多视图真实生成。
- [ ] 多视图一致性检查。
- [ ] Hyper3D Rodin 提交、轮询、下载和 GLB 校验。
- [ ] Hermes Agent 工具编排。
- [ ] 真实 GLB 与预建关节基座装配。
- [ ] 端到端浏览器测试、监控、部署和回滚。

当前可运行链路已由服务端任务状态与 SSE 驱动；`src/agent/mockPipeline.ts` 只保留前端阶段展示映射，
不再负责定时推进。当前 `ready` 阶段使用仓库内受控 GLB 参考资产完成模型检视，这些资产会明确标记为
概念参考网格，不等同于根据本次输入生成的可制造 CAD。真实概念图、多视图生成、Hyper3D Rodin 与
制造级 CAD 仍属于后续阶段，不能在界面或验收报告中冒充已经完成。

## 3. 总体技术架构

### 3.1 前端

继续使用：

- React 19
- TypeScript 6
- Vite 8
- React Three Fiber 9
- Drei
- Vitest + Testing Library

前端只负责：

- 文件和文本输入。
- 展示服务端任务状态。
- 回答 Agent 的补充问题。
- 展示图片、3D 模型和设计说明。
- 触发取消、重试、重新生成和导出。

前端不得持有 LLM、图像模型或 Hyper3D API Key。

### 3.2 后端

新增 `thermalforge-api`，采用：

- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy + Alembic
- Redis + ARQ 后台任务
- 本地开发使用 SQLite 与文件系统
- 联调和生产使用 PostgreSQL 与 S3 兼容对象存储
- Pytest、Ruff、Mypy

选择 Python 的原因：

- Hermes Agent 与文档、AI、几何处理生态更自然。
- 避免额外维护 Node 编排服务与 Python Agent 双后端。
- FastAPI 的 OpenAPI 可生成前端类型，减少契约漂移。

### 3.3 Agent

Hermes 不直接替代确定性工作流。

系统采用“有边界的 Agent”：

- 代码状态机决定阶段顺序和质量门禁。
- Hermes 负责选择策略、调用工具、提出补充问题和决定是否重试。
- Hermes 不允许跳过输入校验、多视图质检或 GLB 校验。
- 所有工具输入输出都使用 Pydantic Schema。
- 每次运行设置工具调用上限、总超时和成本预算。

### 3.4 数据与产物

结构化数据进入数据库：

- 项目
- 任务
- 阶段运行记录
- 工程摘要
- 热设计方案
- 外部任务 ID
- Prompt 版本
- 产物元数据
- 错误与重试记录

大文件进入对象存储：

- 原始工程文档
- 解析文本
- 概念图
- 多视图图片
- GLB
- 缩略图
- 报告

## 4. 目录规划

### 前端

```text
thermalforge-studio/
  src/
    api/
      client.ts
      generated.ts
      taskEvents.ts
    agent/
      AgentExperience.tsx
      agentReducer.ts
      serverEventReducer.ts
    artifacts/
      ImageGallery.tsx
      ArtifactPreview.tsx
    model/
      ModelStage.tsx
      JointAssembly.tsx
      GeneratedShell.tsx
      modelNormalization.ts
    test/
      handlers.ts
```

### 后端

```text
thermalforge-api/
  pyproject.toml
  alembic.ini
  app/
    main.py
    config.py
    api/
      projects.py
      tasks.py
      documents.py
      artifacts.py
      events.py
    domain/
      enums.py
      schemas.py
      errors.py
    models/
      project.py
      task.py
      stage_run.py
      artifact.py
    repositories/
      projects.py
      tasks.py
      artifacts.py
    services/
      documents/
      llm/
      thermal/
      images/
      multiview/
      hyper3d/
      geometry/
      reports/
    agent/
      hermes_runtime.py
      tools.py
      policy.py
    workers/
      queue.py
      pipeline.py
    observability/
      logging.py
      metrics.py
      tracing.py
  tests/
    unit/
    contract/
    integration/
    live/
```

## 5. 核心状态机

服务端任务状态固定为：

```text
created
uploaded
parsing
awaiting_input
briefing
thermal_analysis
concept_imaging
multiview_imaging
multiview_review
modeling
model_review
ready
failed
cancelled
```

状态规则：

- 只有服务端可以推进阶段。
- 前端只能创建、补充输入、取消、重试和确认产物。
- 每个阶段保存 `started_at`、`finished_at`、`attempt`、`input_artifact_ids`、`output_artifact_ids` 和 `error_code`。
- 阶段完成后产物不可原地覆盖；重新生成必须产生新版本。
- 写操作必须携带幂等键。
- 已完成阶段默认复用，除非上游输入发生变化。

## 6. 核心数据契约

### EngineeringBrief

必须包含：

- `hardware_type`
- `joint_type`
- `coordinate_system`
- `dimensions_mm`
- `mounting_envelope_mm`
- `heat_sources`
- `ambient_conditions`
- `materials`
- `forbidden_zones`
- `structural_constraints`
- `thermal_goals`
- `weight_limit_percent`
- `manufacturing_constraints`
- `assumptions`
- `missing_fields`
- `source_references`

每个热源至少包含：

- 名称
- 功率或损耗
- 位置
- 工作占空比
- 允许温度
- 来源页码或用户输入来源

### ThermalDesignSpec

必须包含：

- 推荐方案 ID 和名称
- 基座与热增强外壳边界
- 传热路径
- 材料
- 厚度与安装包络
- 散热结构类型与数量
- 安装锚点
- 预计增重
- 估算温降
- 干涉风险
- 制造建议
- 多视图一致性锚点
- 图像 Prompt
- 不确定性和人工复核项

### ArtifactManifest

所有图片和模型都必须包含：

- `artifact_id`
- `task_id`
- `stage`
- `kind`
- `version`
- `mime_type`
- `sha256`
- `storage_uri`
- `provider`
- `provider_model`
- `provider_task_id`
- `prompt_version`
- `created_at`
- `expires_at`
- `quality_status`

### AgentEvent

SSE 事件统一为：

- `task.started`
- `stage.started`
- `stage.progress`
- `stage.completed`
- `stage.failed`
- `agent.question`
- `artifact.created`
- `task.completed`
- `task.cancelled`

事件必须带递增序号，前端重连时通过 `Last-Event-ID` 补齐缺失事件。

## 7. Phase 0：前端体验骨架

状态：自动化浏览器验收已完成，真实中端设备性能测量在发布前补充。

### 任务

- [x] 用单页 Agent 体验替换七步入口。
- [x] 实现最近两条对话和完整历史抽屉。
- [x] 实现 Mock 阶段状态机。
- [x] 实现本地状态恢复。
- [x] 实现程序化关节基座和热增强外壳。
- [x] 实现旋转、缩放、爆炸、合并和部件选择。
- [x] 实现部件设计说明。
- [x] 拆分 3D 代码包，避免阻塞主界面。
- [x] 通过前端测试、Lint 和构建。
- [x] 使用 Chromium 验证 375px、768px、1440px，无横向溢出。
- [x] 验证核心键盘路径、无障碍名称和减少动画模式。
- [x] 在 4 倍 CPU 限速下完成 WebGL 60 帧响应性基线。
- [ ] 在真实中端设备记录 3D 帧率、首次渲染和显存占用。

### 交付物

- `thermalforge-studio/src/agent/`
- `thermalforge-studio/src/model/`
- `thermalforge-studio/src/styles/agent.css`

### 验收标准

- 中央 3D 是页面最大视觉元素。
- 默认只显示最近两条消息。
- 不出现顶部多步骤导航或永久侧栏。
- 模型交互不依赖隐藏手势。
- 前端单元测试、Lint、构建通过。
- 浏览器级待办完成前，Phase 0 不标记为“视觉验收完成”。

## 8. Phase 1：后端基础与任务骨架

依赖：Phase 0。

### 任务

- [x] 创建 `thermalforge-api/pyproject.toml` 并锁定 Python 版本和依赖。
- [x] 创建 FastAPI 应用、配置加载和 `/health/live`、`/health/ready`。
- [x] 建立统一错误结构：`code`、`message`、`stage`、`retryable`、`trace_id`。
- [x] 建立 Project、Task、StageRun、Artifact 数据模型。
- [x] 创建 Alembic 初始迁移并验证升级、回滚。
- [x] 实现 SQLite 开发配置和 PostgreSQL 部署配置。
- [x] 定义 ArtifactStore 接口。
- [x] 实现本地文件系统 ArtifactStore。
- [x] 实现 S3 兼容 ArtifactStore。
- [x] 创建 Redis + ARQ 队列和 Worker 启动入口。
- [x] 实现任务状态机和非法状态转换保护。
- [x] 实现幂等键与重复提交去重。
- [x] 实现任务取消标记和 Worker 协作取消。
- [x] 实现 SSE 事件存储、发送和断线续传。
- [x] 实现 OpenAPI 并生成前端 TypeScript 类型与 SDK。
- [x] 添加 Docker Compose：API、Worker、Redis、PostgreSQL、LocalStack S3。
- [x] 添加数据库、队列、对象存储的健康检查。
- [x] 为仓库层、状态机、SSE 重连和 Worker 写测试。

对象存储说明：2026-07-11 查证 MinIO 社区仓库已归档且不再持续发布官方预编译镜像，因此本地编排改用固定版本的 LocalStack S3；业务层只依赖标准 S3 ArtifactStore 接口，部署时仍可替换为任意 S3 兼容服务。

### API

- `POST /v1/projects`
- `POST /v1/projects/{project_id}/tasks`
- `GET /v1/tasks/{task_id}`
- `POST /v1/tasks/{task_id}/cancel`
- `POST /v1/tasks/{task_id}/retry`
- `GET /v1/tasks/{task_id}/events`
- `GET /v1/tasks/{task_id}/artifacts`

### 验收标准

- [x] 创建任务后 Worker 能接收并推进一个无外部依赖的测试阶段。
- [x] 服务重启后任务和阶段记录仍存在。
- [x] 同一幂等键不会生成两个任务。
- [x] SSE 断线重连不会丢事件或重复应用事件。
- [ ] API、Worker、Redis、数据库和对象存储可通过 Docker Compose 一键启动（当前机器未安装 Docker，配置已完成静态解析，运行验收 NOT RUN）。

## 9. Phase 2：工程文档上传与解析

依赖：Phase 1。

### 任务

- [x] 实现分片或流式上传，避免把大文件一次性读入内存。
- [x] 支持 PDF、DOCX、TXT、Markdown、PNG、JPEG、WebP。
- [x] 使用扩展名、MIME 和文件魔数三重校验。
- [x] 单文件默认限制 20MB，并将限制配置化。
- [x] 计算 SHA-256，复用同任务内重复文件。
- [x] 拒绝可执行文件、宏文档和压缩炸弹。
- [x] 保存原始文件为不可变 Artifact。
- [x] 解析文本型 PDF。
- [x] 识别扫描 PDF 并进入 OCR 路径。
- [x] 解析 DOCX 段落、表格、标题和内嵌图片。
- [x] 解析 TXT 与 Markdown，并保留标题层级。
- [x] 对图片执行 RapidOCR 和基础尺寸识别。
- [x] 统一文本编码、换行、空白和页码。
- [x] 生成带页码和章节引用的 DocumentChunk。
- [x] 将文档内容明确标记为不可信数据，不能把其中指令提升为系统指令。
- [x] 生成 DocumentBundle：文本、表格、图片、元数据、解析警告。
- [ ] 前端接入真实上传进度和解析状态（统一在 Phase 10 替换 Mock 流水线时接入）。
- [x] 添加正常、空文件、加密 PDF、损坏 DOCX、扫描 PDF、超限文件测试。

### 验收标准

- [x] 每种支持格式至少有一个真实格式测试样本。
- [x] 解析结果能追溯到文件、页码和章节。
- [x] 加密、损坏或不支持的文件返回明确恢复方法。
- [x] 原始文件不进入应用日志。
- [x] 同一文件重复上传不会重复占用存储。

## 10. Phase 3：LLM 工程约束理解

依赖：Phase 2。

### 任务

- [x] 定义 `LLMProvider` 接口，业务代码不直接依赖具体厂商。
- [x] 使用 Anthropic 官方 Python SDK，不使用兼容层伪装其他 API。
- [x] 建立 `EngineeringBrief` Pydantic Schema。
- [x] 建立版本化系统 Prompt 和提取 Prompt。
- [x] 将文档片段、用户描述和来源信息分区传入模型。
- [x] 要求模型输出严格结构化结果。
- [x] 对结构化结果执行 Pydantic 二次校验。
- [x] 将尺寸统一为毫米、质量统一为克、功率统一为瓦、温度统一为摄氏度。
- [x] 对大整数 ID 保持字符串类型。
- [x] 对每个关键数值字段保存来源 ID、页码和原文引用。
- [x] 校验引用必须真实存在于文档、用户描述或补充回答中。
- [x] 缺失关键字段时只生成一个优先级最高的补充问题。
- [x] 实现 `awaiting_input` 状态和用户回答接口。
- [x] 合并用户回答并重新验证 EngineeringBrief。
- [x] 对矛盾约束和超范围值进行阻断或追问。
- [x] 使用官方 SDK 的超时、限流和退避重试，并统一映射 Provider 错误。
- [x] 保存 Prompt 版本、模型标识、Token 用量和延迟，不记录敏感原文。
- [x] 使用固定工程样本建立回归测试集和确定性本地 Fixture。
- [ ] 对结构化输出失败、截断、拒答和空响应写测试。

验证说明：官方 Claude 调用形状已通过 SDK Mock 契约测试；当前没有项目级 Anthropic 凭据，真实模型 E2E 与候选模型准确率评测均为 NOT RUN，不能据此宣称生产模型已经选定。

### 模型选择任务

- [ ] 使用同一组工程文档比较候选 LLM。
- [ ] 比较字段正确率、引用正确率、结构化输出稳定性、延迟和成本。
- [ ] 将测评结果写入 `docs/evaluations/llm-engineering-brief.md`。
- [ ] 根据测评选择首个生产 Provider，并保留适配器边界。

### 验收标准

- [ ] 关键字段准确率达到预设门禁（待真实模型评测）。
- [x] 每个关键字段都有来源或明确标注为用户补充。
- [x] 缺失字段不会被本地校验器静默补造。
- [x] 相同输入在确定性本地 Fixture 下结构化字段保持稳定。
- [x] 用户补充后可从 `awaiting_input` 继续，而不是重建任务。

## 11. Phase 4：热分析与设计方案生成

依赖：Phase 3。

### 任务

- [ ] 固化现有 TypeScript `thermalEngine` 的输入输出样本。
- [ ] 建立跨语言 Golden Fixtures。
- [ ] 将热分析逻辑迁移为后端权威 `ThermalAnalysisService`。
- [ ] 对迁移结果与 TypeScript 引擎做数值容差比对。
- [ ] 定义 `ThermalAnalysisRequest` 和 `ThermalAnalysisResult`。
- [ ] 校验功率、环境温度、材料、热阻和运行时间边界。
- [ ] 根据 EngineeringBrief 计算基线温升。
- [ ] 将现有 `SOLUTIONS` 迁移为后端版本化方案目录。
- [ ] 用确定性规则过滤违反安装、重量和制造约束的方案。
- [ ] 为候选方案计算温降、增重、成本和风险分数。
- [ ] 只允许 LLM 解释和排序有效候选，不允许 LLM 替代数值计算。
- [ ] 执行第二轮 LLM 设计优化，输出 `ThermalDesignSpec`。
- [ ] 生成传热路径、材料、几何锚点和制造建议。
- [ ] 将所有假设和未验证项写入设计方案。
- [ ] 高风险或数据不足方案进入人工确认。
- [ ] 为边界、空值、极端功率和冲突约束写测试。
- [ ] 为跨语言结果一致性写回归测试。

### 验收标准

- 后端热分析与现有 Golden Fixtures 在允许容差内一致。
- 不合规方案不会进入图像生成阶段。
- LLM 解释中的数值必须来自 ThermalAnalysisResult。
- ThermalDesignSpec 能直接驱动后续 Prompt 和部件说明。
- 每个风险都有来源、影响和建议动作。

## 12. Phase 5：概念结构图生成

依赖：Phase 4。

### 任务

- [ ] 定义 `ImageProvider` 接口。
- [ ] 建立 10 组代表性关节和热设计基准 Prompt。
- [ ] 对候选图像模型进行一致性、结构表达、分辨率、延迟、成本和许可评测。
- [ ] 将评测结果写入 `docs/evaluations/image-provider.md`。
- [ ] 选择首个生产图像 Provider。
- [ ] 构建设计概念 Prompt 模板。
- [ ] Prompt 明确只生成热增强外壳，不融合完整关节。
- [ ] Prompt 固定材料、安装区域、散热结构、孔位和禁止区域。
- [ ] 使用中性纯色或透明背景。
- [ ] 保存 Prompt、负向约束、随机种子、模型和版本。
- [ ] 保存原图、缩略图和元数据 Artifact。
- [ ] 对分辨率、透明通道、空图和安全拦截做校验。
- [ ] 为可重试错误实现有限次数重新生成。
- [ ] 在前端展示概念图并允许用户确认或重新生成。
- [ ] 使用 Mock Provider 写契约测试。
- [ ] 使用少量真实 API 调用写独立 Live 测试。

### 验收标准

- 概念图能清楚表现独立热增强外壳。
- 图像不包含文字、水印、额外关节或悬浮零件。
- 相同设计方案可通过 ArtifactManifest 完整复现调用条件。
- 失败不会删除已完成的 EngineeringBrief 和 ThermalDesignSpec。

## 13. Phase 6：三视图与多视图质量门禁

依赖：Phase 5。

### 任务

- [ ] 定义统一坐标系、正面方向、旋转轴和装配原点。
- [ ] 从 ThermalDesignSpec 生成前、左、后、右四视图 Prompt。
- [ ] 需要时增加顶视图。
- [ ] 使用同一参考图、种子和几何锚点生成所有视图。
- [ ] 固定近似正交镜头、比例、背景和光照。
- [ ] 在 Prompt 中固定孔位、鳍片数量、轮廓拐点和接口边界。
- [ ] 生成 `MultiviewManifest`，记录视图顺序和相机方向。
- [ ] 执行图片尺寸、背景、主体占比和透明通道检查。
- [ ] 使用视觉模型检查跨视图身份一致性。
- [ ] 检查孔位数量、鳍片数量、轮廓和左右关系。
- [ ] 将质量项转换为 0～100 分。
- [ ] 低于门禁时自动重新生成失败视图。
- [ ] 限制自动重试次数，超限后请求人工确认。
- [ ] 前端提供多视图检查和单视图重生成。
- [ ] 通过后将视图状态设为 `approved`。
- [ ] 未通过的视图禁止提交 Hyper3D。
- [ ] 为视图顺序错误、镜像、缺图和不一致写测试。

### 验收标准

- 所有视图属于同一外壳设计。
- 关键孔位、散热结构数量和轮廓跨视图一致。
- 视图方向和顺序具有机器可读定义。
- 质量门禁结果可解释，不只有一个总分。
- Hyper3D 只接收已批准的 MultiviewManifest。

## 14. Phase 7：Hyper3D Rodin 生成与模型归一化

依赖：Phase 6。

### 任务

- [ ] 在开发开始时重新核对 Hyper3D 官方 API、认证、输入限制和输出格式。
- [ ] 固定经过验证的 API 版本。
- [ ] 定义 `Hyper3DProvider` 接口。
- [ ] 实现多视图上传和任务提交。
- [ ] 将外部任务 ID 保存到 StageRun。
- [ ] 使用幂等键防止重复扣费和重复建模。
- [ ] 实现状态轮询、指数退避和最大等待时间。
- [ ] 如 Provider 支持回调，校验签名后接收回调。
- [ ] 实现取消能力；不支持取消时标记“停止跟踪”。
- [ ] 下载 GLB 到自有对象存储，不能长期依赖临时 URL。
- [ ] 校验 HTTP 状态、Content-Type、文件大小、SHA-256 和 GLB 文件头。
- [ ] 使用几何工具读取包围盒、顶点数、材质和动画信息。
- [ ] 将模型轴向、单位、原点和缩放归一化。
- [ ] 将外壳缩放到 ThermalDesignSpec 的安装包络。
- [ ] 计算超包络、空网格、破面和异常面数。
- [ ] 必要时执行网格简化和法线修复。
- [ ] 生成 Web 预览缩略图。
- [ ] 保存原始 GLB 和归一化 GLB 两个版本。
- [ ] 失败时保留多视图，允许只重试建模。
- [ ] 使用本地 Mock Server 写提交、轮询、超时和下载测试。
- [ ] 使用受控真实任务写 Live 集成测试。

### 验收标准

- 真实多视图能生成可加载 GLB。
- Provider 超时或失败不会让任务永久卡在 `modeling`。
- 重试不会重复创建多个付费任务。
- GLB 在进入前端前已通过格式、包围盒和网格检查。
- 原始产物和处理后产物均可追溯。

## 15. Phase 8：真实 3D 装配与交互

依赖：Phase 7。

### 任务

- [ ] 将程序化基座替换为受版本控制的标准基座 GLB，或明确保留程序化基座。
- [ ] 定义基座装配锚点和关节轴向。
- [ ] 新增 `GeneratedShell.tsx` 加载归一化 GLB。
- [ ] 使用 Artifact URL 加载真实热增强外壳。
- [ ] 对外壳应用服务端提供的装配变换。
- [ ] 在浏览器再次校验包围盒，防止异常模型破坏相机。
- [ ] 将基座、导热界面和外壳保持为独立 Scene Node。
- [ ] 保留爆炸、合并、部件选择和说明浮层。
- [ ] 部件说明改为读取真实 ThermalDesignSpec。
- [ ] 选中部件时显示材料、传热路径、温降、增重和风险。
- [ ] 为加载过程显示低模或轮廓占位。
- [ ] GLB 失败时降级显示多视图图集。
- [ ] 对超大模型执行 LOD、懒加载和资源释放。
- [ ] 评估 Draco/Meshopt 与 KTX2 压缩。
- [ ] 卸载模型时释放 Geometry、Material 和 Texture。
- [ ] 为爆炸状态、选择状态和错误回退写组件测试。
- [ ] 使用 Playwright 验证真实 WebGL 点击和截图。
- [ ] 在中端设备验证交互帧率和内存。

### 验收标准

- 前端展示的是 Hyper3D 真实产物，而非程序化外壳。
- 基座与外壳装配方向正确且不明显穿模。
- 点击整体可以爆炸，点击外壳可以展示真实方案信息。
- 模型加载失败时用户仍能查看图片和设计说明。
- 连续切换多个模型不会持续增加显存。

## 16. Phase 9：Hermes Agent 编排

依赖：Phase 2～8 的工具都可独立运行。

Hermes 放在工具稳定之后接入，避免用 Agent 掩盖尚未验证的服务。

### 工具清单

- `parse_engineering_document`
- `build_engineering_brief`
- `request_missing_input`
- `run_thermal_analysis`
- `select_thermal_strategy`
- `build_thermal_design_spec`
- `generate_concept_image`
- `build_multiview_prompt`
- `generate_multiview_images`
- `review_multiview_consistency`
- `submit_hyper3d_job`
- `poll_hyper3d_job`
- `normalize_model_artifact`
- `build_design_explanation`
- `publish_design_report`

### 任务

- [ ] 在接入时核对并锁定 Hermes 上游版本或提交。
- [ ] 创建 `hermes_runtime.py`，隔离框架 API。
- [ ] 为每个工具定义严格 Pydantic 输入输出。
- [ ] 禁止工具接收未校验的自由 JSON。
- [ ] 建立 Agent 系统策略：阶段顺序、禁止事项和质量门禁。
- [ ] 将工程文档内容作为不可信数据传入。
- [ ] 限制单次运行最大工具调用次数。
- [ ] 限制总运行时间、单工具超时和外部调用重试次数。
- [ ] 为昂贵工具设置幂等键和成本门禁。
- [ ] 在缺失字段时调用补充问题工具并暂停任务。
- [ ] 将每个工具调用和结果保存到 StageRun。
- [ ] 支持 Worker 中断后从最后完成阶段恢复。
- [ ] 不把模型内部推理发送给前端。
- [ ] 将工具事件转换为用户可理解的 SSE 阶段事件。
- [ ] 为 Prompt 注入、跳过门禁和重复工具调用设置策略测试。
- [ ] 使用全 Mock 工具跑通 Agent 集成测试。
- [ ] 使用真实文档和受控 Provider 跑通一次 Live 链路。

### 验收标准

- Hermes 只能调用白名单工具。
- Hermes 不能跳过多视图或 GLB 质量门禁。
- 中断后恢复不会重复执行已成功的付费阶段。
- Agent 提问、重试和失败信息能正确映射到前端。
- 相同任务的完整工具轨迹可审计。

## 17. Phase 10：前端接入真实后端

依赖：Phase 1～9。

### 任务

- [ ] 从 OpenAPI 生成 `src/api/generated.ts`。
- [ ] 创建统一 API Client、超时和错误映射。
- [ ] 实现真实文件上传和进度。
- [ ] 创建服务端任务并保存 task ID。
- [ ] 用 SSE 替换 `mockPipeline.ts` 定时器。
- [ ] 使用事件序号防止重复应用状态。
- [ ] 实现断线重连和 `Last-Event-ID`。
- [ ] 实现 Agent 补充问题和用户回答。
- [ ] 展示概念图、多视图和质量结果。
- [ ] 提供单阶段重试，不只提供全流程重启。
- [ ] 展示 Hyper3D 排队、建模、下载和归一化状态。
- [ ] 加载真实 GLB。
- [ ] 页面刷新后从 API 恢复任务。
- [ ] 取消操作调用服务端，不只修改本地状态。
- [ ] 将部件说明切换为真实 ThermalDesignSpec。
- [ ] 保留 Mock Provider 作为开发和测试模式，生产构建默认关闭。
- [ ] 删除生产入口对纯定时 Mock 的依赖。
- [ ] 使用 MSW 编写前端 API 与 SSE 测试。
- [ ] 使用 Playwright 编写上传、补问、生成、爆炸和恢复 E2E。

### 验收标准

- 生产模式不引用定时 Mock。
- 刷新、断网重连和浏览器重开后任务状态一致。
- 前端展示的每项结果都能关联 Artifact ID。
- 用户能在失败阶段直接重试。
- 一个真实任务可从上传推进到可交互 GLB。

## 18. Phase 11：设计说明、报告与导出

依赖：Phase 8～10。

### 任务

- [ ] 将现有 `utils/report.ts` 的有效逻辑迁移为后端报告服务。
- [ ] 生成项目摘要、输入来源和约束。
- [ ] 生成热分析基线和推荐方案。
- [ ] 嵌入概念图和多视图。
- [ ] 嵌入 GLB 链接和模型缩略图。
- [ ] 生成传热路径、材料、制造建议和风险。
- [ ] 明确区分计算结果、模型推断和人工假设。
- [ ] 列出未验证项和生产前检查清单。
- [ ] 支持 PDF、JSON 和 ZIP 设计包。
- [ ] ZIP 包含 Manifest、图片、GLB 和报告。
- [ ] 对导出文件进行 SHA-256 校验。
- [ ] 为报告字段完整性和敏感信息泄漏写测试。

### 验收标准

- 报告中的关键数据可追溯到 EngineeringBrief 或 ThermalAnalysisResult。
- 报告不把 Mock、估算或 LLM 推断写成实测结论。
- 导出包在离线环境中仍能查看图片、模型和 Manifest。
- 报告版本与任务、Prompt 和 Artifact 版本一致。

## 19. Phase 12：安全、可靠性与可观测性

该阶段要求应从 Phase 1 起持续落实，并在发布前集中验收。

### 安全任务

- [ ] 所有 API Key 只保存在服务端密钥管理中。
- [ ] `.env`、凭证和临时签名 URL 禁止提交仓库。
- [ ] 文件上传执行类型、大小、魔数和内容安全校验。
- [ ] 文档内容与 Agent 系统指令严格隔离。
- [ ] 每个项目、任务和 Artifact 执行归属校验。
- [ ] 下载使用短期签名 URL。
- [ ] 写接口使用 CSRF 或等价保护。
- [ ] 添加速率限制、并发限制和单用户成本配额。
- [ ] 日志脱敏，不记录文档全文、Prompt 全文和密钥。
- [ ] 定义文件和任务数据保留与删除策略。
- [ ] 执行依赖漏洞与密钥扫描。

### 可靠性任务

- [ ] 外部调用设置连接和响应超时。
- [ ] 仅对可恢复错误重试。
- [ ] 使用指数退避和随机抖动。
- [ ] 付费写操作实现幂等。
- [ ] 队列任务设置最大尝试次数和死信处理。
- [ ] 阶段产物写入成功后再标记阶段完成。
- [ ] 数据库与对象存储失败时保持一致状态。
- [ ] 定义外部 Provider 降级和暂停策略。
- [ ] 定期清理过期临时文件和孤立 Artifact。

### 可观测任务

- [ ] 全链路传递 trace ID。
- [ ] 输出结构化 JSON 日志。
- [ ] 记录任务成功率、阶段耗时、重试率和失败码。
- [ ] 记录 LLM Token、图像次数、Hyper3D 次数和估算成本。
- [ ] 记录队列深度、等待时间和 Worker 存活状态。
- [ ] 使用 OpenTelemetry 追踪 API、Worker 和外部调用。
- [ ] 为错误率、任务积压、成本异常和 Provider 故障配置告警。

### 验收标准

- 未授权用户不能读取其他任务或 Artifact。
- Prompt 注入测试不能改变系统工具边界。
- 同一幂等键不会重复产生付费外部任务。
- 任一失败任务可通过 trace ID 找到完整阶段时间线。
- Provider 故障不会拖垮 API 或造成无限重试。

## 20. Phase 13：测试体系与发布

依赖：全部功能阶段。

### 测试任务

- [ ] 前端单元与组件测试。
- [ ] 后端领域、解析器和状态机单元测试。
- [ ] OpenAPI 契约测试。
- [ ] Provider Adapter Mock 契约测试。
- [ ] 数据库、Redis、对象存储集成测试。
- [ ] Hermes 工具和恢复测试。
- [ ] Playwright 端到端测试。
- [ ] Live API 冒烟测试，使用独立标记和预算。
- [ ] 上传安全、越权和 Prompt 注入测试。
- [ ] 并发任务、重复提交和取消竞态测试。
- [ ] 长任务断网、Worker 重启和 API 重启恢复测试。
- [ ] GLB 大文件和低性能设备测试。

### CI 任务

- [ ] 前端执行 `npm test`。
- [ ] 前端执行 `npm run lint`。
- [ ] 前端执行 `npm run build`。
- [ ] 后端执行 `pytest`。
- [ ] 后端执行 `ruff check`。
- [ ] 后端执行 `mypy app`。
- [ ] 执行数据库迁移检查。
- [ ] 执行依赖漏洞和密钥扫描。
- [ ] 构建前后端 Docker 镜像。
- [ ] 仅在受保护环境运行 Live Provider 测试。

### 部署任务

- [ ] 创建前端多阶段 Dockerfile。
- [ ] 创建 API 和 Worker Dockerfile。
- [ ] 非 root 用户运行容器。
- [ ] 固定基础镜像版本。
- [ ] 配置开发、测试、预发和生产环境。
- [ ] 配置数据库迁移和回滚流程。
- [ ] 配置对象存储生命周期。
- [ ] 配置 Redis 持久化或可接受的任务恢复方案。
- [ ] 配置健康检查和滚动发布。
- [ ] 编写发布后冒烟脚本。
- [ ] 编写回滚步骤和数据兼容说明。

### 最终端到端验收

- [ ] 上传一份真实硬件工程 PDF。
- [ ] 系统解析内容并生成带来源的 EngineeringBrief。
- [ ] 缺失字段时 Agent 提出一个明确问题。
- [ ] 用户回答后任务继续。
- [ ] 热分析生成基线和合规方案。
- [ ] 生成概念图。
- [ ] 生成并批准一致多视图。
- [ ] Hyper3D 返回真实 GLB。
- [ ] GLB 通过校验并装配到基座。
- [ ] 前端可爆炸模型并点击外壳。
- [ ] 部件说明来自真实 ThermalDesignSpec。
- [ ] 导出报告、图片、GLB 和 Manifest。
- [ ] 任意页面刷新后任务仍可恢复。
- [ ] 失败阶段可以单独重试。
- [ ] 完整任务可通过 trace ID 审计。

只有以上全部通过，才可以声明“整个项目真实全链路跑通”。

## 21. 阶段执行顺序

推荐严格按以下顺序推进：

1. 补齐 Phase 0 浏览器验收。
2. Phase 1 后端与任务骨架。
3. Phase 2 文档解析。
4. Phase 3 LLM 工程摘要。
5. Phase 4 热分析与设计方案。
6. Phase 5 概念图。
7. Phase 6 多视图与质量门禁。
8. Phase 7 Hyper3D。
9. Phase 8 真实 3D 装配。
10. Phase 9 Hermes 编排。
11. Phase 10 前端真实接入。
12. Phase 11 报告与导出。
13. Phase 12 安全、可靠性和可观测性验收。
14. Phase 13 全链路测试与发布。

Hermes 必须在各工具单独通过测试后接入。否则 Agent 会把工具缺陷、网络错误和数据问题混在一起，难以定位。

## 22. 每阶段统一交付门禁

每个 Phase 完成前必须满足：

- 需求和数据契约已冻结。
- 正常、异常和边界测试存在。
- 测试曾先失败，再由实现修复。
- 代码通过 Lint、类型检查和构建。
- 新接口同步 OpenAPI 和前端类型。
- 外部调用有超时、错误分类和重试边界。
- 新产物可追溯并有 SHA-256。
- 日志不泄露敏感内容。
- 文档更新为代码真实状态。
- 未完成项明确保留在当前 Phase，不伪装成完成。

## 23. 首个真实闭环建议

第一条真实闭环不要一次接入所有 Provider。

按以下最小路径验证：

1. 真实 PDF 解析。
2. 真实 LLM 输出 EngineeringBrief。
3. 真实热分析和 ThermalDesignSpec。
4. 图像与 Hyper3D 暂时使用受控 Fixture。
5. 前端用 SSE 展示真实前三阶段。
6. 再逐个替换概念图、多视图和 Hyper3D Fixture。
7. 所有工具稳定后接入 Hermes。

这样每次替换一个 Mock，都能明确知道新故障来自哪一层，并且始终保持一条可运行的演示链路。
