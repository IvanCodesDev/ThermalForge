# FOC Arm Thermal Workbench Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 gpt-5.6-sol、Hyper3D Bang、FOC 机械臂热设计快照、真实 GLB 和完整脱敏后端输出接入同一套本地工作台。

**Architecture:** FastAPI 提供安全的演示快照、原始输出、资产和工程理由刷新接口；React/Vite 使用 React Three Fiber 加载真实 GLB，并把输入、阶段、理由和后端 JSON 组织成工业任务控制台。已有输出作为可重复基线，上游调用失败不会破坏本地可查看结果。

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, httpx, pytest, React 19, TypeScript, Vite, Vitest, React Testing Library, Three.js, React Three Fiber, Drei.

---

### Task 1: 安全配置两条模型连接

**Files:**
- Modify: `.env`
- Modify: `.env.example`
- Modify: `core/api/routes/models.py`
- Modify: `core/providers/hyper3d.py`
- Test: `tests/test_model_routes.py`

1. 在测试中定义通用文本路由和 Hyper3D `check_balance` 的请求/响应契约。
2. 运行目标测试，确认因路由/方法不存在而失败。
3. 实现 `/models/text/responses` 兼容别名与 `GET /models/hyper3d/balance`。
4. 更新本地 `.env` 为用户提供的网关、模型与 Hyper3D key；example 保留空密钥。
5. 运行模型路由测试，并用无消耗请求验证两条真实连接。

### Task 2: 定义 FOC 演示后端契约

**Files:**
- Create: `tests/test_foc_demo.py`
- Create: `core/models/foc_demo.py`
- Create: `core/services/foc_demo.py`

1. 写快照、递归脱敏、资产发现与设计理由解析的失败测试。
2. 运行测试并确认缺少模块导致失败。
3. 实现最小 Pydantic 契约和 repository/service。
4. 运行目标测试至通过，再清理重复映射逻辑。

### Task 3: 暴露安全演示 API 与真实资产

**Files:**
- Create: `core/api/routes/foc_demo.py`
- Modify: `core/api/app.py`
- Test: `tests/test_foc_demo.py`

1. 写 `GET /api/v1/foc-demo`、`/raw`、`/assets/{name}` 和 `POST /reasoning` 的失败测试。
2. 验证 404/导入失败符合预期。
3. 实现路由、依赖注入、受控 FileResponse 与上游错误转换。
4. 验证正常响应、路径穿越拒绝、敏感字段不出现。

### Task 4: 建立前端测试与数据层

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/types/focDemo.ts`
- Create: `frontend/src/api/focDemo.ts`
- Create: `frontend/src/App.test.tsx`

1. 安装 Three/R3F、字体和测试依赖。
2. 写页面加载、错误、标签切换和敏感字段不渲染的失败测试。
3. 运行测试，确认当前页面不满足新契约。
4. 实现类型与 API client 的最小数据层。

### Task 5: 实现真实 3D 工程工作台

**Files:**
- Create: `frontend/src/components/ModelViewport.tsx`
- Create: `frontend/src/components/BackendConsole.tsx`
- Create: `frontend/src/components/DecisionLedger.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/vite.config.ts`

1. 让现有失败测试驱动页面骨架、数据状态和控制台交互。
2. 用 R3F/Drei 加载 Rodin/Bang GLB，实现 OrbitControls、整体/分件切换、自动旋转和错误占位。
3. 实现输入、热指标、阶段事件、工程决策、边界声明与完整 JSON 抽屉。
4. 完成航空试验台视觉、响应式布局、键盘焦点和 reduced-motion 支持。
5. 运行前端测试、类型检查与构建。

### Task 6: 刷新真实工程理由并验收服务

**Files:**
- Create: `outputs/foc_robot_arm_design_reasoning.json` (local generated artifact)
- Modify: `outputs/foc_robot_arm_backend_output.json` only if the refresh workflow intentionally persists a new section

1. 启动当前磁盘代码的 FastAPI，验证配置接口不暴露密钥。
2. 调用 gpt-5.6-sol 生成工程决策 JSON，并检查事实/假设/验证边界。
3. 验证 Hyper3D 余额与已存在 Rodin/Bang 资产，不重复消耗生成 credit。
4. 重启 Vite，浏览器打开工作台，确认真实 GLB、理由和完整脱敏输出可见。
5. 运行完整 pytest、前端测试、类型检查、生产构建与 HTTP 健康检查，记录新鲜结果。
