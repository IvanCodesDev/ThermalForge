"""ANSYS SpaceClaim V252 冷板候选脚本生成与模型工件追踪。"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Dict

from ..models.cold_plate import ColdPlateParams


@dataclass(frozen=True)
class SpaceClaimArtifact:
    candidate_id: str
    params_hash: str
    script_path: str
    expected_step_path: str
    manifest_path: str
    source_model_path: str = ""
    api_version: str = "V252"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _f(value: float) -> str:
    return format(float(value), ".12g")


def render_cold_plate_script(
    params: ColdPlateParams,
    output_step_path: str,
    manifest_path: str = "",
    api_version: str = "V252",
) -> str:
    """将参数渲染为可在 SpaceClaim 中执行的独立脚本。

    api_version 对应 ANSYS 版本：2025 R2 -> V252，2025 R1 -> V251。
    """
    errors = params.validate()
    if errors:
        raise ValueError("; ".join(errors))

    values = params.to_dict()
    assignments = "\n".join(f"{name} = {_f(value)}" for name, value in values.items())
    output_literal = repr(str(Path(output_step_path)))
    manifest_literal = repr(str(Path(manifest_path))) if manifest_path else "''"
    params_hash_literal = repr(params.parameter_hash())
    api_import = f"from SpaceClaim.Api.{api_version} import *"

    # 渲染期即可确定的关键派生量，作为可读注释写入脚本（便于人工核对几何）
    n_channels_ref = int((values["flow_width_x"] - values["channel_width"]) / (values["channel_width"] + values["channel_gap"])) + 1
    lx_ref = values["margin_left"] + values["flow_width_x"] + values["margin_right"]
    ly_ref = values["margin_bottom"] + values["flow_length_y"] + values["margin_top"]
    tz_ref = values["t_layer1"] + values["t_layer2"] + values["t_layer3"]
    derived_comment = f"# derived: n_channels = {n_channels_ref}, Lx = {lx_ref}, Ly = {ly_ref}, total_thickness = {tz_ref}"

    return f'''# -*- coding: utf-8 -*-
import System
{api_import}

{assignments}
{derived_comment}
output_step_path = {output_literal}
manifest_path = {manifest_literal}
params_hash = {params_hash_literal}

Lx = margin_left + flow_width_x + margin_right
Ly = margin_bottom + flow_length_y + margin_top
flow_x0 = margin_left
flow_x1 = margin_left + flow_width_x
flow_y0 = margin_bottom
flow_y1 = margin_bottom + flow_length_y
z1 = 0.0
z2 = t_layer1
z3 = t_layer1 + t_layer2
z4 = t_layer1 + t_layer2 + t_layer3
channel_pitch = channel_width + channel_gap
inlet_y0 = flow_y0
inlet_y1 = flow_y0 + manifold_length
outlet_y1 = flow_y1
outlet_y0 = flow_y1 - manifold_length
channel_y0 = inlet_y1
channel_y1 = outlet_y0
channel_length = channel_y1 - channel_y0

if channel_width <= 0 or channel_gap <= 0 or channel_length <= 0:
    raise Exception("Invalid channel geometry parameters")

ClearAll()

def get_bodies():
    return [body for body in GetRootPart().Bodies]

def create_block(name, x0, y0, z0, dx, dy, dz):
    if dx <= 0 or dy <= 0 or dz <= 0:
        return None
    bodies_before = get_bodies()
    p1 = Point.Create(MM(x0), MM(y0), MM(z0))
    p2 = Point.Create(MM(x0 + dx), MM(y0 + dy), MM(z0 + dz))
    result = None
    body = None
    try:
        result = BlockBody.Create(p1, p2, ExtrudeType.ForceIndependent)
    except:
        result = BlockBody.Create(p1, p2)
    try:
        if result != None and result.CreatedBody != None:
            body = result.CreatedBody
    except:
        body = None
    if body == None:
        for candidate in get_bodies():
            if candidate not in bodies_before:
                body = candidate
                break
    if body == None:
        raise Exception("Failed to create body: " + name)
    try:
        body.Name = name
    except:
        pass
    return body

create_block("Layer_1_Base_Plate", 0.0, 0.0, z1, Lx, Ly, t_layer1)
create_block("Layer_2_Left_Frame", 0.0, 0.0, z2, flow_x0, Ly, t_layer2)
create_block("Layer_2_Right_Frame", flow_x1, 0.0, z2, Lx - flow_x1, Ly, t_layer2)
create_block("Layer_2_Bottom_Frame", flow_x0, 0.0, z2, flow_width_x, flow_y0, t_layer2)
create_block("Layer_2_Top_Frame", flow_x0, flow_y1, z2, flow_width_x, Ly - flow_y1, t_layer2)

n_channels = int((flow_width_x - channel_width) / channel_pitch) + 1
total_channel_band = (n_channels - 1) * channel_pitch + channel_width
channel_x_start = flow_x0 + (flow_width_x - total_channel_band) / 2.0
channel_x_list = [channel_x_start + i * channel_pitch for i in range(n_channels)]

for i in range(n_channels - 1):
    x_wall0 = channel_x_list[i] + channel_width
    create_block(
        "Layer_2_Channel_Wall_%03d" % (i + 1),
        x_wall0, channel_y0, z2,
        channel_gap, channel_length, t_layer2
    )

create_block("Layer_3_Cover_Left_Block", 0.0, 0.0, z3, flow_x0, Ly, t_layer3)
create_block("Layer_3_Cover_Right_Block", flow_x1, 0.0, z3, Lx - flow_x1, Ly, t_layer3)
create_block("Layer_3_Cover_Bottom_Frame", flow_x0, 0.0, z3, flow_width_x, inlet_y0, t_layer3)
create_block("Layer_3_Cover_Center_Block", flow_x0, inlet_y1, z3, flow_width_x, outlet_y0 - inlet_y1, t_layer3)
create_block("Layer_3_Cover_Top_Frame", flow_x0, outlet_y1, z3, flow_width_x, Ly - outlet_y1, t_layer3)

body_count = len(get_bodies())
print("ThermalForge SpaceClaim candidate generated")
print("params_hash=" + params_hash)
print("outer_size_mm=%.6f,%.6f,%.6f" % (Lx, Ly, z4))
print("n_channels=%d" % n_channels)
print("body_count=%d" % body_count)

options = ExportOptions.Create()
DocumentSave.Execute(output_step_path, options)

if manifest_path:
    step_path_posix = output_step_path.replace("\\\\", "/")
    manifest = '{{"status":"generated","params_hash":"%s","body_count":%d,"n_channels":%d,"outer_size_mm":[%.9f,%.9f,%.9f],"step_path":"%s"}}' % (
        params_hash,
        body_count,
        n_channels,
        Lx,
        Ly,
        z4,
        step_path_posix,
    )
    writer = System.IO.StreamWriter(manifest_path, False)
    try:
        writer.Write(manifest)
    finally:
        writer.Close()

try:
    Application.Exit()
except Exception:
    pass
'''


def create_candidate_artifact(
    params: ColdPlateParams,
    output_dir: str | Path,
    candidate_id: str | None = None,
    source_model_path: str = "",
    api_version: str = "V252",
) -> SpaceClaimArtifact:
    """创建一个可复现候选的 SpaceClaim 脚本和运行前清单。"""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    params_hash = params.parameter_hash()
    cid = candidate_id or f"CP-{params_hash[:12]}"
    script_path = output / f"{cid}.py"
    step_path = output / f"{cid}.stp"
    manifest_path = output / f"{cid}.json"
    script = render_cold_plate_script(
        params, str(step_path), str(manifest_path), api_version=api_version
    )
    script_path.write_text(script, encoding="utf-8", newline="\n")

    pending_manifest = {
        "candidate_id": cid,
        "status": "script_ready",
        "api_version": api_version,
        "params": params.to_dict(),
        "derived": params.derived(),
        "params_hash": params_hash,
        "script_sha256": sha256(script.encode("utf-8")).hexdigest(),
        "script_path": str(script_path),
        "expected_step_path": str(step_path),
        "source_model_path": source_model_path,
    }
    manifest_path.write_text(
        json.dumps(pending_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return SpaceClaimArtifact(
        candidate_id=cid,
        params_hash=params_hash,
        script_path=str(script_path),
        expected_step_path=str(step_path),
        manifest_path=str(manifest_path),
        source_model_path=source_model_path,
        api_version=api_version,
    )
