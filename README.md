# ThermalForge

面向机电热设计场景的工程 Agent：上传约束文档 → 解析与补问 → 工程摘要与筛选级热设计 → 任务产物与可交互 3D 检视。

当前产品主线是 **`thermalforge-api`（FastAPI）+ `thermalforge-studio`（React Agent 单页）**。仓库里还有历史实验代码与 CAD 素材；它们不是同一条运行时链路，下文会分开说明。

> 配置、依赖版本与接口契约以仓库内源文件为准，不要把本 README 里的示例当成唯一真源。

---

## 当前能做什么 / 还不能做什么

**已可本地跑通（默认 fixture LLM / 图像，无需付费密钥）：**

- 创建项目与任务，流式上传工程文档（含 PDF / DOCX 等解析与 OCR）
- 任务状态机 + SSE 事件流；缺关键约束时可进入补充问答
- Engineering Brief、筛选级热分析 / 热设计产物
- Agent 完成态展示工程依据与脱敏后端输出
- 中央 3D 检视（整体 / 分件、爆炸与部件说明）；`ready` 阶段使用仓库内**受控参考网格**，需明确标注为概念参考，**不等于**本次输入生成的可制造 CAD

**仍属后续能力（文档有规划，当前不要按已交付验收）：**

- 真实多视图概念图质检闭环、Hyper3D Rodin 生成与制造级 CAD 装配
- Hermes Agent 工具编排、端到端生产部署与监控

更细的基线与阶段划分见 [`docs/THERMALFORGE_END_TO_END_DEVELOPMENT.md`](docs/THERMALFORGE_END_TO_END_DEVELOPMENT.md)。

---

## 仓库结构

| 路径 | 作用 |
| --- | --- |
| `thermalforge-api/` | 任务编排 API：文档、澄清、工程摘要、热设计、图像清单、Viewer、SSE、ARQ Worker |
| `thermalforge-studio/` | Agent 前端：对话、上传、进度、结果展示、R3F 模型舞台 |
| `compose.yaml` | 本地联调栈：Postgres、Redis、LocalStack S3、API、Worker |
| `infra/localstack/` | Compose 下 S3 bucket 初始化脚本 |
| `fixtures/` | 上传与热分析测试夹具（含 `fixtures/upload-cases/`） |
| `demo-inputs/` | 演示用中文需求 / 约束样例 |
| `frontend/public/models/` | API / Compose 挂载的参考 GLB 资产根（见环境变量 `THERMALFORGE_MODEL_ASSET_ROOT`） |
| `thermalforge-studio/public/` | Studio 静态资源（含 STL / showcase 等） |
| `docs/` | 设计与全链路开发说明 |
| `3d/` | SolidWorks / STEP 等 CAD 生成与参考资产（独立于 Web 运行时） |
| `core/`、根目录部分脚本与旧文档 | 早期 Agent / 仿真实验与交付笔记；**不是**当前 studio↔api 默认路径 |

---

## 架构（主线）

```text
Browser (thermalforge-studio)
    │  Vite 代理 /v1、/health  →  API
    ▼
thermalforge-api (FastAPI)
    ├─ 任务状态机 + PipelineRunner
    ├─ 队列：开发默认可进程内执行；Compose 启用 Redis + ARQ Worker
    ├─ ArtifactStore：local 文件系统 或 S3 兼容存储
    └─ LLM / Image Provider：fixture | anthropic | openai_compatible（由环境变量切换）
```

任务状态枚举以 [`thermalforge-api/app/domain/enums.py`](thermalforge-api/app/domain/enums.py) 为准，例如：`created` → `uploaded` → `parsing` → … → `ready` / `failed` / `cancelled`。

HTTP 契约以导出的 [`thermalforge-api/openapi.json`](thermalforge-api/openapi.json) 为准；前端类型可由 Studio 脚本从该文件生成。

---

## 环境要求

- **Python** ≥ 3.12（见 `thermalforge-api/pyproject.toml`）
- **Node.js** 与 npm（用于 `thermalforge-studio`；具体 LTS 以你本机已验证版本为准）
- 可选：**Docker / Compose**（跑 Postgres + Redis + LocalStack + API + Worker）
- Windows 上若使用 SolidWorks 自动化脚本，需本机安装对应 CAD 环境（与 Web 主线无关）

---

## 快速开始（本机开发，SQLite + fixture）

适合先验证 API 与 Agent UI，不强制起 Docker。

### 1. 后端

```bash
cd thermalforge-api
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
# source .venv/bin/activate

python -m pip install -r requirements.lock
# 开发依赖（测试 / lint）：
# python -m pip install -r requirements-dev.lock

copy .env.example .env   # Windows；其它系统用 cp
```

按需编辑 `.env`。**密钥只写在本地 `.env`，不要提交仓库。** 权威键名与默认值见：

- [`thermalforge-api/.env.example`](thermalforge-api/.env.example)
- [`thermalforge-api/app/config.py`](thermalforge-api/app/config.py)（前缀均为 `THERMALFORGE_`）

默认开发取向（以 `.env.example` 为准，可被本地 `.env` 覆盖）：

- SQLite + `AUTO_CREATE_SCHEMA=true`
- `QUEUE_ENABLED=false`（进程内跑 pipeline）
- `ARTIFACT_BACKEND=local`
- `LLM_PROVIDER=fixture`、`IMAGE_PROVIDER=fixture`

启动：

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

健康检查：`GET /health/live`、`GET /health/ready`。交互文档：启动后访问 FastAPI 自带 `/docs`。

