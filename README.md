# Self Correcting Robotic Clothes Folding System

同济大学《系统分析与设计》课程第三组项目。

面向仿真环境的机器人叠衣系统，覆盖失败检测、自主恢复、人工协助与任务结果回放。

## 当前进度

已完成选题、软件需求规格说明（SRS）、九张可编辑系统模型和五屏界面原型。
胡知鱼分工已有可操作测试桩原型、需求追踪、数据规范、用户走查材料和英文 Design 工作稿，具体证据与待办见 [Design 交付状态](docs/design/delivery-status.md)。
已收到并复核双臂运行时 I/O、可见仿真 RGB、完整正常折叠取景、投影检查、组件停止与初态重置诊断。马祥珲已完成组件记录、动作前492维输入、后续执行片段与停止证据的离线接入；系统模型源已整合。产品协调器完整集成、失败/恢复采集、模型训练与正式实验仍待完成；界面原型仍不连接机器人或云服务。

当前执行计划为 **[第一阶段：研究问题验证与系统设计](docs/first-stage-plan.md)**。
本阶段同时推进 2025—2026 年相关工作、research gap 诊断、仿真最小验证和课程 Design，按任务依赖与证据验收推进。
计划已依据 Assignment 2 正式 PDF 与 Canvas 页面更新；已形成马祥珲的研究/AI设计成果及可运行离线诊断工具，组件与正常流程已有实测，恢复研究实验、产品闭环与全组设计定稿仍待完成。

**仿真安排已确认：马祥珲已在张茗博电脑上复跑，基础复跑事项关闭。后续仿真、采集及恢复闭环实验统一在张茗博电脑运行，不要求组长电脑安装或换机重跑。** 详见[共享仿真执行安排](docs/research/shared-simulation-workflow.md)；真实接口、停止和恢复实验继续分别验收。

**第三组展示：2026-11-09 13:30–15:05场次（上海时间），每组6分钟，全员出席；Slides须在11月9日13:30之前上传Canvas。** 本组具体出场时刻未公布。当前优先整合三架构、关键决策及理由、重要交互、需求变化与开放问题，见 **[展示计划、三人分工与验收](docs/design/presentation-plan.md)**。

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
| [PR #11–#16审查与任务解锁](docs/reviews/pr11-16-readiness.md) | 控制/课程/动作前输入成果已合并，衣物扰动和中段重放草稿待交接修正；72项软件测试通过 |
| [不可比中段的分块先导方案](docs/research/blocked-trial-pilot-plan.md) | 区分实际试次与同根候选池，处理遗留效应和失败标签边界，不生成虚构研究结论 |
| [运行时动作／观测接入](docs/research/runtime-component-integration.md) | 实测 60 通道、历史／候选编码、停止复算及动作后 RGB 防泄漏；本批已运行 |
| [实测输入与分支有效性决定](docs/design/decisions/ADR-MA-005-measured-input-and-branch-validity.md) | 重置误差的实验影响、后备设计、记录细化与局部分母决定 |
| [马祥珲最终剩余清单](docs/research/ma-remaining-checklist.md) | 已完成项、真实环境/数据阻塞、队友最小交付与个人/课程事项 |
| [Assignment 2 要求与验收](docs/assignment-2-checklist.md) | 九项交付、三人分工、展示/反馈、词数与打包检查 |
| [第三组课堂展示执行计划](docs/design/presentation-plan.md) | 已确认场次、课前上传、三人素材与讲解分配、六页建议结构及验收 |
| [展示上传与反馈记录](docs/design/presentation-feedback.md) | 实际排练、Canvas回执、全员展示及反馈修订的待办/证据登记 |
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
| 张茗博 | 仿真集成、正常控制基线、状态机、失败注入与实验执行工具 |

第一阶段具体分工：马祥珲主责最近邻方法、创新假设和诊断算法；胡知鱼主责评价证据、数据质量及交互设计；张茗博主责仿真验证、控制架构和接口。三人共同评审研究结论、Design 与需求追踪，详细交付见第一阶段计划。

## 本地历史归档

旧提交、压缩包、中文版、审阅报告、生成工具链与渲染截图保存在课程目录的
`archive/2026-11-02-initial-organization/`，不上传 Git。
课程课件继续保留在课程目录。迁移及校验记录同样保存在本地归档内。

## 后续开发

按第一阶段计划并行推进科研核验与 Design 交付：课程设计可基于明确假设先完成，实验结果推动有记录的修订；再依据证据决定核心方法、扩大训练与正式比较。
第一阶段同时覆盖 Assignment 2 的九项设计交付并推进 G1/G2；科研诊断和最小集成是增强目标，完整训练及 180 次比较不属于本次 Design 硬性要求。技术未知项用备选、风险和 Part III PoC 说明；尚未选定的框架不预先写入依赖文件。
