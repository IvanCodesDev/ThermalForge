"""项目仓库 — JSON 文件持久化，支持文件上传存储。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.models.project import Project, ProjectInputs, ModelAsset, AgentStepStatus, ComponentSummary, ProjectStatus

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "projects"


class ProjectRepository:
    def __init__(self, base_dir: Path = DATA_DIR) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _project_dir(self, project_id: str) -> Path:
        d = self.base_dir / project_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _project_file(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "project.json"

    def _uploads_dir(self, project_id: str) -> Path:
        d = self._project_dir(project_id) / "uploads"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _assets_dir(self, project_id: str) -> Path:
        d = self._project_dir(project_id) / "assets"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def create(
        self,
        name: str,
        description: str = "",
        text_description: str = "",
        pdf_filename: str | None = None,
        pdf_content: bytes | None = None,
        image_filenames: list[tuple[str, bytes]] | None = None,
    ) -> Project:
        project_id = f"proj-{uuid4().hex[:8]}"
        inputs = ProjectInputs(
            text_description=text_description,
        )

        uploads = self._uploads_dir(project_id)

        if pdf_filename and pdf_content:
            safe_name = Path(pdf_filename).name
            (uploads / safe_name).write_bytes(pdf_content)
            inputs.pdf_filename = safe_name

        if image_filenames:
            for fname, content in image_filenames:
                safe_name = Path(fname).name
                (uploads / safe_name).write_bytes(content)
                inputs.structure_images.append(safe_name)

        project = Project(
            id=project_id,
            name=name,
            created_at=datetime.now(timezone.utc).isoformat(),
            description=description,
            inputs=inputs,
            steps=Project(id="", name="", created_at="").default_steps(),
        )
        self._save(project)
        return project

    def get(self, project_id: str) -> Project:
        data = json.loads(self._project_file(project_id).read_text(encoding="utf-8"))
        return Project.model_validate(data)

    def list_all(self) -> list[Project]:
        projects = []
        for f in sorted(self.base_dir.glob("proj-*/project.json"), reverse=True):
            try:
                projects.append(Project.model_validate(json.loads(f.read_text(encoding="utf-8"))))
            except Exception:
                continue
        return projects

    def update(self, project: Project) -> Project:
        self._save(project)
        return project

    def update_status(self, project_id: str, status: str) -> Project:
        project = self.get(project_id)
        project.status = status
        return self.update(project)

    def update_step(self, project_id: str, step_id: str, status: str, detail: str = "") -> Project:
        project = self.get(project_id)
        for step in project.steps:
            if step.id == step_id:
                step.status = status
                if detail:
                    step.detail = detail
                break
        return self.update(project)

    def add_asset(self, project_id: str, asset: ModelAsset) -> Project:
        project = self.get(project_id)
        project.model_assets.append(asset)
        return self.update(project)

    def set_components(self, project_id: str, components: list[ComponentSummary]) -> Project:
        project = self.get(project_id)
        project.components = components
        return self.update(project)

    def save_uploaded_asset(self, project_id: str, filename: str, content: bytes) -> Path:
        assets = self._assets_dir(project_id)
        safe_name = Path(filename).name
        path = assets / safe_name
        path.write_bytes(content)
        return path

    def resolve_asset_path(self, project_id: str, asset_id: str) -> Path | None:
        project = self.get(project_id)
        for asset in project.model_assets:
            if asset.id == asset_id:
                path = self._assets_dir(project_id) / asset.filename
                if path.is_file():
                    return path
                uploads = self._uploads_dir(project_id) / asset.filename
                if uploads.is_file():
                    return uploads
        return None

    def _save(self, project: Project) -> None:
        data = project.model_dump(mode="json")
        self._project_file(project.id).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
