# Fluent / Mechanical 真实 Adapter 交接说明

负责人：EU

状态：待真实求解环境接入。当前 Adapter 必须保持 fail-closed，不得返回占位结果、估算结果或成功状态。

## 目标

实现以下真实执行链：

1. 读取已经持久化的 `SimulationHandoffContract`。
2. 校验工程 revision、SpaceClaim 几何哈希、材料、载荷、工况、网格和 solver plan。
3. 在授权的 Fluent 或 Mechanical 环境执行求解。
4. 保存原始日志、网格、场数据和报告。
5. 对每个产物计算 SHA-256。
6. 生成严格的 `SimulationResultContract`。
7. 由后端 `SimulationResultIngestor` 计算 `ResultAcceptance`；Adapter 不得设置 `passed`。

## Fluent Adapter

文件：[fluent.py](../../core/adapters/fluent.py)

必须配置：

- Fluent 可执行程序绝对路径。
- 许可证服务器或本机许可证配置。
- 受控工作目录。
- 允许的 Fluent 版本。
- 最大运行时间、CPU/内存限制和并发数。

必须输出：

- Fluent journal 或等价的可重复执行输入。
- solver stdout/stderr 和完整日志。
- mesh/field/report 文件。
- residual/convergence 证据。
- 每个输出文件的 SHA-256、文件大小和实际路径。

## Mechanical Adapter

文件：[mechanical.py](../../core/adapters/mechanical.py)

必须配置：

- Mechanical/Workbench 可执行程序绝对路径。
- 许可证配置。
- 受控工作目录。
- 允许的 Mechanical 版本。
- 最大运行时间、资源限制和并发数。

必须输出：

- Mechanical 脚本或 Archive/Project 输入。
- 网格质量和收敛记录。
- 温度、应力、安全系数等原始结果文件。
- solver stdout/stderr 和完整日志。
- 每个输出文件的 SHA-256、文件大小和实际路径。

## 禁止事项

- 禁止使用固定温度、固定压降或固定安全系数。
- 禁止在 solver 不可用时返回 `status=success`。
- 禁止根据文件名或请求参数推测求解结果。
- 禁止由客户端设置 validation `passed`。
- 禁止将 Hyper3D concept mesh 作为求解或制造几何。
- 禁止仅上传截图作为求解证据。

## 失败行为

以下情况必须明确失败并写入 ExecutionRecord：

- executable 未配置或不存在。
- 许可证不可用。
- SpaceClaim 几何或哈希不匹配。
- 工况、材料或网格参数缺失。
- solver 超时、崩溃或未收敛。
- 输出文件缺失或哈希校验失败。
- 返回结果不满足 `SimulationResultContract`。

## 完成验收

- 使用一个真实 Fluent 案例和一个真实 Mechanical 案例进行端到端运行。
- 重启后可从 SQLite 恢复 handoff、result 和 acceptance。
- 删除输出文件或修改任意字节后，哈希校验必须失败。
- solver 不可用时 API 必须返回明确错误，不得出现成功结果。
- provenance completion gate 只有在完整证据链存在且服务端 acceptance 为 `passed` 时才能完成 Pipeline。

## 当前后端边界

Simulation 数据已持久化到 SQLite namespaces：

- `simulation_handoff`
- `simulation_result`
- `simulation_acceptance`

生产完成入口为 `AgentPipelineRuntime.complete_with_provenance()`。它只接受服务端 `ProvenanceCompletionGate` 生成、且与当前 Pipeline revision 匹配的报告。开发模式中的旧人工验证接口不得挂载到 Real 模式。
