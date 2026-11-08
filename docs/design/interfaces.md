# AI 恢复与系统控制接口基线

**当前实测接入：** PR #10 已提供命名关节、组件时钟/绝对命令/反馈、可见 RGB 与组件停止；[Ma 编码和独立校验](../research/runtime-component-integration.md)已运行。仍不是冻结的产品 profile：该 RGB 仅为动作后检查，真实前缀/路径约束、跨模块时钟及协调器联调仍待完成。

版本：`recovery-contract/0.1-draft`（保留消息兼容标识）。状态：组长授权下采纳的逻辑接口基线，队友可审核修订；已实现独立离线preflight子集，完整adapter/协调器尚未实现。逻辑方法名不强制 HTTP、语言或消息中间件。SRS 是验收基线，不能因示例值改变阈值。实现范围见[运行说明](../research/execution-guide.md)。

## 1. 身份、版本与时间

所有请求/事件带 `schema_version, request_id, task_id, decision_id, control_generation, sequence_no, profile_version, policy_version`；仅已接受任务有 task_id。重试沿用 idempotency key，禁止复用到不同 payload，冲突返回 `IDEMPOTENCY_CONFLICT`。

`capture_wall_monotonic_s` 必须属于协调器可比较的时钟域；远程相机需标明 clock domain、映射与不确定性，不能直接相减。无法可靠证明≤1s新鲜度时拒绝。`sim_time_s` 仅用于物理窗口，不与 wall time 混算；UTC 用于审计而非时效。

配置 profile 定义 frame IDs、相机外参、通道名称/维数/单位、delta或absolute、允许工作区/关节/速度/前缀、传感器采样与停止证据。profile 未冻结或不兼容则 DR01 拒绝。请求中不可覆盖冻结配置。

## 2. 消息与逻辑调用

| 方法/记录 | 关键输入 | 输出与含义 |
| --- | --- | --- |
| `observe()` / ObservationRef | task/profile/current clock | obs_id、相机/深度引用、机器人通道值、采样时戳、online provenance、有效/缺失、阶段 |
| `history(before_obs)` | task/current generation/history profile | 时间严格不晚于决策的观测与已执行命令、执行量、模式/gap mask；无候选未来 |
| `detect()` / DeviationReport | 新观测、预期持有、历史 | NORMAL/OFFSET/SLIP/UNKNOWN、主/次类、置信/持续窗口、证据引用；不产生动作 |
| `proposeRecovery()` / RecoveryRequest | obs、history、deviation、goal、continuation version、剩余预算、model/calibration refs | RecoveryDecision：0–8候选、状态、原因、预测来源和耗时；只是提案 |
| `acceptAndDispatch()` | decision + coordinator current snapshot | ACCEPTED(command_id, attempt_no) 或 REJECTED(reason)；唯一接纳入口 |
| `cancelGeneration()` | new generation/reason | 协调器撤权，并在adapter安装单调代次屏障；接纳和实际执行前均拒绝旧代，清理旧队列。取消计算本身不证明物理静止 |
| `completeSegment()` / AdapterFeedback | command/generation、实测执行量、队列、结果与故障 | 协调器接受本代反馈后触发重新观测，不用策略自报完成替代 |
| `requestHalt()/reportRest()` | 当前代、最后命令、测量通道/采样、队列/活动状态 | 按 SRS 验证静止；超时锁定；无效证明不解锁 |
| `appendEvaluation()` | trial/task、evidence、review/schema version | 追加 local/quality/autonomous verdict，不改变 terminal outcome |

## 3. Candidate 与评分契约

Candidate：`candidate_id, action_schema, frame_id, channels, values, units, representation, prefix_duration_sim_s, score, score_semantics, calibration_ref, continuation_version, rejection_reasons`。

