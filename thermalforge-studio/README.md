# thermalforge-studio

ThermalForge Agent 前端（React + TypeScript + Vite + React Three Fiber）。

完整安装、联调与能力边界说明见仓库根目录 [`README.md`](../README.md)。

## 常用命令

```bash
npm install
npm run dev
npm run test
npm run build
```

开发时默认把 `/v1`、`/health` 代理到本机 API（见 `vite.config.ts`）。从 OpenAPI 生成客户端：

```bash
npm run api:generate
```

契约文件：`../thermalforge-api/openapi.json`。
