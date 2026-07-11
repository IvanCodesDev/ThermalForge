from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.models.cold_plate import ColdPlateParams
from core.project_connector import ThermalForgeConnector


class FakeRunner:
    available = True
    executable = r"C:\Program Files\ANSYS Inc\v251\scdm\SpaceClaim.exe"
    api_version = "V251"
    launch_mode = "explorer"
    license_feature = "disco_level1"

    def run(self, script_path: str):
        script = Path(script_path)
        manifest = json.loads(script.with_suffix(".json").read_text(encoding="utf-8"))
        script.with_suffix(".stp").write_bytes(
            (manifest["params_hash"] + json.dumps(manifest["derived"], sort_keys=True)).encode("utf-8")
        )
        manifest["status"] = "generated"
        script.with_suffix(".json").write_text(json.dumps(manifest), encoding="utf-8")
        return {
            "available": True,
            "status": "ok",
            "step_path": str(script.with_suffix(".stp")),
            "manifest_path": str(script.with_suffix(".json")),
        }


def make_connector(tmp_path: Path) -> ThermalForgeConnector:
    return ThermalForgeConnector(
        tmp_path,
        output_dir="data/runs",
        runner=FakeRunner(),
    )


def test_connector_rejects_path_escape(tmp_path: Path):
    connector = make_connector(tmp_path)
    with pytest.raises(ValueError, match="项目边界"):
        connector.read_text("../outside.txt")


def test_connector_lists_reads_and_exactly_replaces(tmp_path: Path):
    source = tmp_path / "sample.py"
    source.write_text("value = 1\n", encoding="utf-8")
    connector = make_connector(tmp_path)

    assert connector.list_files(patterns=["*.py"]) == ["sample.py"]
    assert connector.read_text("sample.py") == "value = 1\n"
    result = connector.replace_text("sample.py", "value = 1", "value = 2")
    assert result["replacements"] == 1
    assert source.read_text(encoding="utf-8") == "value = 2\n"


def test_connector_generates_v251_artifact(tmp_path: Path):
    connector = make_connector(tmp_path)
    result = connector.create_model(ColdPlateParams().to_dict(), execute=False)
    script = Path(result["artifact"]["script_path"]).read_text(encoding="utf-8")

    assert result["artifact"]["api_version"] == "V251"
    assert "from SpaceClaim.Api.V251 import *" in script
    assert result["derived"]["n_channels"] == 150


def test_connector_verifies_parameter_driven_model_change(tmp_path: Path):
    connector = make_connector(tmp_path)
    baseline = ColdPlateParams(flow_length_y=40.0, channel_width=0.10, channel_gap=0.10).to_dict()
    changed = ColdPlateParams(flow_length_y=40.0, channel_width=0.12, channel_gap=0.10).to_dict()

    result = connector.verify_model_change(baseline, changed, execute=True)

    assert result["ok"] is True
    assert all(result["checks"].values())
    assert result["derived_diff"]["n_channels"] == {"before": 150, "after": 136}
    assert result["baseline"]["execution"]["status"] == "ok"
    assert result["changed"]["execution"]["status"] == "ok"
