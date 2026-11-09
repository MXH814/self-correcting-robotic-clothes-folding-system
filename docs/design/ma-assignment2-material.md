# 马祥珲 Assignment 2 集成材料

更新：2026-11-09。本工作流的AI辅助设计/分析材料已同步PR27/PR29及PR30至PR32；下方Summary与英文主文档保持同一500词文本。现行诊断协议、ADR-MA-007、可编辑流程图和记录计时已补齐，新包A/B全部958次记录调用已独立重算，PR32新增正常性技术审核也已验收；实际课堂反馈与个人确认仍待对应证据。下方按日期列出的早期增量保留其历史状态，不代表当前仍无检测包或告警恢复记录。本文不代签三人批准或最终提交。

## A2-01 — Design Summary candidate

<!-- summary:start -->

Part I specified a simulated clothes folding system for household users, with maintenance roles managing configurations and models. The scope remains one supported shirt type on a fixed table, focusing on grasp offset and partial slippage. Thirty product requirements and eighteen acceptance tests remain unchanged. Part II develops logical, deployment and technology architectures, domain and interaction models, five interface screens, decision records, and explicit verification plans. Implementation evidence supports these designs without replacing their acceptance conditions.

The task coordinator owns dispatch authority. Detection and recovery workers propose results; the adapter checks execution conditions and reports measurements. Versioned observations, control generations, bounded attempts and persisted acceptance records prevent late proposals from silently regaining authority. The interface separates task state from measured rest. Manual adjustment requires confirmed rest and explicit takeover; returning control requires fresh validation. The browser prototype exercises these interactions using labelled synthetic events and remains separate from actual simulator control.

The development deployment uses Zhang Mingbo's existing workstation with Isaac Sim 4.5 and DexGarmentLab. The normal controller remains GAM plus scripted actions. Simulation dependencies remain isolated from application and inference environments. Process transport and persistent storage choices remain open. The workstation's limited RAM, shared compute resources and untested distributed failure paths remain architectural risks. Subsequent simulation continues on that workstation rather than requiring another installation.

The detector adapts FIPER's observation branch using pretrained ResNet18 features and random network distillation. Hu's archived package was independently reproduced, including its normal false alarm. Zhang's subsequent package distinguishes left and right sleeve phases using past controller intent. One complete normal trial supplies fitting and four supply calibration. A previously viewed development trial is reassigned to calibration. Thresholds, sources and failed development records remain versioned; no statistical guarantee or failure probability is claimed.

New A/B/C records connect this design to execution. A completes normal folding without alarms or recovery. In B, an RGB alarm requests preflight; after measured rest and nominal path checks, a new image reconfirms the alert. Five macro operations produce sixty-one dispatches. Thirteen post-macro measurements confirm sustained holding; a new generation then performs twenty-three continuation checks using declared simulation geometry. During this restricted continuation, fresh holding geometry can support progress despite an unchanged RGB anomaly report. Both channels retain their independent records. The final regional proxy contains 2002 of 2048 points. C returns UNKNOWN for missing detector inputs and requests help without further dispatch. These are development cases, not a recovery-benefit comparison or product-quality certification.

Independent review checks logs, source snapshots, geometry, regional counts and video provenance. Recorded detector-call processing has a median of approximately 32 milliseconds and a maximum of 63 milliseconds in A and B; this excludes unmeasured system queues, UI and exposure latency. Shared checkpoint and RGB now reproduce all recorded decisions within declared numerical tolerance. Design refinements preserve validation origins and distinguish human judgement, alarms and stop acceptance times. AI-assisted material requires source checks, counterexamples and honest attribution. Remaining work includes user evaluation, complete system validation, personal confirmation and classroom-feedback revision before final submission.
<!-- summary:end -->

## A2-02 / A2-03 — 本人负责的具体设计

恢复职责、逻辑组件图、领域关联、恢复时序、输入/动作/评分、取消/拒绝/接管及记录见 [recovery-design.md](recovery-design.md)、[interfaces.md](interfaces.md)和七份核心ADR。当前实际路径以[运行合同](pre-current-runtime-contract.md)、[ADR-MA-007](decisions/ADR-MA-007-phase-conditioned-detection-and-verified-continuation.md)及[新流程图](figures/ma-current-observation-recovery.svg)为准。系统总体架构/部署/技术三视图仍由张茗博整合；本组件图不冒充全组最终架构验收。

## A2-04 — 需求建议

现行FR/NFR/AI/DR产品阈值不变。CR-MA-01已采纳为内部接口细化，记录评分语义、校准与接续版本；CR-01/CR-02已按组长授权采纳为开发记录设计。当前分阶段阈值、前检刷新和限定几何接续由ADR-MA-007补记，不将诊断宏直接当作通过产品0.60概率门槛的实现。

