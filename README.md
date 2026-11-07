# Self Correcting Robotic Clothes Folding System

同济大学《系统分析与设计》课程第三组项目。

面向仿真环境的机器人叠衣系统，覆盖失败检测、自主恢复、人工协助与任务结果回放。

## 当前进度

已完成选题、软件需求规格说明（SRS）、九张可编辑系统模型和五屏界面原型。
仿真集成、机器人控制、模型训练与正式实验尚待实施。界面原型不连接机器人或云服务。

当前执行计划为 **[第一阶段：研究问题验证与系统设计](docs/first-stage-plan.md)**。
本阶段同时推进 2025—2026 年相关工作、research gap 诊断、仿真最小验证和课程 Design，按任务依赖与证据验收推进。
计划已依据 Assignment 2 正式 PDF 与 Canvas 页面更新；已形成马祥珲的研究/AI设计成果及可运行离线诊断工具，真实仿真与研究实验、全组设计整合仍待完成。

**第三组展示：2026-11-09 13:30–15:05场次（上海时间），每组6分钟，全员出席；Slides须在11月9日13:30之前上传Canvas。** 本组具体出场时刻未公布。当前优先整合三架构、关键决策及理由、重要交互、需求变化与开放问题，见 **[展示计划、三人分工与验收](docs/design/presentation-plan.md)**。

**Assignment 2最终截止仍为2026-11-20 19:00。** 展示后纳入实际课堂反馈，完成 **[九项正式交付与验收清单](docs/assignment-2-checklist.md)**；完整训练和研究诊断不是本次展示的前置条件。

## 文件导航

| 路径 | 内容 |
| --- | --- |
| [最终 SRS 提交目录](submissions/assignment-1/Group3_Assignment1_SRS/) | 英文 PDF 与九页可编辑 Draw.io 模型，保留课程提交命名 |
| [英文 Word 源文件](docs/requirements/SRS_EN.docx) | 继续编辑需求文档的有效源文件 |
| [选题说明](docs/idea/Idea_Submission_EN.pdf) | Idea Submission，记录选题背景；范围以最新 SRS 为准 |
| [界面原型](prototypes/ui/index.html) | 用浏览器打开即可查看五个界面 |
| [协作约定](CONTRIBUTING.md) | 分工、分支和证据记录要求 |
| [第一阶段详细计划](docs/first-stage-plan.md) | 近期论文、候选问题、三人任务、Design 交付、依赖与完成标准 |
| [马祥珲第一阶段成果](docs/research/ma-task-workbook.md) | 四篇精读、比较、问题卡、实验协议、AI详细设计及课程材料；待本人/团队评审，实验未执行 |
| [研究工具运行说明](docs/research/execution-guide.md) | 数据校验/分组、B0–B4离线基线、统计、评分诊断、门禁子集和资源估算；无仿真依赖 |
| [张茗博环境与文献成果](docs/research/zhangmingbo/README.md) | 已审查合并的三篇笔记、Isaac Sim 4.5 / DexGarmentLab可行性和历史复现记录 |
| [张茗博交接与后续待办](docs/research/zhangmingbo/handoff-tasks.md) | 最小交接包H01–H05、后续仿真/控制任务、课程Design职责、提交位置与验收标准 |
| [马祥珲数据接入进展](docs/research/ma-data-intake-progress.md) | PR #2已复审合并；真实样例审核、完整轨迹纯数值导出、历史窗口与剩余输入 |
| [仿真接入与审查结论](docs/research/dex-integration-plan.md) | 平台已选定，NPZ安全审计、在线来源隔离、评价差异与后续交接；独立复跑未完成 |
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
