# 五屏界面与恢复接口的对应关系

依据 2026-11-08 的逻辑接口基线 `recovery-contract/0.1-draft`。S01 发送启动意图，S02 显示观测及协调器决策，S03 发送接管与归还请求，S04 读取记录和质量追加结论，S05 展示模型与配置准入。设备确认、是否接受派发、代号和预算均由协调器或适配器负责；测试桩演示其中的界面响应。[接口定义](interfaces.md) · [交互说明](interaction-design.md)

| 原因码 | 用户看到的原因及可做的事 | 状态和记录 | 原型覆盖 |
| --- | --- | --- | --- |
| UNKNOWN | 观测不足，等待停车后检查衣物 | 停止、求助；无新派发不计次 | S02 遮挡 → S03 |
| STALE_OBSERVATION、DECISION_TIMEOUT | 观测过期需重取，或决策超时已取消 | 记录原始原因；活跃决策中连续三次不可用，停止求助 | S02 过期、超时 |
| OLD_GENERATION | 旧控制代号已失效 | 丢弃；活跃决策中计不可用，停车后迟到的回复只审计，保留执行锁 | S02 旧代回复 |
| INVALID_SCHEMA、NONFINITE、OUT_OF_BOUNDS | 候选格式、数值或边界检查失败 | 候选级拒绝，保留原因。可继续审核其余候选 | S02/S03 说明 |
| TOO_MANY_CANDIDATES | 候选数超过 8 | 拒绝整份响应，未派发不计次 | 说明 |
| NO_SUPPORTED_CANDIDATE | 无可执行候选，等待停车和协助 | 整组筛选结束后求助，保留尝试数 | S02 无合格候选 |
| SCORE_UNCALIBRATED、LOW_SCORE | 校准缺失或接受分数不足 | 阻止自主派发，按接口请求停止/求助 | 说明 |
| BUDGET_EXHAUSTED | 时间或费用预算耗尽，查看终态原因 | 现行预算门禁使非终态任务失败并请求停止，追加尾费 | S02/S04 耗尽示例 |
| STOP_PENDING、AUTHORITY_REVOKED | 等待静止证据，或等待交还后的校验 | 拒绝新派发，原代号不能解锁 | S02 暂停、S03 归还 |
| LOG_WRITE_FAILED、EXECUTION_UNCERTAIN | 记录写入失败或执行结果待核 | 停止派发并核实；保留已接受次数 | 说明 |
| IDEMPOTENCY_CONFLICT | 同一标识对应不同载荷 | 拒绝重用，审计冲突，由请求方核对 | 说明 |

“说明”条目供查看接口词义。实际适配器回传、真实停止与拒绝的行为要在集成时验证。S01 拒绝启动时只展示请求信息，无已接受任务可供 S04 导出。设备离线、用户主动暂停和监督员提交质量报告各有独立上下文，不能将未知原因自动改判为检测器 UNKNOWN。

## S04 教学导出与记录字段

导出按钮下载本会话选定任务的 JSON。顶层 `schema_version=folding-ui-demo/1`、`source=synthetic`、`online_authorized=false`、`evaluation_eligible=false` 共同标明使用范围。保留旧版记录字段；下列映射用于读档和事后审核。

| 导出位置 | 审核表对应字段及含义 |
| --- | --- |
| task_id、request_id | 试次登记的任务号、请求号。演示编号只在本次浏览器会话有效，跨会话应保留原文件身份。 |
| frames[].sequence_no、control_generation、reason_code | 事件记录的序号、控制代号、原因。每个任务从 1 连续递增，键为该文件中的任务号与序号。多次导出同一任务保留既有序号。普通界面事件的原因码为 null。 |
| frames[].state、stop、event、attempts | 采样时的演示任务态、停车态、提示、累计已接受次数。界面回放逐条对应。 |
| frames[].activeSeconds、billedSeconds | 手动推进的示例计数。没有观测采样时间、墙钟映射或真实资源账单。 |
| decision_id、profile_version、policy_version、capture_wall_monotonic_s、sim_time_s | 缺少真实对应值时均为 null。现有 cfg、model 字段只描述演示设置。 |
| quality、qualityReason、help、manual | 当前选定记录上的示例质量、依据、求助和接管情况。S04 质量控件更新示例审核结果，终态继续保留。 |

导入正式试次前按来源门禁过滤 synthetic；合格分母仅由已审真实试次构成。真实样例的来源及未知标签见[首帧审核](observation-review.md)。
