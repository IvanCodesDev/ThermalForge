"""
相似度匹配（短期路线：不训模型，用 constraint_vector 余弦相似度检索）

流程：用户给出目标约束（结构类型 + 关键参数）→ 构造查询向量 →
与预参数化案例库逐条算余弦相似度 → 返回 TopK 案例（含预计算热指标）。

这是黑客松 Demo 的「相似度匹配 + 3D/图形展示」路径核心。
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import List, Dict, Any

from ..models.schema import from_dict


def cosine(a: List[float], b: List[float]) -> float:
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class Library:
    """预参数化案例库。每条：{case_id, source, params, constraint_vector, metrics}。"""

    def __init__(self, cases: List[Dict[str, Any]] | None = None):
        self.cases: List[Dict[str, Any]] = cases or []

    @classmethod
    def load(cls, path: str | Path) -> "Library":
        p = Path(path)
        if not p.exists():
            return cls([])
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(data.get("cases", []))

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"cases": self.cases}, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, case: Dict[str, Any]) -> None:
        self.cases.append(case)

    def match(self, query_vector: List[float], structure_type: str | None = None,
              medium: str | None = None, top_k: int = 3) -> List[Dict[str, Any]]:
        """按介质分桶（介质不同机理不同，不跨桶混比）+ 结构类型过滤，再余弦排序。"""
        results = []
        for c in self.cases:
            if structure_type and c.get("params", {}).get("structure_type") != structure_type:
                continue
            if medium and c.get("params", {}).get("cooling_medium") != medium:
                continue
            score = cosine(query_vector, c.get("geometry_vector", []))
            results.append({**c, "similarity": round(score, 4)})
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]


def query_from_params(params) -> List[float]:
    """把一套目标参数转成查询向量。"""
    return params.to_vector()
