# TCLC_018 衣物观测、故障候选和恢复接续

抓偏、部分滑移和对照的后续指尖近景与标签提案见 [DR02 补采](../garment-dr02-20261108/README.md)。后续参考宽度按数据设计采用肩部与下摆的平均值。

需要仓库访问权限才能下载 [原始数据 ZIP](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/releases/tag/zhang-garment-observation-20261108)。[外层 ZIP 的字节数与 SHA256](trace-packages.json) 对应 Release 资产。各 ZIP 内的 `manifest.json` 提供来源、启动入口以及每个成员的字节数和 SHA256。

## 五组第一袖试次

| 试次 | RGB 帧 | 关节派发及反馈 | 实测范围 |
| --- | ---: | ---: | --- |
| `normal` | 159 | 157 | 正常抓持、移送与预定释放。同一试次的预定释放可单独切窗作为合法释放对照。 |
| `contact_offset_candidate` | 155 | 151 | 抓取目标相对预期点偏移 46 mm X、25 mm Y，预期区域仍随手抬升约 279 mm。闭合后 0.35 仿真秒内，衣片相对指尖中点的向量与正常对照相差 45.6–49.0 mm。真实接触中心未知，DR02 标签待审。 |
| `closed_hand_slip_candidate` | 167 | 140 | 闭手期间将布料摩擦设为零并执行偏移运动，恢复原摩擦后的 0.35 仿真秒内，意图区域相对指尖中点的漂移为 20.5–20.7 mm。没有求解器接触读数，DR02 标签待审。 |
| `release_regrasp` | 277 | 239 | 提前开手后实际重抓并抬升，预期区域在重抓抬升窗口平均比初态高 286 mm。第一袖接续有记录，另见完整折叠试次。 |
| `closed_hand_slip_regrasp` | 293 | 259 | 闭手扰动后，同一试次连续覆盖 23.32–23.50 mm 持续漂移、恢复前观测、实际重抓、抬升和第一袖接续。重抓后预期区域相对初态抬高约 351 mm，原漂移代理量在重抓后仍为 115.18–117.34 mm。保留局部偏差未消除的结果，真实接触标签待审。 |

第一袖预期区域定义为初始化时离脚本袖口抓取点最近的 12 个布料网格顶点。抓持预期从 `expected_hold_begins` 持续到第一袖移送结束，`planned_release` 是合法打开。条件字段记录注入方式，`dr02_label` 保持未知。意图区域几何和指尖中点是离线证据。接触位置、持续接触与遮挡判定由胡知鱼复核。

[`W₀` 标定记录](w0-registration.json) 给出 TCLC_018 的暂定参考宽度 474.979 mm，沿平铺衣身近下摆的固定横截面测量。原始顶点来自 `normal.zip`。抓偏门槛为 23.749 mm，闭手相对漂移门槛为 18.999 mm。漂移用 `lifted` 窗口相对向量中位数为零点，`hold` 窗口有 8 个 20 Hz 物理样本，跨度为 0.35 仿真秒。团队需复核参考截面和是否有足够的接触证据。

## 给数据接入方

1. 用 `observation-trace.json` 的 `trial_id`、`observation_id` 与 `command_id` 关联。按 `frame_index` 读 `rgb-frames.npz` 的 `rgb` 数组，形状是 `[N,180,240,3]`，无损 uint8。连续帧最大间隔为约 0.05 仿真秒。
2. `boundaries` 标记高层阶段，包括实际重抓前的 `experimental_regrasp_release`。关节按两臂各自的运行时名称及索引读取，位置为 rad、速度为 rad/s、力矩为 N·m。动作记录的 `targets` 来自实际 Isaac articulation 调用，位置值为绝对目标。SDK 返回时间与随后观测中的关节状态可以逐条核对。多条同仿真步命令可能共享一条反馈观测。
3. `rendering_time_s` 与 `sim_time_s` 属于 Isaac 仿真域。各读取与派发的 `wall_monotonic_ns` 属于 Python 本地单调时钟。两种时钟不可直接相减。同一渲染帧可在多个阶段边界被读取，每次仍有独立关节观测 ID。试次为脚本控制，产品层控制代次、产品 ACK 和可归因于单条命令的物理接触反馈未采集。
4. 离线物理采样和阶段图在 `fault-evidence.json` 中索引。模型视觉历史应只取决策边界之前的观测和已发生的动作，之后的帧及物理证据用于评估。

## 两条完整折叠接续

| 注入条件 | 实际恢复与接续 | 官方最终质量 | 全程墙钟 |
| --- | --- | --- | ---: |
| [提前开手](full-fold-early-open.json) | 规则重抓后，预期区域高度从 41.3 mm 到 285.1 mm。随后接回官方第一袖移送、第二袖、下摆及评分。 | 1984 / 2048（96.875%），通过 | 201.8 s |
| [闭手扰动](full-fold-closed-hand-slip.json) | 8 个 20 Hz 样本的最小漂移代理值为 27.38 mm。诊断门禁通过后实际执行释放、规则重抓、抬升。接续移送后预期区域仍被抬离台面。恢复后持续接触及漂移消除情况未知。 | 1824 / 2048（89.0625%），通过 | 213.1 s |

官方终点阈值是 88% 点位落在目标区。完整试次的 ZIP 内有阶段截图、点云与控制器文件指纹，可以离线重算评分。完整试次保留恢复前后的阶段图，连续 RGB 与逐条派发见上面的第一袖试次。实际候选仅经过诊断门禁，产品层的许可、求助和预算判定未接入。试次期间没有脚本外人工操纵记录。这两次独立运行的初态及 GAM 输出均可变化，分数不能用来估计恢复的因果收益。

```powershell
python tools/simulation/verify_garment_observation_trace.py <extracted-trial-directory>
powershell -ExecutionPolicy Bypass -File tools/simulation/run_local.ps1 -Stage garment-fault -Headless -GarmentTraceCase closed_hand_slip_candidate -OutputRoot <output-directory>
powershell -ExecutionPolicy Bypass -File tools/simulation/run_local.ps1 -Stage garment-fault -Headless -GarmentTraceCase closed_hand_slip_regrasp -OutputRoot <output-directory>
powershell -ExecutionPolicy Bypass -File tools/simulation/run_local.ps1 -Stage fold-recovery -Headless -FoldRecoveryCondition early-open -RegraspLateralOffsetM 0 -OutputRoot <output-directory>
powershell -ExecutionPolicy Bypass -File tools/simulation/run_local.ps1 -Stage fold-recovery -Headless -FoldRecoveryCondition closed-hand-slip -RegraspLateralOffsetM 0 -OutputRoot <output-directory>
```

复跑使用已有 [本机环境与资产入口](../second-machine-install.md)。批量采集时循环传入 `-GarmentTraceCase`、`-FoldRecoveryCondition` 或 `-RegraspLateralOffsetM`，每次生成独立目录和试次 ID。重抓入口限制横向偏置在 ±20 mm 内。正常、抓偏候选和闭手扰动三个第一袖包的初始沉降顶点数组完全一致。旧包单试次 `root_mesh_*` 的零值来自该试次自比。失败中段的布料速度、接触与随机状态仍需单独验证。
