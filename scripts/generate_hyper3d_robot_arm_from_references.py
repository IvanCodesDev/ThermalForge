"""使用参考图片真实调用 Hyper3D Rodin，并下载机械臂 GLB 与预览图。"""
from __future__ import annotations

import asyncio
import json
import mimetypes
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import Settings
from core.providers.hyper3d import Hyper3DClient

REFERENCE_DIR = Path(r"C:\Users\llwxy\Downloads\机械臂")
OUTPUT_DIR = ROOT / "outputs" / "hyper3d_robot_arm"
MANIFEST = OUTPUT_DIR / "hyper3d_manifest.json"
REFERENCE_NAMES = ["2 (2).JPG", "4.JPG", "5.JPG", "Capture.JPG", "Untitled.JPG"]

PROMPT = """
A mechanically plausible complete articulated industrial robotic arm based on the supplied reference photographs. Preserve the recognizable overall arm proportions and joint placement from the references. Design a coherent six-axis arm with a rotating base, shoulder, elbow and compact three-axis wrist. Every joint uses a brushless FOC motor module and precision reducer. The visible product is a custom 3D-printable protective enclosure system: clearly separated left and right shell halves, removable joint covers, service panels, cable routing channels, fastener seams and metal mounting interfaces. Avoid fantasy shapes, disconnected floating parts, decorative rings and toy-like geometry. Continuous manufacturable surfaces, realistic joint clearances, consistent scale, neutral PBR materials, no text or logos. Make major enclosure regions visually distinct so downstream mesh segmentation and exploded-view layout are possible.
""".strip()


def load_images() -> list[tuple[str, bytes, str]]:
    images: list[tuple[str, bytes, str]] = []
    for name in REFERENCE_NAMES:
        path = REFERENCE_DIR / name
        if not path.is_file():
            raise FileNotFoundError(path)
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        images.append((path.name, path.read_bytes(), mime))
    return images


async def wait_for_done(client: Hyper3DClient, subscription_key: str, attempts: int = 90) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for _ in range(attempts):
        last = await client.check_status(subscription_key=subscription_key)
        jobs = last.get("jobs") or []
        statuses = [job.get("status") for job in jobs if isinstance(job, dict)]
        if statuses and all(status == "Done" for status in statuses):
            return last
        if any(status == "Failed" for status in statuses):
            raise RuntimeError(f"Hyper3D task failed: {statuses}")
        await asyncio.sleep(8)
    raise TimeoutError(f"Hyper3D task did not finish: {last}")


async def download_assets(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
        for index, item in enumerate(items):
            url = str(item.get("url", ""))
            original = str(item.get("name") or Path(urlparse(url).path).name or f"asset-{index}")
            suffix = Path(original).suffix.lower() or ".bin"
            role = "model" if suffix == ".glb" else "preview"
            target = OUTPUT_DIR / f"hyper3d-robot-arm-{role}-{index:02d}{suffix}"
            response = await client.get(url)
            response.raise_for_status()
            target.write_bytes(response.content)
            saved.append({
                "role": role,
                "name": original,
                "local_path": str(target.relative_to(ROOT)).replace("\\", "/"),
                "size_bytes": len(response.content),
            })
    return saved


async def main() -> None:
    settings = Settings()
    client = Hyper3DClient(settings)
    images = load_images()
    submitted = await client.submit(
        prompt=PROMPT,
        images=images,
        options={
            "tier": "Gen-2",
            "geometry_file_format": "glb",
            "material": "PBR",
            "mesh_mode": "Quad",
            "quality": "high",
            "preview_render": True,
        },
    )
    status = await wait_for_done(client, submitted["jobs"]["subscription_key"])
    downloads = await client.download(task_uuid=submitted["uuid"])
    assets = await download_assets(downloads.get("list") or [])
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "Hyper3D",
        "endpoint": "rodin",
        "tier": "Gen-2",
        "task_uuid": submitted["uuid"],
        "source_references": [str((REFERENCE_DIR / name).resolve()) for name in REFERENCE_NAMES],
        "prompt": PROMPT,
        "options": {
            "geometry_file_format": "glb",
            "material": "PBR",
            "mesh_mode": "Quad",
            "quality": "high",
            "preview_render": True,
        },
        "final_status": status,
        "assets": assets,
        "fidelity": "concept_mesh",
        "disclaimer": "Hyper3D 生成的概念网格，不是可制造 CAD；内部器件与工程材料仍需确定性装配和人工确认。",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(MANIFEST), "task_uuid": submitted["uuid"], "assets": assets}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
