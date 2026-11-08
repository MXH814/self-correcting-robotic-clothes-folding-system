# 恢复评分训练样本契约 v1

状态：马祥珲2026-11-08制定并实现训练端检查；已从#24编译首条确定性区域代理宏样本，尚无可训练的正负覆盖和独立划分集合。[共享上下文及代理协议](shared-context-and-proxy-protocol.md)细化当前执行口径，原始正式标签不改，不改变SRS自主成功判据。

## 一个样本代表什么

一行是**一个明确恢复决策时刻、一个事先提出的完整宏候选、它的实际执行和同一试次后续结局**。不是一帧，也不是一次任意关节派发。只有实际执行、拥有目标定义所需证据且完成审核的候选能带监督；未执行/缺证据保持未知，不补成负样本。

当前原型目标名为`fixed-controller-continuation/v1`。`continuation_context_reference`必须指向冻结的正常接续控制器、目标/质量定义、剩余预算和求助/人工处理规则；这一版本训练器仅接收同一个上下文引用。目标可以是明确命名的开发代理，但不能将官方88%区域分数直接改称SRS自主成功。不同目标应另建数据/模型版本。

## 必需字段

| 字段 | 内容与检查 |
| --- | --- |
| schema / decision_scope | `reviewed-recovery-sample/1` / `recovery_macro` |
| trial_id / lineage_group | 同一次真实运行，以及完整轨迹/相关分支族；同族与同试次不得跨train/development |
| decision_id / candidate_id | 恢复决策和候选唯一标识，不重复；候选向量对应完整已声明宏计划 |
| split | 编译可为unassigned；正式训练仅train或development，封存测试不进入此开发入口 |
| target_definition / continuation_context_reference | 目标版本及固定上下文的可回查引用 |
| continuation_success / label_review_reference | 审核后的布尔结局及证据/审核引用；未知样本留待审索引，不喂本训练入口 |
| candidate_spec_reference / candidate_available_before_decision | 事先提案原始记录与实际可用时刻的证据；不根据执行轨迹事后猜出“当时提案” |
| features | 当前观测、过去观测/动作、掩码、profile、时刻及下述宏候选；不得包含监督、隐藏网格或未来观测 |
| encoding_reference / source_context_reference | 共享编码版本及该trial原始动态上下文引用；检查点同时绑定共享上下文和编码版本 |

## 宏候选与特征组装

宏候选schema为`recovery-macro-proposal/1`，目前只支持`release-retreat-regrasp-lift`。记录candidate_id、trial_id、source_reference、available_at、arm、coordinate_frame=world、position_unit=m、retreat_world_m、pick_world_m、lift_world_m、orientation_wxyz、open_wait_steps、close_wait_steps。

用`recovery_candidates.recovery_features(dispatch_input, candidate)`将已校验因果上下文与提前存在的提案组装。它会以17维完整宏编码替换180维底层关节目标，校验同试次、单位/姿态和可用时刻。候选特征版本与可执行宏接口须一并冻结。等待步数对应的物理步长、动作/接触/速度/预算限制由执行profile和门禁明确，编码成功不等于DR04通过。

序列训练器检查提案编码/候选ID/试次一致、提案不晚于决策、标签引用、共享上下文/编码版本、划分与正负训练覆盖。检查字符串不证明人实际完成审核；自动数值代理和人工判读分别记录，实际参与者需提供自己的复核意见。训练集拟合归一化后固定用于开发；v2检查点保存config、权重、归一化、profile及共享上下文/编码版本，读取采用weights_only模式。

## 早期七包与最新完整链

- 五条第一袖trace可产生946条底层派发输入，用于时序/接口/网络前向检查；不能自动变成946个恢复标签。
- 两条完整接续有不同trial_id，不能把其最终分数挂到前述五条轨迹上。
- 同一闭手重抓trace已具备恢复前后连续链，但没有审核后的接触/局部恢复/完整接续监督；保留待审。
- 未知阶段/预算、正式故障标签与审核未齐均如实保留。先交可确认的开发代理目标与证据，经过评审冻结后再训练；不必等完整论文规模或课程180次验收完成。
- #24已解除同次完整链交接缺口；本轮冻结共享上下文并编译1条确定性代理正样本，原始continuation_success仍null。当前没有负例与分组划分，不强训或代签SRS/局部恢复标签。

## 代码验证与研究结论

[软件测试](../../tests/test_sequence_ranker.py)使用显式构造fixture，仅验证反向传播、划分拒绝和检查点往返；不代表真实用户审核或机器人效果。真实输入的随机网络前向也仅说明接口能运行。H1/H2、有效候选覆盖、校准和强基线收益仍须实际实验，不由模型文件存在推导。
