# TCLC_018 衣物观测、故障候选和恢复接续

需要仓库访问权限才能下载 [原始数据 ZIP](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/releases/tag/zhang-garment-observation-20261108)。[外层 ZIP 的字节数与 SHA256](trace-packages.json) 对应 Release 资产。各 ZIP 内的 `manifest.json` 提供来源、启动入口以及每个成员的字节数和 SHA256。

## 四组第一袖试次

| 试次 | RGB 帧 | 关节派发及反馈 | 实测范围 |
| --- | ---: | ---: | --- |
| `normal` | 159 | 157 | 正常抓持、移送与预定释放。同一试次的预定释放可单独切窗作为合法释放对照。 |
| `contact_offset_candidate` | 155 | 151 | 抓取目标相对预期点偏移 46 mm X、25 mm Y，预期区域仍随手抬升约 279 mm。真实接触中心未知，DR02 标签待审。 |
| `closed_hand_slip_candidate` | 167 | 140 | 闭手期间将布料摩擦设为零并执行偏移运动，恢复原摩擦后的 0.35 仿真秒内，意图区域相对指尖中点的漂移为 20.5–20.7 mm。没有求解器接触读数，DR02 标签待审。 |
| `release_regrasp` | 277 | 239 | 提前开手后实际重抓并抬升，预期区域在重抓抬升窗口平均比初态高 286 mm。第一袖接续有记录，另见完整折叠试次。 |

第一袖预期区域定义为初始化时离脚本袖口抓取点最近的 12 个布料网格顶点。抓持预期从 `expected_hold_begins` 持续到第一袖移送结束，`planned_release` 是合法打开。条件字段记录注入方式，`dr02_label` 保持未知。意图区域几何和指尖中点是离线证据。接触位置、持续接触与遮挡判定由胡知鱼复核。

[`W₀` 标定记录](w0-registration.json) 给出 TCLC_018 的暂定参考宽度 474.979 mm，沿平铺衣身近下摆的固定横截面测量。原始顶点来自 `normal.zip`。抓偏门槛为 23.749 mm，闭手相对漂移门槛为 18.999 mm。漂移用 `lifted` 窗口相对向量中位数为零点，`hold` 窗口有 8 个 20 Hz 物理样本，跨度为 0.35 仿真秒。团队需复核参考截面和是否有足够的接触证据。

## 给数据接入方

1. 用 `observation-trace.json` 的 `trial_id`、`observation_id` 与 `command_id` 关联。按 `frame_index` 读 `rgb-frames.npz` 的 `rgb` 数组，形状是 `[N,180,240,3]`，无损 uint8。连续帧最大间隔为约 0.05 仿真秒。
2. `boundaries` 标记高层阶段，包括实际重抓前的 `experimental_regrasp_release`。关节按两臂各自的运行时名称及索引读取，位置为 rad、速度为 rad/s、力矩为 N·m。动作记录的 `targets` 来自实际 Isaac articulation 调用，位置值为绝对目标。SDK 返回时间与随后观测中的关节状态可以逐条核对。多条同仿真步命令可能共享一条反馈观测。
3. `rendering_time_s` 与 `sim_time_s` 属于 Isaac 仿真域。各读取与派发的 `wall_monotonic_ns` 属于 Python 本地单调时钟。两种时钟不可直接相减。同一渲染帧可在多个阶段边界被读取，每次仍有独立关节观测 ID。试次为脚本控制，产品层控制代次、产品 ACK 和可归因于单条命令的物理接触反馈未采集。
4. 离线物理采样和阶段图在 `fault-evidence.json` 中索引。模型视觉历史应只取决策边界之前的观测和已发生的动作，之后的帧及物理证据用于评估。

```powershell
python tools/simulation/verify_garment_observation_trace.py <extracted-trial-directory>
powershell -ExecutionPolicy Bypass -File tools/simulation/run_local.ps1 -Stage garment-fault -Headless -GarmentTraceCase closed_hand_slip_candidate -OutputRoot <output-directory>
powershell -ExecutionPolicy Bypass -File tools/simulation/run_local.ps1 -Stage fold-recovery -Headless -FoldRecoveryCondition early-open -RegraspLateralOffsetM 0 -OutputRoot <output-directory>
```

复跑使用已有 [本机环境与资产入口](../second-machine-install.md)。批量采集时循环传入 `-GarmentTraceCase`、`-FoldRecoveryCondition` 或 `-RegraspLateralOffsetM`，每次生成独立目录和试次 ID。重抓入口限制横向偏置在 ±20 mm 内。各次独立初始化，配对根状态仍需单独证明。