- `channels/values/units` 一一对应、有限实数、维度/边界严格匹配 profile，禁止字段缺省为任意动作。
- `prefix_duration_sim_s>0` 且不大于 profile 最大值及剩余动作预算；速度/轨迹连续性由 adapter profile 可验证方法计算，不能只查端点。
- score 为 `[0,1]`、语义为 `conditional_full_task_success`，校准与模型/输入版本一致时才可用于门槛。`rank_only`、Q、logit 或相似度不能转成概率门禁。
- 评分条件包括同一目标、接续控制器和剩余预算；拒绝 `continuation_version` 不匹配。
- `conditional_full_task_success`指从当前候选决策起、在剩余预算与固定接续控制器下，无进一步求助/人工介入地完成并通过最终质量的概率。历史求助不会把该后续目标永久置零；整试次`autonomous_success`仍保留既往求助/介入并按AI03判定。未验证人工返回后的输入/校准适用性时拒绝派发，不因为目标可定义就声称模型可用。
- 候选 >8 整个响应返回 `TOO_MANY_CANDIDATES`；其余逐个过滤后，最高合格分≥0.60才可被接受。无合格返回 help 建议，由协调器发起停止和交接。

## 4. 纯教学消息例子

以下仅说明结构，profile A、模型 M、校准 C 均为虚构标识，不是运行证据；通道、阈值和 duration 由真实 profile 决定。

```json
{
  "schema_version": "recovery-contract/0.1-draft",
  "task_id": "example-task",
  "decision_id": "example-decision",
  "control_generation": 4,
  "observation_id": "example-obs",
  "profile_version": "example-profile-A",
  "policy_version": "example-model-M",
  "continuation_version": "example-controller-B",
  "status": "PROPOSED",
  "candidates": [],
  "reason": "NO_SUPPORTED_CANDIDATE"
}
```

这个空响应不消耗尝试，也不意味着物理已经停止。正常含动作消息必须附上第 3 节完整字段，待 adapter profile 确认后提供实际例子，不能编造关节维数让示例貌似能运行。

## 5. 拒绝与控制后果

| 原因 | 处置 | 尝试/状态 |
| --- | --- | --- |
| UNKNOWN / unsupported deviation | 取消自主计算、停止、求助 | 无新动作不计次 |
| STALE_OBSERVATION | 当前代内丢弃，状态允许时重新观测 | 按当前代不可用规则计数；不能恢复过期权限 |
| OLD_GENERATION | 丢弃并记旧代审计/T18相关记录 | 不改变当前代的连续不可用计数或状态，不触发新代停止 |
| DECISION_TIMEOUT | 2 wall s 取消，记录不可用 | 连续3次停止求助 |
| INVALID_SCHEMA / NONFINITE / OUT_OF_BOUNDS | 拒绝候选/响应、保留理由 | 不计未派发尝试 |
| SCORE_UNCALIBRATED / LOW_SCORE | 禁止自主派发，停止/求助 | 不虚构概率 |
| BUDGET_EXHAUSTED | 按 SRS 失败/停止及费用审计 | 保留实际消耗与尾费 |
| STOP_PENDING / AUTHORITY_REVOKED | 拒绝新派发 | 仅合法来源校验后可恢复 |
| LOG_WRITE_FAILED / EXECUTION_UNCERTAIN | 禁止新动作，停止并核实 | 不自动回滚已接受计数 |

同代连续段不强制每段请求停车，但需前段完成 ACK、无冲突/排队、观测新鲜和当前授权；Pause/Return 等来源才要求相应新停止证明。约束来源为 SRS §5.6.4/5.6.5。

代次更新使当前代的连续不可用计数从零开始，旧代累计审计保留；重复回复按decision ID去重，不重复推进连续计数。报告静止前，adapter必须已确认撤权/代次屏障、清空旧代队列并满足SRS测量窗口；首次迟到的旧命令也不能仅因command ID未见过而获准执行。具体并发协议和反例见[契约澄清](contract-clarifications.md)。

## 6. 训练/验证契约

训练 job 另带 dataset/split/label schema/feature provenance、预算与最大分配时长；`train/validation/sealed_test` 访问隔离。推理只读已批准版本，不能读取最终标签文件。评分校准必须保存方法、拟合数据 manifest、适用条件、可靠性证据和门槛决定；没有记录不能给有效 calibration_ref。

## 7. 交接与待确认

逻辑契约无需等待共同签核即可推进。张茗博提供真实动作通道/坐标/profile、并发和停止反馈；胡知鱼审核 UI 原因码与试次/案例字段映射；马祥珲负责历史、评分条件与离线来源。参考 `hzy@067cf91` 数据规范，字段冲突在集成时显式映射，不覆盖其未合并工作。未获真实profile/集成证据前，消息仍标draft，不能宣称部署兼容。
