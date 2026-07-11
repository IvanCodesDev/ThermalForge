# ThermalForge 参数中枢 v0.2（参数化契约 · 子叶负责）

> 定位：PRD-ThermalForge-team.md §9.5「参数中枢（最难任务）归属子叶」——连接理解层与生成层的 schema contract，全队并行前提。
> 模型（3D 几何生成 / 热仿真）交由其他队友；本模块守住"参数怎么定义、用户输入与库案例如何在同一空间匹配"。
> 对齐文档：`parameter-schema-v0.1.md`（参数中枢总纲）、`annotation-strategy-v0.1.md`（几何参数集）。

---

## 1. 解决什么问题

第一轮后端（backend-v0.1）已有结构几何参数（叶脉/流道/平板）+ 几何相似度匹配，但缺三块契约层：

1. **上游输入层**：用户/上游给出的器件信息没有结构化契约（device_type / power_w / max_temp_c / material / has_fan / max_weight_g / manufacturing / ambient_temp_c）。
2. **库条目层**：开源案例未参数化入库（缺 case_id / source / device_context / model_path / perf_notes）。
3. **约束向量（意图空间）**：用户与库案例未在同一个特征空间匹配——之前只有几何向量（17 维），没有意图向量。

v0.2 把这三块补成可运行契约，实现 **「用户输入 ↔ 库案例同空间匹配」+「意图 → 结构模板推荐」**。

---

## 2. 架构与文件

```
core/models/user_input.py      UserInput（上游输入层）+ to_vector() 23 维意图约束向量
core/models/library.py         LibraryEntry（§2.5 库条目）+ constraint_vector 由 device_context 派生
core/models/schema.py          结构几何参数（叶脉/流道/平板）+ RANGE_SPECS 字段范围表
core/parameter_hub.py          ParameterHub：match_user_to_library() + recommend_structure()
core/api/app.py                新增 /match_user /recommend /schema（/generate /evaluate /compare /match /library 保留）
scripts/export_schemas.py      导出 data/schemas/*.json（契约文件，供 GitHub 上传）
scripts/build_library.py       8 个种子案例，每个附 device_context（§2.5 库参数化）
scripts/demo_hub.py            中枢闭环演示
data/schemas/*.schema.json     契约 JSON Schema（叶脉/流道/平板/user_input/library_entry）
data/schemas/constraint_vector.spec.json  23 维约束向量规格
data/seed_library.json         含 geometry_vector（几何匹配）+ device_context（意图匹配）
```

### 两个向量空间（关键设计）
| 向量 | 维度 | 用途 | 键名 |
|---|---|---|---|
| 几何向量 `to_vector()` | 16/15/4 | 结构间几何相似度匹配 | `geometry_vector` |
| 意图向量 `UserInput.to_vector()` | 23 | 用户输入 ↔ 库案例同空间匹配 | `LibraryEntry.constraint_vector` |

两者**不混用**：几何匹配走 `geometry_vector`，意图匹配走意图向量。库案例的意图向量由 `device_context`（UserInput）派生，保证与用户输入同空间。

### 意图约束向量（23 维，固定顺序）
`device_type` one-hot(5) + `material` one-hot(6) + `manufacturing` one-hot(3) + `has_fan`(1) + `thermal_load`(1) + `temp_headroom`(1) + `max_weight`(1) + `ambient`(1) + `preferred_medium` one-hot(4)。
派生：`thermal_load = power_w / 体积`；`preferred_medium` 由热负载/温度余量派生（液冷 or 气冷）。

---

## 3. API 端点

| 端点 | 入参 | 出参 |
|---|---|---|
| `POST /match_user` | `user_input` + `top_k` | 库案例按意图余弦 TopK（含 sim / perf_notes / preview_img / model_path） |
| `POST /recommend` | `user_input` | 意图 → 结构模板（可直接喂 `/generate`） |
| `GET /schema` | — | 约束向量规格 + 结构 schema 清单 |
| `POST /match` | 结构参数 | 几何相似度匹配（回归，已改用 `geometry_vector`） |
| `POST /generate` `/evaluate` `/compare` `/library` | — | 同 v0.1 |

---

## 4. 运行

```bash
# 1. 导出契约 JSON Schema（GitHub 上传用）
venv python scripts/export_schemas.py
# 2. 重建种子库（含 device_context 意图上下文）
venv python scripts/build_library.py
# 3. 中枢闭环演示
venv python scripts/demo_hub.py
# 4. 启服务
venv uvicorn core.api.app:app --reload --port 8000
```

---

## 5. 验证结果（2026-07-10）

- `/schema`：constraint_vector 维度 = 23，结构 schema = [leaf_vein, channel, flat]。
- `/match_user`（关节电机 28W 气冷 50mm）：LV-001 sim=1.0000、CH-001 0.9997、FB-000 0.9997（同 device_type 优先）。
- `/recommend`：关节电机→叶脉 50mm 气冷；Jetson→平行液冷冷板 70mm；传感器舱→蛇形通风 40mm（尺寸随设备自适应）。
- `/match`（几何回归）：叶脉查询 LV-001 0.9944、LV-002 0.9459。

---

## 6. 诚实边界

- 意图向量为工程特征工程（one-hot + 归一化），非学习所得；余弦相似度只反映字段接近度。
- `recommend_structure` 为启发式规则映射，非优化结果；真正多目标优化留给 Optuna（队友/后续）。
- 库案例的 `model_path` 暂空（3D 模型待补），`preview_img` 暂用 2D SVG。
- 种子库仅 8 例程序化生成，无真实开源案例入库（§2.5 库预处理的人工/半自动转参数待队友）。

---

## 7. 下一步

- 接前端 5 步动效：`/match_user` 接 Step1（输入工况）、`/recommend`+`/generate` 接 Step2-3（建模/结构）、`/evaluate`+`/compare` 接 Step4-5（交互/优化）。
- 扩库：真实开源电机/舵机/关节案例参数化入库（补 `model_path` 3D）。
- 扩结构：§2.6 的 `topology`/`fish_scale_fin`/`ventilation`/`thermal_sheet` 从几何扁平字段升级为独立参数对象（第二轮）。
- GitHub 上传（annotation §6）：`data/schemas/` + 种子库 + demo，需仓库地址 + 可见性。
