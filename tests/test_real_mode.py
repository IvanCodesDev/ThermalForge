from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from core.config import Settings


def _real_openapi_paths() -> set[str]:
    code = (
        "import json; "
        "from core.api.app import app; "
        "print(json.dumps(sorted(app.openapi()['paths'])))"
    )
    environment = os.environ.copy()
    environment["THERMALFORGE_MODE"] = "real"
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=os.getcwd(),
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    return set(json.loads(completed.stdout.strip().splitlines()[-1]))


def test_runtime_mode_accepts_only_real_or_development() -> None:
    assert Settings(THERMALFORGE_MODE="real").is_real is True
    assert Settings(THERMALFORGE_MODE="development").is_real is False
    with pytest.raises(ValidationError):
        Settings(THERMALFORGE_MODE="mock")


def test_real_mode_openapi_excludes_demo_screening_and_manual_success_routes() -> None:
    paths = _real_openapi_paths()

    forbidden_exact = {
        "/library",
        "/generate",
        "/evaluate",
        "/compare",
        "/match",
        "/match_user",
        "/recommend",
        "/optimize/leaf-direction",
        "/api/v1/agent-executions",
    }
    assert forbidden_exact.isdisjoint(paths)
    assert not any(path.startswith("/api/v1/foc-demo") for path in paths)
    assert not any(path.startswith("/api/v1/workbench") for path in paths)
    assert not any(path.endswith("/geometry") for path in paths)
    assert not any(path.endswith("/hyper3d/submitted") for path in paths)
    assert not any(path.endswith("/hyper3d/result") for path in paths)
    assert not any(path.endswith("/validation") for path in paths)
    assert not any(path.endswith("/spaceclaim-artifacts") for path in paths)
    assert not any(path.endswith("/result") and "simulation-handoffs" in path for path in paths)

    assert "/health" in paths
    assert "/models/config" in paths
    assert "/api/v1/agent-pipelines" in paths
    assert "/api/v1/agent-definitions" in paths
    assert "/api/v1/engineering-projects/{project_id}/state" in paths
    assert "/api/v1/simulation-handoffs/projects/{project_id}" in paths
