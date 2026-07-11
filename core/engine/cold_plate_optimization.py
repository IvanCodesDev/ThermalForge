"""微流道冷板候选生成和仿真反馈排序。"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from itertools import product
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from ..models.cold_plate import ColdPlateParams


@dataclass(frozen=True)
class ColdPlateObjectives:
    max_temperature_c: float
    pressure_drop_pa: float
    mass_g: float
    max_stress_mpa: float | None = None


@dataclass(frozen=True)
class ColdPlateConstraints:
    max_temperature_c: float = 80.0
    max_pressure_drop_pa: float = 1000.0
    max_stress_mpa: float = 120.0


def build_cold_plate_candidates(
    base: ColdPlateParams,
    channel_widths: Iterable[float],
    channel_gaps: Iterable[float],
    layer2_thicknesses: Iterable[float],
    manifold_lengths: Iterable[float],
) -> List[ColdPlateParams]:
    candidates: List[ColdPlateParams] = []
    for width, gap, layer2, manifold in product(
        channel_widths,
        channel_gaps,
        layer2_thicknesses,
        manifold_lengths,
    ):
        item = replace(
            base,
            channel_width=float(width),
            channel_gap=float(gap),
            t_layer2=float(layer2),
            manifold_length=float(manifold),
        )
        if not item.validate():
            candidates.append(item)
    return candidates


def evaluate_objectives(
    objectives: ColdPlateObjectives,
    constraints: ColdPlateConstraints | None = None,
) -> Dict[str, Any]:
    """将外部 CFD/FEA 指标转换为可排序的约束惩罚目标。分数越低越好。"""
    limits = constraints or ColdPlateConstraints()
    violations = {
        "temperature": max(0.0, objectives.max_temperature_c - limits.max_temperature_c),
        "pressure_drop": max(0.0, objectives.pressure_drop_pa - limits.max_pressure_drop_pa),
        "stress": max(
            0.0,
            (objectives.max_stress_mpa or 0.0) - limits.max_stress_mpa,
        ),
    }
    feasible = all(value == 0.0 for value in violations.values())
    constraint_penalty = (
        1000.0 * violations["temperature"]
        + 10.0 * violations["pressure_drop"]
        + 100.0 * violations["stress"]
    )
    weighted_cost = (
        objectives.max_temperature_c
        + 0.005 * objectives.pressure_drop_pa
        + 0.02 * objectives.mass_g
        + constraint_penalty
    )
    return {
        "feasible": feasible,
        "constraint_violations": violations,
        "weighted_cost": round(weighted_cost, 6),
        "objectives": {
            "max_temperature_c": objectives.max_temperature_c,
            "pressure_drop_pa": objectives.pressure_drop_pa,
            "mass_g": objectives.mass_g,
            "max_stress_mpa": objectives.max_stress_mpa,
        },
    }


def rank_simulation_results(results: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """对外部仿真回传结果排序；可行候选优先，其次按加权成本。"""
    ranked = list(results)
    ranked.sort(key=lambda item: (not bool(item["evaluation"]["feasible"]), item["evaluation"]["weighted_cost"]))
    return ranked


# ---------------------------------------------------------------------------
# 采样搜索：在合法参数空间内生成候选（网格之外的自动变化策略）
# ---------------------------------------------------------------------------

def _sample_float(rng, low: float, high: float) -> float:
    return low + (high - low) * rng.random()


def sample_cold_plate_candidates(
    base: ColdPlateParams,
    search_space: Dict[str, List[float]],
    n_samples: int = 30,
    seed: int = 7,
) -> List[ColdPlateParams]:
    """在合法参数空间内随机采样。

    search_space 形如 {"channel_width": [0.08, 0.12], "t_layer2": [0.2, 0.3], ...}，
    每个键给出该维度的取值范围 [low, high]。采样后只保留 validate() 通过的候选。
    与 build_cold_plate_candidates（网格）并存：网格保证可复现边界覆盖，采样
    探索网格之间的连续空间。
    """
    import random

    bounds = {k: (float(v[0]), float(v[1])) for k, v in search_space.items() if len(v) >= 2}
    if not bounds:
        return []

    rng = random.Random(seed)
    candidates: List[ColdPlateParams] = []
    seen_hashes = set()
    attempts = 0
    max_attempts = max(n_samples * 20, 200)
    while len(candidates) < n_samples and attempts < max_attempts:
        attempts += 1
        values = {k: _sample_float(rng, lo, hi) for k, (lo, hi) in bounds.items()}
        try:
            item = replace(base, **values)
        except Exception:
            continue
        if not item.validate():
            if item.parameter_hash() not in seen_hashes:
                seen_hashes.add(item.parameter_hash())
                candidates.append(item)
    return candidates


# ---------------------------------------------------------------------------
# 闭环编排：参数 -> 候选 -> (SpaceClaim) -> 仿真 -> 评分 -> 排序 -> 报告
# ---------------------------------------------------------------------------

def run_cold_plate_loop(
    base: ColdPlateParams,
    search_space: Dict[str, List[float]],
    backend: Any,
    context: Any = None,
    mode: str = "grid",
    n_samples: int = 30,
    seed: int = 7,
    candidate_builder: Optional[Callable[[ColdPlateParams, str, str], Any]] = None,
    spaceclaim_runner: Any = None,
    source_model_path: str = "",
    api_version: str = "V252",
) -> Dict[str, Any]:
    """运行一次“参数自动变化 -> 仿真反馈 -> 排序”闭环。

    参数:
        backend: ColdPlateSimulationBackend 实例（lumped 或 external）。
        context: 传给 backend.evaluate 的上下文（如 SimulationContext）。
        mode: "grid" 用 build_cold_plate_candidates；"sample" 用 sample_cold_plate_candidates。
        candidate_builder: 可选，签名 (params, output_dir, candidate_id) -> artifact；
            用于渲染 SpaceClaim 脚本并生成运行前清单；不传则跳过脚本生成。
        spaceclaim_runner: 可选，已安装 SpaceClaim 时的无头执行器；未传或不可用则跳过执行。
        api_version: 渲染脚本使用的 SpaceClaim API 版本。
    """
    if mode == "sample":
        candidates = sample_cold_plate_candidates(base, search_space, n_samples, seed)
    else:
        candidates = build_cold_plate_candidates(
            base,
            channel_widths=search_space.get("channel_width", [base.channel_width]),
            channel_gaps=search_space.get("channel_gap", [base.channel_gap]),
            layer2_thicknesses=search_space.get("t_layer2", [base.t_layer2]),
            manifold_lengths=search_space.get("manifold_length", [base.manifold_length]),
        )

    results: List[Dict[str, Any]] = []
    params_by_id: Dict[str, Dict[str, Any]] = {}
    for index, params in enumerate(candidates, start=1):
        cid = f"CP-CAND-{index:04d}"
        entry: Dict[str, Any] = {
            "candidate_id": cid,
            "params": params.to_dict(),
            "derived": params.derived(),
            "params_hash": params.parameter_hash(),
        }
        params_by_id[cid] = params.to_dict()

        # 1) 渲染 SpaceClaim 候选脚本（可选）
        if candidate_builder is not None:
            try:
                artifact = candidate_builder(
                    params, str(Path.cwd() / "data" / "loop_spaceclaim"), cid,
                    source_model_path, api_version,
                )
                entry["script_path"] = artifact.script_path
                entry["expected_step_path"] = artifact.expected_step_path
                entry["manifest_path"] = artifact.manifest_path
            except Exception as exc:  # 脚本渲染失败也记录，不中断闭环
                entry["script_error"] = str(exc)

        # 2) 无头执行 SpaceClaim（可选，未安装则跳过）
        if spaceclaim_runner is not None:
            try:
                run_result = spaceclaim_runner.run(entry.get("script_path", ""))
                entry["spaceclaim"] = run_result
            except Exception as exc:
                entry["spaceclaim_error"] = str(exc)

        # 3) 仿真指标
        try:
            objectives = backend.evaluate(params, context)
            entry["objectives"] = {
                "max_temperature_c": objectives.max_temperature_c,
                "pressure_drop_pa": objectives.pressure_drop_pa,
                "mass_g": objectives.mass_g,
                "max_stress_mpa": objectives.max_stress_mpa,
            }
            evaluation = evaluate_objectives(
                objectives,
                constraints=getattr(context, "constraints", None) if context is not None else None,
            )
        except Exception as exc:
            entry["objectives"] = None
            evaluation = {
                "feasible": False,
                "constraint_violations": {},
                "weighted_cost": 1.0e9,
                "objectives": None,
                "error": str(exc),
            }
        entry["evaluation"] = evaluation
        results.append(entry)

    ranked = rank_simulation_results(results)
    best = ranked[0] if ranked else None
    return {
        "mode": mode,
        "backend": getattr(backend, "name", "unknown"),
        "count": len(results),
        "best": best,
        "ranked": ranked,
        "params_by_id": params_by_id,
    }


def write_loop_report(out_dir: str | Path, loop_result: Dict[str, Any]) -> Dict[str, str]:
    """写出闭环结果：report.json（机器可读）+ report.md（可读摘要）。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ranked = loop_result.get("ranked", [])
    best = loop_result.get("best")

    report_json = out / "report.json"
    report_json.write_text(
        json.dumps(loop_result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    lines = [
        "# 冷板参数化优化闭环报告",
        "",
        f"- 模式: {loop_result.get('mode')}",
        f"- 仿真后端: {loop_result.get('backend')}",
        f"- 候选数: {loop_result.get('count')}",
        "",
        "## 最优候选",
        "",
    ]
    if best is not None:
        lines.append(f"- candidate_id: {best.get('candidate_id')}")
        lines.append(f"- weighted_cost: {best['evaluation']['weighted_cost']}")
        lines.append(f"- feasible: {best['evaluation']['feasible']}")
        obj = best.get("objectives") or {}
        lines.append(f"- max_temperature_c: {obj.get('max_temperature_c')}")
        lines.append(f"- pressure_drop_pa: {obj.get('pressure_drop_pa')}")
        lines.append(f"- mass_g: {obj.get('mass_g')}")
        lines.append("")
        lines.append("### 最优参数")
        for k, v in (best.get("params") or {}).items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("（无候选）")

    lines.append("")
    lines.append("## 排名（前 20）")
    lines.append("")
    lines.append("| 排名 | candidate_id | 成本 | 可行 | 温度°C | 压降Pa | 质量g |")
    lines.append("|---|---|---|---|---|---|---|")
    for rank, item in enumerate(ranked[:20], start=1):
        obj = item.get("objectives") or {}
        lines.append(
            f"| {rank} | {item.get('candidate_id')} | {item['evaluation']['weighted_cost']} | "
            f"{item['evaluation']['feasible']} | {obj.get('max_temperature_c')} | "
            f"{obj.get('pressure_drop_pa')} | {obj.get('mass_g')} |"
        )

    report_md = out / "report.md"
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"report_json": str(report_json), "report_md": str(report_md)}
