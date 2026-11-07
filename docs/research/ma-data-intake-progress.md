# 马祥珲数据接入进展与下一步入口

更新：2026-11-07。PR #2的修复提交`f8bfaaa`已复审通过并合并，原P2路径问题关闭。本文记录本分工新增的真实样例审核、纯数值轨迹导出与历史窗口实现，不声称已复跑仿真或产生恢复实验结果。

状态续记（2026-11-08）：PR #3/#4/#5已批准合并，见[审查记录](../reviews/pr3-5-document-review.md)。作者已报告用本工具完成data_2的77帧导出/逐帧核对，也为data_3准备76帧及同次日志/最终图证据包。无需重复导出；当前缺实际收到完整包及运行入口，下面的命令可供复用，不再作为作者“尚未编写/运行导出器”的待办。本机仍未独立校验这些ZIP或完整轨迹。

## 1 已经实际完成

| 工作 | 结果与证据 |
| --- | --- |
| PR复审 | 新PowerShell回归实际通过：相对根目录、空格路径、显式相对覆盖、CheckOnly不启动，以及失败后的cwd/环境恢复；[批准记录](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/2#pullrequestreview-5813345542) |
| 真实入库样例审核 | 资产清单及最终图像的字节大小/hash与manifest一致；提交JSON有60个有限关节位置，声明血缘与轨迹hash一致；不等于从原始NPZ独立提取验证 |
| 证据文件 | [审核JSON](evidence/ma-handoff-audit-20261107.json)保存输入指纹、验证范围和剩余条件；首帧观测不与最终图像伪配对 |
| 全轨迹导出器 | [export_numeric_trajectory.py](../../tools/simulation/export_numeric_trajectory.py)已实现：从独立可信的原始对象NPZ导出各阶段关节、对应RGB数值及血缘，剔除未批准点云/affordance字段 |
| 导出后校验与历史窗口 | [legacy_observations.py](../../research_tools/legacy_observations.py)核记录/图像hash、类型、维数、帧顺序、阶段边界；构造不含当前/未来且不跨阶段的历史与mask |
| 软件验证 | 40项Python测试通过，另有PowerShell启动器回归通过；新增逻辑用人工轨迹验证，不冒充真实恢复评测 |

原始`data_2.npz`仍未共享到本机，也没有可访问的Isaac运行入口。现有JSON和最终图像足以完成结构/文件审核，不足以生成H1/H2数据集或训练完整恢复模型。

## 2 采集机可以直接执行的导出命令

无需重新设计导出器。张茗博可以在已有源码和数据的机器上，从最新仓库根目录执行：

```powershell
python -m tools.simulation.export_numeric_trajectory `
  --input 'E:\Robotics\DexGarmentLab\Data\Fold_Tops\train_data\data_2.npz' `
  --sha256 2309165bccd101c6ad65460716844d4f47d4b71e2f2f3dd775ecf37c47dac552 `
  --output-dir '<一个尚不存在的新输出目录>' `
  --trusted-object-source
```

`python`须为有NumPy的环境；此命令不导入Isaac、不需要启动机器人。`--trusted-object-source`表示操作者已经通过独立渠道确认来源可信，hash匹配本身不证明pickle安全；来源不明时不要执行。输入需包含三个阶段的一维字典数组，关节60个有限数、RGB为uint8 H×W×3；不符时拒绝，不自行猜格式。每文件默认限制256MiB压缩大小，适合当前约27MB样例，不用于未经审查的大型批量档案。

输出为`observations.jsonl`、对应的`rgb/*.npy`和最后写入的`manifest.json`。RGB文件是纯数值数组，后续用`allow_pickle=False`读取。输出目录必须新建，已有目录不覆盖；中途失败的目录保留排障，缺少完成manifest不得导入。该命令仍会读取受信任原始对象数组；后续接收方则无需再次反序列化对象。

导出器没有发明时间或动作：sim/wall时间、命令、ACK和成功标签保持null，关节顺序/单位及相机来源标记未验证；三个阶段起点分别设置history gap。导出的RGB与关节来自同一原记录，但不保证物理采样同步或实测延迟。

## 3 马祥珲接收后执行

先确认发送方导出完成、存储访问和文件hash，再运行：

```powershell
python -m research_tools.legacy_observations --input-dir '<导出目录>' --index 2 --history 4
python -m research_tools.handoff_audit
```

第一条校验manifest、记录与纯数值RGB，再构造过去帧窗口，左侧缺测补零/空引用并给mask；不跨阶段或轨迹，不含当前帧或未来帧。序号只表示记录顺序，不能换算真实时间。运行前仍应确认文件包来源，普通hash只检查所给包内部一致性。

第二条审核仓库当前的交接样例与清单。若别人改了JSON换行或文件内容造成hash不同，应核原文件/修订清单，不悄悄忽略差异。审核不能替代原始轨迹重提取、相机核验或SRS质量评估。

## 4 与现有恢复诊断的边界

这批输入是**正常历史示范观测**，不是“每候选一行”的恢复结果数据。禁止把每帧当成一个恢复候选、把状态差当实际命令、把最终图像当首帧，或用上游True填autonomous_success。当前导出格式刻意不同于diagnostics的schema，避免误用。

目前可做来源/形状检查、图像与关节的记录关联、阶段内历史构造，及后续冻结视觉编码的接入。还不能得到B3要求的已执行动作历史、真实1秒新鲜度、停止证明、局部恢复或最终成功标签，因而不能运行有效H1/H2比较。

## 5 真正剩余的最小交接

1. **现有正常轨迹访问**：提供原始可信NPZ或使用本导出器分享纯数值包。无需再重复交一份关节JSON或最终图。
2. **可运行环境入口**：同机安排、可用远程入口或可复现安装材料，支持第二人实际复跑；PR合并不等于已提供该入口。
3. **动作与新记录**：实际关节名/索引/类型/单位、命令与ACK、真实双时钟；历史NPZ缺失的内容需要新采集，不能事后补造。
4. **研究分支**：抓偏/滑移实际生效案例、起点可比性、合法候选执行和固定控制器接续结果；胡知鱼审核局部/最终/未知口径。

拿到1即可继续真实轨迹接入；拿到2可独立复跑；3和4到位才能形成完整恢复诊断。完整HALO重训、多任务论文复现与180次正式比较仍非本次Design提交前置。
