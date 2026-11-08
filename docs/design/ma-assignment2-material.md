# 马祥珲 Assignment 2 集成材料

状态：本工作流的 AI 辅助设计/分析稿。已依据 PR #9/#10 整合入英文 Design 工作稿；本页保留本人分工材料及归属边界，不声明三人已批准。以下 Summary 为全组报告候选文本，需整合最终实际进展/课堂反馈；不是马祥珲个人总结或已经提交的作业。

## A2-01 — Design Summary candidate

<!-- summary:start -->
Part I specified a simulated clothes folding system for one supported shirt type on a fixed table. The design prioritises grasp offset and partial slippage, bounded recovery, and explicit human assistance. It translates these requirements into three architecture views, five interface screens, recovery contracts and verification procedures. The team retains the original acceptance requirements while recording implementation evidence separately from design decisions.

The recovery worker proposes actions; the task coordinator owns execution authority. Before accepting a segment, the coordinator checks the current control generation, observation freshness, action constraints, calibration and remaining budgets. The adapter must reject revoked commands and report measured feedback. This separation adds protocol and latency, but allows the recovery method to change without transferring control authority to the model. A score cannot prove rest, and an earlier terminal outcome cannot be overwritten by a late response. The interaction prototype exercises preparation, pause, assistance, return and replay using explicitly synthetic events.

Isaac Sim 4.5 with DexGarmentLab runs on Zhang Mingbo's workstation, where Ma Xianghui completed the basic rerun. Two normal exports comprising 153 frames were received and encoded. Subsequent records provide named joint mappings, a component position command, measured feedback and visible simulated RGB. Ma's offline intake now encodes sixty joint channels, masked histories and sparse absolute targets. It preserves an important limitation: the new RGB was captured after the command and cannot be reused as its decision input. Legacy joint ordering is not retrospectively declared verified.

A single-process adapter probe records dispatch acknowledgement, deduplication, generation rejection and measured stopping. Independent recalculation gives pause and termination confirmation delays of approximately 0.676 and 0.692 seconds. The submitted windows cover all sixty rotational joints and satisfy the probe's recorded sampling and speed conditions. These results support component feasibility; they do not verify transport queues, disconnection handling or the complete product coordinator. Fold Tops images and a three-target projection check support camera integration. The upstream success flag remains distinct from the system's quality and autonomy criteria.

Repeated initial resets produced maximum settled mesh differences of approximately 31.7 millimetres. The design therefore requires mid-task state, velocity and contact checks before treating recovery branches as comparable. If these checks fail, independent blocked trials replace claims about identical-state candidate choices. Research questions about history and continuation quality remain open because labelled failure and recovery branches are unavailable. Local diagnostic reporting uses confirmed recoveries over accepted actions, with unknown outcomes and coverage shown separately. Additional development records distinguish validation origins, offline human judgements, system alarms and stop acceptance without changing product thresholds.

Current deliverables include decision records, editable diagrams, grouped-data safeguards, baseline and preflight software, annotation procedures and presentation material. The next integration connects real decision-time observations and executed segments to the coordinator, then collects audited grasp-offset and slip cases. Participant walkthroughs, a timed team rehearsal, classroom feedback and final submission remain pending. The final report will incorporate their actual evidence rather than treating generated documents or component tests as proof of a completed system.
<!-- summary:end -->

## A2-02 / A2-03 — 本人负责的具体设计

恢复职责、逻辑组件图、领域关联、恢复时序、输入/动作/评分、取消/拒绝/接管及记录见 [recovery-design.md](recovery-design.md)、[interfaces.md](interfaces.md) 和三个 [ADR](decisions/ADR-MA-001-control-and-scoring.md)。系统总体架构/部署/技术三视图仍由张茗博整合；本组件图不冒充完成全组架构。

## A2-04 — 需求建议

现行 FR/NFR/AI/DR 阈值不变。CR-MA-01 已依据组长授权采纳为内部接口细化，显式记录评分语义、校准与接续版本；未改变产品验收。胡知鱼 CR-01/CR-02 仍待审，本稿不批准其变更。

## A2-06 — 算法开放问题

见 [ma-risks-and-validation.md](ma-risks-and-validation.md)。每项有影响、最小 PoC、判据、负责人/复核及后备方案。部分统计规模和阈值校准需试跑后决定，不能预填通过。

## A2-07 — AI Tools Reflection contribution draft

Codex assisted this workstream by locating versioned primary sources, extracting the SRS constraints, comparing the existing teammate branch, and drafting literature notes, hypothesis cards, interfaces, decision records, and report material. The outputs were checked for source attribution, document links, requirement consistency, and annotation length. These checks establish document properties, not model accuracy or successful robot execution.

Critical corrections were necessary. Reading only abstracts would have overstated novelty: RedFlow already reports clothes folding, and TAIL-Safe distinguishes empirical assurance from formal invariance. Progress and robot pose do not establish identical contact states. Numerical scores from different methods also cannot be substituted into the SRS probability threshold. The draft therefore separates reported findings, our interpretations, proposed design decisions, and experiments that remain unperformed.

The workflow uses the existing assistant and local tools; no GPU rental, training on real robot data, participant study, or robot API job was launched. Individual human effort, attributable subscription cost, and token usage for this stage have not been supplied and are not inferred from the earlier assignment. The owner should add the available work record and any justified estimates before the final report is attributed. Team review, source PDF reconciliation where needed, and physical interface testing remain outstanding.

