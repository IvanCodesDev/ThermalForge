"""基于 OpenAPI 自动生成 ThermalForge 后端 API 参考文档。

用法：
    python scripts/generate_api_reference.py

输出：
    docs/api-reference.md

说明：
- 本脚本在导入 app 前将 THERMALFORGE_MODE 设为 development，以确保开发模式专属
  路由（workbench / foc-demo / *-development）也纳入文档。
- 文档由 OpenAPI schema 渲染，**请勿手改**；改端点文档后重跑本脚本即可。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# 必须在导入 app 之前设置，确保 dev-only 路由被挂载进 OpenAPI schema。
os.environ.setdefault("THERMALFORGE_MODE", "development")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.openapi.utils import get_openapi  # noqa: E402

from core.api.app import app, OPENAPI_TAGS  # noqa: E402

OUT = ROOT / "docs" / "api-reference.md"


def _resolve_ref(ref: str, components: dict) -> Any:
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return None
    node: Any = components
    for part in ref.lstrip("#/").split("/"):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _type_name(schema: Any) -> str:
    if not isinstance(schema, dict):
        return "any"
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]
    t = schema.get("type")
    if t == "array" and isinstance(schema.get("items"), dict):
        return f"array<{_type_name(schema['items'])}>"
    if t:
        return t
    if "anyOf" in schema or "oneOf" in schema:
        return "union"
    return "object"


def _render_params(op: dict) -> str:
    params = op.get("parameters", [])
    if not params:
        return ""
    rows = ["| 参数 | 位置 | 类型 | 必填 | 说明 |", "| --- | --- | --- | --- | --- |"]
    for p in params:
        name = p.get("name", "")
        loc = p.get("in", "")
        required = "是" if p.get("required") else "否"
        schema = p.get("schema", {})
        typ = _type_name(schema)
        desc = (p.get("description") or schema.get("description") or "").replace("\n", " ")
        rows.append(f"| `{name}` | {loc} | {typ} | {required} | {desc} |")
    return "\n".join(rows) + "\n"


def _render_body(op: dict, components: dict) -> str:
    rb = op.get("requestBody")
    if not isinstance(rb, dict):
        return ""
    content = rb.get("content", {})
    schema = content.get("application/json", {}).get("schema")
    if not isinstance(schema, dict):
        return ""
    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], components) or {}
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    if not props:
        return ""
    lines = ["**请求体**", "", "| 字段 | 类型 | 必填 | 说明 |", "| --- | --- | --- | --- |"]
    for fname, fschema in props.items():
        typ = _type_name(fschema)
        req = "是" if fname in required else "否"
        desc = (fschema.get("description") or "").replace("\n", " ")
        lines.append(f"| `{fname}` | {typ} | {req} | {desc} |")
    return "\n".join(lines) + "\n"


def _render_example(op: dict) -> str:
    resp = op.get("responses", {}).get("200") or op.get("responses", {}).get("201")
    if not isinstance(resp, dict):
        return ""
    example = resp.get("content", {}).get("application/json", {}).get("example")
    if example is None:
        return ""
    text = json.dumps(example, ensure_ascii=False, indent=2)
    return f"**示例响应**\n\n```json\n{text}\n```\n"


def main() -> None:
    spec = get_openapi(title=app.title, version=app.version, routes=app.routes)
    paths: dict = spec.get("paths", {})
    components: dict = spec.get("components", {})

    # 收集每个 tag 下的操作，保持路径顺序
    by_tag: dict[str, list[tuple[str, str, dict]]] = {}
    for path, methods in paths.items():
        for method, op in methods.items():
            if method.lower() not in {"get", "post", "put", "delete", "patch"}:
                continue
            tags = op.get("tags") or ["untagged"]
            by_tag.setdefault(tags[0], []).append((method.upper(), path, op))

    tag_order = [t["name"] for t in OPENAPI_TAGS] + ["untagged"]
    tag_desc = {t["name"]: t.get("description", "") for t in OPENAPI_TAGS}

    total = sum(len(v) for v in by_tag.values())

    out: list[str] = []
    out.append("# ThermalForge 后端 API 参考\n")
    out.append(f"> 自动生成自 OpenAPI schema（共 **{total}** 个端点）。本文件由 "
               "`scripts/generate_api_reference.py` 生成，**请勿手改**；修改端点文档后重跑该脚本。\n")
    out.append("启动服务后访问 `/docs`(Swagger) 或 `/redoc` 可交互调试。\n")

    # 目录
    out.append("## 目录\n")
    for tag in tag_order:
        if tag not in by_tag:
            continue
        title = tag_desc.get(tag, tag)
        out.append(f"- **{tag}** — {title}（{len(by_tag[tag])} 个端点）")
    out.append("")

    # 各分组
    for tag in tag_order:
        ops = by_tag.get(tag)
        if not ops:
            continue
        out.append(f"## {tag}\n")
        if tag in tag_desc:
            out.append(f">{tag_desc[tag]}\n")
        for method, path, op in ops:
            summary = op.get("summary") or ""
            description = op.get("description") or ""
            status = op.get("status_code", "200")
            out.append(f"### `{method} {path}`\n")
            if summary:
                out.append(f"**{summary}**  \n")
            if description:
                out.append(f"{description}\n")
            out.append(f"- 成功状态码：`{status}`")
            params_md = _render_params(op)
            if params_md:
                out.append("\n" + params_md)
            body_md = _render_body(op, components)
            if body_md:
                out.append("\n" + body_md)
            example_md = _render_example(op)
            if example_md:
                out.append("\n" + example_md)
            out.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {OUT} ({total} endpoints across {len(by_tag)} tags)")


if __name__ == "__main__":
    main()
