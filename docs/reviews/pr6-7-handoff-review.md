# PR 6与7：架构素材和真实数据交接审查

日期：2026-11-08。已审查并合并[PR #6](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/6)与[PR #7](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/7)。批准范围是这两批架构草稿和交接材料，不代表此前五项任务全部完成。

## 已执行的检查

- PR #6提交`389fbdb`：全文对照恢复接口、控制权/停止约束和6分钟展示计划；逻辑图、部署图、技术选型表、核心交互、风险及135秒讲解候选素材已提供。相对链接及3个Mermaid源围栏通过；本轮未渲染图形或整合最终Slides。简图不能替代正常/恢复派发的完整持久化及授权门禁。[批准记录](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/6#pullrequestreview-5816752284)。
- PR #7提交`fb17c75`：通过成员认证实际下载私有Release的两个ZIP和两份清单，核对大小、SHA-256、CRC、逐文件集合/大小/hash，检查无重复或越界路径后解压。没有执行包内程序或读取原始对象NPZ。
- 使用现有`research_tools.legacy_observations.load_export`读取全部153帧：RGB为纯数值数组，记录与图像hash、60维有限关节值和阶段计数通过。逐帧检查历史排除当前帧、不跨阶段、阶段首帧缺测掩码；未记录的时间、实际动作、ACK和标签保持未知。[机器可读审核证据](../research/evidence/ma-release-intake-audit-20261108.json)。
- data3最终图和脱敏日志hash与既有记录一致，日志含data_3/img_3输出及上游`final result: True`。这些不构成第二人仿真复跑或SRS质量通过。[PR #7批准记录](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/7#pullrequestreview-5816752325)。

| 数据包 | 实际文件数 | 实际帧数 | 阶段帧数 | 结论 |
| --- | --- | --- | --- | --- |
| data2纯数值包 | 79 | 77 | 27/27/23 | 下载、清单、ZIP及全部数值记录通过 |
| data3证据包 | 81 | 76 | 27/27/22 | 同上；第81项实际为`READ_ME_交接.txt`，80/81疑问关闭 |

## 原五项交接要求的状态

| 要求 | 当前状态 | 对马祥珲工作的影响 |
| --- | --- | --- |
| 1 核实80/81 | 已独立核实并关闭 | 无需再要求解释或重打包 |
| 2 交付完整正常轨迹 | 已实际接收、校验并读取 | 可推进真实RGB/关节观测接入、阶段内历史及离线编码；不是恢复候选数据 |
| 3 可执行环境 | 部分完成：有换机准备方案，精确源码归档/依赖获取及独立安装未闭环 | 仿真独立复跑、采集和闭环实验仍受阻 |
| 4 真实输入输出 | 尚未补齐运行时DOF映射/单位、双时钟、实际命令/ACK和停止测量 | 观测不能自动转成可执行动作或在线时效/停止保证 |
| 5 失败/恢复候选案例 | 尚未交付抓偏/滑移、可比重置、合法候选及固定接续结果 | 有效H1/H2与恢复训练/校准仍受阻 |

剩余优先级：先提供可实际取得的固定源码/依赖/资产及运行条件，再推进真实profile和失败/候选采集。允许采用明确记录差异的新冻结版本，不为找回旧ZIP无限等待；不能把未试安装写成已运行。接收方实际安装和复跑由执行者记录，作者提供条件并配合。胡知鱼审核评价口径和真实案例标签，之后独立复核关键结果。

后续清单已直接写在[PR #7普通评论区](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/7#issuecomment-6717710906)。原PR #3回复作为历史任务来源保留，已解决项以本次审查和[最新接入进展](../research/ma-data-intake-progress.md)为准，不重复索要已接收数据。架构素材可进入课堂Slides整合，最终图形可读性、全员计时排练和Canvas上传分别验收。
