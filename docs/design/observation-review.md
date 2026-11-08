# Fold Tops 单帧观测的字段与标签审核

**审核对象**为 main@0b0fd543 的 `stage_1` 第 0 条。按 Git 返回的 2,602 个原始字节重算 SHA-256 为 `aa147f90585c4233b903281a5367f1bc4b28ef5e68acf80507055aaf9f455985`，Git blob 为 `616e8c7126411bf08e924637aabda11a7bd54717`。解析关节数组得到 60 个有限数，最小 −3.3006420135498047，最大 2.500012159347534，与马祥珲入库审核一致。源 NPZ 哈希 `2309165bccd101c6ad65460716844d4f47d4b71e2f2f3dd775ecf37c47dac552` 属作者声明的血缘，本轮可核范围到入库 JSON。[原始样例](../research/zhangmingbo/observation-example.json) · [已有审核 JSON](../research/evidence/ma-handoff-audit-20261107.json)

| 原字段 | 本次可确认或上游声明 | 案例索引及使用限制 |
| --- | --- | --- |
| stage、index、timestamps | stage_1，记录序号 0；timestamps 为 not recorded | 证据定位写路径、阶段和索引；仿真秒、单调墙钟秒、t₀ 空缺并注明原因。 |
| joint_state | 数组存在，声明 float32；作者记录左 30、右 30。 | 保留未命名原始通道；关节名与索引映射、类型和逐通道单位待运行时 profile 核实。无速度或静止证明。 |
| image | 元数据声明 uint8，480×640×3，JSON 只含形状与类型。 | 同帧像素引用留空。最终图单列为另一份证据；不得填作首帧。 |
| env_point_cloud | 声明 float64，2048×6，后三列在源码补零。 | 来源初查为相机点云调用；坐标系、单位、同步及生成机制待核，禁止按 RGB 解释补零列。 |
| garment_point_cloud | 声明 float32，2048×3，使用仿真语义标注并临时隐藏双臂。 | 来源记仿真语义/离线专用，检查动作前采集和重用。 |
| points_affordance_feature | 声明 float32，2048×2，来自 GAM 与参考索引。 | 记录权重与点云来源依赖；暂禁在线输入或概率评分解释。 |
| action、action_note | action 为 null，无该帧派发命令及 ACK。 | 命令号、恢复尝试、动作历史与接触结论留空。组件冒烟测试另有独立运行，不能拼接到此帧。 |

**录入决定。** 来源记“作者机仿真示范的离线观测”，可作开发资料的结构与血缘索引，`online_authorized=false`。检测器没有运行输出，预测类填缺测并写原因；UNKNOWN 专指检测器实际弃判，AMBIGUOUS 用于有待评片段的真值歧义。该单帧缺少 DR02 持续窗、阶段持有真值和人工裁决，不能从“示范”推成 NORMAL。保持恢复候选/局部结果缺测，终态与自主成功缺测，离线质量为无法评估（缺目标、地标和稳定窗口）。不生成试次或动作行，不进入 AI01、局部动作或 AI03 分母。若后续以真实片段立案，再写案例号、父试次、分支族与审核版本。[评价口径](data-design.md)

**两包来源与现状（2026-11-08）。** main 的入库审核记录显示 data2 的 79 个文件、77 帧（27/27/23），data3 的 81 个文件、76 帧（27/27/22）均已完成 ZIP、逐文件和阶段内历史校验。团队已完成 153 帧固定 RGB、关节与阶段内历史编码，马祥珲已在张茗博电脑完成基础复跑，后续采集使用该机。该结论引用团队记录；本工作流的直接检查仍限前述入库单帧。[包核验记录](../research/evidence/ma-release-intake-audit-20261108.json) · [共享机运行安排](../research/shared-simulation-workflow.md) · [研究进展](../research/ma-remaining-checklist.md)

这 153 帧可用于正常观测接入和阶段内历史检查。缺少命名动作通道、可比时钟、实际派发及 ACK、停止测量和恢复分支，AI01 失败片段、局部恢复及 AI03 合格试次的正式分母均未从两包增加。

## PR #14 首袖五例的证据预审

源运行编号 `5cca8e1b-b938-4dab-b6fd-b7be7c0405e2`，固定上衣 TCLC_018。已逐文件核对 manifest 的 SHA-256；原始 JSON 为 610,459 字节。索引用 `trials[].condition` 定位；下列时间为各例 `continuous_samples` 第一条到末条的仿真秒，不能充当标注的故障起点。[原始测量](../research/zhangmingbo/garment-fault-20261108/fault-evidence.json) · [文件清单](../research/zhangmingbo/garment-fault-20261108/manifest.json)

| 案例索引 | 连续样本／仿真秒 | 可复核的阶段与结果 | 本例待补证据 |
| --- | --- | --- | --- |
| [normal](../research/zhangmingbo/garment-fault-20261108/normal-hold.png) | 125／2.033–8.233 | 闭手、提起、保持、转移后计划释放；对照提起约 306.4 mm。 | 核实真实接触和预期持有窗，计划释放需按阶段豁免。正常条件本身不能生成 NORMAL 真值。 |
| [grasp_offset](../research/zhangmingbo/garment-fault-20261108/grasp_offset-lifted.png) | 129／2.033–8.433 | 指令抓点横移 −130 mm，目标衣片仅升约 0.1 mm。 | 注入位移与闭合后的接触中心误差是两个量；需注册 W₀、测得接触中心并复核 0.2 秒持续窗。 |
| [unexpected_release](../research/zhangmingbo/garment-fault-20261108/unexpected_release-hold.png) | 131／2.033–8.533 | 有效提起迹象后在 5.083 秒注入开手，持有窗首末漂移约 39.8 mm；五张阶段图相同，像素全黑。 | 用原始运动序列及补充视觉/接触证据核实先前夹持与失持起点；开手命令不能直接定为 SLIP。 |
| [offset_regrasp](../research/zhangmingbo/garment-fault-20261108/offset_regrasp-hold.png) | 79／2.033–5.933 | 已闭手、提起、保持；退让 IK 失败，脚本以 aborted 结束，后续重抓未执行。 | 保留中断与失败原因，区分脚本尝试及产品接受派发；未执行的候选无成功或失败标签。 |
| [release_regrasp](../research/zhangmingbo/garment-fault-20261108/release_regrasp-regrasp_lifted.png) | 216／2.033–12.783 | 提前开手后尝试重抓，重抓提起约 299.6 mm；随后转移、计划释放。 | 补重抓实际接触、DR05 持续清除与下一阶段可行证据，固定全任务接续后另审最终质量。 |

**共同裁决。** 原始 W₀ 与接触传感字段均为 null。衣片网格质心及指尖几何中点可供离线预审，正式主类须由张茗博补注册 W₀、阶段持有及接触/持续窗证据，再由胡知鱼独立复核。五例仅覆盖第一袖，起点网格也有差异。原始 dr02_label 和 terminal_task_result 五例均为 null；本轮局部恢复、整任务质量、自主成功均留空。脚本 completed 仅表示该脚本路径走完。这五例本轮对 AI01、局部恢复率和 AI03 正式分母的新增数均为 0。
