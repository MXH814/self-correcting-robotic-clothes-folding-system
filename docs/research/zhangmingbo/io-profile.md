# Fold Tops 真实样本 I/O 初查

**新采集进展（2026-11-08，待完成）：** 已准备[运行时组件采集脚本及说明](runtime-io-probe.md)，用于读取实时 DOF 和命令前后观测。本机试跑时系统可用虚拟内存降至约 0.75 GiB，主动停止采集进程，未生成样本；这不是程序报错或成功的证据。脚本尚未完成仿真运行验证，当前仍未提供完整新样本、协调器 ACK 或停止反馈。旧数据不补造上述字段。

来源：2026-11-04 作者机器图形示范 `data_2.npz`；[数值样例](observation-example.json)为 stage_1 第 0 个记录，均为读取可信本机文件后导出。此为离线样本，不是在线适配器协议或动作安全保证。上游源码 ZIP 和文件 hash 见[清单](artifact-manifest.json)。

| 字段 | 该帧形状和类型 | 生成过程与限制 |
|---|---|---|
| `joint_state` | 60，float32 | 上游 `Fold_Tops_Env.py` 的 `get_joint_positions()` 左手臂+手 30 值后接右手臂+手 30 值；具体 articulation 索引与关节名一一对应尚未记录。不能把另一份 `hand_dof_names` 列表当成运行时索引顺序。关节位置 API 通常以 rad 表示旋转关节，逐关节类型/单位仍需在运行时核验。 |
| `image` | 480×640×3，uint8 | 环境相机 RGB；样例 JSON 不含图像负载。最终图像单独提供，不能认为是此观测帧。相机外参/同步与延迟尚未实测。 |
| `env_point_cloud` | 2048×6，float64 | 源码调用相机 `get_pointcloud_from_depth()`；其内部调用 `camera.get_pointcloud()`，去掉 z≤0.005 点并采样；后 3 列由源码补零，不是 RGB。虽然相机启用了深度，点云内部生成机制、坐标系、单位和标定仍待独立核实，暂不据名称断言可部署为真实深度输入。 |
| `garment_point_cloud` | 2048×3，float32 | 通过衣物专用相机的 Replicator 语义分割 pointcloud annotator 获取，临时隐藏双臂后采样；该衣物点云在动作前取得并赋给记录，不能称每帧实时深度观测。此处使用仿真语义标签，在线可部署性待核。 |
| `points_affordance_feature` | 2048×2，float32 | GAM 对衣物点云与参考索引推理、分阶段选择并归一化的 similarity 特征；依赖权重和点源，不应默认为纯 RGB 特征。 |

源文件顶层 `usd_path`、`pos`、`ori` 和 `stage_1`–`stage_3`；三阶段分别 27、27、23 帧，object 数组含字典。各阶段记录从源码回调的每 5 个物理 callback 取一次；**没有保存 sim time、wall time、帧间真实耗时或跨阶段连续性**，相机设置的 nominal frequency=20 Hz 不等于实测录制频率。

## 一次已执行的组件动作及反馈

作者此前的 `smoke_test.py` 调用 `set_both_hand_state("open", "open")`，随后 `set_both_hand_state("close", "close")` 并推进 60 步；记录的左右关节最大位置变化分别为 1.2788401842 和 1.2788426876。之后各对一个手臂关节下发 `ArticulationAction(joint_positions=...)`：在刚才测得的位置基础上左侧加 0.03、右侧减 0.03；再推进 60 步，测得左右绝对变化均约 0.02996075。它们是组件测试中已执行命令与测量反馈，不是 `data_2.npz` 中可关联的命令。脚本使用绝对关节位置目标，示例中 0.03 为相对当前关节读数构造的目标偏移；旋转关节 rad 仍需逐 DOF 验证。动作前后的完整数值、时间戳和命令 ACK 未保存。

Fold 示例另调用 `dense_step_action` 和双臂 IK、手部状态，输入包括目标位置与四元数；其精确参考系、单位、执行频率和每次实际派发结果尚需通过源码和运行时 profile 验证。NPZ 不记录 action、控制命令 ID、接受/拒绝、速度、停止请求/静止反馈、独占控制、暂停或完整布料接触快照；不将相邻观察差值冒充指令或执行成功。采集工具将这些空缺交由后续 D02/D04/D05 验证。
