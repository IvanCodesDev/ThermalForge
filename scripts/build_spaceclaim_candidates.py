"""生成可由 ANSYS SpaceClaim V252 批量执行的冷板候选脚本。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.engine.cold_plate_optimization import build_cold_plate_candidates
from core.engine.spaceclaim import create_candidate_artifact
from core.models.cold_plate import ColdPlateParams


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 ThermalForge SpaceClaim 冷板候选")
    parser.add_argument("--config", required=True, help="候选空间 JSON")
    parser.add_argument("--output-dir", required=True, help="脚本、STEP 和清单输出目录")
    parser.add_argument("--source-model", default="", help="参考 STEP 路径，仅用于追踪")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    base = ColdPlateParams.from_dict(config.get("base", {}))
    search = config["search_space"]
    candidates = build_cold_plate_candidates(
        base,
        channel_widths=search["channel_width"],
        channel_gaps=search["channel_gap"],
        layer2_thicknesses=search["t_layer2"],
        manifold_lengths=search["manifold_length"],
    )

    artifacts = []
    for index, params in enumerate(candidates, start=1):
        artifact = create_candidate_artifact(
            params,
            args.output_dir,
            candidate_id=f"CP-CAND-{index:04d}",
            source_model_path=args.source_model,
        )
        artifacts.append(artifact.to_dict())

    index_path = Path(args.output_dir) / "candidates.json"
    index_path.write_text(
        json.dumps({"count": len(artifacts), "candidates": artifacts}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Generated {len(artifacts)} SpaceClaim candidate scripts")
    print(str(index_path))


if __name__ == "__main__":
    main()
