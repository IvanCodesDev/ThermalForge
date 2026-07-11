"""三层微流道冷板的参数契约。"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Dict, List


@dataclass(frozen=True)
class ColdPlateParams:
    flow_width_x: float = 30.0
    flow_length_y: float = 48.0
    margin_left: float = 2.0
    margin_right: float = 2.0
    margin_bottom: float = 2.0
    margin_top: float = 2.0
    t_layer1: float = 2.0
    t_layer2: float = 0.25
    t_layer3: float = 1.0
    channel_width: float = 0.10
    channel_gap: float = 0.10
    manifold_length: float = 4.0

    def validate(self) -> List[str]:
        errors: List[str] = []
        positive = (
            "flow_width_x",
            "flow_length_y",
            "margin_left",
            "margin_right",
            "margin_bottom",
            "margin_top",
            "t_layer1",
            "t_layer2",
            "t_layer3",
            "channel_width",
            "channel_gap",
            "manifold_length",
        )
        for name in positive:
            if float(getattr(self, name)) <= 0:
                errors.append(f"{name} 必须大于 0")
        if 2.0 * self.manifold_length >= self.flow_length_y:
            errors.append("两端集流区总长度必须小于内部流道长度")
        if self.channel_width > self.flow_width_x:
            errors.append("channel_width 不能大于 flow_width_x")
        if self.channel_pitch > self.flow_width_x:
            errors.append("channel_pitch 不能大于 flow_width_x")
        if self.n_channels < 1:
            errors.append("至少需要一条微流道")
        return errors

    @property
    def channel_pitch(self) -> float:
        return self.channel_width + self.channel_gap

    @property
    def outer_width_x(self) -> float:
        return self.margin_left + self.flow_width_x + self.margin_right

    @property
    def outer_length_y(self) -> float:
        return self.margin_bottom + self.flow_length_y + self.margin_top

    @property
    def total_thickness(self) -> float:
        return self.t_layer1 + self.t_layer2 + self.t_layer3

    @property
    def straight_channel_length(self) -> float:
        return self.flow_length_y - 2.0 * self.manifold_length

    @property
    def n_channels(self) -> int:
        return int((self.flow_width_x - self.channel_width) / self.channel_pitch) + 1

    @property
    def total_channel_band(self) -> float:
        return (self.n_channels - 1) * self.channel_pitch + self.channel_width

    @property
    def channel_x_offset(self) -> float:
        return (self.flow_width_x - self.total_channel_band) / 2.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def derived(self) -> Dict[str, Any]:
        return {
            "outer_width_x": self.outer_width_x,
            "outer_length_y": self.outer_length_y,
            "total_thickness": self.total_thickness,
            "channel_pitch": self.channel_pitch,
            "n_channels": self.n_channels,
            "straight_channel_length": self.straight_channel_length,
            "channel_x_offset": self.channel_x_offset,
        }

    def parameter_hash(self) -> str:
        encoded = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256(encoded).hexdigest()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColdPlateParams":
        unknown = sorted(set(data) - set(cls.__dataclass_fields__))
        if unknown:
            raise ValueError("未知冷板参数: " + ", ".join(unknown))
        params = cls(**data)
        errors = params.validate()
        if errors:
            raise ValueError("; ".join(errors))
        return params
