# 微流道冷板：参数化 → 仿真反馈 → 优化闭环

本文档说明 ThermalForge 中冷板（基于你提供的 SpaceClaim V252 三层微流道脚本与 `0710.stp`）是如何实现「参数自动变化 → 几何重建 → 仿真反馈 → 自动排序/优化」的。

## 1. 闭环总览

```
┌─────────────────────────────────────────────────────────────────────┐
│  参数空间 (search_space JSON)                                        │
│  channel_width / channel_gap / t_layer2 / manifold_length ...        │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │  网格 或 采样 (Latin-hypercube / 随机)
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  ColdPlateParams（参数契约，含 validate + derived + parameter_hash） │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │  render_cold_plate_script()
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  SpaceClaim 候选脚本 (.py) + 运行前清单 (.json)                       │
│  → SpaceClaimRunner 无头执行（已安装授权 ANSYS 时）→ STEP + 结果 json │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │  ColdPlateSimulationBackend.evaluate()
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  ColdPlateObjectives                                                 │
│  max_temperature_c / pressure_drop_pa / mass_g / max_stress_mpa      │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │  evaluate_objectives() 约束惩罚 + 加权成本
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  rank_simulation_results() 排序 → 最优候选 + 排名报告                 │
│  （可选）把结果回灌优化器，提出下一组参数 → 回到顶部迭代              │
└─────────────────────────────────────────────────────────────────────┘
```

关键点：每次迭代都记录了 `candidate_id → params_hash → 脚本 → STEP → 仿真指标`，因此不会出现「仿真结果很好但不知对应哪个模型」的情况。

## 2. 参数如何“自动变化”

参数不能直接修改现有 STEP 里的网格。我们建立一套**可重新生成的参数化建模规则**：每个候选都是根据一组 `ColdPlateParams` 重新渲染出的 SpaceClaim 脚本，由 SpaceClaim 重新构建实体。

两种探索策略（与 `build_cold_plate_candidates` / `sample_cold_plate_candidates` 对应）：

- **网格（grid）**：每个维度取离散边界值，组合可复现、覆盖边界。
  `channel_width × channel_gap × t_layer2 × manifold_length` = 3×3×3×3 = 81 个候选。
- **采样（sample）**：每个维度在 `[low, high]` 连续区间随机取值，探索网格之间的连续空间，
  用 `random.Random(seed)` 保证可复现，丢弃 `validate()` 不通过的非法组合。

当 `SpaceClaimRunner` 可用时，脚本会被无头执行成真实 STEP；不可用时闭环只生成脚本、由 `ColdPlateLumpedBackend` 给出趋势估算，流程不中断。

## 3. 仿真结果如何反哺优化

仿真后端返回物理指标 `ColdPlateObjectives`，由 `evaluate_objectives()` 转成可排序的**加权成本**（分数越低越好）：

```
weighted_cost = max_temperature_c
              + 0.005 * pressure_drop_pa
              + 0.02  * mass_g
              + 约束惩罚（温度/压降/应力超限时放大）
```

- 约束：`max_temperature_c ≤ 80`、`pressure_drop_pa ≤ 1000`、`max_stress_mpa ≤ 120`。
- 排序规则：**可行候选优先**，其次按加权成本升序。

`ColdPlateExternalBackend` 读取 ANSYS（Fluent/Mechanical）导出的结果 JSON，字段映射见 `core/engine/cold_plate_simulation.py` 顶部表格，支持直接 `{"max_temperature_c": ...}` 或嵌套 `{"result": {...}}`。
接入真实仿真后，用 `ColdPlateExternalBackend` 替换 `ColdPlateLumpedBackend` 即可，其余闭环不变。

## 4. 本机当前状态（重要边界）

- **SpaceClaim 已安装于本机 `C:\Program Files\ANSYS Inc\v251\scdm\SpaceClaim.exe`（ANSYS 2025 R1，API 命名空间 `SpaceClaim.Api.V251`），但当前未授权**：`Shared Files/Licensing/license_files` 为空、无 license server、`ANSYS, Inc. License Manager CVD` 服务 Stopped。因此 `SpaceClaimRunner.preflight()` 会失败，闭环自动降级——只生成 SpaceClaim 脚本而不执行，仿真用 `ColdPlateLumpedBackend` 解析估算。授权完成后 preflight 通过，即可无头生成真实 STEP。
- **注意 API 版本**：用户原始脚本写的是 `V252`，但本机实际安装是 **V251**。无头执行必须用 `--api-version V251`；加 `--spaceclaim` 时 CLI 会自动用探测到的版本（V251）覆盖默认 V252，无需手填。
- runner 用 `-RunScript=<脚本>` 触发无头执行（早期误用的 `/IronPython` 不是执行开关）；生成的候选脚本末尾已加 `Application.Exit()`，确保批处理进程能正常退出。
- **`ColdPlateLumpedBackend` 是趋势 oracle，不是真实 CFD/FEA**。其温度/压降量级经过调参，能正确区分「通道越密、流道层越厚 → 越凉」「质量随体积增长」等趋势，但绝对值不能直接当作设计指标。
- 真实高保真验证路线：SpaceClaim 无头生成 STEP → 网格 → Fluent/Mechanical → 导出结果 JSON → `ColdPlateExternalBackend` 回灌。

## 5. 如何运行

```bash
# 1) 网格 + 离线估算，生成 81 个 SpaceClaim 脚本并排序（本机用 V251 匹配安装）
python scripts/run_cold_plate_optimization.py \
    --config data/cold_plate_search_space.json \
    --mode grid --backend lumped \
    --output-dir data/loop_output --api-version V251 \
    --source-model "C:/Users/.../0710.stp"

# 2) 已安装授权 ANSYS：--spaceclaim 会自动 preflight 自检，
#    通过则用探测到的 V251 无头执行候选脚本并接外部结果
python scripts/run_cold_plate_optimization.py \
    --config data/cold_plate_search_space.json \
    --mode sample --samples 40 --backend external \
    --results-json ansys_out/results.json --spaceclaim
```

输出：`data/loop_output/report.json`（机器可读）+ `report.md`（可读排名）。每个候选的 SpaceClaim 脚本在 `data/loop_spaceclaim/`。

## 6. 参数 → 几何映射（与你的原始脚本一致）

| 参数 | 含义 | 影响 |
|---|---|---|
| `flow_width_x / flow_length_y` | 内部流道区域尺寸 | 外形 `Lx/Ly`、通道数、流道长度 |
| `margin_*` | 四周边框 | 外形尺寸 |
| `t_layer1/2/3` | 底板/流道层/上盖厚度 | 体积、质量、导热路径 |
| `channel_width / channel_gap` | 单通道宽 / 隔墙宽 | 节距、通道数、换热面积 |
| `manifold_length` | 进出口集流区长度 | 平直流道长度、压降 |

派生量（脚本内计算并以 `# derived:` 注释写入，便于人工核对）：
`n_channels = int((flow_width_x - channel_width) / (channel_width + channel_gap)) + 1`。

## 7. 已知限制 / 下一步

- 当前几何为「三层长方体拼装 + 微通道隔墙」，未做布尔融合、流体域抽取、圆角/拔模。
- `max_stress_mpa` 为占位上界，真实值需 FEA。
- 优化器目前是「一次性枚举 + 排序」，尚未接 NSGA-II / 贝叶斯做自动迭代提议（接口已预留）。
- 接真实 Fluent 时建议先用 `ColdPlateLumpedBackend` 筛掉明显差结构，再对高潜力候选跑 CFD，控制许可证与算力成本。
