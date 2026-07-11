from __future__ import annotations

import hashlib
import json
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "pche_pattern_batch"

BASE_PARAMS = {
    "api_version": "V251",
    "flow_width_x_mm": 30.0,
    "flow_length_y_mm": 40.0,
    "channel_depth_mm": 0.25,
    "base_thickness_mm": 1.0,
    "cover_thickness_mm": 1.0,
    "manifold_length_mm": 8.0,
    "margin_mm": 2.0,
    "feature_width_mm": 1.2,
    "lane_count": 6,
    "segment_length_mm": 4.0,
    "chevron_amplitude_mm": 2.4,
    "wave_amplitude_mm": 1.6,
    "spindle_length_mm": 4.0,
    "spindle_width_mm": 0.8,
}

CANDIDATES = [
    ("CHEVRON-ALIGNED", "chevron", "aligned"),
    ("CHEVRON-STAGGERED", "chevron", "staggered"),
    ("WAVE-ALIGNED", "wave", "aligned"),
    ("WAVE-STAGGERED", "wave", "staggered"),
    ("SPINDLE-ALIGNED", "spindle", "aligned"),
    ("SPINDLE-STAGGERED", "spindle", "staggered"),
    ("VEIN-DEMO", "vein", "branching"),
]

COMMON = dedent(
    r'''
    # -*- coding: utf-8 -*-
    from SpaceClaim.Api.V251 import *
    import math

    flow_width_x = 30.0
    flow_length_y = 40.0
    channel_depth = 0.25
    base_thickness = 1.0
    cover_thickness = 1.0
    manifold_length = 8.0
    margin = 2.0
    feature_width = 1.2
    lane_count = 6
    segment_length = 4.0
    chevron_amplitude = 2.4
    wave_amplitude = 1.6
    spindle_length = 4.0
    spindle_width = 0.8

    Lx = flow_width_x + 2.0 * margin
    Ly = flow_length_y + 2.0 * margin
    flow_x0 = margin
    flow_y0 = margin
    channel_y0 = flow_y0 + manifold_length
    channel_y1 = flow_y0 + flow_length_y - manifold_length
    active_length = channel_y1 - channel_y0

    ClearAll()

    def bodies():
        return [body for body in GetRootPart().Bodies]

    def block(name, x0, y0, z0, dx, dy, dz):
        if dx <= 0 or dy <= 0 or dz <= 0:
            return None
        before = bodies()
        p1 = Point.Create(MM(x0), MM(y0), MM(z0))
        p2 = Point.Create(MM(x0 + dx), MM(y0 + dy), MM(z0 + dz))
        try:
            result = BlockBody.Create(p1, p2, ExtrudeType.ForceIndependent)
        except:
            result = BlockBody.Create(p1, p2)
        body = None
        try:
            body = result.CreatedBody
        except:
            pass
        if body == None:
            for candidate in bodies():
                if candidate not in before:
                    body = candidate
                    break
        if body != None:
            try:
                body.Name = name
            except:
                pass
        return body

    def add_envelope(prefix):
        block(prefix + '_Base', 0.0, 0.0, 0.0, Lx, Ly, base_thickness)
        block(prefix + '_Left_Frame', 0.0, 0.0, base_thickness, margin, Ly, channel_depth)
        block(prefix + '_Right_Frame', margin + flow_width_x, 0.0, base_thickness, margin, Ly, channel_depth)
        block(prefix + '_Bottom_Frame', margin, 0.0, base_thickness, flow_width_x, margin, channel_depth)
        block(prefix + '_Top_Frame', margin, margin + flow_length_y, base_thickness, flow_width_x, margin, channel_depth)

    def finish(candidate_id, pattern, arrangement):
        model_bodies = bodies()
        print('BATCH MODEL READY: %s pattern=%s arrangement=%s bodies=%d' % (candidate_id, pattern, arrangement, len(model_bodies)))
        print('PARAMETERS: depth=0.250 mm base=1.000 mm manifold=8.000 mm active_length=%.3f mm' % active_length)
        try:
            ViewHelper.SetViewMode(InteractionMode.Solid)
        except:
            pass
        try:
            ViewHelper.ZoomToEntity(Selection.Create(model_bodies))
        except Exception as error:
            print('VIEW WARNING: %s' % error)
    '''
).strip()


