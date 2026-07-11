# ThermalForge 上传测试案例

把下列文件直接拖到 Agent 输入框即可测试：

- `01-foc-joint-complete.md`：完整 FOC 关节约束，预期直接完成工程摘要和热设计。
- `02-liquid-cold-plate-complete.txt`：完整液冷冷板约束，覆盖不同功率、包络和制造要求。
- `03-robot-joint-needs-clarification.md`：故意缺少最高环境温度，预期进入补充信息阶段。测试回答可填写“最高环境温度 38 °C”。
- `04-foc-joint-complete.pdf`：第一项的 PDF 版本，用于测试 PDF 解析。
- `05-liquid-cold-plate-complete.docx`：第二项的 DOCX 版本，用于测试 DOCX 解析。

建议输入框目标：

`请提取可追溯约束，完成筛选级热设计，生成六视图概念图，并展示可交互的任务模型。不要把概念网格描述为可制造 CAD。`

`generate_binary_cases.py` 用于从文本案例重新生成 PDF 和 DOCX；它依赖后端开发环境中的 PyMuPDF 与 python-docx。
