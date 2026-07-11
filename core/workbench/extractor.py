"""离线、确定性的中英文工程需求抽取。"""
from __future__ import annotations

import re
from typing import Callable

from .contracts import EngineeringBrief


_DEVICE_KEYWORDS = (
    (("关节", "joint motor", "robot joint"), "关节电机"),
    (("jetson", "边缘计算", "edge computer"), "Jetson/边缘计算盒"),
    (("mosfet", "驱动器", "driver"), "MOSFET/驱动器"),
    (("传感器舱", "sensor enclosure", "sensor pod"), "传感器舱"),
    (("灵巧手", "dexterous hand"), "灵巧手模组"),
    (("无人机电机", "drone motor"), "无人机动力电机"),
    (("无人机电调", "drone esc", "electronic speed controller"), "无人机电调"),
    (("变频器", "inverter"), "工业变频器"),
    (("医疗激光", "medical laser"), "医疗激光模块"),
)
_MATERIAL_KEYWORDS = (
    (("6061",), "铝6061"),
    (("1060",), "铝1060"),
    (("铜", "copper"), "铜"),
    (("钢", "steel"), "钢"),
    (("塑料", "plastic"), "工程塑料"),
    (("pcb",), "PCB基材"),
)
_MANUFACTURING_KEYWORDS = (
    (("cnc+3d", "cnc + 3d", "cnc 加 3d"), "CNC+3D打印"),
    (("3d打印", "3d 打印", "3d print", "additive"), "3D打印"),
    (("cnc", "机加工"), "CNC"),
    (("钣金", "sheet metal"), "钣金"),
)
_NUMBER = r"(\d+(?:\.\d+)?)"


def _keyword_value(text: str, rules: tuple[tuple[tuple[str, ...], str], ...], default: str) -> tuple[str, bool]:
    for keywords, value in rules:
        if any(keyword in text for keyword in keywords):
            return value, True
    return default, False


def _number(text: str, patterns: tuple[str, ...], cast: Callable[[str], float] = float) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return cast(match.group(1))
    return None


def _dimensions(text: str) -> dict[str, float] | None:
    match = re.search(
        rf"{_NUMBER}\s*(?:mm|毫米)?\s*[x×*]\s*{_NUMBER}\s*(?:mm|毫米)?\s*[x×*]\s*{_NUMBER}\s*(?:mm|毫米)?",
        text,
        re.IGNORECASE,
    )
    if match:
        return {"length_mm": float(match.group(1)), "width_mm": float(match.group(2)), "height_mm": float(match.group(3))}
    diameter = _number(text, (rf"(?:外径|outer\s*diameter|od)\s*[:：]?\s*{_NUMBER}\s*(?:mm|毫米)?",))
    height = _number(text, (rf"(?:高度|高|height)\s*[:：]?\s*{_NUMBER}\s*(?:mm|毫米)?",))
    if diameter is not None:
        result = {"outer_dia_mm": diameter, "height_mm": height or 40.0}
        inner = _number(text, (rf"(?:内径|inner\s*diameter|id)\s*[:：]?\s*{_NUMBER}\s*(?:mm|毫米)?",))
        if inner is not None:
            result["inner_dia_mm"] = inner
        return result
    return None


def extract_engineering_brief(source_text: str) -> EngineeringBrief:
    normalized = source_text.strip().lower()
    missing: list[str] = []
    assumptions: list[str] = []

    device_type, found = _keyword_value(normalized, _DEVICE_KEYWORDS, "关节电机")
    if not found:
        missing.append("device_type")
        assumptions.append("未识别器件类型，暂按关节电机筛选")

    dimensions = _dimensions(normalized)
    if dimensions is None:
        dimensions = {"length_mm": 60.0, "width_mm": 60.0, "height_mm": 40.0}
        missing.append("dimensions")
        assumptions.append("未识别尺寸，采用 60×60×40 mm 筛选尺寸")

    power_w = _number(normalized, (rf"(?:持续热耗散|设计热耗散|热耗散|功耗|tdp|heat dissipation|thermal power|power)\s*(?:按|为|约|:|：)?\s*{_NUMBER}\s*(?:w|瓦)?", rf"{_NUMBER}\s*(?:w|瓦)\s*(?:热耗散|功耗|tdp|heat)"))
    if power_w is None:
        power_w = 28.0
        missing.append("power_w")
        assumptions.append("未识别功耗，采用 28 W")

    max_temp_c = _number(normalized, (rf"(?:最高温|温度上限|目标低于|壳温目标低于|max(?:imum)?\s*temp(?:erature)?)\s*[:：]?\s*{_NUMBER}\s*(?:°?c|℃|度)?",))
    if max_temp_c is None:
        max_temp_c = 80.0
        missing.append("max_temp_c")
        assumptions.append("未识别温度上限，采用 80 ℃")

    ambient_temp_c = _number(normalized, (rf"(?:环境温度|环境|ambient(?:\s*temp(?:erature)?)?)\s*[:：]?\s*{_NUMBER}\s*(?:°?c|℃|度)?",))
    if ambient_temp_c is None:
        ambient_temp_c = 25.0
        missing.append("ambient_temp_c")
        assumptions.append("未识别环境温度，采用 25 ℃")

    max_weight_g = _number(normalized, (rf"(?:重量上限|最大重量|质量不超过|重量不超过|max(?:imum)?\s*weight|weight limit)\s*[:：]?\s*{_NUMBER}\s*(?:g|克)?", rf"{_NUMBER}\s*(?:g|克)\s*(?:以内|以下|max)"))
    if max_weight_g is None:
        max_weight_g = 60.0
        missing.append("max_weight_g")
        assumptions.append("未识别重量上限，采用 60 g")

    material, found = _keyword_value(normalized, _MATERIAL_KEYWORDS, "铝6061")
    if not found:
        missing.append("material")
        assumptions.append("未识别材料，采用铝6061意图映射")

    manufacturing, found = _keyword_value(normalized, _MANUFACTURING_KEYWORDS, "3D打印")
    if not found:
        missing.append("manufacturing")
        assumptions.append("未识别制造方式，采用3D打印")

    fan_keywords = ("风扇", "强制风冷", "fan", "forced air", "forced-air")
    fan_negations = ("无独立风扇", "无风扇", "不使用风扇", "without fan", "fanless", "no fan")
    has_fan = any(keyword in normalized for keyword in fan_keywords) and not any(
        keyword in normalized for keyword in fan_negations
    )

    return EngineeringBrief(
        source_text=source_text,
        device_type=device_type,
        dimensions=dimensions,
        power_w=power_w,
        max_temp_c=max_temp_c,
        material=material,
        has_fan=has_fan,
        max_weight_g=max_weight_g,
        manufacturing=manufacturing,
        ambient_temp_c=ambient_temp_c,
        missing_fields=missing,
        assumptions=assumptions,
    )
