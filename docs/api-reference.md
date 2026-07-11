# ThermalForge 后端 API 参考

> 自动生成自 OpenAPI schema（共 **65** 个端点）。本文件由 `scripts/generate_api_reference.py` 生成，**请勿手改**；修改端点文档后重跑该脚本。

启动服务后访问 `/docs`(Swagger) 或 `/redoc` 可交互调试。

## 目录

- **system** — 服务健康与全局契约元信息。（2 个端点）
- **screening** — 结构生成 / 热路评估 / 相似度检索等核心筛选能力（需非 real 模式 is_real=False 才挂载）。（8 个端点）
- **engineering-state** — 版本化 EngineeringState 唯一事实源与 Artifact 不可变血缘登记。（7 个端点）
- **simulation-orchestration** — 仿真交接契约的编译、查询与结果验收（Fluent/Mechanical 适配器隔离）。（3 个端点）
- **simulation-development** — 仿真编排的开发期端点：登记 SpaceClaim 几何产物与仿真结果（开发模式）。（2 个端点）
- **knowledge** — 常见文档模板固化后的知识库检索：按电机类型 / 材质 / 关键字查询默认条目。（3 个端点）
- **agent-governance** — Agent 定义、Prompt 版本与 SHA256、Skill、Tool 策略等治理元数据的只读查询。（1 个端点）
- **agent-governance-development** — Agent 执行审计记录查询（开发模式）。（2 个端点）
- **agent-pipeline** — 数据手册 → Hyper3D 资产的可审计 Agent 流水线：创建、规格抽取/提议/评审、几何与 Hyper3D 登记。（8 个端点）
- **agent-pipeline-development** — Agent 流水线的开发期端点：几何登记、Hyper3D 提交/结果、验证报告（开发模式）。（4 个端点）
- **component-analysis** — 概念 3D 组件清单与工程分析，输出前端可消费的 ComponentManifest。（1 个端点）
- **external-models** — 对 Hyper3D、GPT Image 2 与兼容 Responses API 的代理端点，不存储密钥。（9 个端点）
- **project-connector** — 本地项目连接器：文件列举/读取/替换与模型创建/变更校验（开发辅助）。（6 个端点）
- **agent-workbench** — Agent 工作台纵向切片：工程 Brief 抽取/确认与评估（FOC 演示，非 real 模式）。（5 个端点）
- **foc-demo** — 可复现 FOC 机械臂热设计演示的资产与推理端点（FOC 演示，非 real 模式）。（4 个端点）

## system

>服务健康与全局契约元信息。

### `GET /health`

**健康检查**  

返回服务运行状态、运行模式与种子案例库规模。可用于探测/就绪检查。

- 成功状态码：`200`

**示例响应**

```json
{
  "status": "ok",
  "mode": "screening",
  "real_only": false,
  "library_cases": 12
}
```


### `GET /schema`

**参数中枢契约概要**  

返回参数中枢（UserInput）的约束向量规格与已支持的结构参数 schema 清单。

- 成功状态码：`200`

**示例响应**

```json
{
  "constraint_vector": [
    "power_w",
    "t_ambient_c",
    "t_limit_c",
    "material"
  ],
  "dimension": 4,
  "structure_schemas": [
    "leaf_vein",
    "channel",
    "flat"
  ],
  "note": "完整 JSON Schema 见 data/schemas/（export_schemas.py 生成）"
}
```


## screening

>结构生成 / 热路评估 / 相似度检索等核心筛选能力（需非 real 模式 is_real=False 才挂载）。

### `POST /match_user`

**用户意图 ↔ 库案例 相似检索**  

将上游 UserInput 映射到参数中枢向量空间，返回最相似的种子案例（同空间最近邻）。用于从自然语言/结构化需求直接定位可复用的结构模板。

- 成功状态码：`200`

**示例响应**

