"""
ThermalForge 后端 API（FastAPI）

为前端提供机器人关节热管理外壳优化的数据接口，覆盖以下能力分组：

- 系统（system）：`GET /health` 健康检查、`GET /schema` 参数中枢契约概要
- 筛选（screening，非 real 模式启用）：`/match_user`、`/recommend`、`/library`、
  `/generate`、`/evaluate`、`/compare`、`/optimize/leaf-direction`、`/match`
- 工程状态（engineering-state）：`/api/v1/engineering-projects/...`（版本化 EngineeringState 与 Artifact）
- 仿真编排（simulation-orchestration）：`/api/v1/simulation-handoffs/...`
- 知识库（knowledge）：`/api/v1/knowledge/...`（默认 BLDC 电机 / 材质检索）
- Agent 治理（agent-governance）：`/api/v1/agent-definitions`
- Agent 流水线（agent-pipeline）：`/api/v1/agent-pipelines/...`
- 组件分析（component-analysis）：`/api/v1/components/analyze`
- 外部模型（external-models）：`/models/...`（Hyper3D / GPT Image / Responses 代理）
- 项目连接器（project-connector）：`/connector/...`
- Agent 工作台（agent-workbench）：`/api/v1/workbench/...`（FOC 演示用，非 real 模式）

启动（工作目录须为 thermalforge/ 根）：
    uvicorn core.api.app:app --reload --port 8000

交互式文档：启动后访问 http://localhost:8000/docs （Swagger UI）或
http://localhost:8000/redoc 。完整接口清单亦见 docs/api-reference.md （由
scripts/generate_api_reference.py 基于 OpenAPI 自动生成）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from core.models.schema import from_dict
from core.models.user_input import UserInput
from core.parameter_hub import ParameterHub
from core.engine.generator import generate
from core.engine.thermal import evaluate, compare
from core.engine.matcher import Library
from core.engine.simulation import SimulationContext, LumpedSimulationBackend
from core.engine.optimizer import OptimizationWeights, optimize_leaf_direction
from core.api.routes.models import router as models_router
from core.api.routes.components import router as components_router
from core.api.routes.connector import router as connector_router
from core.api.routes.workbench import router as workbench_router
from core.api.routes.foc_demo import router as foc_demo_router
from core.api.routes.agent_pipeline import router as agent_pipeline_router, development_router as agent_pipeline_development_router
from core.api.routes.optimization import router as optimization_router, development_router as optimization_development_router
from core.api.routes.engineering_state import router as engineering_state_router
from core.api.routes.simulation_orchestration import router as simulation_orchestration_router, development_router as simulation_development_router
from core.api.routes.agent_registry import router as agent_registry_router, development_router as agent_registry_development_router
from core.api.routes.knowledge import router as knowledge_router
from core.config import get_settings

DATA = ROOT / "data"
settings = get_settings()

OPENAPI_TAGS = [
    {"name": "system", "description": "服务健康与全局契约元信息。"},
    {"name": "screening", "description": "结构生成 / 热路评估 / 相似度检索等核心筛选能力（需非 real 模式 is_real=False 才挂载）。"},
    {"name": "engineering-state", "description": "版本化 EngineeringState 唯一事实源与 Artifact 不可变血缘登记。"},
    {"name": "simulation-orchestration", "description": "仿真交接契约的编译、查询与结果验收（Fluent/Mechanical 适配器隔离）。"},
    {"name": "simulation-development", "description": "仿真编排的开发期端点：登记 SpaceClaim 几何产物与仿真结果（开发模式）。"},
    {"name": "knowledge", "description": "常见文档模板固化后的知识库检索：按电机类型 / 材质 / 关键字查询默认条目。"},
    {"name": "agent-governance", "description": "Agent 定义、Prompt 版本与 SHA256、Skill、Tool 策略等治理元数据的只读查询。"},
    {"name": "agent-governance-development", "description": "Agent 执行审计记录查询（开发模式）。"},
    {"name": "agent-pipeline", "description": "数据手册 → Hyper3D 资产的可审计 Agent 流水线：创建、规格抽取/提议/评审、几何与 Hyper3D 登记。"},
    {"name": "agent-pipeline-development", "description": "Agent 流水线的开发期端点：几何登记、Hyper3D 提交/结果、验证报告（开发模式）。"},
    {"name": "optimization-loop", "description": "SolidWorks 模型优化反馈闭环：用户反馈 → LLM 规划 → SolidWorks 执行 → 迭代。"},
    {"name": "optimization-loop-development", "description": "优化闭环开发期端点：执行 SolidWorks 优化（开发模式）。"},
    {"name": "component-analysis", "description": "概念 3D 组件清单与工程分析，输出前端可消费的 ComponentManifest。"},
    {"name": "external-models", "description": "对 Hyper3D、GPT Image 2 与兼容 Responses API 的代理端点，不存储密钥。"},
    {"name": "project-connector", "description": "本地项目连接器：文件列举/读取/替换与模型创建/变更校验（开发辅助）。"},
    {"name": "agent-workbench", "description": "Agent 工作台纵向切片：工程 Brief 抽取/确认与评估（FOC 演示，非 real 模式）。"},
    {"name": "foc-demo", "description": "可复现 FOC 机械臂热设计演示的资产与推理端点（FOC 演示，非 real 模式）。"},
]

app = FastAPI(
    title="ThermalForge API",
    version="0.2.0",
    description="机器人关节热管理外壳优化 · 结构生成 + 热路评估 + 外部生成模型。详见各 tag 分组与 docs/api-reference.md。",
    openapi_tags=OPENAPI_TAGS,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/",
    include_in_schema=False,
)
def root():
    """根路径重定向到交互式 Swagger 文档。"""
    return RedirectResponse(url="/docs")


app.include_router(models_router)
app.include_router(components_router)
app.include_router(connector_router)
app.include_router(agent_pipeline_router)
app.include_router(optimization_router)
app.include_router(engineering_state_router)
app.include_router(simulation_orchestration_router)
app.include_router(agent_registry_router)
app.include_router(knowledge_router)
if not settings.is_real:
    app.include_router(workbench_router)
    app.include_router(foc_demo_router)
    app.include_router(agent_pipeline_development_router)
    app.include_router(optimization_development_router)
    app.include_router(simulation_development_router)
    app.include_router(agent_registry_development_router)

screening_router = APIRouter(tags=["screening"])


# ---------- 请求模型 ----------
class ParamsIn(BaseModel):
    params: Dict[str, Any] = Field(..., description="结构参数 dict，须含 structure_type（leaf_vein/channel/flat）及几何字段")


class EvaluateIn(BaseModel):
    params: Dict[str, Any] = Field(..., description="结构参数 dict，须含 structure_type 与几何字段")
    power_w: float = Field(28.0, description="热源功率 (W)")
    t_ambient_c: float = Field(25.0, description="环境温度 (°C)")
    t_limit_c: float = Field(80.0, description="允许温升上限 (°C)")
    material: str = Field("AlSi10Mg", description="外壳材质名称")


class CompareIn(BaseModel):
    baseline: Dict[str, Any] = Field(..., description="基线结构参数 dict")
    candidates: List[Dict[str, Any]] = Field(..., description="候选结构参数 dict 列表")
    power_w: float = Field(28.0, description="热源功率 (W)")
    t_ambient_c: float = Field(25.0, description="环境温度 (°C)")
    t_limit_c: float = Field(80.0, description="允许温升上限 (°C)")
    material: str = Field("AlSi10Mg", description="外壳材质名称")


class MatchIn(BaseModel):
    params: Dict[str, Any] = Field(..., description="结构参数 dict，须含 structure_type 与几何字段")
    top_k: int = Field(3, description="返回的最相似案例数量")
    filter_medium: bool = Field(True, description="是否按冷却介质过滤")


class MatchUserIn(BaseModel):
    user_input: Dict[str, Any] = Field(..., description="上游输入层 UserInput dict（设备上下文 + 需求）")
    top_k: int = Field(3, description="返回的最相似案例数量")
    require_medium: bool = Field(False, description="是否要求冷却介质匹配")


class RecommendIn(BaseModel):
    user_input: Dict[str, Any] = Field(..., description="上游输入层 UserInput dict（设备上下文 + 需求）")


class LeafOptimizeIn(BaseModel):
    base_params: Dict[str, Any] = Field(..., description="叶脉基础参数 dict，须含 structure_type=leaf_vein")
    flow_directions_deg: List[float] = Field(default=[0, 45, 90, 135, 180, 225, 270, 315], description="候选主流方向 (deg)")
    branch_angles: Optional[List[float]] = Field(None, description="候选分叉角列表（None 使用默认）")
    power_w: float = Field(28.0, description="热源功率 (W)")
    t_ambient_c: float = Field(25.0, description="环境温度 (°C)")
    t_limit_c: float = Field(80.0, description="允许温升上限 (°C)")
    material: str = Field("AlSi10Mg", description="外壳材质名称")
    interface_r: float = Field(0.35, description="界面热阻 (K/W)")
    source_model_path: str = Field("", description="可选源模型路径（用于高精度仿真）")
    preferred_flow_direction_deg: Optional[float] = Field(None, description="偏好主流方向 (deg)")
    aesthetic_weight: float = Field(0.20, description="美学权重")
    thermal_weight: float = Field(0.70, description="热学权重")
    mass_weight: float = Field(0.10, description="质量权重")
    top_k: int = Field(5, description="返回的最优候选数量")


def _load_hub() -> ParameterHub:
    return ParameterHub.from_library_json(DATA / "seed_library.json")


# ---------- 系统接口 ----------
@app.get(
    "/health",
    tags=["system"],
    summary="健康检查",
    description="返回服务运行状态、运行模式与种子案例库规模。可用于探测/就绪检查。",
    response_description="服务健康状态对象",
    responses={
        200: {
            "description": "服务正常",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ok",
                        "mode": "screening",
                        "real_only": False,
                        "library_cases": 12,
                    }
                }
            },
        }
    },
)
def health():
    lib = Library.load(DATA / "seed_library.json")
    return {
        "status": "ok",
        "mode": settings.thermalforge_mode,
        "real_only": settings.is_real,
        "library_cases": len(lib.cases) if not settings.is_real else None,
    }


@app.get(
    "/schema",
    tags=["system"],
    summary="参数中枢契约概要",
    description="返回参数中枢（UserInput）的约束向量规格与已支持的结构参数 schema 清单。",
    response_description="约束向量与结构 schema 概要",
    responses={
        200: {
            "description": "契约概要",
            "content": {
                "application/json": {
                    "example": {
                        "constraint_vector": ["power_w", "t_ambient_c", "t_limit_c", "material"],
                        "dimension": 4,
                        "structure_schemas": ["leaf_vein", "channel", "flat"],
                        "note": "完整 JSON Schema 见 data/schemas/（export_schemas.py 生成）",
                    }
                }
            },
        }
    },
)
def schema():
    """返回参数中枢契约概要：约束向量规格 + 结构参数 schema 清单。"""
    return {
        "constraint_vector": UserInput.vector_spec(),
        "dimension": len(UserInput.vector_spec()),
        "structure_schemas": ["leaf_vein", "channel", "flat"],
        "note": "完整 JSON Schema 见 data/schemas/（export_schemas.py 生成）",
    }


# ---------- 筛选接口（screening，非 real 模式） ----------
@screening_router.post(
    "/match_user",
    summary="用户意图 ↔ 库案例 相似检索",
    description="将上游 UserInput 映射到参数中枢向量空间，返回最相似的种子案例（同空间最近邻）。"
    "用于从自然语言/结构化需求直接定位可复用的结构模板。",
    response_description="维度、命中数量与命中列表",
    responses={
        200: {
            "description": "检索成功",
            "content": {
                "application/json": {
                    "example": {
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
                                "device_context": {"power_w": 28.0},
                            }
                        ],
                    }
                }
            },
        },
        422: {"description": "user_input 校验失败", "content": {"application/json": {"example": {"detail": "user_input 校验失败: power_w 缺失"}}}},
    },
)
def api_match_user(body: MatchUserIn):
    """用户意图 ↔ 库案例 同空间最近邻检索（参数中枢核心端点）。"""
    try:
        ui = UserInput.from_dict(body.user_input)
        errs = ui.validate()
        if errs:
            raise HTTPException(422, "user_input 校验失败: " + "; ".join(errs))
        hub = _load_hub()
        hits = hub.match_user_to_library(ui, top_k=body.top_k, require_medium=body.require_medium)
    except HTTPException:
        raise
    except Exception as e:  # noqa
        raise HTTPException(400, f"match_user failed: {e}")
    return {
        "dimension": len(ui.to_vector()),
        "count": len(hits),
        "hits": [
            {
                "case_id": e.case_id,
                "source": e.source,
                "note": e.perf_notes,
                "structure_type": e.structure_type,
                "similarity": round(sim, 4),
                "preview_img": e.preview_img,
                "model_path": e.model_path,
                "device_context": e.device_context.to_dict(),
            }
            for e, sim in hits
        ],
    }


@screening_router.post(
    "/recommend",
    summary="结构模板推荐",
    description="基于 UserInput 推荐合适的结构模板（意图到生成的入口），返回推荐的结构类型与参数骨架。",
    response_description="推荐结果",
    responses={
        200: {
            "description": "推荐成功",
            "content": {"application/json": {"example": {"recommended": {"structure_type": "leaf_vein", "reason": "高功率密度"}}}},
        },
        422: {"description": "user_input 校验失败"},
    },
)
def api_recommend(body: RecommendIn):
    """用户意图 → 结构模板推荐（意图到生成的入口）。"""
    try:
        ui = UserInput.from_dict(body.user_input)
        errs = ui.validate()
        if errs:
            raise HTTPException(422, "user_input 校验失败: " + "; ".join(errs))
        hub = _load_hub()
        rec = hub.recommend_structure(ui)
    except HTTPException:
        raise
    except Exception as e:  # noqa
        raise HTTPException(400, f"recommend failed: {e}")
    return {"recommended": rec}


@screening_router.get(
    "/library",
    summary="列出种子案例库",
    description="返回种子案例库的全部案例（含指标与预览资源路径）。",
    response_description="案例数量与案例列表",
    responses={
        200: {
            "description": "案例库",
            "content": {"application/json": {"example": {"count": 12, "cases": [{"case_id": "case_001", "structure_type": "leaf_vein"}]}}},
        }
    },
)
def library():
    lib = Library.load(DATA / "seed_library.json")
    return {"count": len(lib.cases), "cases": lib.cases}


@screening_router.post(
    "/generate",
    summary="参数 → 结构 SVG + 几何量",
    description="根据结构参数生成结构 SVG 与几何统计量（Step2 建模 / Step3 结构）。返回 SVG 字符串与几何 stats。",
    response_description="结构类型、SVG 与几何量",
    responses={
        200: {
            "description": "生成成功",
            "content": {
                "application/json": {
                    "example": {"structure_type": "leaf_vein", "svg": "<svg>...</svg>", "geometry": {"area_mm2": 120.5}}
                }
            },
        },
        400: {"description": "参数非法", "content": {"application/json": {"example": {"detail": "generate failed: ..."}}}},
    },
)
def api_generate(body: ParamsIn):
    try:
        p = from_dict(body.params)
        svg, stats = generate(p)
    except Exception as e:  # noqa
        raise HTTPException(400, f"generate failed: {e}")
    return {"structure_type": p.structure_type, "svg": svg, "geometry": stats.__dict__}


@screening_router.post(
    "/evaluate",
    summary="参数 → 热路评估",
    description="生成结构并做热路评估（Step1 可行性 / Step5 优化），返回温升、极限时间等指标。",
    response_description="热路评估结果 dict",
    responses={
        200: {
            "description": "评估成功",
            "content": {
                "application/json": {
                    "example": {"t_rise_c": 42.3, "time_to_limit_s": 159.56, "pass": True}
                }
            },
        },
        400: {"description": "参数或评估失败"},
    },
)
def api_evaluate(body: EvaluateIn):
    try:
        p = from_dict(body.params)
        _, stats = generate(p)
        medium = body.params.get("cooling_medium", "air")
        res = evaluate(stats, power_w=body.power_w, t_ambient_c=body.t_ambient_c,
                       t_limit_c=body.t_limit_c, material=body.material,
                       medium=medium, structure_type=p.structure_type)
    except Exception as e:  # noqa
        raise HTTPException(400, f"evaluate failed: {e}")
    return res.to_dict()


@screening_router.post(
    "/compare",
    summary="多结构相对基线收益",
    description="对比基线结构与若干候选结构，返回各候选相对基线的三指标收益（PDF §9.4）。",
    response_description="基线与各候选结果及收益",
    responses={
        200: {
            "description": "对比成功",
            "content": {
                "application/json": {
                    "example": {
                        "baseline": {"t_rise_c": 50.0},
                        "candidates": [{"result": {"t_rise_c": 42.3}, "gain": {"time_to_limit_gain_pct": 12.4}}],
                    }
                }
            },
        },
        400: {"description": "参数或评估失败"},
    },
)
def api_compare(body: CompareIn):
    try:
        bp = from_dict(body.baseline)
        _, bstats = generate(bp)
        bmed = body.baseline.get("cooling_medium", "air")
        base_res = evaluate(bstats, power_w=body.power_w, t_ambient_c=body.t_ambient_c,
                            t_limit_c=body.t_limit_c, material=body.material,
                            medium=bmed, structure_type=bp.structure_type)
        out = {"baseline": base_res.to_dict(), "candidates": []}
        for c in body.candidates:
            cp = from_dict(c)
            _, cstats = generate(cp)
            cmed = c.get("cooling_medium", "air")
            cres = evaluate(cstats, power_w=body.power_w, t_ambient_c=body.t_ambient_c,
                            t_limit_c=body.t_limit_c, material=body.material,
                            medium=cmed, structure_type=cp.structure_type)
            gain = compare(base_res, cres)
            # inf 转成字符串，便于 JSON 序列化
            if gain["time_to_limit_gain_pct"] == float("inf"):
                gain["time_to_limit_gain_pct"] = "inf"
            out["candidates"].append({"result": cres.to_dict(), "gain": gain})
    except Exception as e:  # noqa
        raise HTTPException(400, f"compare failed: {e}")
    return out


@screening_router.post(
    "/optimize/leaf-direction",
    summary="叶脉方向/分叉角自动优化",
    description="自动替换叶脉主流方向与分叉角，调用仿真适配器返回最优候选。当前使用 "
    "LumpedSimulationBackend；真实 ANSYS 接入时只替换 backend 实现。",
    response_description="最优候选列表",
    responses={
        200: {
            "description": "优化成功",
            "content": {
                "application/json": {
                    "example": {"best": {"flow_direction_deg": 45, "t_rise_c": 38.1}, "candidates": []}
                }
            },
        },
        422: {"description": "base_params 非 leaf_vein"},
        400: {"description": "优化失败"},
    },
)
def api_optimize_leaf_direction(body: LeafOptimizeIn):
    """自动替换叶脉方向/分叉角，调用仿真适配器并返回最优候选。

    当前使用 LumpedSimulationBackend；真实 ANSYS 接入时只替换 backend 实现。
    """
    try:
        params = from_dict(body.base_params)
        if getattr(params, "structure_type", "") != "leaf_vein":
            raise HTTPException(422, "base_params 必须是 leaf_vein")
        context = SimulationContext(
            power_w=body.power_w,
            t_ambient_c=body.t_ambient_c,
            t_limit_c=body.t_limit_c,
            material=body.material,
            interface_r=body.interface_r,
            source_model_path=body.source_model_path,
            preferred_flow_direction_deg=body.preferred_flow_direction_deg,
        )
        result = optimize_leaf_direction(
            params,
            context=context,
            backend=LumpedSimulationBackend(),
            flow_directions_deg=body.flow_directions_deg,
            branch_angles=body.branch_angles,
            weights=OptimizationWeights(
                thermal=body.thermal_weight,
                aesthetics=body.aesthetic_weight,
                mass=body.mass_weight,
            ),
            top_k=body.top_k,
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa
        raise HTTPException(400, f"leaf optimization failed: {e}")
    return result


@screening_router.post(
    "/match",
    summary="结构参数相似度检索",
    description="将结构参数映射到向量空间，在种子库中检索最相似案例（区别于 /match_user 的是直接吃参数而非 UserInput）。",
    response_description="命中数量与命中列表",
    responses={
        200: {
            "description": "检索成功",
            "content": {"application/json": {"example": {"count": 3, "hits": [{"case_id": "case_001", "similarity": 0.88}]}}},
        },
        400: {"description": "参数非法"},
    },
)
def api_match(body: MatchIn):
    try:
        p = from_dict(body.params)
        lib = Library.load(DATA / "seed_library.json")
        medium = body.params.get("cooling_medium") if body.filter_medium else None
        hits = lib.match(p.to_vector(), structure_type=p.structure_type,
                         medium=medium, top_k=body.top_k)
    except Exception as e:  # noqa
        raise HTTPException(400, f"match failed: {e}")
    return {"count": len(hits), "hits": hits}


if not settings.is_real:
    app.include_router(screening_router)