## A2-06 — 算法开放问题

见 [ma-risks-and-validation.md](ma-risks-and-validation.md)。每项有影响、最小 PoC、判据、负责人/复核及后备方案。部分统计规模和阈值校准需试跑后决定，不能预填通过。

## A2-07 — AI Tools Reflection contribution draft

The current contribution adds a concrete audit trail rather than accepting generated evidence summaries at face value. A self-consistent modified-image fixture exposed the missing review-source binding in PR27; the revised gate rejected it before decoding or fitting. Full numerical reproduction then verified the archived package. For PR29, independent source, event, geometry, regional and video checks established a limited development execution chain. Tiny floating-point differences were isolated from unchanged identity, timing and status. A new analysis tool checks original file hashes before summarizing recorded processing times, explicitly separating internal detector-call time from product end-to-end latency. PR31 subsequently supplied the checkpoint and complete RGB. Independent replay now reproduces all 958 recorded calls, including the preflight refresh, with identical decision fields and explicit score tolerances. Simulation capture belongs to Zhang and the archived detector package belongs to Hu; personal understanding, effort and classroom participation still require the owner’s confirmation.

Codex assisted this workstream by locating versioned primary sources, extracting the SRS constraints, comparing the existing teammate branch, and drafting literature notes, hypothesis cards, interfaces, decision records, and report material. The outputs were checked for source attribution, document links, requirement consistency, and annotation length. These checks establish document properties, not model accuracy or successful robot execution.

Critical corrections were necessary. Reading only abstracts would have overstated novelty: RedFlow already reports clothes folding, and TAIL-Safe distinguishes empirical assurance from formal invariance. Progress and robot pose do not establish identical contact states. Numerical scores from different methods also cannot be substituted into the SRS probability threshold. The draft therefore separates reported findings, our interpretations, proposed design decisions, and experiments that remain unperformed.

The workflow uses the existing assistant and local tools; no GPU rental, training on real robot data, participant study, or robot API job was launched. Individual human effort, attributable subscription cost, and token usage for this stage have not been supplied and are not inferred from the earlier assignment. The owner should add the available work record and any justified estimates before the final report is attributed. Team review, source PDF reconciliation where needed, and physical interface testing remain outstanding.

In a subsequent implementation pass, Codex also produced standard-library diagnostic code, optional PyTorch MLP ablations, unit tests, synthetic fixtures, a resource estimator, and execution instructions. The tests exercise software boundaries including data leakage, unknown outcomes, stale observations, and score semantics. A short CPU training run on manufactured fixtures verifies the neural path, with an approximate parameter-matched current-only control. These checks do not establish closed-loop recovery performance or reproduce the closest papers.

On 7 November, the handoff PR was re-reviewed after a reproducible path bug was fixed. Its launcher regression passed, and the PR was merged. A repository audit checked the submitted numeric sample and artifact fingerprints. New tooling exports independently trusted legacy trajectories to numeric observations and constructs stage-local history without inventing timestamps, dispatched actions, or success labels. Forty Python tests pass; the original full trajectory and a working simulation environment remain inaccessible to this workstream. The synthetic export checks therefore remain software evidence, not recovery experiments.

On 8 November, two normal demonstration exports were actually received from the private release. ZIP hashes, CRC, complete per-file inventories, numeric observations and stage-local history checks passed for all 153 frames. The extra file in the 81-file package is a handoff note. This closes normal-data access, not independent simulator reproduction or recovery experiments; actual action mapping, timing, stopping and recovery outcomes remain missing.

The next pass added a fixed 8-by-8 RGB mean encoder, raw joint features and masked past observations, and ran it on all 153 real frames. This representation has no learned parameters and provides no recovery labels. Forty-nine software tests pass after integrating the asset-verifier PR, including checks for future-frame isolation, stage boundaries, corrupted inputs and malformed preflight generations. Design corrections separate continuation success from trial-level autonomy, isolate old-generation accounting, and require adapter generation barriers. Two editable presentation figures, English speaking drafts, decision comparisons and answer notes were produced and visually checked; no actual rehearsal, classroom feedback or final slide upload is claimed.

## A2-08 — 参考文献

原四篇英文注释及新增FIPER设计影响注释位于 [annotated-references.md](../research/annotated-references.md)，分别满足 200–300 词的结构检查。正式报告应只纳入实际使用的来源，文献清单和每篇注释由作者本人及另一成员核原文。

## A2-09 — 可核验贡献与署名边界