```json
{
  "dimension": 4,
  "count": 2,
  "hits": [
    {
      "case_id": "case_001",
      "source": "seed",
      "note": "leaf_vein baseline",
      "structure_type": "leaf_vein",
      "similarity": 0.91,
      "preview_img": "data/leaf_vein/case_001.svg",
      "model_path": "data/leaf_vein/case_001.glb",
      "device_context": {
        "power_w": 28.0
      }
    }
  ]
}
```


### `POST /recommend`

**结构模板推荐**  

基于 UserInput 推荐合适的结构模板（意图到生成的入口），返回推荐的结构类型与参数骨架。

- 成功状态码：`200`

**示例响应**

```json
{
  "recommended": {
    "structure_type": "leaf_vein",
    "reason": "高功率密度"
  }
}
```


### `GET /library`

**列出种子案例库**  

返回种子案例库的全部案例（含指标与预览资源路径）。

- 成功状态码：`200`

**示例响应**

```json
{
  "count": 12,
  "cases": [
    {
      "case_id": "case_001",
      "structure_type": "leaf_vein"
    }
  ]
}
```


### `POST /generate`

**参数 → 结构 SVG + 几何量**  

根据结构参数生成结构 SVG 与几何统计量（Step2 建模 / Step3 结构）。返回 SVG 字符串与几何 stats。

- 成功状态码：`200`

**示例响应**

```json
{
  "structure_type": "leaf_vein",
  "svg": "<svg>...</svg>",
  "geometry": {
    "area_mm2": 120.5
  }
}
```


### `POST /evaluate`

**参数 → 热路评估**  

生成结构并做热路评估（Step1 可行性 / Step5 优化），返回温升、极限时间等指标。

- 成功状态码：`200`

**示例响应**

```json
{
  "t_rise_c": 42.3,
  "time_to_limit_s": 159.56,
  "pass": true
}
```


### `POST /compare`

**多结构相对基线收益**  

对比基线结构与若干候选结构，返回各候选相对基线的三指标收益（PDF §9.4）。

- 成功状态码：`200`

**示例响应**

```json
{
  "baseline": {
    "t_rise_c": 50.0
  },
  "candidates": [
    {
      "result": {
        "t_rise_c": 42.3
      },
      "gain": {
        "time_to_limit_gain_pct": 12.4
      }
    }
  ]
}
```


### `POST /optimize/leaf-direction`

**叶脉方向/分叉角自动优化**  

自动替换叶脉主流方向与分叉角，调用仿真适配器返回最优候选。当前使用 LumpedSimulationBackend；真实 ANSYS 接入时只替换 backend 实现。

- 成功状态码：`200`

**示例响应**

```json
{
  "best": {
    "flow_direction_deg": 45,
    "t_rise_c": 38.1
  },
  "candidates": []
}
```


### `POST /match`

**结构参数相似度检索**  

将结构参数映射到向量空间，在种子库中检索最相似案例（区别于 /match_user 的是直接吃参数而非 UserInput）。

- 成功状态码：`200`

**示例响应**

```json
{
  "count": 3,
  "hits": [
    {
      "case_id": "case_001",
      "similarity": 0.88
    }
  ]
}
```


## engineering-state

>版本化 EngineeringState 唯一事实源与 Artifact 不可变血缘登记。

### `PUT /api/v1/engineering-projects/{project_id}/state`

**写入工程状态**  

版本化写入 EngineeringState（唯一事实源）。expected_revision 用于乐观锁，冲突返回 409。路径 project_id 必须与 body 中一致。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `project_id` | path | string | 是 |  |


### `GET /api/v1/engineering-projects/{project_id}/state`

**读取工程状态**  

按 project_id（可选 revision）读取 EngineeringState。省略 revision 时返回最新版。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `project_id` | path | string | 是 |  |
| `revision` | query | union | 否 |  |


### `POST /api/v1/engineering-projects/{project_id}/confirm`

**确认工程状态**  