In a subsequent implementation pass, Codex also produced standard-library diagnostic code, optional PyTorch MLP ablations, unit tests, synthetic fixtures, a resource estimator, and execution instructions. The tests exercise software boundaries including data leakage, unknown outcomes, stale observations, and score semantics. A short CPU training run on manufactured fixtures verifies the neural path, with an approximate parameter-matched current-only control. These checks do not establish closed-loop recovery performance or reproduce the closest papers.

On 7 November, the handoff PR was re-reviewed after a reproducible path bug was fixed. Its launcher regression passed, and the PR was merged. A repository audit checked the submitted numeric sample and artifact fingerprints. New tooling exports independently trusted legacy trajectories to numeric observations and constructs stage-local history without inventing timestamps, dispatched actions, or success labels. Forty Python tests pass; the original full trajectory and a working simulation environment remain inaccessible to this workstream. The synthetic export checks therefore remain software evidence, not recovery experiments.

On 8 November, two normal demonstration exports were actually received from the private release. ZIP hashes, CRC, complete per-file inventories, numeric observations and stage-local history checks passed for all 153 frames. The extra file in the 81-file package is a handoff note. This closes normal-data access, not independent simulator reproduction or recovery experiments; actual action mapping, timing, stopping and recovery outcomes remain missing.

The next pass added a fixed 8-by-8 RGB mean encoder, raw joint features and masked past observations, and ran it on all 153 real frames. This representation has no learned parameters and provides no recovery labels. Forty-nine software tests pass after integrating the asset-verifier PR, including checks for future-frame isolation, stage boundaries, corrupted inputs and malformed preflight generations. Design corrections separate continuation success from trial-level autonomy, isolate old-generation accounting, and require adapter generation barriers. Two editable presentation figures, English speaking drafts, decision comparisons and answer notes were produced and visually checked; no actual rehearsal, classroom feedback or final slide upload is claimed.

## A2-08 — 参考文献

四篇英文注释位于 [annotated-references.md](../research/annotated-references.md)，分别满足 200–300 词的结构检查。正式报告应只纳入实际使用的来源，文献清单和每篇注释由作者本人及另一成员核原文。

## A2-09 — 可核验贡献与署名边界

本分工已形成的文档成果：四篇原文分析、最近邻比较、H1/H2问题卡、诊断协议、AI组件/接口、四项ADR、风险/PoC、参考注释和此报告片段；新增张茗博PR审查、实际数据接收校验、153帧固定观测编码、核心契约澄清、两张SVG展示图及讲解/问答。关联Git提交可证明产物版本，不等于证明个人阅读掌握、独立实现或人工评审完成。代码与文字的AI辅助及人工待确认边界保留。

组长授权下当前技术基线已确定；本人仍需掌握文章/注释、审核真实接口和参加展示。后续新增离线诊断软件与测试见[运行说明](../research/execution-guide.md)。张茗博/胡知鱼工作不得据本稿归为本人完成；贡献表记录实际参与及审核，不预填工时或比例。

## 展示讲稿提纲（个人部分）

**已交付可整合素材：[两页SVG/PNG、中英讲解、决策表和问答](ma-presentation-materials.md)。** 后文提纲保留为背景，实际整合以该素材和全组计时为准。

2026-11-08按[6分钟Design展示计划](presentation-plan.md)调整。本人主讲恢复核心设计/关键取舍约70秒、开放问题/验证约40秒；这是准备额度，不是已计时结果。老师要求设计进展及理由，论文背景和H1/H2细节放备份或提问，不逐篇汇报论文。

核心设计提纲：“恢复模块读取有来源和时效的观测与历史，生成有限候选，但不直接驱动机器人。任务协调器独占授权，派发前复检控制代次、时效、动作边界与剩余预算；不满足时拒绝或求助。与模型直接发动作相比，这样能限制旧结果和暂停竞态，代价是更多协议与检查延迟。候选评分保留替换接口，先用简单诊断再决定复杂模型；排序值不能直接当作已校准成功概率。人工返回必须按状态重新授权，设备停止由测量反馈确认。”

开放问题提纲：“平台已选Isaac Sim 4.5 / DexGarmentLab，马已在张电脑完成基础复跑，后续统一在该电脑执行。当前优先验证真实观测/动作映射、停止反馈和恢复评分；每项给出负责人、通过标准和后备。基础复跑已关闭，恢复性能仍待对应实验；数据或模型尚不可用时采用隔离的离线诊断与可替换接口。”

配一张与三架构命名一致的核心交互图，并从实际ADR挑选备选与代价。结合三人整套Slides完整排练、删去重复内容；不展示虚构曲线或把算法提案演示成实测能力。


### 2026-11-08 本轮新增反思与可核验贡献

在 PR #9/#10 合并后，Codex 按组长要求新增运行时 I/O 离线接入、单关节候选编码、停止证明关联检查及 14 项回归，并在已提交的真实组件记录上执行。发现并防止把动作后的唯一 RGB 倒填为动作前输入；未将 API 返回补成产品执行历史，也未把组件停止记为正式 SRS 验收。依据实测重置差异形成 ADR-MA-005，更新摘要、风险与讲解；这些属于本分工的新工具和设计分析，仿真采集仍归张茗博。没有运行新的 Isaac、开展真实用户走查或填写个人工时。本人仍须核实和掌握材料，团队实际反馈与提交记录不预填。
