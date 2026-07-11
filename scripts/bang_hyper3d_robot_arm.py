"""对本次 Hyper3D 整臂 Rodin 资产执行 Bang，并下载可追溯结果。"""
from __future__ import annotations

import asyncio
import json
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

SOURCE_MANIFEST = ROOT / "outputs" / "hyper3d_robot_arm" / "hyper3d_manifest.json"
OUTPUT_DIR = ROOT / "outputs" / "hyper3d_robot_arm_bang"
OUTPUT_MANIFEST = OUTPUT_DIR / "bang_manifest.json"


async def wait_for_done(client: Hyper3DClient, subscription_key: str, attempts: int = 90) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for _ in range(attempts):
        last = await client.check_status(subscription_key=subscription_key)
        jobs = last.get("jobs") or []
        statuses = [job.get("status") for job in jobs if isinstance(job, dict)]
        if statuses and all(status == "Done" for status in statuses):
            return last
        if any(status == "Failed" for status in statuses):
            raise RuntimeError(f"Hyper3D Bang failed: {statuses}")
        await asyncio.sleep(8)
    raise TimeoutError(f"Hyper3D Bang did not finish: {last}")


async def download_assets(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
        for index, item in enumerate(items):
            url = str(item.get("url", ""))
            original = str(item.get("name") or Path(urlparse(url).path).name or f"asset-{index}")
            suffix = Path(original).suffix.lower() or ".bin"
            target = OUTPUT_DIR / f"hyper3d-robot-arm-bang-{index:02d}{suffix}"
            response = await client.get(url)
            response.raise_for_status()
            target.write_bytes(response.content)
            saved.append({"name": original, "local_path": str(target.relative_to(ROOT)).replace("\\", "/"), "size_bytes": len(response.content)})
    return saved


async def main() -> None:
    source = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    rodin_task_uuid = source["task_uuid"]
    client = Hyper3DClient(Settings())
    submitted = await client.bang(
        asset_id=rodin_task_uuid,
        model=None,
        image=None,
        prompt=None,
        options={"strength": 5, "geometry_file_format": "glb", "material": "PBR", "resolution": "Basic"},
    )
    status = await wait_for_done(client, submitted["jobs"]["subscription_key"])
    downloads = await client.download(task_uuid=submitted["uuid"])
    assets = await download_assets(downloads.get("list") or [])
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "Hyper3D",
        "endpoint": "bang",
        "source_rodin_task_uuid": rodin_task_uuid,
        "task_uuid": submitted["uuid"],
        "strength": 5,
        "final_status": status,
        "assets": assets,
        "fidelity": "concept_mesh",
        "semantic_status": "needs_ai_and_human_review",
    }
    OUTPUT_MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(OUTPUT_MANIFEST), "task_uuid": submitted["uuid"], "assets": assets}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
