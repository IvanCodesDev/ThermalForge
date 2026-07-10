const express = require('express');
const cors = require('cors');
const axios = require('axios');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());

// 密钥只从环境变量读取，避免源码和日志泄露真实凭证
const API_KEY = process.env.DASHSCOPE_API_KEY;
const APP_ID = process.env.DASHSCOPE_APP_ID;
const MODEL = process.env.DASHSCOPE_MODEL || 'qwen-plus-latest';

// 阿里云API端点
const API_URL = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation';

// 聊天API路由
app.post('/api/chat', async (req, res) => {
  try {
    const { message, sessionId } = req.body;

    if (!API_KEY || !APP_ID) {
      return res.status(503).json({
        error: 'AI service is not configured',
        details: '请配置 DASHSCOPE_API_KEY 和 DASHSCOPE_APP_ID'
      });
    }

    if (!message) {
      return res.status(400).json({ error: 'Message is required' });
    }

    // 构建阿里云 API 请求体（指示模型输出 JSON 格式的结构化诊断方案）
    const systemPrompt = `你是工业自动化领域的智能助手，目标是接收用户关于设备/产线的自然语言问题，结合内部知识库生成结构化诊断方案。请严格按 JSON 格式返回内容，字段如下：
{
  "summary": "一句话摘要，用于聊天气泡显示（简短）",
  "problem": "问题识别（简短）",
  "steps": ["步骤1", "步骤2", "..."],
  "basis": "依据（文档或手册名）",
  "role": "责任人或岗位",
  "requiresAuth": true/false,
  "authStatus": "pending/approved/rejected",
  "risks": "风险提示（简短）"
}
只返回 JSON，不要有任何多余解释或代码块。如果无法确定具体字段，尽量返回空字符串或空数组。`;

    const requestBody = {
      model: MODEL,
      input: {
        messages: [
          {
            role: 'system',
            content: systemPrompt
          },
          {
            role: 'user',
            content: message
          }
        ]
      },
      parameters: {
        max_tokens: 1500,
        temperature: 0.0
      }
    };

    // 调用阿里云API
    const response = await axios.post(API_URL, requestBody, {
      headers: {
        'Authorization': `Bearer ${API_KEY}`,
        'Content-Type': 'application/json',
        'X-DashScope-AppId': APP_ID
      },
      timeout: 30000 // 30秒超时
    });

    // 调试：打印完整响应以便排查（仅在开发环境）
    if (process.env.NODE_ENV !== 'production') {
      console.log('阿里云原始响应：', response.data);
    }

    // 解析API响应，尝试从常见字段中取文本
    let aiText = '';
    if (typeof response.data === 'string') {
      aiText = response.data;
    } else if (response.data.output && typeof response.data.output === 'string') {
      aiText = response.data.output;
    } else if (response.data.output?.text) {
      aiText = response.data.output.text;
    } else if (response.data.output?.choices?.[0]?.message?.content) {
      aiText = response.data.output.choices[0].message.content;
    } else if (response.data.result) {
      aiText = typeof response.data.result === 'string' ? response.data.result : JSON.stringify(response.data.result);
    } else {
      aiText = JSON.stringify(response.data);
    }

    // 尝试把 aiText 当作 JSON 解析（模型按指令返回 JSON 时）
    let structured = null;
    try {
      structured = JSON.parse(aiText);
    } catch (err) {
      // 解析失败，structured 保持 null
    }

    // 返回结构化或原始文本
    res.json({
      success: true,
      response: aiText,
      structured: structured ? true : false,
      structuredData: structured || null,
      sessionId: sessionId,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('API调用错误:', error.response?.data || error.message);

    // 返回错误信息
    res.status(500).json({
      success: false,
      error: 'AI服务暂时不可用，请稍后重试',
      details: error.response?.data?.message || error.message
    });
  }
});

// 健康检查路由
app.get('/api/health', (req, res) => {
  res.json({ status: 'OK', timestamp: new Date().toISOString() });
});

app.listen(PORT, () => {
  console.log(`后端服务运行在端口 ${PORT}`);
});