对指定版本的 EngineeringState 做人工确认（审批门），记录确认人、主题与证据，推进 approved 状态。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `project_id` | path | string | 是 |  |


### `POST /api/v1/engineering-projects/{project_id}/artifacts`

**登记 Artifact**  

登记一个不可变 Artifact（如 STEP/SCDOC/JSON），返回带血缘的 Artifact 对象。开发期用于把几何/仿真产物挂到状态上。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `project_id` | path | string | 是 |  |


### `GET /api/v1/engineering-projects/{project_id}/artifacts`

**列出 Artifact 注册表**  

返回该项目的全部 Artifact 注册表（含 lineage 索引）。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `project_id` | path | string | 是 |  |


### `GET /api/v1/engineering-projects/{project_id}/artifacts/{artifact_id}/lineage`

**查询 Artifact 血缘**  

返回指定 Artifact 的来源与下游血缘关系（不可变 lineage）。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `project_id` | path | string | 是 |  |
| `artifact_id` | path | string | 是 |  |


### `GET /api/v1/engineering-projects/{project_id}/artifacts/{artifact_id}`

**读取单个 Artifact**  

按 artifact_id 返回单个 Artifact 详情。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `project_id` | path | string | 是 |  |
| `artifact_id` | path | string | 是 |  |


## simulation-orchestration

>仿真交接契约的编译、查询与结果验收（Fluent/Mechanical 适配器隔离）。

### `POST /api/v1/simulation-handoffs/projects/{project_id}`

**编译仿真交接契约**  

将「已批准且关键值全 confirmed」的 EngineeringState 编译为 SimulationHandoffContract，返回 handoff_id 与契约对象。前置条件不满足（未 approved/含 unresolved/几何非 MANUFACTURING_CAD）时返回 409。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `project_id` | path | string | 是 |  |


**示例响应**

```json
{
  "handoff_id": "ho_001",
  "contract": {
    "schema": "thermalforge.simulation_handoff",
    "version": "1.0.0"
  }
}
```


### `GET /api/v1/simulation-handoffs/{handoff_id}`

**读取仿真交接契约**  

按 handoff_id 返回 SimulationHandoffContract 详情。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `handoff_id` | path | string | 是 |  |


### `GET /api/v1/simulation-handoffs/{handoff_id}/validation-summary`

**仿真验收摘要**  

返回该交接契约的验收摘要（已登记结果、是否超阈值、是否进入 review_required）。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `handoff_id` | path | string | 是 |  |


## simulation-development

>仿真编排的开发期端点：登记 SpaceClaim 几何产物与仿真结果（开发模式）。

### `POST /api/v1/simulation-handoffs/{handoff_id}/spaceclaim-artifacts`

**登记 SpaceClaim 几何产物（开发）**  

把 SpaceClaim 生成的几何 Artifact 列表挂到交接契约上，闭合几何→仿真链路。开发模式端点。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `handoff_id` | path | string | 是 |  |


### `POST /api/v1/simulation-handoffs/{handoff_id}/result`

**登记仿真结果（开发）**  

回灌真实 Fluent/Mechanical 仿真结果，做「先身份校验→原始登记→验收」并支持 review_required 路由。开发模式端点。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `handoff_id` | path | string | 是 |  |


## knowledge

>常见文档模板固化后的知识库检索：按电机类型 / 材质 / 关键字查询默认条目。

### `GET /api/v1/knowledge/motor-type/{motor_type}`

**按电机类型检索**  

在全局知识库（data/knowledge.db）中按 motor_type 检索默认电机条目（如 BLDC），返回结构化条目列表。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `motor_type` | path | string | 是 |  |


**示例响应**

```json
{
  "count": 1,
  "results": [
    {
      "entry_id": "kb-bldc-default",
      "motor_type": "BLDC",
      "rated_power_w": 50.0
    }
  ]
}
```


### `GET /api/v1/knowledge/material/{name}`

**按材质检索**  

