# 视锂工坊工业AI协同系统

一个基于React和Node.js的工业AI对话系统，集成了阿里云Qwen大语言模型。

## 功能特性

- 🤖 智能AI对话助手
- 📊 实时生产监控仪表板
- 🔒 安全操作双人复核机制
- 📱 现代化的用户界面
- 🔄 多会话管理

## 技术栈

- **前端**: React 19, TypeScript, Vite, Tailwind CSS, Recharts, Lucide React
- **后端**: Node.js, Express, Axios
- **AI**: 阿里云Qwen Plus模型

## 安装和运行

### 1. 安装依赖

```bash
# 安装所有依赖（根目录、后端、前端）
npm run install:all
```

### 2. 启动服务

#### 方式一：同时启动前后端（推荐）
```bash
npm run dev
```

#### 方式二：分别启动
```bash
# 终端1：启动后端服务
npm run backend

# 终端2：启动前端服务
npm run frontend
```

### 3. 访问应用

打开浏览器访问：http://localhost:5173

## API配置

复制 `.env.example` 为 `.env`，再填写自己的阿里云 DashScope 配置：

```env
DASHSCOPE_API_KEY=your_api_key
DASHSCOPE_APP_ID=your_app_id
DASHSCOPE_MODEL=qwen-plus-latest
```

`.env` 已被 Git 忽略，严禁把真实密钥写入源码或提交到仓库。

## 项目结构

```
shiligongfang/
├── backend/                 # Node.js后端服务
│   ├── server.js           # Express服务器主文件
│   └── package.json        # 后端依赖
├── frontend/               # React前端应用
│   ├── components/         # React组件
│   │   ├── AIChat.tsx     # AI对话组件
│   │   └── Dashboard.tsx  # 仪表板组件
│   ├── src/               # 源码目录
│   └── package.json       # 前端依赖
├── data/                   # 静态数据和图片
└── package.json           # 项目根配置
```

## 主要功能

### AI对话系统
- 支持自然语言对话
- 智能识别高风险操作指令
- 自动生成结构化执行方案
- 双人复核安全机制

### 生产监控
- 实时产线节拍监控
- 缺陷率统计分析
- 设备状态可视化
- 角色协同状态展示

## 开发说明

### 后端API接口

- `GET /api/health` - 健康检查
- `POST /api/chat` - AI对话接口

  请求体：
  ```json
  {
    "message": "用户消息",
    "sessionId": "会话ID"
  }
  ```

  响应：
  ```json
  {
    "success": true,
    "response": "AI回复内容",
    "sessionId": "会话ID",
    "timestamp": "时间戳"
  }
  ```

### 安全机制

系统对高风险操作（如设备启动、停止、重启等）会自动触发：
1. 生成详细的SOP执行步骤
2. 标识潜在风险
3. 要求双人复核确认
4. 记录操作日志

## 注意事项

1. 确保后端服务（端口3001）和前端服务（端口5173）都正常运行
2. AI回复可能需要几秒钟处理时间
3. 高风险操作需要通过双人复核才能执行

## 许可证

本项目仅用于教育和演示目的。
