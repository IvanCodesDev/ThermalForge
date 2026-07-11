# ThermalForge 完整 Agent 系统交付概览

## 已完成

- 建立版本化 Agent Definition、Prompt Registry、Skill Registry、Tool Policy 与 Execution 审计。
- 所有 LLM Agent 在 Settings、Registry、Execution 三层强制使用 `gpt-5.6-sol`。
- 将 `EngineeringState(project_id, revision)` 收敛为几何与仿真的唯一工程事实源。
- 实现不可变 Artifact lineage，区分 source、engineering proxy、manufacturing CAD 与 Hyper3D concept mesh。
- 实现 SpaceClaim V251 handoff、确定性 renderer 与 runner API 版本门。
- 实现 Fluent/Mechanical 隔离 Adapter，默认禁止真实外部执行。
- 实现 Simulation handoff/result 编排：先校验身份并保存原始结果，再执行验收；失败进入 `review_required`。
- 新增 Agent Registry、Engineering State、Artifact lineage、Simulation orchestration 等 API。
- 提供五类通过 Pydantic 契约验证的 JSON 示例。

## 关键决策

- Hyper3D 永久属于 `concept_mesh` 展示支路，程序上禁止作为制造 CAD 或仿真几何。
- SpaceClaim 固定使用 `SpaceClaim.Api.V251`，不得根据本机环境静默漂移。
- 规格、材料、载荷工况、分件语义和失败结果均保留人工审核门。
- LLM 负责严格契约编译与解释，确定性工具负责几何、数值校验和外部执行。

## 验证

- QA Round 2：103 passed，0 failed，通过率 100%。
- 智能路由：NoOne。
- 未调用付费 API，未启动 SpaceClaim、Fluent 或 Mechanical。

## 后续事项

- 在正规 ANSYS 许可证和队列环境中实现并验证真实 CAE Adapter。
- 为 Registry 和工程状态增加持久化数据库及电子签名审批。
- 处理 3 个非阻断 Pydantic `schema` 字段命名警告。
