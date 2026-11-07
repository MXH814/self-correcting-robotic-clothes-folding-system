# 马祥珲 Assignment 2 集成材料

状态：本工作流的 AI 辅助设计/分析稿。供与 `hzy@067cf91` Design 草稿合并时选用，不覆盖其文档，也不声明三人已批准。以下 Summary 为全组报告候选文本，需整合最终实际进展/课堂反馈；不是马祥珲个人总结或已经提交的作业。

## A2-01 — Design Summary candidate

<!-- summary:start -->
Part I established requirements for a simulated robotic clothes folding system operating on one supported shirt type at a fixed table. The system must detect grasp offset and partial slippage, attempt bounded recovery, and request human assistance when autonomous continuation is not justified. The present design work translates those requirements into explicit recovery responsibilities, information boundaries, and interfaces that can be integrated with the overall architecture.

The research review examines calibrated policy steering, learned safety monitoring, offline corrective learning, and garment simulation. These sources show that candidate selection, value-guided correction, and learning from failed rollouts already have substantial precedents. Accordingly, the proposed research questions have been narrowed to the information needed to distinguish garment recovery contexts and the relationship between local recovery quality and subsequent task completion. Neither question is presented as an established contribution. Diagnostic protocols specify comparisons, counterexamples, and conditions under which the hypotheses should be rejected or revised.

The recovery worker proposes actions but cannot authorize motion. An observation gateway verifies declared sensor sources and timestamps, while a history store retains observations and actually executed actions. Candidate generation, validation, and continuation scoring remain replaceable components. The task coordinator checks current authority, control generation, action bounds, observation freshness, and remaining budgets before accepting a dispatch. A late model response cannot restore authority after a pause or termination. Measured device feedback, rather than a policy score, establishes whether stopping has been confirmed.

The design preserves separate meanings for runtime completion, offline quality, assistance, and autonomous success. A continuation score is conditioned on the goal, remaining budget, and pinned continuation controller; it is not interchangeable with an uncalibrated similarity or safety value. Calibration evidence must accompany any model used for the probability acceptance threshold. Proposed dispatch records bind the accepted attempt, budget reservation, and unique command identifier. Unknown execution status or a logging failure blocks further motion until the controller has resolved the device state.

Isaac Sim 4.5 with DexGarmentLab is selected for development, supported by a teammate's demonstration and training pipeline reports. Independent reproduction, observation provenance, action mapping, stop feedback, and state restoration remain unverified. The data design separates online sensor evidence from hidden simulation information used for offline labels and quality assessment. Related branches and garments must remain grouped during data splitting, and sealed evaluation data cannot influence matching libraries or calibration.

Four decision records establish the current implementation baseline for control separation, diagnostic-first algorithm selection, reproducible data handling, and platform adoption under the team leader's authorization. Offline diagnostic software now supports grouped data validation, simple candidate ranking, paired analysis, and preflight checks. Automated tests and synthetic fixtures verify software behavior, not the research hypotheses or physical execution. Open issues have verification methods and fallback choices for Part III. The companion workstreams supply environment, interaction, recording, and traceability drafts for integration. No new robot performance, user study, independent simulation reproduction, or physical acceptance is claimed. The final report must incorporate actual presentation feedback and integration evidence before submission.
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

## A2-08 — 参考文献

四篇英文注释位于 [annotated-references.md](../research/annotated-references.md)，分别满足 200–300 词的结构检查。正式报告应只纳入实际使用的来源，文献清单和每篇注释由作者本人及另一成员核原文。

## A2-09 — 可核验贡献与署名边界

本分工已形成的文档成果：四篇原文分析、最近邻比较、H1/H2 问题卡、诊断协议、AI 组件/接口、四项 ADR、风险/PoC、参考注释和此报告片段；新增张茗博分支技术审查、平台接入与数据审计。关联 Git 提交记录可证明产物版本，不等于证明个人阅读掌握、独立实现或人工评审完成。

组长授权下当前技术基线已确定；本人仍需掌握文章/注释、审核真实接口和参加展示。后续新增离线诊断软件与测试见[运行说明](../research/execution-guide.md)。张茗博/胡知鱼工作不得据本稿归为本人完成；贡献表记录实际参与及审核，不预填工时或比例。

## 展示讲稿提纲（个人部分）

“我们的研究聚焦叠衣失败后如何继续完成任务。已有方法覆盖候选排序、价值修正和失败数据学习，所以当前创新假设是恢复上下文的信息是否充分，以及局部重抓是否代表整任务收益。系统设计把研究模块放在提案侧，由任务协调器独占授权；动作要经过时效、约束和预算复检。未校准分数不能证明成功，模型返回也不能证明设备静止。接下来用固定基线和配对失败案例检验假设，若证据不支持，则采用简单方案并调整研究方向。”

讲稿需结合最终实际设计与课堂总时长排练；不展示虚构曲线或把算法提案演示成实测能力。
