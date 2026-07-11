"""继续已提交的 Rodin 任务，完成下载、Bang 分件和子模型下载。"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import Settings
from core.providers.errors import ProviderError
from core.providers.hyper3d import Hyper3DClient
from core.providers.openai_models import OpenAIModelsClient

OUTPUT = ROOT / "outputs" / "foc_robot_arm_backend_output.json"
ASSET_DIR = ROOT / "outputs" / "foc_robot_arm_assets"


async def wait_for_done(client: Hyper3DClient, subscription_key: str, attempts: int = 60) -> dict[str, Any]:
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


async def download_assets(items: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
        for index, item in enumerate(items):
            url = str(item.get("url", ""))
            name = str(item.get("name") or Path(urlparse(url).path).name or f"asset-{index}")
            safe_name = Path(name).name
            target = ASSET_DIR / f"{prefix}-{index:02d}-{safe_name}"
            response = await client.get(url)
            response.raise_for_status()
            target.write_bytes(response.content)
            saved.append({"name": name, "local_path": str(target.relative_to(ROOT)), "size_bytes": len(response.content)})
    return saved


async def main() -> None:
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    settings = Settings()
    hyper3d = Hyper3DClient(settings)
    openai = OpenAIModelsClient(settings)

    # 使用用户指定的 OpenAI 兼容网关重新做一次最小真实调用。
    try:
        llm = await openai.create_response(
            input_data="输出 JSON：{\"status\":\"ok\",\"task\":\"FOC机械臂热设计后端连通性\"}",
            instructions="只输出合法 JSON，不要 Markdown。",
            max_output_tokens=200,
        )
        payload["external_calls"]["gpt_5_6_sol"] = {"status": "success", "response": llm}
    except ProviderError as exc:
        payload["external_calls"]["gpt_5_6_sol"] = {
            "status": "failed",
            "error": {"provider": exc.provider, "message": exc.message, "details": exc.details},
        }

    rodin = payload["external_calls"]["hyper3d_rodin"]["response"]
    rodin_status = await wait_for_done(hyper3d, rodin["jobs"]["subscription_key"])
    rodin_download = await hyper3d.download(task_uuid=rodin["uuid"])
    rodin_local = await download_assets(rodin_download.get("list") or [], "rodin")
    payload["external_calls"]["hyper3d_rodin"].update(
        {"status": "done", "final_status": rodin_status, "download": rodin_download, "local_assets": rodin_local}
    )
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        bang = await hyper3d.bang(
            asset_id=rodin["uuid"],
            model=None,
            image=None,
            prompt=None,
            options={"strength": 5, "geometry_file_format": "glb", "material": "PBR", "resolution": "Basic"},
        )
        payload["external_calls"]["hyper3d_bang"] = {"status": "submitted", "response": bang}
        OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        bang_status = await wait_for_done(hyper3d, bang["jobs"]["subscription_key"])
        bang_download = await hyper3d.download(task_uuid=bang["uuid"])
        bang_local = await download_assets(bang_download.get("list") or [], "bang")
        payload["external_calls"]["hyper3d_bang"].update(
            {"status": "done", "final_status": bang_status, "download": bang_download, "local_assets": bang_local}
        )
    except (ProviderError, RuntimeError, TimeoutError, httpx.HTTPError) as exc:
        if isinstance(exc, ProviderError):
            error: Any = {"provider": exc.provider, "message": exc.message, "details": exc.details}
        else:
            error = str(exc)
        payload["external_calls"]["hyper3d_bang"] = {"status": "failed", "error": error}

    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "asset_dir": str(ASSET_DIR)}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