### 2. 前端

```bash
cd thermalforge-studio
npm install
npm run dev
```

默认开发服务器会把 `/v1` 与 `/health` 代理到 `http://127.0.0.1:8000`（可用环境变量 `VITE_API_PROXY_TARGET` 覆盖，见 `vite.config.ts`）。也可设置 `VITE_API_BASE_URL` 直连 API。

浏览器打开终端里 Vite 打印的本地地址（通常是 `http://127.0.0.1:5173`）。

### 3. 试用上传案例

将 [`fixtures/upload-cases/`](fixtures/upload-cases/) 中的样例拖入 Agent 输入框。说明见该目录下的 README。`demo-inputs/` 也可作中文演示素材。

---

## Docker Compose 联调

根目录 [`compose.yaml`](compose.yaml) 会拉起 Postgres、Redis、LocalStack（S3）、API、Worker。

```bash
# 在仓库根目录
docker compose up --build
```

要点（细节以 `compose.yaml` 为准，勿写死到脚本外别处）：

- API 映射宿主机 **8000**；LocalStack **4566**
- Compose 内默认 `QUEUE_ENABLED=true`、`ARTIFACT_BACKEND=s3`，并跑 `alembic upgrade head`
- LLM / Image 仍可通过宿主机环境变量注入（未设置时回落到 fixture）
- 模型资产卷挂载为 `./frontend/public/models` → 容器内 `THERMALFORGE_MODEL_ASSET_ROOT`

数据库密码等敏感项请用环境变量覆盖 Compose 中的开发默认值，不要提交真实口令。

Studio 仍建议在宿主机 `npm run dev`，CORS 已允许本地 Vite 源（见 API 配置中的 `THERMALFORGE_CORS_ORIGINS`）。

---

## 配置说明（不要写死）

| 主题 | 真源 |
| --- | --- |
| API 全部配置项 | `thermalforge-api/app/config.py` + `thermalforge-api/.env.example` |
| Compose 服务与环境 | `compose.yaml` |
| 根目录旧式/其它密钥样例 | 根 `.env.example`（偏历史实验；**主线 API 用 `thermalforge-api/.env.example`**） |
| OpenAPI 契约 | `thermalforge-api/openapi.json`（可用 `thermalforge-api/scripts/export_openapi.py` 再导出） |
| 前端 OpenAPI 客户端生成 | `thermalforge-studio` → `npm run api:generate` |

切换真实 LLM 时，把 `THERMALFORGE_LLM_PROVIDER` 设为 `anthropic` 或 `openai_compatible`，并填入对应密钥与 `BASE_URL` / `MODEL`。图像同理（`THERMALFORGE_IMAGE_PROVIDER`）。**切真实供应商会产生费用，且行为依赖上游可用性。**

---

## API 一览

路径完整列表见 OpenAPI。当前分组包括：

- `GET /health/live`、`GET /health/ready`
- `POST /v1/projects`、任务创建与查询
- 文档上传、澄清回答、任务 start / cancel / retry
- `GET /v1/tasks/{task_id}/events`（SSE）
- engineering-brief、thermal-analysis、thermal-design
- image-manifest / 图像内容、viewer-manifest / 模型内容、viewer-library

---

## 前端脚本

在 `thermalforge-studio/`：

| 命令 | 作用 |
| --- | --- |
| `npm run dev` | 开发服务器 |
| `npm run build` | 生产构建 |
| `npm run test` | Vitest 单元 / 组件测试 |
| `npm run test:e2e` | Playwright（需本机浏览器依赖） |
| `npm run lint` | Oxlint |
| `npm run api:generate` | 从 `../thermalforge-api/openapi.json` 生成客户端 |

视觉与交互约定见 [`docs/design.md`](docs/design.md)。

---

## 后端测试与质量工具

在已激活的 `thermalforge-api` 虚拟环境中：

```bash
pytest
ruff check .
mypy app
```

依赖与工具版本以 `pyproject.toml`、`requirements.lock`、`requirements-dev.lock` 为准。

---

## CAD / 3D 资产

- Web Viewer 参考网格：优先看 `frontend/public/models/`（Compose / API 默认挂载点）以及 Studio `public/models/`。
- 冷板生成脚本与审查产物等：`3d/generated/cold-plate/`。
- 其它 STEP / SLDPRT 参考件在 `3d/` 子目录下，供设计与自动化实验使用，**不随 `npm run dev` 自动加载**。

---

## 安全与诚实工程原则

- 切勿提交 `.env`、密钥、私钥或生产连接串（根 `.gitignore` 已忽略常见密钥与本地数据目录）。
- 前端不得持有 LLM / 图像 / Hyper3D 等密钥；一律经后端配置注入。
- 界面与报告中区分：**可追溯工程产物** vs **概念参考网格** vs **尚未实现的生成链路**。

---

## 相关文档

- [`docs/THERMALFORGE_END_TO_END_DEVELOPMENT.md`](docs/THERMALFORGE_END_TO_END_DEVELOPMENT.md) — 全链路目标、已完成与未完成清单
- [`docs/design.md`](docs/design.md) — Agent 前端设计规范
- [`fixtures/upload-cases/README.md`](fixtures/upload-cases/README.md) — 上传测试案例说明
- [`thermalforge-api/openapi.json`](thermalforge-api/openapi.json) — HTTP 契约

---

## 贡献与分支

默认以 `main` 为集成分支。改动 API 契约后请同步更新 `openapi.json` 并重新生成 Studio 客户端。提交前在本机跑通与改动相关的测试。
