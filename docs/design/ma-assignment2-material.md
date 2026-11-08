# 马祥珲 Assignment 2 集成材料

状态：本工作流的 AI 辅助设计/分析稿。供与 `hzy@067cf91` Design 草稿合并时选用，不覆盖其文档，也不声明三人已批准。以下 Summary 为全组报告候选文本，需整合最终实际进展/课堂反馈；不是马祥珲个人总结或已经提交的作业。

## A2-01 — Design Summary candidate

<!-- summary:start -->
Part I established requirements for a simulated robotic clothes folding system operating on one supported shirt type at a fixed table. The system must detect grasp offset and partial slippage, attempt bounded recovery, and request human assistance when autonomous continuation is not justified. The present design work translates those requirements into explicit recovery responsibilities, information boundaries, and interfaces that can be integrated with the overall architecture.

The research review examines calibrated policy steering, learned safety monitoring, offline corrective learning, and garment simulation. These sources show that candidate selection, value-guided correction, and learning from failed rollouts already have substantial precedents. Accordingly, the proposed research questions have been narrowed to the information needed to distinguish garment recovery contexts and the relationship between local recovery quality and subsequent task completion. Neither question is presented as an established contribution. Diagnostic protocols specify comparisons, counterexamples, and conditions under which the hypotheses should be rejected or revised.

The recovery worker proposes actions but cannot authorize motion. An observation gateway verifies declared sensor sources and timestamps, while a history store retains observations and actually executed actions. Candidate generation, validation, and continuation scoring remain replaceable components. The task coordinator checks current authority, control generation, action bounds, observation freshness, and remaining budgets before accepting a dispatch. A late model response cannot restore authority after a pause or termination. Measured device feedback, rather than a policy score, establishes whether stopping has been confirmed.

The design preserves separate meanings for runtime completion, offline quality, assistance, and autonomous success. A continuation score concerns completion from the current decision without further assistance, conditioned on the goal, remaining budget and pinned controller. It does not erase earlier human intervention from the trial-level autonomous metric. Calibration evidence must accompany any model used for the probability acceptance threshold. Proposed dispatch records bind the accepted attempt, budget reservation, and unique command identifier. Unknown execution status or a logging failure blocks further motion until the controller has resolved the device state.

Isaac Sim 4.5 with DexGarmentLab is selected for development, supported by a teammate's demonstration and training pipeline reports. Independent reproduction, observation provenance, action mapping, stop feedback, and state restoration remain unverified. The data design separates online sensor evidence from hidden simulation information used for offline labels and quality assessment. Related branches and garments must remain grouped during data splitting, and sealed evaluation data cannot influence matching libraries or calibration.

Four decision records establish the current implementation baseline for control separation, diagnostic-first algorithm selection, reproducible data handling, and platform adoption under the team leader's authorization. Offline software supports grouped validation, candidate ranking, paired analysis and preflight checks. Two normal demonstration exports, comprising 153 frames, have been downloaded and independently checked against file inventories and numeric schemas. Fixed RGB features and masked histories now process these observations without inventing actions or labels. They contain no recovery outcomes. Automated tests and synthetic fixtures verify software behavior, not research hypotheses or physical execution. Open issues have verification methods and fallbacks for Part III. Companion workstreams supply architecture, interaction and traceability drafts. No new robot performance, user study, independent simulation reproduction or physical acceptance is claimed. Actual presentation feedback must enter the final report.
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

开放问题提纲：“平台已选Isaac Sim 4.5 / DexGarmentLab，现有作者试跑和导出报告支持选型，不能证明独立复现和恢复性能。当前优先验证真实观测/动作映射、停止反馈和恢复评分；每项给出负责人、通过标准和后备。数据或模型尚不可用时采用明确隔离的离线诊断与可替换接口，完整运行及研究假设放Part III验证，不虚报为已完成。”

配一张与三架构命名一致的核心交互图，并从实际ADR挑选备选与代价。结合三人整套Slides完整排练、删去重复内容；不展示虚构曲线或把算法提案演示成实测能力。