def pattern_code(candidate_id: str, pattern: str, arrangement: str) -> str:
    phase_rule = "0.0" if arrangement == "aligned" else "(math.pi if lane % 2 else 0.0)"
    row_shift = "0.0" if arrangement == "aligned" else "(0.5 * segment_length if lane % 2 else 0.0)"
    spindle_shift = "0.0" if arrangement == "aligned" else "(0.5 * x_pitch if row % 2 else 0.0)"

    if pattern == "chevron":
        geometry = f'''
add_envelope('{candidate_id}')
pitch = flow_width_x / lane_count
rows = int(active_length / segment_length)
for lane in range(lane_count):
    center = flow_x0 + (lane + 0.5) * pitch
    y_shift = {row_shift}
    for row in range(rows):
        half_period = 3
        saw = row % (2 * half_period)
        tri = saw if saw <= half_period else 2 * half_period - saw
        offset = chevron_amplitude * (tri / float(half_period) - 0.5)
        x = center + offset - feature_width / 2.0
        x = max(flow_x0 + 0.4, min(flow_x0 + flow_width_x - 0.4 - feature_width, x))
        y = channel_y0 + row * segment_length + y_shift
        if y + segment_length * 0.82 <= channel_y1:
            block('{candidate_id}_L%02d_S%02d' % (lane + 1, row + 1), x, y, base_thickness, feature_width, segment_length * 0.82, channel_depth)
'''
    elif pattern == "wave":
        geometry = f'''
add_envelope('{candidate_id}')
pitch = flow_width_x / lane_count
rows = int(active_length / segment_length)
for lane in range(lane_count):
    center = flow_x0 + (lane + 0.5) * pitch
    phase_offset = {phase_rule}
    for row in range(rows):
        phase = 2.0 * math.pi * row / 6.0 + phase_offset
        x = center + wave_amplitude * math.sin(phase) - feature_width / 2.0
        x = max(flow_x0 + 0.4, min(flow_x0 + flow_width_x - 0.4 - feature_width, x))
        y = channel_y0 + row * segment_length
        block('{candidate_id}_L%02d_S%02d' % (lane + 1, row + 1), x, y, base_thickness, feature_width, segment_length * 0.82, channel_depth)
'''
    elif pattern == "spindle":
        geometry = f'''
add_envelope('{candidate_id}')
rows = 6
cols = 6
x_pitch = flow_width_x / cols
y_pitch = active_length / rows
for row in range(rows):
    stagger = {spindle_shift}
    for col in range(cols):
        x = flow_x0 + col * x_pitch + stagger + 0.5 * (x_pitch - spindle_length)
        y = channel_y0 + row * y_pitch + 0.5 * (y_pitch - spindle_width)
        if x >= flow_x0 + 0.3 and x + spindle_length <= flow_x0 + flow_width_x - 0.3:
            block('{candidate_id}_R%02d_C%02d' % (row + 1, col + 1), x, y, base_thickness, spindle_length, spindle_width, channel_depth)
'''
    else:
        geometry = f'''
add_envelope('{candidate_id}')
trunk_x = flow_x0 + flow_width_x / 2.0 - feature_width / 2.0
block('{candidate_id}_Trunk', trunk_x, channel_y0, base_thickness, feature_width, active_length, channel_depth)
levels = 5
for level in range(levels):
    y = channel_y0 + (level + 0.7) * active_length / levels
    branch_length = 0.38 * flow_width_x
    branch_height = 0.55
    for side in [-1, 1]:
        steps = 4
        for step in range(steps):
            dx = branch_length / steps
            x = trunk_x + (feature_width if side > 0 else -dx) + side * step * dx
            yy = y + step * 0.8
            block('{candidate_id}_L%02d_%s_S%02d' % (level + 1, 'R' if side > 0 else 'L', step + 1), x, yy, base_thickness, dx, branch_height, channel_depth)
'''

    return COMMON + "\n\n" + geometry.strip() + f"\n\nfinish('{candidate_id}', '{pattern}', '{arrangement}')\n"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "batch_id": "PCHE-7-CONFIG-V251",
        "description": "Six aligned/staggered pattern candidates plus one vein demonstration",
        "base_parameters": BASE_PARAMS,
        "candidates": [],
    }
    for candidate_id, pattern, arrangement in CANDIDATES:
        script = pattern_code(candidate_id, pattern, arrangement)
        path = OUTPUT / f"{candidate_id.lower()}.py"
        path.write_text(script, encoding="utf-8")
        digest = hashlib.sha256(script.encode("utf-8")).hexdigest()
        manifest["candidates"].append(
            {
                "candidate_id": candidate_id,
                "pattern": pattern,
                "arrangement": arrangement,
                "script": path.name,
                "script_sha256": digest,
                "expected_step": f"{candidate_id.lower()}.stp",
            }
        )
    (OUTPUT / "batch_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"output": str(OUTPUT), "count": len(CANDIDATES)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
