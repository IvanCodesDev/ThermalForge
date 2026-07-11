"""项目路由 — 3D 结构创作系统的入口。"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from core.models.project import ComponentSummary, ModelAsset, Project, ProjectStatus
from core.services.project_repository import ProjectRepository

router = APIRouter(prefix="/api/v1", tags=["projects"])

_repo = ProjectRepository()


def _repo_from_cwd() -> ProjectRepository:
    return _repo


@router.post("/projects", response_model=Project)
async def create_project(
    name: str = Form(...),
    description: str = Form(""),
    text_description: str = Form(""),
    pdf: UploadFile | None = File(None),
    images: list[UploadFile] = [],
):
    """创建项目，支持上传 PDF、文本描述和结构图片。"""
    repo = _repo_from_cwd()
    pdf_filename = None
    pdf_content = None
    if pdf and pdf.filename:
        pdf_filename = pdf.filename
        pdf_content = await pdf.read()

    image_data: list[tuple[str, bytes]] = []
    for img in images:
        if img and img.filename:
            image_data.append((img.filename, await img.read()))

    return repo.create(
        name=name,
        description=description,
        text_description=text_description,
        pdf_filename=pdf_filename,
        pdf_content=pdf_content,
        image_filenames=image_data,
    )


@router.get("/projects", response_model=list[Project])
async def list_projects():
    """列出所有项目。"""
    return _repo_from_cwd().list_all()


@router.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str):
    """获取项目详情。"""
    try:
        return _repo_from_cwd().get(project_id)
    except FileNotFoundError:
        raise HTTPException(404, f"项目 {project_id} 不存在")


@router.post("/projects/{project_id}/parse", response_model=Project)
async def parse_project(project_id: str):
    """解析项目输入，提取工程信息。

    如果有 PDF，尝试用 pypdf 提取文本。
    如果有文本描述，直接使用。
    调用 LLM 提取工程规格（失败时使用兜底）。
    """
    repo = _repo_from_cwd()
    project = repo.get(project_id)

    repo.update_step(project_id, "parse", "running", "正在解析输入")

    extracted_text = ""

    if project.inputs.pdf_filename:
        pdf_path = repo.base_dir / project_id / "uploads" / project.inputs.pdf_filename
        if pdf_path.is_file():
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(pdf_path))
                extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
            except ImportError:
                extracted_text = "（pypdf 未安装，无法提取 PDF 文本）"
            except Exception as exc:
                extracted_text = f"（PDF 解析失败: {exc}）"

    if not extracted_text and project.inputs.text_description:
        extracted_text = project.inputs.text_description

    project = repo.get(project_id)
    project.inputs.pdf_extracted_text = extracted_text[:5000]
    repo.update(project)
    repo.update_step(project_id, "parse", "done", f"提取文本 {len(extracted_text)} 字符")
    project = repo.update_status(project_id, ProjectStatus.parsed)
    return project


@router.post("/projects/{project_id}/import-model", response_model=Project)
async def import_model(
    project_id: str,
    model_type: str = Form("whole"),
    model_file: UploadFile = File(...),
):
    """导入已有模型文件（OBJ/GLB）作为项目资产。"""
    repo = _repo_from_cwd()
    project = repo.get(project_id)

    if not model_file.filename:
        raise HTTPException(400, "模型文件名不能为空")

    content = await model_file.read()
    path = repo.save_uploaded_asset(project_id, model_file.filename, content)

    suffix = path.suffix.lower().lstrip(".")
    fmt = "obj" if suffix in ("obj",) else "glb" if suffix in ("glb", "gltf") else suffix

    asset = ModelAsset(
        id=f"asset-{path.stem[:8]}",
        type=model_type,
        format=fmt,
        url=f"/api/v1/projects/{project_id}/model/asset-{path.stem[:8]}",
        source="uploaded",
        fidelity="concept_mesh" if model_type == "whole" else "concept_mesh",
        filename=model_file.filename,
    )
    return repo.add_asset(project_id, asset)


@router.post("/projects/{project_id}/import-textures", response_model=Project)
async def import_textures(
    project_id: str,
    textures: list[UploadFile] = [],
):
    """导入 PBR 纹理文件。"""
    repo = _repo_from_cwd()
    project = repo.get(project_id)

    for tex in textures:
        if tex and tex.filename:
            content = await tex.read()
            repo.save_uploaded_asset(project_id, tex.filename, content)

    return repo.get(project_id)


@router.post("/projects/{project_id}/set-components", response_model=Project)
async def set_components(
    project_id: str,
    components: list[dict] = [],
):
    """设置项目组件清单。"""
    repo = _repo_from_cwd()
    parsed = [ComponentSummary.model_validate(c) for c in components]
    return repo.set_components(project_id, parsed)


@router.get("/projects/{project_id}/model/{asset_id}")
async def download_model(project_id: str, asset_id: str):
    """下载模型文件。"""
    repo = _repo_from_cwd()
    path = repo.resolve_asset_path(project_id, asset_id)
    if not path:
        raise HTTPException(404, f"资产 {asset_id} 不存在")
    media_types = {
        ".glb": "model/gltf-binary",
        ".obj": "model/obj",
        ".gltf": "model/gltf+json",
        ".stp": "model/step",
        ".step": "model/step",
        ".stl": "model/stl",
    }
    media_type = media_types.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(str(path), media_type=media_type, filename=path.name)


@router.get("/projects/{project_id}/texture/{filename}")
async def download_texture(project_id: str, filename: str):
    """下载纹理文件。"""
    repo = _repo_from_cwd()
    safe = Path(filename).name
    for d in ["assets", "uploads"]:
        path = repo.base_dir / project_id / d / safe
        if path.is_file():
            return FileResponse(str(path))
    raise HTTPException(404, f"纹理 {filename} 不存在")


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """删除项目。"""
    import shutil
    repo = _repo_from_cwd()
    project_dir = repo.base_dir / project_id
    if not project_dir.is_dir():
        raise HTTPException(404, f"项目 {project_id} 不存在")
    shutil.rmtree(project_dir)
    return {"status": "deleted", "id": project_id}
