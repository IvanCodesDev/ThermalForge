# ThermalForge 参数—模型—仿真联动验证

## 验证结论

当前链路对内部程序化模型可用：修改已接入生成器的参数后，会重新生成 SVG 结构与 `GeometryStats`，集总热阻仿真随后使用新几何统计量计算温度、质量和热阻。

当前链路尚不能代表真实三维 CAD/CFD 闭环：系统没有读取或编辑 STEP/STL/GLB 的参数化 CAD 实现，也没有网格生成和 ANSYS/Fluent 求解；`ExternalSimulationBackend` 仍是占位接口。

## 已验证场景

1. 叶脉 `branch_levels: 2 → 5`
   - SVG 分支结构变化。
   - 有效换热面积与材料体积增加。
   - 集总仿真的热点温度下降、质量上升。

2. Pin-fin `channel_count: 16 → 64`
   - SVG 针阵列数量变化。
   - 有效换热面积与材料体积增加。
   - 集总仿真的热点温度下降、质量上升。

3. 蛇形流道参数反序列化
   - `channel_pattern=serpentine`、`serpentine_turns`、宽度和高度能够进入生成器。
   - 生成蛇形结构并产生高于底面积的有效换热面积。

4. 流向参数
   - `flow_direction_deg` 会改变 SVG 方位。
   - 没有主流向上下文时，它不会改变标量几何量和集总热结果。
   - 提供 `preferred_flow_direction_deg` 时，当前开发期后端使用方向偏差惩罚模拟流向耦合。

5. API 闭环
   - `/generate` 和 `/evaluate` 均会根据本次提交参数重新生成几何。
   - 修复了 `/optimize/leaf-direction` 未向仿真上下文传递 `preferred_flow_direction_deg` 的问题。
   - 修复了方向惩罚后外层与嵌套 `t_hotspot_c` 不一致的问题，并保留惩罚前温度字段。

## 自动化测试

新增：`tests/test_parameter_geometry_simulation_pipeline.py`

完整测试结果：`10 passed`。

测试命令：

```bash
"C:/Users/llwxy/.workbuddy/binaries/python/envs/default/Scripts/python.exe" -m pytest "C:/Users/llwxy/Desktop/thermalforge/tests" -q
```

最终在隔离的 Python 3.13 环境中通过全部测试。当前仅有一条第三方依赖弃用警告：FastAPI/Starlette 的测试客户端提示未来迁移到 `httpx2`，不影响本次验证结果。

## 当前可通过代码修改的有效结构参数

### 叶脉

优先使用：

- `trunk_count`
- `branch_levels`
- `branch_angle`
- `branch_ratio`
- `width_trunk`
- `width_tip`
- `length_scale`
- `channel_depth`
- `density_gradient`
- `tortuosity`
- `symmetry`
- `boundary_shape`
- `flow_direction_deg`（主要改变 SVG；需要主流向上下文才影响当前热评分）
- `cooling_medium`

示例：

```python
from core.models.schema import from_dict
from core.engine.generator import generate
from core.engine.simulation import LumpedSimulationBackend, SimulationContext

params = from_dict({
    "structure_type": "leaf_vein",
    "branch_levels": 5,
    "branch_angle": 42,
    "flow_direction_deg": 90,
    "cooling_medium": "forced_air",
})

svg, geometry = generate(params)
outcome = LumpedSimulationBackend().evaluate_candidate(
    params,
    SimulationContext(
        power_w=28,
        preferred_flow_direction_deg=90,
    ),
)
```

### 流道 / Pin-fin

目前明确进入生成与仿真的参数包括：

- `channel_pattern`
- `length_scale`
- `channel_width`
- `channel_height`
- `channel_length`
- `channel_count`
- `serpentine_turns`
- `cooling_medium`

## 尚未形成真实结构语义的参数

部分公开参数目前只存在于 Schema 或匹配向量中，并未真正改变生成结构，例如叶脉的 `vein_archetype`、`porosity`、`inlet_pos`、`outlet_pos`，以及流道的 `channel_pitch`、`bend_radius`、`manifold_type`、`wall_thickness`、`topology_complexity` 等。

此外，`manifold` 和 `topo_opt` 暂时退化为普通并行流道。不能把这些参数描述为已经完成真实参数化建模。

## 下一阶段建议

若目标是“编辑代码参数后，真实改变三维模型并进行可信仿真”，建议按以下顺序推进：

1. 定义参数到 CAD 特征的明确映射和版本化契约。
2. 接入 CadQuery/OpenCASCADE 或 SpaceClaim，输出 STEP/STL，并记录参数哈希与模型哈希。
3. 建立流体域、命名边界和网格生成。
4. 实现 `ExternalSimulationBackend`，保证每个仿真任务引用本次参数生成的新模型。
5. 增加契约测试：参数哈希变化 → CAD 模型哈希变化 → 仿真输入模型哈希一致。

在这之前，当前结果适合概念筛选和快速排序，不适合作为真实 CFD/FEA 定型依据。
