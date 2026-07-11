"""
ThermalForge 后端 API（FastAPI）

给前端动效 5 步提供数据接口：
  GET  /health                 健康检查
  GET  /library                列出种子案例库（含指标 + svg 路径）
  POST /generate               参数 → 结构 SVG + 几何量（Step2 建模 / Step3 结构）
  POST /evaluate               参数 → 热路评估（Step1 可行性 / Step5 优化）
  POST /compare                多结构相对基线收益（PDF §9.4 三指标）
  POST /match                  相似度匹配（Step 相似度检索）

启动：
  venv uvicorn core.api.app:app --reload --port 8000
  （工作目录须为 thermalforge/ 根）
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
from core.api.routes.engineering_state import router as engineering_state_router
from core.api.routes.simulation_orchestration import router as simulation_orchestration_router, development_router as simulation_development_router
from core.api.routes.agent_registry import router as agent_registry_router, development_router as agent_registry_development_router
from core.api.routes.knowledge import router as knowledge_router
from core.config import get_settings

DATA = ROOT / "data"
settings = get_settings()

app = FastAPI(title="ThermalForge API", version="0.2.0",
              description="机器人关节热管理外壳优化 · 结构生成 + 热路评估 + 外部生成模型")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(models_router)
app.include_router(components_router)
app.include_router(connector_router)
app.include_router(agent_pipeline_router)
app.include_router(engineering_state_router)
app.include_router(simulation_orchestration_router)
app.include_router(agent_registry_router)
app.include_router(knowledge_router)
if not settings.is_real:
    app.include_router(workbench_router)
    app.include_router(foc_demo_router)
    app.include_router(agent_pipeline_development_router)
    app.include_router(simulation_development_router)
    app.include_router(agent_registry_development_router)

screening_router = APIRouter(tags=["development-screening"])


# ---------- 请求模型 ----------
class ParamsIn(BaseModel):
    params: Dict[str, Any] = Field(..., description="结构参数，须含 structure_type")


class EvaluateIn(BaseModel):
    params: Dict[str, Any]
    power_w: float = 28.0
    t_ambient_c: float = 25.0
    t_limit_c: float = 80.0
    material: str = "AlSi10Mg"


class CompareIn(BaseModel):
    baseline: Dict[str, Any]
    candidates: List[Dict[str, Any]]
    power_w: float = 28.0
    t_ambient_c: float = 25.0
    t_limit_c: float = 80.0
    material: str = "AlSi10Mg"


class MatchIn(BaseModel):
    params: Dict[str, Any]
    top_k: int = 3
    filter_medium: bool = True


class MatchUserIn(BaseModel):
    user_input: Dict[str, Any] = Field(..., description="上游输入层 UserInput")
    top_k: int = 3
    require_medium: bool = False


class RecommendIn(BaseModel):
    user_input: Dict[str, Any] = Field(..., description="上游输入层 UserInput")


class LeafOptimizeIn(BaseModel):
    base_params: Dict[str, Any] = Field(..., description="叶脉基础参数，须含 structure_type=leaf_vein")
    flow_directions_deg: List[float] = Field(default=[0, 45, 90, 135, 180, 225, 270, 315])
    branch_angles: Optional[List[float]] = None
    power_w: float = 28.0
    t_ambient_c: float = 25.0
    t_limit_c: float = 80.0
    material: str = "AlSi10Mg"
    interface_r: float = 0.35
    source_model_path: str = ""
    preferred_flow_direction_deg: Optional[float] = None
    aesthetic_weight: float = 0.20
    thermal_weight: float = 0.70
    mass_weight: float = 0.10
    top_k: int = 5


def _load_hub() -> ParameterHub:
    return ParameterHub.from_library_json(DATA / "seed_library.json")


# ---------- 接口 ----------
@app.get("/health")
def health():
    lib = Library.load(DATA / "seed_library.json")
    return {
        "status": "ok",
        "mode": settings.thermalforge_mode,
        "real_only": settings.is_real,
        "library_cases": len(lib.cases) if not settings.is_real else None,
    }


@app.get("/schema")
def schema():
    """返回参数中枢契约概要：约束向量规格 + 结构参数 schema 清单。"""
    return {
        "constraint_vector": UserInput.vector_spec(),
        "dimension": len(UserInput.vector_spec()),
        "structure_schemas": ["leaf_vein", "channel", "flat"],
        "note": "完整 JSON Schema 见 data/schemas/（export_schemas.py 生成）",
    }


@screening_router.post("/match_user")
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


@screening_router.post("/recommend")
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


@screening_router.get("/library")
def library():
    lib = Library.load(DATA / "seed_library.json")
    return {"count": len(lib.cases), "cases": lib.cases}


@screening_router.post("/generate")
def api_generate(body: ParamsIn):
    try:
        p = from_dict(body.params)
        svg, stats = generate(p)
    except Exception as e:  # noqa
        raise HTTPException(400, f"generate failed: {e}")
    return {"structure_type": p.structure_type, "svg": svg, "geometry": stats.__dict__}


@screening_router.post("/evaluate")
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


@screening_router.post("/compare")
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


@screening_router.post("/optimize/leaf-direction")
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


@screening_router.post("/match")
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