在知识库中按材质名（如 al/steel）检索默认材质条目，返回兼容 MaterialProperties 的字段。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | path | string | 是 |  |


**示例响应**

```json
{
  "count": 1,
  "results": [
    {
      "material_id": "al",
      "name": "Aluminum",
      "density_kg_m3": 2700
    }
  ]
}
```


### `GET /api/v1/knowledge/keyword/{text}`

**按关键字检索**  

在知识库中按关键字（如 aluminum、无刷）检索文档/条目，用于通用数据快速调用。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `text` | path | string | 是 |  |


**示例响应**

```json
{
  "count": 0,
  "results": []
}
```


## agent-governance

>Agent 定义、Prompt 版本与 SHA256、Skill、Tool 策略等治理元数据的只读查询。

### `GET /api/v1/agent-definitions`

**查询 Agent 治理元数据**  

返回全部 Agent 定义、Prompt（含 version 与 sha256）、Skill 与 Tool 策略的只读快照，用于治理审计与前端展示。

- 成功状态码：`200`

**示例响应**

```json
{
  "definitions": [],
  "prompts": [
    {
      "id": "p1",
      "version": "1",
      "sha256": "abc..."
    }
  ],
  "skills": [],
  "tools": []
}
```


## agent-governance-development

>Agent 执行审计记录查询（开发模式）。

### `GET /api/v1/agent-executions/{execution_id}`

**查询单次执行记录（开发）**  

按 execution_id 查询 Agent 执行审计记录。开发模式端点（当前为占位实现）。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `execution_id` | path | string | 是 |  |


### `GET /api/v1/agent-executions`

**列出执行记录（开发）**  

按 project_id / revision 过滤列出 Agent 执行审计记录。开发模式端点（当前返回空列表）。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `project_id` | query | union | 否 |  |
| `revision` | query | union | 否 |  |


## agent-pipeline

>数据手册 → Hyper3D 资产的可审计 Agent 流水线：创建、规格抽取/提议/评审、几何与 Hyper3D 登记。

### `POST /api/v1/agent-pipelines`

**创建 Agent 流水线**  

基于请求体创建一条可审计的 Agent 流水线（数据手册 → Hyper3D 资产），返回初始 Pipeline 对象。

- 成功状态码：`200`

**示例响应**

```json
{
  "id": "3f1a...",
  "project_id": "iki1602",
  "stage": "created"
}
```


### `GET /api/v1/agent-pipelines/{pipeline_id}`

**获取流水线**  

按 pipeline_id 返回完整 Pipeline 对象（含各阶段状态与登记产物）。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `pipeline_id` | path | string | 是 |  |


### `GET /api/v1/agent-pipelines/{pipeline_id}/status`

**获取流水线状态**  

返回流水线的阶段状态机快照（created/extracting/specified/reviewing/...）。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `pipeline_id` | path | string | 是 |  |


### `GET /api/v1/agent-pipelines/{pipeline_id}/manifest`

**获取前端 Manifest**  

返回前端可消费的交付 Manifest（模型 URL、爆炸变换、组件、置信度与讲解）。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `pipeline_id` | path | string | 是 |  |


### `POST /api/v1/agent-pipelines/{pipeline_id}/specification/extract`

**抽取工程规格**  

调用 LLM（gpt-5.6-sol）从源文档内容抽取工程规格，并记录所用 Agent/Prompt 定义，返回更新后的流水线。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `pipeline_id` | path | string | 是 |  |


### `POST /api/v1/agent-pipelines/{pipeline_id}/specification`

**提议工程规格**  

由上游/人工提交工程规格草案，进入待评审状态。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `pipeline_id` | path | string | 是 |  |


### `POST /api/v1/agent-pipelines/{pipeline_id}/specification/review`

**评审工程规格**  

对提议的规格做接受/拒绝评审，记录评审人与期望版本。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `pipeline_id` | path | string | 是 |  |


