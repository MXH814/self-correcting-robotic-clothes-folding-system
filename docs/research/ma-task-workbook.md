# 马祥珲第一阶段成果与完成状态

更新：2026-11-07。研究/设计文档与离线软件已形成；PR #2复审合并，真实入库样例已审核，完整轨迹纯数值导出和历史工具已实现。真实仿真独立复跑、恢复研究实验及个人掌握尚未完成。

最新入口：[运行说明](execution-guide.md) · [执行决定](ma-owner-decisions.md) · [详细剩余清单](ma-remaining-checklist.md)。

2026-11-08展示优先更新：第三组参加11月9日13:30–15:05场次，Slides在13:30之前上传。本人先交恢复核心交互图、关键设计取舍与备选、AI需求细化及风险/PoC，并终审技术事实；三人素材、约110秒个人正文和完整6分钟验收见[展示计划](../design/presentation-plan.md)。科研输入待办继续，不能阻塞课程展示。

本轮进展：[PR #2复审](../reviews/pr2-handoff-review.md) · [数据接入与可直接执行的导出命令](ma-data-intake-progress.md)。

后续PR #6/#7已审查合并：三架构展示源稿已提供，data2/data3正常轨迹已实际下载并通过ZIP/逐文件/全部153帧数值与历史检查；80/81问题关闭。仍缺可运行环境、真实profile和失败/恢复候选数据，见[最新审查](../reviews/pr6-7-handoff-review.md)。

## 成果导航

| 分工成果 | 入口 | 当前状态 |
| --- | --- | --- |
| UPS 精读 | [L05](papers/L05-ups-reading-note.md) | 版本、证据索引、方法/实验边界及设计影响已整理 |
| TAIL-Safe 精读 | [L07](papers/L07-tail-safe-reading-note.md) | 已整理，并提出数字/数学范围待核问题 |
| RedFlow 精读 | [L08](papers/L08-redflow-reading-note.md) | 明确已有叠衣结果、离线匹配与目标边界 |
| DexGarmentLab 共同阅读 | [L01](papers/L01-dexgarmentlab-reading-note.md) | 已整理；平台选定，作者环境报告已合并，本工作流独立复跑未完成 |
| 张茗博分支审查与平台采用 | [审查结论](../reviews/zhang-bc5e48c-review.md)、[ADR-MA-004](../design/decisions/ADR-MA-004-simulation-platform.md) | 文档审查通过并合并；环境已选定，独立复跑仍未完成 |
| 现有轨迹安全审计与接入 | [接入设计](dex-integration-plan.md)、[接入进展](ma-data-intake-progress.md) | data2/data3纯数值包已接收并校验153帧及阶段内历史；运行入口和恢复候选数据仍待交付，无需再加载原始NPZ |
| 最近邻比较 | [比较矩阵](related-work-matrix.md) | 已撰写，强基线复现待执行 |
| 研究提案与问题卡 | [H1/H2/H3](hypothesis-cards.md) | 假设、反证与方案已写，没有实验支持结论 |
| 诊断实验设计 | [协议](diagnostic-protocol.md) | 分组、配对、指标、统计与资源方案已写 |
| AI 恢复详细设计 | [恢复模块](../design/recovery-design.md) | 逻辑组件、类关联、时序、异常、SRS映射已写 |
| 算法与控制接口 | [契约](../design/interfaces.md) | 逻辑基线已采纳；离线preflight子集已实现，真实profile未接入 |
| 设计决策 | [ADR-001](../design/decisions/ADR-MA-001-control-and-scoring.md)、[ADR-002](../design/decisions/ADR-MA-002-history-and-continuation.md)、[ADR-003](../design/decisions/ADR-MA-003-reproducible-data.md) | 组长授权下采纳为实现基线，队友可审核修订；不是实测通过 |
| 算法风险与验证 | [PoC清单](../design/ma-risks-and-validation.md) | 已写，实测未执行 |
| 课程文献注释 | [英文注释](annotated-references.md) | 四篇200–300词候选稿 |
| 课程集成材料 | [Summary/反思/贡献/讲稿](../design/ma-assignment2-material.md) | 可供整合，最终事实与人工归属待确认 |
| 原文溯源 | [来源登记](source-register.md) | URL、版本、分类依据、源hash与限制 |

## 分工覆盖与实际未完成项

- [x] 文献分析稿、最近邻比较、问题卡和诊断协议已形成。
- [x] AI设计、接口、ADR、风险和报告候选材料已形成。
- [x] 离线诊断、分组防泄漏、基线/统计、门禁子集、评分诊断和资源估算已实现，自动化测试与人工fixture检查已执行。
- [x] 可选CPU MLP消融及近似容量对照实现并完成人工fixture训练/评估小试。
- [x] 可独立决定的研究/软件基线已确定，不等待联合签核。
- [x] PR #2复审通过合并，真实样例/hash审核及全轨迹导出/阶段内历史工具完成；40项Python测试及启动器回归通过。
- [ ] 马祥珲本人完成原文审阅、技术决定确认和个人阅读反馈。
- [ ] 与张茗博确认环境/动作通道/profile、前缀、停止时效与部署。
- [ ] 与胡知鱼确认标签、数据字段、参考注释和界面原因码。
- [ ] 另一成员复现环境与失败；运行诊断并取得支持/否定/未定决定。
- [ ] 数据采集、模型训练、评分校准及运行验收。
- [ ] 全组报告整合、评审、展示反馈和Canvas提交。

## 队友交接

已只读核对 `origin/hzy@067cf91` 的数据/需求/追踪/报告草稿，不覆盖、不自动合并。其请求 Ma 提供的恢复交互、算法风险、反思和参考注释，现由本成果包提供。

张茗博分支`bc5e48c`已完成原文/文档审查并保留原提交合并main：已有历史示范与训练小试；当前电脑无其E:\Robotics路径，独立复跑仍需环境交接。平台已选定，详见[审查结论](../reviews/zhang-bc5e48c-review.md)和[剩余清单](ma-remaining-checklist.md)。

PR #2的`f8bfaaa`已复审合并：已有可配置脚本、配置清单、真实关节JSON和最终图像；不再把这些列为完全未提供。完整轨迹和可运行环境仍未共享；新导出器可在采集机直接使用，不需要再设计一套样例格式。

张茗博提供动作与时钟profile、串行接纳/停止和部署事实；胡知鱼可整合注释/报告并审核数据/UI映射。CR-MA-01已由组长授权下采纳为内部接口细化，hzy CR-01/02仍未批准；SRS阈值未修改。没有向队友发送消息、租GPU、产生真实机器人性能结果或预填个人工时。
