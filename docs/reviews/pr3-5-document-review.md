# PR 3至5文档审查记录

日期：2026-11-08。三个PR均已批准并合并，未发现阻碍文档入库的问题；作者原提交保留。没有执行新仿真、训练或读取未交付的原始轨迹/ZIP。

| PR | 核对提交 | 审查与结论 |
| --- | --- | --- |
| [3 正常基线](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/3) | `2184a01` | 正常示范与HALO/SRS验收分开，data_3为27/27/22共76帧，约288秒包含启动加载，脱敏日志与原日志hash分开；[批准意见](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/3#pullrequestreview-5813693157) |
| [4 数值导出记录](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/4) | `54a2c10` | 声明来源与已入库清单一致，27/27/23共77帧，77数组＋记录/manifest为79文件；未知时间、动作、ACK、标签保持未知，团队访问未关闭；[批准意见](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/4#pullrequestreview-5813693180) |
| [5 中文论文汇报](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/5) | `5f6637f` | 全文对照已有L01/L02/L06原文复核记录，检查方法、任务/输入边界、表格值、百分点/距离差值，三个Mermaid源的职责方向无明显冲突；[批准意见](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/5#pullrequestreview-5813693174) |

本地相对链接、代码围栏及数值计算检查通过。三个PR只增加Markdown，不重复运行与改动无关的算法测试。Mermaid本轮仅作源/语义检查，未重新图形渲染。

## 非阻塞补充与验收边界

- data_3包报告81文件，正文可明确推得76数组＋记录/manifest＋最终图＋脱敏日志为80项；另外一项未列明。已在PR #3意见中要求随交付附完整目录清单，未据此判定文件包错误。本机未取得包，无法核CRC、包内数量或SHA256。
- data_2和data_3的文件/哈希与帧数分别保存；同次运行、同记录及真实时间同步不是同一含义，不能混配或填造动作/时间/成功标签。
- 作者机导出已被报告，不再要求重新导出或重复写说明。实际接收仍未完成，可直接向组长交付文件或同机访问，不必先建设专用存储平台。
- D01/D07、实际环境独立复跑、停止/重置和恢复数据验收仍待完成；入库历史运行记录不等于这些项目通过。
- 15–20分钟论文组会稿不替代全员6分钟课程Design展示，也不替代三架构/设计模型、200–300词英文注释和个人反思/贡献。

PR #3中的[完整后续任务回复](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/3#issuecomment-6709661983)继续有效；已报告的作者工作与接收方独立验证分别记账。
