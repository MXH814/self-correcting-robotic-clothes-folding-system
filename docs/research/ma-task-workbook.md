# 马祥珲第一阶段成果与完成状态

**PR #15/#18/#20/#21后的当前状态：** 已合并并实际接入五条衣物轨迹的1051帧/946派发，两个完整接续结局独立复算；新增完整宏提案、序列评分训练/推理、独立试次描述及19项测试，合计91项通过。真实输入已跑随机网络前向，真实恢复监督训练尚未发生。下文早期数量/缺口保留为历史快照，当前以[算法进展](garment-algorithm-progress.md)和[剩余清单](ma-remaining-checklist.md)为准，不再要求重复基础复跑、旧包或已交快照。

**最新交接：** PR #12/#13已合并，动作前包6文件和因果顺序已核验，马已实际运行[视觉/本体/候选输入与后续片段编码](preaction-integration-progress.md)。不再等待第一条动作前组件链；真实衣物失败和恢复分支仍缺。

**当前状态（PR #9/#10 合并后）：** 基础复跑、旧正常包和运行时关节 profile 已收到；新 I/O、相机取景、组件 ACK/停止及重置诊断不再列为“尚无”。马已完成[实测编码与独立停止校验](runtime-component-integration.md)。后文早期记录保留为历史快照，当前缺口以[剩余清单](ma-remaining-checklist.md)为准：动作前视觉/执行片段、产品协调器联调、DR02失败、中段可比重置和恢复分支标签。

当前状态更新：2026-11-08。研究/设计文档、49项软件测试、153帧正常观测编码及展示素材已形成。马祥珲确认已在张电脑完成基础复跑，该项关闭；后续仿真/采集/恢复闭环统一使用张电脑，不要求组长电脑安装或换机复跑。恢复研究实验、真实新接口与个人答辩掌握分别验收，见[执行安排](shared-simulation-workflow.md)。

最新入口：[运行说明](execution-guide.md) · [执行决定](ma-owner-decisions.md) · [详细剩余清单](ma-remaining-checklist.md)。

2026-11-08展示优先更新：第三组参加11月9日13:30–15:05场次，Slides在13:30之前上传。本人先交恢复核心交互图、关键设计取舍与备选、AI需求细化及风险/PoC，并终审技术事实；三人素材、约110秒个人正文和完整6分钟验收见[展示计划](../design/presentation-plan.md)。科研输入待办继续，不能阻塞课程展示。

本轮进展：[PR #2复审](../reviews/pr2-handoff-review.md) · [数据接入与可直接执行的导出命令](ma-data-intake-progress.md)。

后续PR #6/#7已审查合并：三架构展示源稿已提供，data2/data3正常轨迹已实际下载并通过ZIP/逐文件/全部153帧数值与历史检查；80/81问题关闭。仍缺可运行环境、真实profile和失败/恢复候选数据，见[最新审查](../reviews/pr6-7-handoff-review.md)。

**本次独立推进（2026-11-08）：** 已在153帧运行固定RGB/关节/历史编码，新增6项特征边界及2项preflight类型检查，连同PR #8资产核验共49项测试通过。已澄清评分/代次/停止屏障，完成两张可编辑SVG展示图、PNG、中英文讲解、决策对比和问答。进入[展示素材](../design/ma-presentation-materials.md)与[真实接入结果](normal-observation-integration.md)即可使用；实际排练、队友独立审核和物理实验仍待执行。

PR #8后续已[审查合并](../reviews/pr8-environment-review.md)，固定源码、带哈希依赖及资产核验入口已齐；剩余为目标机实际部署/复跑及真实profile、停止和恢复候选采集，不再把版本/依赖入口列为张未交付。

## 成果导航

| 分工成果 | 入口 | 当前状态 |
| --- | --- | --- |
| UPS 精读 | [L05](papers/L05-ups-reading-note.md) | 版本、证据索引、方法/实验边界及设计影响已整理 |
| TAIL-Safe 精读 | [L07](papers/L07-tail-safe-reading-note.md) | 已整理，并提出数字/数学范围待核问题 |
| RedFlow 精读 | [L08](papers/L08-redflow-reading-note.md) | 明确已有叠衣结果、离线匹配与目标边界 |
| DexGarmentLab 共同阅读 | [L01](papers/L01-dexgarmentlab-reading-note.md) | 已整理；平台选定，用户确认同机基础复跑完成，不重复要求 |
| 张茗博分支审查与平台采用 | [审查结论](../reviews/zhang-bc5e48c-review.md)、[ADR-MA-004](../design/decisions/ADR-MA-004-simulation-platform.md) | 已采用张电脑已有环境，基础复跑项关闭；新接口/恢复能力待测 |
| 现有轨迹安全审计与接入 | [接入设计](dex-integration-plan.md)、[接入进展](ma-data-intake-progress.md) | data2/data3纯数值包已校验153帧并编码；继续接真实profile和恢复候选数据 |
| 真实正常观测编码 | [接入结果/预览](normal-observation-integration.md) | 153帧固定192维RGB、60维原始关节及带mask历史已运行；零学习参数，无候选/恢复标签 |
| 展示与答辩素材 | [两页素材包](../design/ma-presentation-materials.md) | 两张SVG/PNG已视觉检查，中英讲解、三项取舍和问答已写；全组PPT整合/排练未完成 |
| 核心契约歧义修正 | [评分/代次/屏障](../design/contract-clarifications.md) | 后续成功与整试次指标分开，旧代只审计，adapter屏障明确；真实并发/停止待测 |
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
- [x] PR #7后153帧真实观测固定编码已运行，PR #8整合后49项软件测试通过；正常数据未冒充恢复候选。
- [x] 两张展示SVG/PNG及中英讲解/取舍/问答已交付；评分与代次歧义已澄清。
- [ ] 马祥珲本人完成原文审阅、技术决定确认和个人阅读反馈。
- [ ] 与张茗博确认环境/动作通道/profile、前缀、停止时效与部署。
- [ ] 与胡知鱼确认标签、数据字段、参考注释和界面原因码。
- [x] 基础复跑：马祥珲确认已在张电脑完成；后续统一使用该环境，不要求换机或重复基础复跑。
- [ ] 张电脑采集真实失败/候选并审核标签，运行诊断取得支持/否定/未定决定。
- [ ] 数据采集、模型训练、评分校准及运行验收。
- [ ] 全组报告整合、评审、展示反馈和Canvas提交。

## 队友交接

已只读核对 `origin/hzy@067cf91` 的数据/需求/追踪/报告草稿，不覆盖、不自动合并。其请求 Ma 提供的恢复交互、算法风险、反思和参考注释，现由本成果包提供。

张茗博分支`bc5e48c`已完成原文/文档审查并保留原提交合并main。马祥珲现确认在张电脑完成基础复跑；本开发电脑不存在其E:\Robotics路径不再构成环境阻塞。后续统一在张电脑执行，详见[执行安排](shared-simulation-workflow.md)和[剩余清单](ma-remaining-checklist.md)。

PR #2脚本/小样例和PR #7完整正常轨迹均已交接，153帧已编码；基础复跑已关闭。剩余新增输入为真实profile及恢复候选数据，不再索要组长本机安装或重复正常包。

张茗博提供动作与时钟profile、串行接纳/停止和部署事实；胡知鱼可整合注释/报告并审核数据/UI映射。CR-MA-01已由组长授权下采纳为内部接口细化，CR-01/02现已按ADR-MA-005采用为开发设计细化，SRS阈值未修改；本轮工具不发送机器人动作、不租GPU、不预填个人工时。既有PR审查通知和张的仿真实测分别保留实际来源。
