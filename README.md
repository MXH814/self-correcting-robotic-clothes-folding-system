# Self Correcting Robotic Clothes Folding System

**PR #27 数值已复核，待一项修正：** 完整模型、阈值 `1.1895795584` 及逐帧正常复验可独立复现；normal-03 有一次误报片段。当前请求修改“未绑定固定已审核源 manifest”的接收逻辑及回归，暂未合并；不重采三条数据，不因误报反复调本版阈值。[审阅与证据](docs/reviews/pr27-review.md)

**PR #26 已审核合并：** 三条固定 640×480 正常采集共 1,401 帧、1,428 次观测、2,318 条派发，原包/时序/读取器/相机与控制兼容性已独立核验。匹配原始数据交接缺口关闭；胡可直接开展阶段审核、完整试次划分、拟合和独立校准，不重复索要数据。[下载与读取](docs/research/zhangmingbo/matched-normal-data-20261109/README.md) · [复审证据与后续](docs/reviews/pr26-review.md)。原始正常标签及用途仍待接收方审核分配，不代表 A/B 或 SRS 质量通过。

**PR #25 已合并。** 胡的 5 条首袖离线分数（1,051帧）已独立复算一致，九试次回放可用；这是只拟合输出头的开发探针，没有正式阈值或在线检测包。#26 匹配数据已接收，当前优先完整拟合/独立校准和真实恢复接线，**PPT 暂不制作或修改，工作完成后最后整理**。[复审记录与待办](docs/reviews/pr25-review.md)

**当前优先完成 Pre 核心演示，研究训练暂缓。** 马已交付 FIPER RND-OE 观测分支适配、固定 ResNet18 编码、在线窗口/缺测处理、恢复请求和新观测复检；143 项软件检查通过，真实 540 帧已编码。胡负责同配置独立正常数据的拟合/校准/验证及分数回放，张负责观测导出、真实 A/B/C 接线和整组 PPT。缺 SADP_G 不阻塞该观测分支；当前尚无真实检测效果或由检测触发的仿真恢复结论。[实际接口与命令](docs/design/pre-detection-integration.md) · [新核心图与讲稿](docs/design/ma-presentation-materials.md) · [选型 ADR](docs/design/decisions/ADR-MA-006-observation-detector.md)

**当前算法进展：** #23/#24已合并，共享相机/控制器/目标/预算配置已冻结，首条同次宏样本已编译为明确命名的区域代理正样本。五种时间/容量对照及配置绑定模型已实现，115项测试通过；真实训练尚未发生，当前缺更多结局覆盖和训练/开发分组。[共享协议及下一步](docs/research/shared-context-and-proxy-protocol.md) · [组长剩余清单](docs/research/ma-remaining-checklist.md)

同济大学《系统分析与设计》课程第三组项目。

面向仿真环境的机器人叠衣系统，覆盖失败检测、自主恢复、人工协助与任务结果回放。

## 当前进度

已完成选题、软件需求规格说明（SRS）、九张可编辑系统模型和五屏界面原型。
胡知鱼分工已有可操作测试桩原型、需求追踪、数据规范、用户走查材料和英文 Design 工作稿，具体证据与待办见 [Design 交付状态](docs/design/delivery-status.md)。
已收到并复核双臂运行时 I/O、可见仿真 RGB、完整正常折叠取景、投影检查、组件停止与初态重置诊断。马祥珲已完成组件记录、动作前492维输入、后续执行片段与停止证据的离线接入；系统模型源已整合。PR #15/#18/#20/#21已合并：五条衣物轨迹1051帧/946派发已实际接入，两个完整Fold Tops结局已独立复算；完整恢复宏编码、序列评分训练/推理原型及独立试次描述已实现，91项Python测试通过。真实恢复监督训练、强基线/校准与产品闭环仍待完成；界面原型仍不连接机器人或云服务。

**追加 #22：** 指尖近景补采三条试次已核验合并，408帧/448派发也已接入；合计1459帧/1394条底层派发输入（不是1394个恢复样本）。肩/下摆均值与接触几何标签为待审核提案；移动近景与固定视角分开记录。[最新算法进展](docs/research/garment-algorithm-progress.md)

当前执行计划为 **[第一阶段：研究问题验证与系统设计](docs/first-stage-plan.md)**。
本阶段同时推进 2025—2026 年相关工作、research gap 诊断、仿真最小验证和课程 Design，按任务依赖与证据验收推进。
计划已依据 Assignment 2 正式 PDF 与 Canvas 页面更新；已形成马祥珲的研究/AI设计成果及可运行离线诊断工具，组件与正常流程已有实测，恢复研究实验、产品闭环与全组设计定稿仍待完成。

**仿真安排已确认：马祥珲已在张茗博电脑上复跑，基础复跑事项关闭。后续仿真、采集及恢复闭环实验统一在张茗博电脑运行，不要求组长电脑安装或换机重跑。** 详见[共享仿真执行安排](docs/research/shared-simulation-workflow.md)；真实接口、停止和恢复实验继续分别验收。