本分工已形成的文档成果：四篇原文分析、最近邻比较、H1/H2问题卡、诊断协议、AI组件/接口、七项ADR、风险/PoC、参考注释和此报告片段；新增组员PR审查、完整原始材料接收与958次检测调用复算、当前运行合同/时序、可编辑流程图、记录计时、19页中文展示整合稿及讲解/问答。关联Git提交可证明产物版本，不等于证明个人阅读掌握、独立实现或人工评审完成。代码与文字的AI辅助及人工待确认边界保留。

组长授权下当前技术基线已确定；本人仍需掌握文章/注释、审核真实接口和参加展示。后续新增离线诊断软件与测试见[运行说明](../research/execution-guide.md)。张茗博/胡知鱼工作不得据本稿归为本人完成；贡献表记录实际参与及审核，不预填工时或比例。

## 展示讲稿提纲（个人部分）

**已交付可整合素材：[两页SVG/PNG、中英讲解、决策表和问答](ma-presentation-materials.md)。** 后文提纲保留为背景，实际整合以该素材和全组计时为准。

2026-11-08按[6分钟Design展示计划](presentation-plan.md)调整。本人主讲恢复核心设计/关键取舍约70秒、开放问题/验证约40秒；这是准备额度，不是已计时结果。老师要求设计进展及理由，论文背景和H1/H2细节放备份或提问，不逐篇汇报论文。

核心设计提纲：“恢复模块读取有来源和时效的观测与历史，生成有限候选，但不直接驱动机器人。任务协调器独占授权，派发前复检控制代次、时效、动作边界与剩余预算；不满足时拒绝或求助。与模型直接发动作相比，这样能限制旧结果和暂停竞态，代价是更多协议与检查延迟。候选评分保留替换接口，先用简单诊断再决定复杂模型；排序值不能直接当作已校准成功概率。人工返回必须按状态重新授权，设备停止由测量反馈确认。”

开放问题提纲：“平台已选Isaac Sim 4.5 / DexGarmentLab，马已在张电脑完成基础复跑，后续统一在该电脑执行。当前优先验证真实观测/动作映射、停止反馈和恢复评分；每项给出负责人、通过标准和后备。基础复跑已关闭，恢复性能仍待对应实验；数据或模型尚不可用时采用隔离的离线诊断与可替换接口。”

配一张与三架构命名一致的核心交互图，并从实际ADR挑选备选与代价。结合三人整套Slides完整排练、删去重复内容；不展示虚构曲线或把算法提案演示成实测能力。


### 2026-11-08 本轮新增反思与可核验贡献

在 PR #9/#10 合并后，Codex 按组长要求新增运行时 I/O 离线接入、单关节候选编码、停止证明关联检查及 14 项回归，并在已提交的真实组件记录上执行。发现并防止把动作后的唯一 RGB 倒填为动作前输入；未将 API 返回补成产品执行历史，也未把组件停止记为正式 SRS 验收。依据实测重置差异形成 ADR-MA-005，更新摘要、风险与讲解；这些属于本分工的新工具和设计分析，仿真采集仍归张茗博。没有运行新的 Isaac、开展真实用户走查或填写个人工时。本人仍须核实和掌握材料，团队实际反馈与提交记录不预填。


### PR #12/#13 后新增工作

审阅并合并课程模型和动作前采集链，独立核验6文件清单、时钟/身份/意图/反馈及位移；实现492维当前输入与仅用于后续决策的242维组件片段。新增9项回归验证当前动作不能进入本次历史、跨任务/代次拒绝及未来反馈不改变早期输入。另修正Git换行对测量文件指纹的影响，并从原始Git blob验证。没有执行新仿真、获得衣物失败标签或证实H1/H2；个人归属仍由本人确认。
# 本次 Pre 检测适配追加交付（2026-11-08）

本节为最新增量，原有英文事实底稿继续作为历史及报告整合素材。马负责的 FIPER 观测分支适配、冻结 ResNet18 编码、正常拟合/校准工具、在线报告、诊断恢复生命周期、写前日志和宏后新窗口复检已经形成代码。143 项软件检查通过，原始恢复试次 540 帧已实际编码为 512 维特征；这些不是检测性能或在线恢复结果。

已提供 [ADR-MA-006](decisions/ADR-MA-006-observation-detector.md)、[接入指南](pre-detection-integration.md)、[核心图与中英讲解](ma-presentation-materials.md)、[机器证据](../research/evidence/ma-pre-detection-20261108.json)。原作者网络工厂与视觉骨干按固定来源复用，保留许可证和差异，不能归为本组原创方法。代码与文档由 Codex 辅助实现，马仍需本人理解、核实和确认贡献归属。

依赖：胡提供匹配的独立正常拟合/校准和开发验证，张接真实观测/宏/测量许可并跑 A/B/C。马需据实际结果复核与修正、终审最终 Slides 并完成本人实际排练；当前没有这些项目的通过记录。

---
