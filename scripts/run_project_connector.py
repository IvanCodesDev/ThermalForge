"""ThermalForge 项目连接器 CLI。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.models.cold_plate import ColdPlateParams
from core.project_connector import ThermalForgeConnector


def main() -> None:
    parser = argparse.ArgumentParser(description="ThermalForge 项目连接器")
    parser.add_argument("command", choices=["status", "preflight", "create", "verify-change"])
    parser.add_argument("--params-json", default="", help="create 使用的参数 JSON 文件")
    parser.add_argument("--baseline-json", default="", help="verify-change 的基线参数 JSON")
    parser.add_argument("--changed-json", default="", help="verify-change 的变体参数 JSON")
    parser.add_argument("--output-dir", default="data/connector_runs")
    parser.add_argument("--launch-mode", choices=["direct", "explorer"], default="explorer")
    parser.add_argument("--no-execute", action="store_true")
    args = parser.parse_args()

    connector = ThermalForgeConnector(
        ROOT,
        output_dir=args.output_dir,
        launch_mode=args.launch_mode,
    )
    if args.command == "status":
        result = connector.status()
    elif args.command == "preflight":
        result = connector.runner.preflight()
    elif args.command == "create":
        params = ColdPlateParams().to_dict()
        if args.params_json:
            params = json.loads((ROOT / args.params_json).read_text(encoding="utf-8"))
        result = connector.create_model(params, execute=not args.no_execute)
    else:
        if not args.baseline_json or not args.changed_json:
            parser.error("verify-change 需要 --baseline-json 和 --changed-json")
        baseline = json.loads((ROOT / args.baseline_json).read_text(encoding="utf-8"))
        changed = json.loads((ROOT / args.changed_json).read_text(encoding="utf-8"))
        result = connector.verify_model_change(baseline, changed, execute=not args.no_execute)

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    if isinstance(result, dict) and result.get("ok") is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
