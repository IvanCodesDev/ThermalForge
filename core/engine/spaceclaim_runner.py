"""SpaceClaim 执行适配器。

支持两种启动模式：
- direct: 标准网络/商用许可证环境，直接以无头进程运行。
- explorer: Connected/PLE 授权要求由 Windows Explorer 发起时，创建临时快捷方式，
  由 Explorer 启动 SpaceClaim，并通过产物/标记文件判断完成状态。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_LARGE_PENALTY = 1.0e9


class SpaceClaimRunner:
    def __init__(
        self,
        executable: Optional[str] = None,
        timeout: float = 600.0,
        launch_mode: Optional[str] = None,
        license_feature: str = "disco_level1",
    ):
        self.timeout = timeout
        self.executable = executable or self._detect_executable()
        self.available = bool(self.executable) and Path(self.executable).exists()
        self.api_version = self._infer_api_version(self.executable)
        self.launch_mode = (launch_mode or os.environ.get("SPACECLAIM_LAUNCH_MODE", "direct")).lower()
        if self.launch_mode not in {"direct", "explorer"}:
            raise ValueError("launch_mode 必须是 direct 或 explorer")
        self.license_feature = license_feature

    @staticmethod
    def _infer_api_version(executable: Optional[str]) -> str:
        if not executable:
            return "V252"
        lowered = executable.lower().replace("/", "\\")
        for token, version in (("v261", "V261"), ("v252", "V252"), ("v251", "V251")):
            if token in lowered:
                return version
        return "V252"

    @staticmethod
    def _detect_executable() -> Optional[str]:
        env = os.environ.get("SPACECLAIM_EXE")
        if env and Path(env).exists():
            return env
        candidates: List[str] = [
            r"C:\Program Files\ANSYS Inc\v261\scdm\SpaceClaim.exe",
            r"C:\Program Files\ANSYS Inc\v252\SpaceClaim\SpaceClaim.exe",
            r"C:\Program Files\ANSYS Inc\v251\SpaceClaim\SpaceClaim.exe",
            r"C:\Program Files\ANSYS Inc\v251\scdm\SpaceClaim.exe",
        ]
        for path in candidates:
            if Path(path).exists():
                return path
        return shutil.which("SpaceClaim.exe") or shutil.which("SpaceClaim")

    def _spaceclaim_arguments(self, script_path: Path, *, headless: bool) -> List[str]:
        args = [
            f"/p={self.license_feature}",
            f"/RunScript={script_path}",
            f"/ScriptAPI={self.api_version}",
            f"/Headless={'True' if headless else 'False'}",
            "/Splash=False",
            "/Welcome=False",
            "/ExitAfterScript=True",
        ]
        if self.launch_mode == "explorer":
            args.insert(0, "/UseLicenseMode=true")
        return args

    def _create_shortcut(self, script_path: Path) -> Path:
        """为 Explorer 模式创建临时 .lnk。pylnk3 为纯 Python 依赖。"""
        try:
            import pylnk3
        except ImportError as exc:  # pragma: no cover - 由运行环境决定
            raise RuntimeError("explorer 模式需要依赖 pylnk3") from exc

        shortcut = Path(tempfile.gettempdir()) / f"thermalforge-sc-{script_path.stem}-{os.getpid()}.lnk"
        arguments = " ".join(
            f'"{arg}"' if " " in arg else arg
            for arg in self._spaceclaim_arguments(script_path, headless=False)
        )
        if shortcut.exists():
            shortcut.unlink()
        pylnk3.for_file(
            self.executable,
            str(shortcut),
            arguments=arguments,
            description=f"ThermalForge SpaceClaim runner: {script_path.name}",
            work_dir=str(script_path.parent),
        )
        return shortcut

    def _launch(self, script_path: Path) -> Optional[subprocess.CompletedProcess[str]]:
        if self.launch_mode == "direct":
            return subprocess.run(
                [self.executable, *self._spaceclaim_arguments(script_path, headless=True)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

        shortcut = self._create_shortcut(script_path)
        try:
            if not hasattr(os, "startfile"):
                raise RuntimeError("explorer 模式仅支持 Windows ShellExecute")
            # os.startfile 走 Windows ShellExecute，语义等同于用户在 Explorer 中双击 .lnk。
            os.startfile(str(shortcut))  # type: ignore[attr-defined]
        finally:
            # ShellExecute 已接收路径后即可删除；失败时保留也不会影响模型产物。
            time.sleep(0.5)
            try:
                shortcut.unlink(missing_ok=True)
            except OSError:
                pass
        return None

    @staticmethod
    def _wait_for(paths: List[Path], timeout: float) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if all(path.exists() and path.stat().st_size > 0 for path in paths):
                return True
            time.sleep(0.5)
        return False

    def preflight(self, timeout: float = 90.0, required_api_version: str | None = None) -> Dict[str, Any]:
        if required_api_version is not None and self.api_version != required_api_version:
            return {"ok": False, "reason": f"需要 {required_api_version}，检测到 {self.api_version}"}
        if not self.available or not self.executable:
            return {"ok": False, "reason": "SpaceClaim 未安装"}

        tmp_dir = Path(tempfile.gettempdir())
        script = tmp_dir / f"tf_sc_preflight_{os.getpid()}.py"
        marker = tmp_dir / f"tf_sc_preflight_marker_{os.getpid()}.txt"
        marker.unlink(missing_ok=True)
        script.write_text(
            "from SpaceClaim.Api.%s import *\n"
            "import System\n"
            "System.IO.File.WriteAllText(r'%s', 'OK')\n"
            % (self.api_version, str(marker).replace("\\", "/")),
            encoding="utf-8",
        )
        try:
            proc = self._launch(script)
            if self.launch_mode == "explorer":
                ok = self._wait_for([marker], timeout)
            else:
                ok = marker.exists()
        except subprocess.TimeoutExpired:
            return {"ok": False, "reason": "SpaceClaim 执行超时（可能被授权对话框阻塞）"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "reason": f"执行异常: {exc}"}
        finally:
            script.unlink(missing_ok=True)

        if ok:
            marker.unlink(missing_ok=True)
            return {
                "ok": True,
                "reason": "preflight 通过",
                "api_version": self.api_version,
                "launch_mode": self.launch_mode,
                "license_feature": self.license_feature,
            }
        stderr = "" if proc is None else (proc.stderr or "")[-500:]
        return {"ok": False, "reason": "SpaceClaim 未生成自检标记", "stderr": stderr}

    def run(self, script_path: str, required_api_version: str | None = None) -> Dict[str, Any]:
        if required_api_version is not None and self.api_version != required_api_version:
            return {"available": self.available, "status": "version_mismatch", "reason": f"需要 {required_api_version}，检测到 {self.api_version}", "penalty": _LARGE_PENALTY, "step_path": None}
        if not self.available or not self.executable:
            return {
                "available": False,
                "status": "skipped",
                "reason": "SpaceClaim 未安装，跳过执行",
                "penalty": _LARGE_PENALTY,
                "step_path": None,
            }

        script = Path(script_path).resolve()
        if not script.exists():
            return {
                "available": True,
                "status": "invalid_geometry",
                "reason": f"脚本不存在: {script_path}",
                "penalty": _LARGE_PENALTY,
                "step_path": None,
            }

        step_path = script.with_suffix(".stp")
        result_manifest = script.with_suffix(".json")
        for old in (step_path, result_manifest):
            old.unlink(missing_ok=True)

        try:
            proc = self._launch(script)
            if self.launch_mode == "explorer":
                complete = self._wait_for([step_path, result_manifest], self.timeout)
                returncode = 0 if complete else None
            else:
                complete = step_path.exists() and result_manifest.exists()
                returncode = proc.returncode if proc is not None else None
        except subprocess.TimeoutExpired:
            return {
                "available": True,
                "status": "invalid_geometry",
                "reason": "SpaceClaim 执行超时",
                "penalty": _LARGE_PENALTY,
                "step_path": None,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "available": True,
                "status": "invalid_geometry",
                "reason": f"执行异常: {exc}",
                "penalty": _LARGE_PENALTY,
                "step_path": None,
            }

        if returncode not in (0, None):
            return {
                "available": True,
                "status": "invalid_geometry",
                "reason": f"SpaceClaim 返回非零: {returncode}",
                "stderr": "" if proc is None else (proc.stderr or "")[-2000:],
                "penalty": _LARGE_PENALTY,
                "step_path": None,
            }
        if not complete:
            return {
                "available": True,
                "status": "invalid_geometry",
                "reason": "未在超时前生成 STEP 与 manifest",
                "penalty": _LARGE_PENALTY,
                "step_path": None,
            }

        return {
            "available": True,
            "status": "ok",
            "penalty": 0.0,
            "step_path": str(step_path),
            "manifest_path": str(result_manifest),
            "stdout": "" if proc is None else (proc.stdout or "")[-1000:],
            "launch_mode": self.launch_mode,
            "api_version": self.api_version,
            "license_feature": self.license_feature,
        }
