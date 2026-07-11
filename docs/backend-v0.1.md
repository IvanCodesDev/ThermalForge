# ThermalForge 后端核心 v0.1（第一轮）

> 定位（据 07-09 关节热管理调研 PDF 收口）：**机器人关节热管理外壳优化**——把只承力的关节壳体，改造成同时导热/扩散/扰流的热结构件。
> 本轮交付 = 可运行的**后端核心引擎**：参数化结构生成 + 简化热路评估 + 相似度匹配 + API。前端动效 5 步全部调这套引擎。

## 1. 目录

```
core/
  models/schema.py      叶脉/流道·pin-fin/平板 三套参数 schema（参数即标签，含 cooling_medium）
  engine/generator.py   程序化结构生成 → SVG + 几何量（有效换热面积/材料体积/扩散因子）
  engine/thermal.py     简化热路模型：热阻网络 + 集总热容 → T_hotspot / time-to-limit / 质量
  engine/matcher.py     constraint_vector 余弦相似度检索（按介质分桶）
  api/app.py            FastAPI：/generate /evaluate /compare /match /library /health
data/
  seed_library.json     8 个预参数化种子案例（含预计算指标 + SVG 路径）
  leaf_vein/*.svg  channel/*.svg   预生成结构图
scripts/
  build_library.py      重建种子库
  demo_pipeline.py      Happy Path 端到端演示（路演最小闭环）
```

## 2. 三种候选结构（对齐 PDF 四候选，本轮实现前三）

| 结构 | 适用 | 特点 |
|---|---|---|
| 平板基线 flat | 对照组 | 无面积增益，易过热 |
| 叶脉热桥 leaf_vein | 热点扩散、弱气流 | 分形分支，扩散因子最高，单位重量收益优 |
| pin-fin 阵列 | MOSFET 热点、弱气流 | 圆柱针阵扰流，轻但热容小 |
| （TPMS/Gyroid） | 有明确风道/液冷 | 第二轮扩展 |

## 3. 热路模型（PDF「可信的简化版」）

```
热源 --R_interface--> 结构 --R_spread--> 换热面 --R_conv--> 介质
T_hotspot = T_amb + P · R_total
瞬态: T(t)=T_amb+P·R_total·(1-e^(-t/τ)),  τ=R_total·C_th
```
- 材料默认 AlSi10Mg（k=150, ρ=2670, c=900），可选 Cu / Graphite。
- 介质对流系数 h：air=45 / liquid=900 / phase_change=1500 / heat_pipe=1200。
- 三大评审指标（PDF §9.4）：T_hotspot 下降、time-to-limit、单位重量收益。

## 4. 跑通验证（Happy Path 结果，功率 28W / 气冷 / 阈值 80℃）

| 结构 | T_hotspot | 到阈值 | 质量 |
|---|---|---|---|
| 平板基线 | 133.9℃（过热） | 126s | 51.3g |
| **叶脉热桥** | **69.8℃（稳态不越限）** | 不越限 | 29.1g |
| pin-fin 阵列 | 106.9℃ | 6s | 2.1g |

**结论**：叶脉热桥把关节从过热（133.9℃）压到降额阈值以下（69.8℃），降温 64℃、还轻 22g——正是 PDF §9.4 核心卖点。

## 5. 运行

```bash
# 依赖
pip install -r requirements.txt

# 重建种子库（生成 SVG + 指标）
python scripts/build_library.py

# 端到端演示（路演最小闭环）
python scripts/demo_pipeline.py

# 启动 API（前端联调）
uvicorn core.api.app:app --reload --port 8000
# 浏览器打开 http://localhost:8000/docs 看交互式接口文档
```

## 6. 已知边界（诚实标注）

- 热路模型是**量纲正确的工程估算**，非 CFD；用于对比与讲故事，不做绝对定量承诺（路演口径同 PDF）。
- 结构生成目前是 2D SVG；3D（STL/CadQuery）与真实 CFD 是第二轮。
- pin-fin 在弱气流下不如叶脉（与 PDF 结论一致），不是所有工况都赢。

## 7. 下一步（第二轮）

1. 3D 生成（CadQuery → STL）+ 前端 three.js 展示。
2. 扩展 TPMS/Gyroid、导热桥、隔热/加热片结构。
3. 自采 + 半自动提取真实开源案例入库（GrabCAD/学术叶脉），扩大匹配覆盖。
4. 第一轮完成 → 上传 GitHub（仓库地址/可见性待定）。
