"""运行冷板参数化优化闭环。

默认离线模式（无需 ANSYS）：
    python scripts/run_cold_plate_optimization.py --mode grid --backend lumped

可选：生成 SpaceClaim 候选脚本并（若本机已安装授权 ANSYS）无头执行：
    python scripts/run_cold_plate_optimization.py --mode sample --samples 40 \
        --backend external --results-json ansys_out/results.json --spaceclaim
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.engine.cold_plate_optimization import (
    run_cold_plate_loop,
    write_loop_report,
)
from core.engine.cold_plate_simulation import (
    ColdPlateExternalBackend,
    ColdPlateLumpedBackend,
)
from core.engine.spaceclaim import create_candidate_artifact
from core.engine.spaceclaim_runner import SpaceClaimRunner
from core.models.cold_plate import ColdPlateParams


def main() -> None:
    parser = argparse.ArgumentParser(description="ThermalForge 冷板参数化优化闭环")
    parser.add_argument("--config", required=True, help="候选空间 JSON（同 build_spaceclaim_candidates）")
    parser.add_argument("--mode", choices=["grid", "sample"], default="grid")
    parser.add_argument("--samples", type=int, default=30, help="sample 模式下的采样数")
    parser.add_argument("--backend", choices=["lumped", "external"], default="lumped")
    parser.add_argument("--results-json", default="", help="external 后端使用的 ANSYS 结果 JSON")
    parser.add_argument("--spaceclaim", action="store_true", help="尝试无头执行 SpaceClaim（需已安装授权）")
    parser.add_argument("--output-dir", default="data/loop_output", help="报告与脚本输出目录")
    parser.add_argument("--api-version", default="V252", help="SpaceClaim API 版本（R2=V252, R1=V251）")
    parser.add_argument("--source-model", default="", help="参考 STEP 路径，仅追踪")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    base = ColdPlateParams.from_dict(config.get("base", {}))
    search_space = config["search_space"]

    if args.backend == "external":
        backend = ColdPlateExternalBackend(results_path=args.results_json)
    else:
        backend = ColdPlateLumpedBackend()

    runner = SpaceClaimRunner() if args.spaceclaim else None
    if args.spaceclaim:
        if not runner or not runner.available:
            print("[warn] 未检测到已安装的 SpaceClaim，将仅生成脚本而不执行。")
        else:
            pre = runner.preflight()
            if pre["ok"]:
                print(
                    f"[ok] SpaceClaim 自检通过（api_version={runner.api_version}），"
                    f"将无头执行候选脚本。"
                )
                # 用安装推断出的 API 版本覆盖默认 V252，确保生成脚本与本地 SpaceClaim 匹配
                args.api_version = runner.api_version
            else:
                print(
                    f"[warn] SpaceClaim 自检未通过：{pre['reason']}；"
                    f"将仅生成脚本而不执行（避免逐候选空等超时）。"
                )
                runner = None

    loop_result = run_cold_plate_loop(
        base=base,
        search_space=search_space,
        backend=backend,
        context=None,
        mode=args.mode,
        n_samples=args.samples,
        candidate_builder=create_candidate_artifact,
        spaceclaim_runner=runner,
        source_model_path=args.source_model,
        api_version=args.api_version,
    )

    reports = write_loop_report(args.output_dir, loop_result)
    best = loop_result.get("best")
    print(f"闭环完成：{loop_result['count']} 个候选，后端={loop_result['backend']}")
    if best is not None:
        obj = best.get("objectives") or {}
        print(
            f"最优候选 {best['candidate_id']} | 成本={best['evaluation']['weighted_cost']} | "
            f"温度={obj.get('max_temperature_c')}°C | 压降={obj.get('pressure_drop_pa')}Pa | "
            f"质量={obj.get('mass_g')}g"
        )
    print(f"报告: {reports['report_json']}")
    print(f"摘要: {reports['report_md']}")


if __name__ == "__main__":
    main()
