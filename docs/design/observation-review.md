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

**后续核验入口。** 作者记录 data_2 有 77 帧，三个阶段为 27、27、23，并在作者机逐帧校验；data_3 的 76 帧包另有交接说明。完整包接收方须比对哈希、来源、同记录 RGB、阶段分界及历史 mask。旧数据没有时钟、执行命令或真实失败分支，这些量须由后续采集提供。接收包与独立仿真复跑分别留证。[I/O 初查](../research/zhangmingbo/io-profile.md) · [作者导出记录](../research/zhangmingbo/data2-numeric-export-20261107.md) · [数据接入进展](../research/ma-data-intake-progress.md)