**第三组展示：2026-11-09 13:30–15:05场次（上海时间），每组6分钟，全员出席；Slides须在11月9日13:30之前上传Canvas。** 本组具体出场时刻未公布。当前优先整合三架构、关键决策及理由、重要交互、需求变化与开放问题，见 **[展示计划、三人分工与验收](docs/design/presentation-plan.md)**。

**Pre 总负责人现为张茗博：整组 PPTX/PDF、完整逐页演讲稿与三人交接、备份问答、排练计时、课前 Canvas 上传核对和课堂反馈原始记录均由张茗博统筹。马祥珲终审核心技术事实；胡知鱼交 UI/需求变化素材并负责后续报告变更追踪。讲解仍按胡→张→马分段，三人均到场。** 具体交付和公告逐条覆盖见[展示计划](docs/design/presentation-plan.md)。

**Assignment 2最终截止仍为2026-11-20 19:00。** 展示后纳入实际课堂反馈，完成 **[九项正式交付与验收清单](docs/assignment-2-checklist.md)**；完整训练和研究诊断不是本次展示的前置条件。

## 文件导航

| 路径 | 内容 |
| --- | --- |
| [最终 SRS 提交目录](submissions/assignment-1/Group3_Assignment1_SRS/) | 英文 PDF 与九页可编辑 Draw.io 模型，保留课程提交命名 |
| [英文 Word 源文件](docs/requirements/SRS_EN.docx) | 继续编辑需求文档的有效源文件 |
| [选题说明](docs/idea/Idea_Submission_EN.pdf) | Idea Submission，记录选题背景；范围以最新 SRS 为准 |
| [界面原型](prototypes/ui/index.html) | 用浏览器打开即可查看五个界面 |
| [Design 英文工作稿](docs/design/system-design.md) | 九项报告章节及待团队确认的内容 |
| [交互设计与复验](docs/design/interaction-design.md) | 五屏流程、测试桩操作与异常路径 |
| [需求变更](docs/design/requirements-changes.md) / [追踪表](docs/design/traceability.md) | 英文 SRS 基线、待审建议及 30 项需求与 18 项测试 |
| [记录与评价规范](docs/design/data-design.md) | 标签、分母、数据划分与空白案例模板 |
| [用户走查](docs/design/user-walkthrough.md) | 主持流程、参与者任务与匿名记录，实际走查待补 |
| [Design 交付状态](docs/design/delivery-status.md) | 九项证据、缺项、复核人与交接 |
| [协作约定](CONTRIBUTING.md) | 分工、分支和证据记录要求 |
| [第一阶段详细计划](docs/first-stage-plan.md) | 近期论文、候选问题、三人任务、Design 交付、依赖与完成标准 |
| [马祥珲第一阶段成果](docs/research/ma-task-workbook.md) | 四篇精读、比较、问题卡、实验协议、AI详细设计及课程材料；待本人/团队评审，实验未执行 |
| [研究工具运行说明](docs/research/execution-guide.md) | 数据校验/分组、B0–B4离线基线、统计、评分诊断、门禁子集和资源估算；无仿真依赖 |
| [张茗博环境与文献成果](docs/research/zhangmingbo/README.md) | 已审查合并的三篇笔记、Isaac Sim 4.5 / DexGarmentLab可行性和历史复现记录 |
| [张茗博交接与后续待办](docs/research/zhangmingbo/handoff-tasks.md) | 最小交接包H01–H05、后续仿真/控制任务、课程Design职责、提交位置与验收标准 |
| [马祥珲数据接入进展](docs/research/ma-data-intake-progress.md) | 两条正常轨迹153帧已实际校验；数值导出、阶段内历史、环境及恢复实验剩余输入 |
| [PR #6/#7审查与数据接收](docs/reviews/pr6-7-handoff-review.md) | 架构素材已合并，两个正常数据包153帧已实际校验；80/81关闭，环境/profile/恢复数据仍待完成 |
| [三架构展示素材](docs/design/architecture-presentation-draft.md) | 张茗博的逻辑/部署图源、技术取舍、交互及135秒讲解候选稿，待整合Slides |
| [马祥珲两页展示素材](docs/design/ma-presentation-materials.md) | 可编辑SVG/PNG核心图和风险图，中英讲解、决策对比与答辩问答 |
| [153帧真实观测编码](docs/research/normal-observation-integration.md) | 固定RGB/关节/历史编码已运行、真实预览和可复跑入口；无恢复标签或科研结论 |
| [评分与并发契约澄清](docs/design/contract-clarifications.md) | 后续成功/整试次指标、旧代不可用计数及adapter代次屏障的精确定义 |
| [PR #8固定环境准备审查](docs/reviews/pr8-environment-review.md) | 固定源码/依赖/资产材料已补齐；换机部署不再是当前任务，真实控制与恢复待验证 |
| [仿真接入与审查结论](docs/research/dex-integration-plan.md) | 平台已选定，组长确认同机复跑完成；继续验证在线来源、真实接口及恢复数据 |
| [动作前因果输入接入](docs/research/preaction-integration-progress.md) | PR #12/#13已合并；492维输入、后续片段和原始字节交接已验证；失败/恢复标签仍缺 |
| [真实衣物输入与核心算法进展](docs/research/garment-algorithm-progress.md) | 946条因果输入、17维恢复宏、序列评分训练/推理和独立试次工具；真实训练标签仍待审核 |
| [共享配置与代理监督协议](docs/research/shared-context-and-proxy-protocol.md) | 冻结共享头、首条自动数值代理样本、五种对照和固定先导采集，不修改原始标签 |
| [先导采集配置](configs/research/pilot-macro-collection-v1.json) | 一轮5个宏偏置位置，保留全部试次/失败/未知；不是充分训练或统计规模 |
| [恢复评分训练样本契约](docs/research/recovery-sample-contract.md) | 同次预决策宏计划/上下文/执行/结局、划分与审核要求，拒绝低层派发冒充恢复样本 |
| [PR #15/#18/#20/#21最新审阅](docs/reviews/pr15-18-20-review.md) | 四PR已合并，七包指纹/两次点云评分与UI实测核验；91项软件测试通过 |
| [PR #11–#16历史审查](docs/reviews/pr11-16-readiness.md) | 控制/课程/动作前输入成果已合并，保留当时快照；原始字节/快照问题现已解决，当前以#15/#18/#20审阅为准 |
| [不可比中段的分块先导方案](docs/research/blocked-trial-pilot-plan.md) | 区分实际试次与同根候选池，处理遗留效应和失败标签边界，不生成虚构研究结论 |
| [运行时动作／观测接入](docs/research/runtime-component-integration.md) | 实测 60 通道、历史／候选编码、停止复算及动作后 RGB 防泄漏；本批已运行 |
| [实测输入与分支有效性决定](docs/design/decisions/ADR-MA-005-measured-input-and-branch-validity.md) | 重置误差的实验影响、后备设计、记录细化与局部分母决定 |
| [马祥珲最终剩余清单](docs/research/ma-remaining-checklist.md) | 已完成项、真实环境/数据阻塞、队友最小交付与个人/课程事项 |
| [Assignment 2 要求与验收](docs/assignment-2-checklist.md) | 九项交付、三人分工、展示/反馈、词数与打包检查 |
| [第三组课堂展示执行计划](docs/design/presentation-plan.md) | 已确认场次、课前上传、三人素材与讲解分配、六页建议结构及验收 |
| [展示上传与反馈记录](docs/design/presentation-feedback.md) | 实际排练、Canvas回执、全员展示及反馈修订的待办/证据登记 |
| [用户截图保存索引](docs/course/user-screenshot-index.md) | 本次及历史课程要求原图、其他可访问历史截图的本地归档与校验索引 |
| [老师新展示公告](docs/course/assignment-2/presentation-announcement.md) | 原始截图与排期、6分钟和展示内容要求的准确摘录 |
| [Assignment 2 官方说明](docs/course/assignment-2/System%20Analysis%20%26%20Design%20Assignment_2.pdf) | 原要求 PDF；本地作业目录同时保留 |
| [项目路线图](docs/roadmap.md) | 第一阶段与 SRS G1—G4 的关系及后续验收 |

Draw.io 模型是系统图的编辑源。修改后需同步 Word 和最终 PDF。
英文 SRS 是当前需求基线；历史中文版未跟随最新英文修订，不作为当前基线。

## 项目范围

固定桌面、双臂机器人、一类上衣；优先处理抓取偏移和部分滑移。
实现任务准备、闭环运行、有限恢复、暂停/终止、人工接管、结果与回放。
当前不包含实体家庭部署、行走、混合衣物分拣或任意打结处理。

## 团队

| 成员 | 后续主要职责 |
| --- | --- |
| 马祥珲 | 恢复策略、数据标签、模型训练、对照与消融实验 |
| 胡知鱼 | 用户交互、界面实现、可用性测试、回放与结果展示 |
| 张茗博 | 仿真集成、正常控制基线、状态机、失败注入与实验执行工具；Pre PPT/完整演讲稿、排练与上传统筹 |

第一阶段具体分工：马祥珲主责最近邻方法、创新假设和诊断算法；胡知鱼主责评价证据、数据质量及交互设计；张茗博主责仿真验证、控制架构和接口。三人共同评审研究结论、Design 与需求追踪，详细交付见第一阶段计划。

## 本地历史归档

旧提交、压缩包、中文版、审阅报告、生成工具链与渲染截图保存在课程目录的
`archive/2026-11-02-initial-organization/`，不上传 Git。
课程课件继续保留在课程目录。迁移及校验记录同样保存在本地归档内。

## 后续开发

按第一阶段计划并行推进科研核验与 Design 交付：课程设计可基于明确假设先完成，实验结果推动有记录的修订；再依据证据决定核心方法、扩大训练与正式比较。
第一阶段同时覆盖 Assignment 2 的九项设计交付并推进 G1/G2；科研诊断和最小集成是增强目标，完整训练及 180 次比较不属于本次 Design 硬性要求。技术未知项用备选、风险和 Part III PoC 说明；尚未选定的框架不预先写入依赖文件。
