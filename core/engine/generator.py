"""
结构生成器（程序化生成 · 参数即标签主路径）

输入一套参数 → 输出：
  1) SVG 字符串（可直接前端渲染 / 存盘）
  2) 派生几何量 GeometryStats（有效换热面积、材料体积等），供热路模型消费

三种结构：
  - 叶脉热桥  generate_leaf_vein
  - pin-fin/流道  generate_channel
  - 平板基线  generate_flat

坐标系：SVG viewBox 统一 0 0 200 200，结构居中。
所有几何量以 mm 为单位（length_scale 即物理边长）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

from ..models.schema import LeafVeinParams, ChannelParams, FlatBaselineParams


@dataclass
class GeometryStats:
    """派生几何量（供热路模型）。"""
    base_area_mm2: float       # 结构占位底面积
    eff_area_mm2: float        # 有效换热表面积（越大散热越好）
    material_vol_mm3: float     # 固体材料体积（决定质量）
    spread_factor: float        # 热扩散能力 0-1（越大热点越均匀）
    area_enhance: float         # 相对平板的换热面积增益倍数


SVG_HEADER = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">'
SVG_BG = '<rect x="0" y="0" width="200" height="200" fill="#f6f8fa"/>'


def _svg_wrap(body: str, title: str) -> str:
    label = f'<text x="6" y="194" font-family="sans-serif" font-size="9" fill="#57606a">{title}</text>'
    return SVG_HEADER + SVG_BG + body + label + "</svg>"


# ---------------- 叶脉热桥 ----------------
def _leaf_branches(x: float, y: float, angle: float, length: float,
                   width: float, level: int, p: LeafVeinParams,
                   segs: List[str]) -> None:
    """递归画分形叶脉。"""
    if level <= 0 or length < 1.5:
        return
    rad = math.radians(angle)
    x2 = x + length * math.cos(rad)
    y2 = y - length * math.sin(rad)
    segs.append(
        f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="#c0392b" stroke-width="{max(width,0.6):.2f}" stroke-linecap="round"/>'
    )
    nxt_len = length * p.branch_ratio
    nxt_w = width * p.branch_ratio
    da = p.branch_angle * (1.0 + (0.5 - p.symmetry) * 0.4)
    _leaf_branches(x2, y2, angle + da, nxt_len, nxt_w, level - 1, p, segs)
    _leaf_branches(x2, y2, angle - da, nxt_len, nxt_w, level - 1, p, segs)


def generate_leaf_vein(p: LeafVeinParams) -> Tuple[str, GeometryStats]:
    segs: List[str] = []
    direction_rad = math.radians(p.flow_direction_deg)
    cx = 100.0 - 75.0 * math.cos(direction_rad)
    cy = 100.0 + 75.0 * math.sin(direction_rad)
    # 主干围绕用户指定主流向铺开；90° 为由下向上。
    tc = max(1, p.trunk_count)
    spread = 120.0
    trunk_len = 55.0 * (0.6 + 0.4 * p.tortuosity / 3.0)
    for i in range(tc):
        a = p.flow_direction_deg + (spread * (i / max(1, tc - 1) - 0.5) if tc > 1 else 0.0)
        _leaf_branches(cx, cy, a, trunk_len, p.width_trunk, p.branch_levels, p, segs)
    if p.boundary_shape == "circle":
        segs.insert(0, '<circle cx="100" cy="100" r="92" fill="none" stroke="#d0d7de" stroke-dasharray="4 3"/>')
    else:
        segs.insert(0, '<rect x="8" y="8" width="184" height="184" fill="none" stroke="#d0d7de" stroke-dasharray="4 3"/>')

    # 几何量估算
    base_area = p.length_scale ** 2 * (math.pi / 4 if p.boundary_shape == "circle" else 1.0)
    avg_w = (p.width_trunk + p.width_tip) / 2.0
    total_len_mm = tc * trunk_len * (2 ** p.branch_levels) * 0.4  # 近似总脉长(尺度)
    total_len_mm *= p.length_scale / 60.0
    # 有效换热面积 = 底面(全) + 叶脉侧壁扩展；叶脉是最强热扩散结构
    vein_surface = total_len_mm * p.channel_depth * 2.0
    eff_area = base_area + vein_surface
    material_vol = total_len_mm * avg_w * p.channel_depth
    spread_factor = min(1.0, 0.6 + 0.07 * p.branch_levels + 0.1 * (1 - p.density_gradient))
    stats = GeometryStats(
        base_area_mm2=base_area,
        eff_area_mm2=eff_area,
        material_vol_mm3=material_vol,
        spread_factor=spread_factor,
        area_enhance=eff_area / (base_area + 1e-6),
    )
    return _svg_wrap("".join(segs), "leaf-vein heat bridge"), stats


# ---------------- pin-fin / 流道 ----------------
def generate_channel(p: ChannelParams) -> Tuple[str, GeometryStats]:
    segs: List[str] = []
    if p.boundary_shape == "circle":
        segs.append('<circle cx="100" cy="100" r="92" fill="none" stroke="#d0d7de" stroke-dasharray="4 3"/>')
    else:
        segs.append('<rect x="8" y="8" width="184" height="184" fill="none" stroke="#d0d7de" stroke-dasharray="4 3"/>')

    base_area = p.length_scale ** 2
    if p.channel_pattern == "pinfin":
        # 圆柱针阵列
        n = max(1, p.channel_count)
        cols = max(1, int(round(math.sqrt(n))))
        rows = max(1, math.ceil(n / cols))
        margin = 20.0
        span = 160.0
        r = max(1.5, min(span / cols / 2.5, 6.0))
        placed = 0
        for ri in range(rows):
            for ci in range(cols):
                if placed >= n:
                    break
                x = margin + span * (ci + 0.5) / cols
                y = margin + span * (ri + 0.5) / rows
                segs.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#2980b9"/>')
                placed += 1
        # 每根针侧壁 π*d*h + 顶面 π*(d/2)^2；d=channel_width 视为针径
        pin_area = n * (math.pi * p.channel_width * p.channel_height + math.pi * (p.channel_width / 2) ** 2)
        eff_area = base_area + pin_area
        material_vol = n * math.pi * (p.channel_width / 2) ** 2 * p.channel_height
        spread_factor = min(1.0, 0.5 + 0.002 * n)
        title = "pin-fin array"
    elif p.channel_pattern == "serpentine":
        turns = max(1, p.serpentine_turns or 6)
        margin = 20.0
        span = 160.0
        step = span / turns
        path = f'M {margin} {margin} '
        for t in range(turns):
            y = margin + t * step
            if t % 2 == 0:
                path += f'H {margin+span} V {y+step:.1f} '
            else:
                path += f'H {margin} V {y+step:.1f} '
        segs.append(f'<path d="{path}" fill="none" stroke="#2980b9" stroke-width="{max(2,p.channel_width*2):.1f}"/>')
        chan_len = turns * p.channel_length
        eff_area = base_area + chan_len * (p.channel_width + p.channel_height) * 2
        material_vol = chan_len * p.channel_width * p.channel_height
        spread_factor = 0.75
        title = "serpentine channel"
    else:  # parallel / manifold / topo_opt → 并行流道
        n = max(2, min(p.channel_count, 40))
        margin = 20.0
        span = 160.0
        for i in range(n):
            x = margin + span * (i + 0.5) / n
            segs.append(f'<line x1="{x:.1f}" y1="{margin}" x2="{x:.1f}" y2="{margin+span}" '
                        f'stroke="#2980b9" stroke-width="{max(1.5,p.channel_width*1.5):.1f}"/>')
        chan_len = n * p.channel_length
        eff_area = base_area + chan_len * (p.channel_width + p.channel_height) * 2
        material_vol = chan_len * p.channel_width * p.channel_height
        spread_factor = 0.6
        title = f"{p.channel_pattern} channel"

    stats = GeometryStats(
        base_area_mm2=base_area,
        eff_area_mm2=eff_area,
        material_vol_mm3=material_vol,
        spread_factor=spread_factor,
        area_enhance=eff_area / (base_area + 1e-6),
    )
    return _svg_wrap("".join(segs), title), stats


# ---------------- 平板基线 ----------------
def generate_flat(p: FlatBaselineParams) -> Tuple[str, GeometryStats]:
    if p.boundary_shape == "circle":
        body = '<circle cx="100" cy="100" r="80" fill="#95a5a6" stroke="#7f8c8d"/>'
    else:
        body = '<rect x="30" y="30" width="140" height="140" fill="#95a5a6" stroke="#7f8c8d"/>'
    base_area = p.length_scale ** 2
    stats = GeometryStats(
        base_area_mm2=base_area,
        eff_area_mm2=base_area,          # 平板无面积增益
        material_vol_mm3=base_area * p.channel_depth,
        spread_factor=0.4,
        area_enhance=1.0,
    )
    return _svg_wrap(body, "flat baseline"), stats


def generate(params) -> Tuple[str, GeometryStats]:
    """按 structure_type 分派。"""
    if isinstance(params, LeafVeinParams):
        return generate_leaf_vein(params)
    if isinstance(params, ChannelParams):
        return generate_channel(params)
    if isinstance(params, FlatBaselineParams):
        return generate_flat(params)
    raise TypeError(f"unknown params type: {type(params)}")
