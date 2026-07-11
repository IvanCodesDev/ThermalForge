# ThermalForge

机电热设计工程 Agent：上传约束文档 → 解析与补问 → 工程摘要与筛选级热设计 → 产物与可交互 3D 检视。

主线代码：`thermalforge-api`（FastAPI）+ `thermalforge-studio`（React Agent 单页）。

---

## 仓库结构

| 路径 | 作用 |
| --- | --- |
| `thermalforge-api/` | 任务编排 API（文档、澄清、工程摘要、热设计、图像、Viewer、SSE、Worker） |
| `thermalforge-studio/` | Agent 前端（对话、上传、进度、结果、R3F 模型舞台） |
| `compose.yaml` | Postgres、Redis、LocalStack S3、API、Worker |
| `infra/localstack/` | Compose S3 初始化 |
| `fixtures/` | 上传与热分析测试夹具 |
| `demo-inputs/` | 演示用需求 / 约束样例 |
| `frontend/public/models/` | API / Compose 挂载的参考 GLB |
| `thermalforge-studio/public/` | Studio 静态资源 |
| `docs/` | 设计与全链路开发文档 |
| `3d/` | CAD 生成脚本与参考模型 |

---

## 本地开发

### 后端

```bash
cd thermalforge-api
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# macOS / Linux: source .venv/bin/activate
python -m pip install -r requirements.lock
cp .env.example .env   # Windows 可用 copy
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

配置项见 `thermalforge-api/.env.example` 与 `thermalforge-api/app/config.py`（前缀 `THERMALFORGE_`）。密钥写在本地 `.env`，不要提交。

默认开发：SQLite、进程内队列、本地产物、`fixture` LLM / 图像。健康检查：`/health/live`、`/health/ready`；Swagger：`/docs`。

### 前端

```bash
cd thermalforge-studio
npm install
npm run dev
```

开发服务器把 `/v1`、`/health` 代理到 `http://127.0.0.1:8000`（`VITE_API_PROXY_TARGET` / `VITE_API_BASE_URL` 可改）。上传样例见 `fixtures/upload-cases/`。

---

## Docker Compose

```bash
docker compose up --build
```

服务与环境变量以根目录 `compose.yaml` 为准。API 默认映射 `8000`，LocalStack `4566`。模型资产挂载：`./frontend/public/models`。Studio 可在宿主机继续 `npm run dev`。

---

## 配置与契约

| 内容 | 文件 |
| --- | --- |
| API 配置 | `thermalforge-api/.env.example`、`thermalforge-api/app/config.py` |
| Compose | `compose.yaml` |
| HTTP 契约 | `thermalforge-api/openapi.json` |
| 前端客户端生成 | `cd thermalforge-studio && npm run api:generate` |

真实 LLM：设置 `THERMALFORGE_LLM_PROVIDER` 为 `anthropic` 或 `openai_compatible`，并配置对应密钥与模型。图像：`THERMALFORGE_IMAGE_PROVIDER`。

---

## 常用命令

**Studio（`thermalforge-studio/`）**

| 命令 | 作用 |
| --- | --- |
| `npm run dev` | 开发 |
| `npm run build` | 构建 |
| `npm run test` | Vitest |
| `npm run test:e2e` | Playwright |
| `npm run lint` | Oxlint |
| `npm run api:generate` | 从 OpenAPI 生成客户端 |

**API（`thermalforge-api/`，已激活 venv）**

```bash
pytest
ruff check .
mypy app
```

---

## 文档

- [`docs/THERMALFORGE_END_TO_END_DEVELOPMENT.md`](docs/THERMALFORGE_END_TO_END_DEVELOPMENT.md)
- [`docs/design.md`](docs/design.md)
- [`fixtures/upload-cases/README.md`](fixtures/upload-cases/README.md)
- [`thermalforge-api/openapi.json`](thermalforge-api/openapi.json)
