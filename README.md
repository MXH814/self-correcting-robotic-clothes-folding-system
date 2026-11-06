# Self Correcting Robotic Clothes Folding System

同济大学《系统分析与设计》课程第三组项目。

面向仿真环境的机器人叠衣系统，覆盖失败检测、自主恢复、人工协助与任务结果回放。

## 当前进度

已完成选题、软件需求规格说明（SRS）、九张可编辑系统模型和五屏界面原型。
已补充可操作的五屏测试桩原型、需求变更与追踪、记录与评价规范、用户走查材料及英文 Design 工作稿。
真实用户走查、团队设计复核和系统测试待完成，逐项证据及缺项见 [Design 交付状态](docs/design/delivery-status.md)。
仿真集成、机器人控制、模型训练与正式实验尚待实施。界面原型不连接机器人或云服务。

当前执行计划为 **[第一阶段：研究问题验证与系统设计](docs/first-stage-plan.md)**。
本阶段同时推进 2025—2026 年相关工作、research gap 诊断、仿真最小验证和课程 Design，按任务依赖与证据验收推进。
计划已依据 Assignment 2 正式 PDF 与 Canvas 页面更新；Design 已有部分工作稿，研究与最终设计验收继续推进。

**Assignment 2 截止：2026-11-20 19:00（上海时间）。** 全员参加 6 分钟课堂展示，Slides 须在本组展示前上传 Canvas，具体场次待 Canvas 通知。详见 **[九项正式交付与验收清单](docs/assignment-2-checklist.md)**；最终设计须纳入展示反馈。

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
| [Assignment 2 要求与验收](docs/assignment-2-checklist.md) | 九项交付、三人分工、展示/反馈、词数与打包检查 |
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
