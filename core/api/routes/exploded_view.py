"""
Exploded view API routes: OBJ parsing, part description, and example data.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.config import Settings, get_settings
from core.models.exploded_view import (
    DescribePartsRequest,
    ExplodedViewResult,
    ParseObjRequest,
)
from core.providers.errors import ProviderError
from core.providers.openai_models import OpenAIModelsClient
from core.api.routes.models import get_openai_client
from core.services.exploded_view_service import (
    build_exploded_parts,
    generate_descriptions,
    parse_and_describe,
    parse_obj_file,
)

router = APIRouter(prefix="/api/v1/exploded-view", tags=["exploded-view"])

ROOT = Path(__file__).resolve().parent.parent.parent.parent
# Use the Downloads base.obj which has 29 parts (the frontend copy only has 1 merged mesh)
ROBOT_ARM_OBJ = Path(r"C:\Users\llwxy\Downloads\base.obj")
CACHE_DIR = ROOT / "data" / "exploded_view_cache"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/parse",
    summary="Parse OBJ file and extract part metadata",
    description="Parse a Wavefront OBJ file, extract per-object geometry metadata, and classify each part.",
)
async def parse_obj(body: ParseObjRequest):
    try:
        parsed = parse_obj_file(body.obj_path)
        parts = build_exploded_parts(parsed)
        return {
            "model_name": body.model_name,
            "source_file": body.obj_path,
            "total_parts": len(parts),
            "parts": [p.model_dump() for p in parts],
        }
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(400, f"Parse failed: {e}")


@router.post(
    "/describe",
    summary="Generate LLM descriptions for parts",
    description="Send part metadata to the LLM and generate professional descriptions for each part.",
)
async def describe_parts(
    body: DescribePartsRequest,
    client: OpenAIModelsClient = Depends(get_openai_client),
):
    try:
        from core.models.exploded_view import ExplodedPart
        parts = [ExplodedPart(**p) if isinstance(p, dict) else p for p in body.parts]
        descriptions = await generate_descriptions(parts, client, body.model_context)
        return {
            "total": len(descriptions),
            "descriptions": [d.model_dump() for d in descriptions],
        }
    except ProviderError as e:
        raise HTTPException(502, f"LLM provider error: {e.message}")
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(400, f"Describe failed: {e}")


@router.get(
    "/robot-arm/parts",
    summary="Get pre-parsed robot arm parts metadata",
    description="Returns the 29 parts of the robot arm model with geometry and classification.",
)
async def get_robot_arm_parts():
    cache_file = CACHE_DIR / "robot_arm_parts.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    if not ROBOT_ARM_OBJ.exists():
        raise HTTPException(404, f"OBJ file not found: {ROBOT_ARM_OBJ}")
    try:
        parsed = parse_obj_file(ROBOT_ARM_OBJ)
        parts = build_exploded_parts(parsed)
        result = {
            "model_name": "robot-arm",
            "source_file": str(ROBOT_ARM_OBJ),
            "total_parts": len(parts),
            "parts": [p.model_dump() for p in parts],
        }
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    except Exception as e:
        raise HTTPException(400, f"Parse failed: {e}")


@router.get(
    "/robot-arm/descriptions",
    summary="Get LLM-generated descriptions for robot arm parts",
    description="Returns pre-generated descriptions. If not cached, generates them via LLM.",
)
async def get_robot_arm_descriptions(
    client: OpenAIModelsClient = Depends(get_openai_client),
    settings: Settings = Depends(get_settings),
):
    cache_file = CACHE_DIR / "robot_arm_descriptions.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    # Parse parts first
    parts_cache = CACHE_DIR / "robot_arm_parts.json"
    if parts_cache.exists():
        parts_data = json.loads(parts_cache.read_text(encoding="utf-8"))
    else:
        parsed = parse_obj_file(ROBOT_ARM_OBJ)
        from core.models.exploded_view import ExplodedPart
        parts = build_exploded_parts(parsed)
        parts_data = {"parts": [p.model_dump() for p in parts]}

    from core.models.exploded_view import ExplodedPart
    parts = [ExplodedPart(**p) for p in parts_data["parts"]]

    try:
        descriptions = await generate_descriptions(
            parts, client, "六轴机械臂，使用 IKI1602 系列伺服电机"
        )
        result = {
            "total": len(descriptions),
            "descriptions": [d.model_dump() for d in descriptions],
        }
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    except ProviderError as e:
        raise HTTPException(502, f"LLM provider error: {e.message}")
    except Exception as e:
        raise HTTPException(400, f"Generate descriptions failed: {e}")


@router.get(
    "/robot-arm/full",
    summary="Get complete exploded view data for robot arm",
    description="Returns parts metadata + descriptions in one call.",
)
async def get_robot_arm_full(
    client: OpenAIModelsClient = Depends(get_openai_client),
):
    cache_file = CACHE_DIR / "robot_arm_full.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    # Get parts
    parts_cache = CACHE_DIR / "robot_arm_parts.json"
    if parts_cache.exists():
        parts_data = json.loads(parts_cache.read_text(encoding="utf-8"))
    else:
        parsed = parse_obj_file(ROBOT_ARM_OBJ)
        from core.models.exploded_view import ExplodedPart
        parts = build_exploded_parts(parsed)
        parts_data = {
            "model_name": "robot-arm",
            "source_file": str(ROBOT_ARM_OBJ),
            "total_parts": len(parts),
            "parts": [p.model_dump() for p in parts],
        }
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        parts_cache.write_text(json.dumps(parts_data, ensure_ascii=False, indent=2), encoding="utf-8")

    from core.models.exploded_view import ExplodedPart
    parts = [ExplodedPart(**p) for p in parts_data["parts"]]

    # Get descriptions
    desc_cache = CACHE_DIR / "robot_arm_descriptions.json"
    if desc_cache.exists():
        desc_data = json.loads(desc_cache.read_text(encoding="utf-8"))
    else:
        try:
            descriptions = await generate_descriptions(
                parts, client, "六轴机械臂，使用 IKI1602 系列伺服电机"
            )
            desc_data = {
                "total": len(descriptions),
                "descriptions": [d.model_dump() for d in descriptions],
            }
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            desc_cache.write_text(json.dumps(desc_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except ProviderError as e:
            raise HTTPException(502, f"LLM provider error: {e.message}")
        except Exception as e:
            raise HTTPException(400, f"Generate descriptions failed: {e}")

    result = {
        "model_id": "exploded-robot-arm",
        "model_name": "robot-arm",
        "source_file": str(ROBOT_ARM_OBJ),
        "total_parts": parts_data["total_parts"],
        "parts": parts_data["parts"],
        "descriptions": desc_data["descriptions"],
    }
    cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