### `POST /api/v1/agent-pipelines/{pipeline_id}/hyper3d/compile`

**编译 Hyper3D 请求**  

将评审通过的规格编译为 Hyper3D Rodin 请求（提示词 + 图像清单），进入提交准备。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `pipeline_id` | path | string | 是 |  |


## agent-pipeline-development

>Agent 流水线的开发期端点：几何登记、Hyper3D 提交/结果、验证报告（开发模式）。

### `POST /api/v1/agent-pipelines/{pipeline_id}/geometry`

**登记几何产物（开发）**  

登记由 SpaceClaim/网格等产出的几何 Artifact 列表，进入几何阶段。开发模式端点。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `pipeline_id` | path | string | 是 |  |


### `POST /api/v1/agent-pipelines/{pipeline_id}/hyper3d/submitted`

**标记 Hyper3D 已提交（开发）**  

记录 Hyper3D 提交的 task_uuid，进入轮询阶段。开发模式端点。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `pipeline_id` | path | string | 是 |  |


### `POST /api/v1/agent-pipelines/{pipeline_id}/hyper3d/result`

**登记 Hyper3D 结果（开发）**  

登记 Hyper3D 任务完成后的资产（GLB/图像及来源 Manifest）。开发模式端点。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `pipeline_id` | path | string | 是 |  |


### `POST /api/v1/agent-pipelines/{pipeline_id}/validation`

**提交验证报告（开发）**  

提交尺寸/轴线碰撞等验证报告，进入可交付状态。开发模式端点。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `pipeline_id` | path | string | 是 |  |


## component-analysis

>概念 3D 组件清单与工程分析，输出前端可消费的 ComponentManifest。

### `POST /api/v1/components/analyze`

**组件工程分析**  

对概念 3D 组件清单做工程分析，输出前端可消费的 ComponentManifest。AI 分析可由请求体 use_ai 开关；REAL 模式下强制 use_ai=true（关闭确定性回退）。

- 成功状态码：`200`

**示例响应**

```json
{
  "components": [
    {
      "id": "root.0",
      "role": "shell",
      "material": "PA12-CF"
    }
  ]
}
```


## external-models

>对 Hyper3D、GPT Image 2 与兼容 Responses API 的代理端点，不存储密钥。

### `GET /models/config`

**Model Config**  

返回可公开的模型配置，不回显任何密钥。

- 成功状态码：`200`

**示例响应**

```json
{
  "openai": {
    "configured": true,
    "text_model": "gpt-5.6-sol"
  },
  "hyper3d": {
    "configured": true
  },
  "timeout_seconds": 120,
  "routes": {
    "text_responses": "/models/text/responses"
  }
}
```


### `POST /models/gpt-5.5/responses`

**Text Responses**  

代理 OpenAI Responses API，默认模型由 OPENAI_TEXT_MODEL 管理。

- 成功状态码：`200`

### `POST /models/text/responses`

**Text Responses**  

代理 OpenAI Responses API，默认模型由 OPENAI_TEXT_MODEL 管理。

- 成功状态码：`200`

### `POST /models/gpt-image-2/generations`

**Gpt Image 2 Generations**  

代理 OpenAI Image API，默认模型为 gpt-image-2。

- 成功状态码：`200`

### `POST /models/hyper3d/tasks`

**Hyper3D Submit**  

提交 Hyper3D Rodin 文生或图生 3D 异步任务。

- 成功状态码：`200`

### `POST /models/hyper3d/bang`

**Hyper3D Bang**  

提交 Bang 分件任务，支持 Rodin asset_id 或自定义模型上传。

- 成功状态码：`200`

### `GET /models/hyper3d/balance`

**Hyper3D Balance**  

查询 Hyper3D 余额，不提交生成任务。

- 成功状态码：`200`

### `POST /models/hyper3d/status`

**Hyper3D Status**  

按提交响应中的 subscription_key 查询任务进度。

- 成功状态码：`200`

