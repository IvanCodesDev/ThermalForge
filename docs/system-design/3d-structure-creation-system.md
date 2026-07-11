# ThermalForge 3D 结构创作与组件处理系统设计

## 1. 系统目标

输入 PDF + 文本描述 + 结构图片，通过 Agent 自动化流程生成可交互的 3D 结构模型，支持爆炸拆分、组件点击、工程说明和 SolidWorks 修正。

## 2. 数据流

```
用户上传 PDF + 文本 + 图片
    ↓
输入解析（pypdf + LLM 提取）
    ↓
EngineeringState（关节、组件、材料、热负荷）
    ↓
GPT Image 2 多视图生成（母图 + 正/侧/后/俯 + 剖面）
    ↓
Hyper3D Rodin Gen-2.5（整体 GLB）
    ↓
Bang 分件（多 mesh GLB / 多 object OBJ）
    ↓
组件语义分析（Agent 识别电机/外壳/散热等）
    ↓
组件专业说明（Agent 生成结构理由、材质、散热设计）
    ↓
3D 交互展示（爆炸、点击、聚焦、详情面板）
    ↓
SolidWorks 修正反馈（用户反馈 → Agent 规划 → SolidWorks 执行）
```

## 3. 数据契约

### 3.1 Project

```json
{
  "id": "proj-001",
  "name": "FOC 机械臂",
  "created_at": "2026-07-11T17:00:00Z",
  "status": "created|parsing|parsed|generating|generated|decomposed|analyzed|completed",
  "inputs": {
    "pdf_filename": "robot_arm_spec.pdf",
    "pdf_extracted_text": "...",
    "text_description": "设计一款四自由度 FOC 机械臂...",
    "structure_images": ["front_view.png", "side_view.png"]
  },
  "engineering_state_id": "es-001",
  "model_assets": [
    {
      "id": "asset-001",
      "type": "whole",
      "format": "glb",
      "url": "/api/v1/projects/proj-001/model/asset-001",
      "source": "hyper3d",
      "fidelity": "concept_mesh"
    },
    {
      "id": "asset-002",
      "type": "decomposed",
      "format": "glb",
      "url": "/api/v1/projects/proj-001/model/asset-002",
      "source": "hyper3d_bang",
      "fidelity": "concept_mesh"
    }
  ],
  "component_manifest_id": "cm-001",
  "optimization_history": []
}
```

### 3.2 ComponentManifest

```json
{
  "project_id": "proj-001",
  "components": [
    {
      "id": "root.0",
      "name": "root.0",
      "display_name": "关节壳体",
      "semantic_type": "housing",
      "geometry": { "bbox_mm": [160, 140, 110], "vertex_count": 50000, "face_count": 98000 },
      "material_candidates": [{ "name": "6061-T6 铝合金", "confidence": 0.8 }],
      "thermal_role": "散热路径末端",
      "structural_role": "承力壳体",
      "design_rationale": "采用 6061-T6 铝合金 CNC 加工...",
      "aesthetics_note": "深石墨色承力骨架...",
      "model_spec": "6061-T6 铝合金 · CNC",
      "confidence": 0.75,
      "review_status": "needs_review"
    }
  ]
}
```

### 3.3 Agent 流程步骤

```json
{
  "project_id": "proj-001",
  "steps": [
    { "id": "parse", "label": "输入解析", "status": "done", "agent_id": "specification_agent" },
    { "id": "image_prompts", "label": "多视图提示词", "status": "done", "agent_id": "foc_arm_multiview_prompt_agent" },
    { "id": "image_generation", "label": "图片生成", "status": "done" },
    { "id": "model_creation", "label": "3D 模型创作", "status": "done" },
    { "id": "decomposition", "label": "Bang 分件", "status": "done" },
    { "id": "component_analysis", "label": "组件语义分析", "status": "done", "agent_id": "component_analysis_agent" },
    { "id": "component_explanation", "label": "组件说明生成", "status": "pending", "agent_id": "component_explanation_agent" }
  ]
}
```

## 4. API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/projects` | 创建项目（multipart: PDF + 文本 + 图片） |
| GET | `/api/v1/projects/{id}` | 获取项目状态和资产 |
| GET | `/api/v1/projects` | 列出所有项目 |
| POST | `/api/v1/projects/{id}/parse` | 解析输入，生成 EngineeringState |
| POST | `/api/v1/projects/{id}/create-3d` | 3D 创作（Image 2 → Hyper3D → Bang） |
| POST | `/api/v1/projects/{id}/analyze-components` | 组件语义分析 |
| GET | `/api/v1/projects/{id}/components` | 获取组件清单 |
| POST | `/api/v1/projects/{id}/components/{cid}/explain` | 生成组件专业说明 |
| POST | `/api/v1/projects/{id}/optimization/feedback` | SolidWorks 修正反馈 |
| GET | `/api/v1/projects/{id}/model/{asset_id}` | 获取模型文件 |

## 5. Agent 可扩展架构

每个 Agent 步骤实现统一接口：

```python
class AgentStep(Protocol):
    step_id: str
    agent_id: str | None
    def can_run(self, project: Project) -> bool: ...
    async def run(self, project: Project) -> StepResult: ...
```

新增处理节点只需：
1. 实现 `AgentStep` 接口
2. 注册到 `AgentPipeline`
3. 在前端步骤列表中显示

## 6. 前端架构

```
App
├── 项目创建页（上传 PDF + 文本 + 图片）
├── 处理进度页（Agent 步骤时间线）
├── 3D 交互页
│   ├── AssemblyViewer（OBJ/GLB + PBR + 爆炸 + 聚焦）
│   ├── ComponentDetailPanel（结构理由、材质、散热设计）
│   ├── ComponentBrowser（散件列表）
│   └── OptimizationPanel（SolidWorks 反馈）
└── 项目列表页
```

## 7. 现有工程复用

| 能力 | 现有文件 | 复用方式 |
|---|---|---|
| EngineeringState | `core/models/engineering_state.py` | 直接复用 |
| Agent Pipeline | `core/services/agent_pipeline.py` | 扩展步骤 |
| Agent 执行 | `core/agents/execution.py` | 直接复用 |
| 组件分析 | `core/services/component_analysis.py` | 直接复用 |
| 组件说明 | `core/api/routes/component_explanations.py` | 直接复用 |
| Hyper3D 客户端 | `core/providers/hyper3d.py` | 直接复用 |
| OpenAI 客户端 | `core/providers/openai_models.py` | 直接复用 |
| PDF 提取 | `core/knowledge/extractor.py` | 直接复用 |
| 3D Viewer | `frontend/src/RobotArmViewer.tsx` | 直接复用 |
| 说明面板 | `frontend/src/App.tsx` | 扩展 |