### `POST /models/hyper3d/download`

**Hyper3D Download**  

任务完成后按 task_uuid 获取模型下载列表。

- 成功状态码：`200`

## project-connector

>本地项目连接器：文件列举/读取/替换与模型创建/变更校验（开发辅助）。

### `GET /connector/status`

**连接器状态**  

返回项目连接器状态（项目根路径、可访问性等），用于本地开发辅助。

- 成功状态码：`200`

**示例响应**

```json
{
  "root": "/project",
  "accessible": true
}
```


### `POST /connector/files/list`

**列举文件**  

按路径与 glob 模式列举项目文件，支持 limit 上限。返回匹配的文件路径列表。

- 成功状态码：`200`

**示例响应**

```json
{
  "files": [
    "core/api/app.py",
    "README.md"
  ]
}
```


### `POST /connector/files/read`

**读取文件**  

读取指定文件的文本内容（受 max_chars 限制），返回路径与内容。

- 成功状态码：`200`

**示例响应**

```json
{
  "path": "README.md",
  "content": "# ThermalForge"
}
```


### `POST /connector/files/replace`

**替换文本**  

在指定文件中将 old_text 全量替换为 new_text，返回受影响的统计。

- 成功状态码：`200`

### `POST /connector/model/create`

**创建模型**  

基于参数创建模型候选（调用 SpaceClaim/生成内核）。execute=false 时仅做干跑校验。

- 成功状态码：`200`

### `POST /connector/model/verify-change`

**校验模型变更**  

对比基线参数与变更参数，校验变更是否可安全应用（几何/碰撞等），execute=false 时仅校验不执行。

- 成功状态码：`200`

## agent-workbench

>Agent 工作台纵向切片：工程 Brief 抽取/确认与评估（FOC 演示，非 real 模式）。

### `GET /api/v1/workbench/capabilities`

**工作台能力**  

返回 Agent 工作台当前支持的能力清单（抽取、确认、评估等）。

- 成功状态码：`200`

### `POST /api/v1/workbench/briefs/extract`

**抽取工程 Brief**  

从自然语言文本抽取结构化工程 Brief（设备上下文与热设计需求），创建并返回。

- 成功状态码：`200`

### `GET /api/v1/workbench/briefs/{brief_id}`

**读取工程 Brief**  

按 brief_id 返回工程 Brief 详情。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `brief_id` | path | string | 是 |  |


### `POST /api/v1/workbench/briefs/{brief_id}/confirm`

**确认工程 Brief**  

对 Brief 做接受/拒绝确认，记录确认人与期望版本，推进状态机。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `brief_id` | path | string | 是 |  |


### `POST /api/v1/workbench/evaluations`

**评估工程 Brief**  

对指定 Brief 做热设计评估，返回评估结果与指标。需先确认 Brief。

- 成功状态码：`200`

## foc-demo

>可复现 FOC 机械臂热设计演示的资产与推理端点（FOC 演示，非 real 模式）。

### `GET /api/v1/foc-demo`

**FOC 演示快照**  

返回可复现 FOC 机械臂热设计演示的当前快照（场景、工程输入、Brief、热仿真、局限）。

- 成功状态码：`200`

### `GET /api/v1/foc-demo/raw`

**FOC 演示原始数据**  

返回演示的原始工程数据与上下文（未加工 dict），供调试与前端高级消费。

- 成功状态码：`200`

### `GET /api/v1/foc-demo/assets/{name}`

**获取演示资产**  

按路径返回演示资产文件（GLB/WebP/图像等），Content-Type 按扩展名推断。

- 成功状态码：`200`

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | path | string | 是 |  |


### `POST /api/v1/foc-demo/reasoning`

**刷新 FOC 设计推理**  

调用 LLM（gpt-5.6-sol）基于当前快照生成可审计的 FOC 关节热设计台账（架构/热路径/决策/风险/验证任务），并持久化。

- 成功状态码：`200`
