# A/B 第二轮改进方案

用户要求先将 A/B 的运行结果改进至预期，随后再更新 Z3 和提交 PR。验收以新试次的实际最终状态为准。

## 新试次验收条件

- A 从抓取、提起、移送、计划释放运行至完整折叠结束，恢复次数 0，非预期告警数 0。
- B 经观测告警进入执行前检查，完成 release、retreat、regrasp、close、lift，取得宏后的持续持有证据，接续并完成后续全部折叠阶段。
- 两场景记录最终点云区域代理及控制终态，独立审核继续保留实际签核状态。

## 诊断和改动

第一轮将左右袖持有合并为 HOLD。三条正常试次的左袖窗口最大分数约 1.11–1.18，右袖约 1.20–1.31，统一阈值 1.20660808 在右袖触发告警。

第二轮沿用原 RND 视觉编码与预测器结构，按过去正常控制命令的 arm 意图映射 LEFT_SLEEVE_HOLD、RIGHT_SLEEVE_HOLD。每个阶段分别计算独立校准试次的五帧窗口最大值，再取经验 0.95 高分位数。校准与在线推理均采用 batch 1。阶段转换清空窗口。

相机、控制器、采集源码和阶段映射版本共同形成新的上下文引用。新旧包通过元数据和上下文区分，原始第一轮实验记录继续保留。

拆分阶段后的左袖原始校准阈值为 1.18465152，右袖为 1.31139717。开发复查发现左袖阈值收紧会重新触发旧 A 的正常窗口，因此最终版本以第一轮独立正常校准阈值 1.20660808 作为下限。最终左袖阈值为 1.20660808，右袖为 1.31139717。生成时逐参数核对两个包的学习网络相同，阈值下限来源与包哈希保存在 `normal-floor-result.json`。

首次分阶段包的新 A/B 均完整折叠结束。保留下限版本的首轮配套复验保存在 `AB_final_same_package/`，其中 A 通过，B 宏后持有检查通过后再次越线求助，该失败记录继续保留。

随后增加恢复接续检查。一次宏后的 0.2 秒连续持有窗口通过后，在新控制代次建立新的 0.2 秒基线，再对左袖固定接续的每个新 RGB 观测同步读取新几何。几何必须保持 HELD，RGB 必须有效，暖窗单列。几何未知、失持或 RGB 缺失立即求助。计划释放结束该检查，后续右袖仍按原始 RND 判定。

这是本轮为完成仿真演示作出的协调器决策。接续期间 RND 越线时仍保存 ANOMALY 和实际分数，是否继续由连续几何证据决定。该策略使用仿真内部信息，实验结果需要结合此方法解释。

## 数据用途

- original-normal-01 为拟合试次，保持 10 epochs、seed 17、学习率 0.0001、batch 64。
- original-normal-02、original-normal-03 及两条新增完整正常试次用于校准。
- original-normal-03 曾用于第一轮开发检查，第二轮已明确改为校准用途。
- 第一轮 A-04、B-01 已用于诊断模型阶段设计。
- 第二轮 A/B 使用模型包冻结后的新运行，参数和校准方案在这些新结果产生前记录于 `AB_v2_calibration_plan.json`。

开发时的正常性依据为原始记录、数据核验和代理技术图像审核。后续胡已完成两条新增正常记录的独立技术判读，通过 PR32 验收。经验校准的统计保证字段保留为空。

## 运行记录

2026-11-09 最终新试次均使用包 `b9df07d40a29968947949a7a202e89b31d1fb37771fb4c2ff5094fc73ff3eb1b`，上下文为 `pre-observation-context/1#sha256=1d1647b37737a31c865659e5fab23eaa2ecde0739f950d07bd4b33c737f26a75`。阈值与权重在本轮新运行前冻结。

| 项目 | A 正常控制 | B 提前开手 |
| --- | --- | --- |
| 试次 | `db18b274-f2e2-4cf2-9962-856a8364aad7` | `b5e90454-5cda-4cc0-8ec2-5606971bdf38` |
| 完整结束 | 26.40 仿真秒 | 30.85 仿真秒 |
| RGB／唯一检测报告 | 466／465 | 554／492 |
| 新恢复请求 | 0 | 1 |
| 恢复执行 | 0 次 | 1 次，五操作 61 条实际派发 |
| 宏后持有复检 | 无恢复 | 13 个新样本，9.933334–10.133334 秒 |
| 新代次接续持有检查 | 无恢复 | 新基线后 23 次，逐项复算通过 |
| 告警 | 0 | 首个告警 7.033334 秒，等待前检期间另 4 个原始越线报告，接续阶段越线报告 0 |
| 求助 | 0 | 0 |
| 最终区域代理 | 2048／2048 | 2002／2048，超过上游 0.88 门槛 |
| 自动开发核验 | 通过 | 通过 |

B 注入记录为 5.983334 秒，首报分数 1.23103256。告警仍只读 RGB 编码、允许阶段和过去窗口。材料点与注入事件不进入 RND。宏前真实静止测量、空队列、当前运行权限和名义路径 IK／关节限位检查均留有独立证据引用。最终点云区域计数已重新计算。

检测适用阶段为左右袖提起／移送。计划释放和其他阶段的 UNKNOWN、窗口预热均保留原始原因。A 的 UNKNOWN 413 个，B 的 UNKNOWN 417 个，可判报告分别为 52 和 75 个。

本机完整证据根目录为 `C:/Users/Lenovo/Desktop/系统分析与设计/output/Pre_Z交付_20261109/`。

- A 为 `official-A-v3-final/fold-recovery-28d2fed5-5c0e-42e8-8ddc-6e74783417d3/`。
- B 为 `official-B-v3-continuation/fold-recovery-312d4b8a-d0b7-43bb-8ff1-936c7a7672aa/`。
- 核验报告为 `official-A-v3-final-audit.json` 与 `official-B-v3-continuation-audit.json`。
- 新增正常采集为 `normal-calibration-v2/`，模型为 `AB_detector_v2/package-preserved-floor/`。

PR 内保留[便携证据目录](pre-abc-evidence-20261109/)，完整 A/B RGB 大数组、学习权重和两条新增正常记录已按原始指纹共享到团队仓库。[下载与读取](shared-pre-artifacts-20261109/README.md)。每条试次均带原始源码快照，便于区分实跑版本与后续文档／视频生成变动。

胡的 #27 完整模型、阈值与源绑定修复已合入本分支。其封存包阈值为 1.1895795584，仍保留正常开发复验的误报片段。本页的分阶段包是本地后续开发版本，数据用途与方法变化已在上文记录。原三条正常记录已有胡的接收审核。后续 PR31 完成新包全部 A/B 记录调用的独立分数复算，PR32 完成两条新增正常记录和 B 原始图像的独立技术判读。[数值审核](../../reviews/pr30-31-review.md) · [案例判读](../../design/hu-abc-case-review.md)

## 结果边界

本轮达到两个场景的自动开发验收条件。最终区域代理只评价指定区域内点数比例，连续持有使用声明的仿真几何启发式。独立主观折叠质量、SRS 全面质量和物理停车验收仍待完成。

## 软件回归

相关 84 项检查通过。合入主分支 #26/#27 后全量运行 201 项，其中 200 项通过，`test_total_three_observations_ignore_older_history_and_actions` 因严格浮点相等失败，数值为 2.0914342403411865 与 2.0914340019226074，相差约 2.4e-7。同一失败已在改动前基线记录中出现，保留原测试与完整日志。

## 本机复跑入口

在仓库根目录执行，输出必须为新目录。命令采用本机已安装的 Isaac 配置，模型和编码器按保存的指纹加载。

```powershell
$delivery = 'C:/Users/Lenovo/Desktop/系统分析与设计/output/Pre_Z交付_20261109'
./tools/simulation/run_official_ab.ps1 -Scenario normal-a -SeparateSleeves -Package "$delivery/AB_detector_v2/package-preserved-floor" -Encoder "$delivery/AB_detector_dev/resnet18-f37072fd.pth" -OutputRoot "$delivery/new-A"
./tools/simulation/run_official_ab.ps1 -Scenario fault-b -SeparateSleeves -Package "$delivery/AB_detector_v2/package-preserved-floor" -Encoder "$delivery/AB_detector_dev/resnet18-f37072fd.pth" -OutputRoot "$delivery/new-B"
python tools/simulation/verify_official_ab.py '<新试次目录>' --output '<新的核验JSON路径>'
```

连续 RGB 每个唯一渲染帧只进入一次检测，模型阶段从过去控制命令映射。自动核验返回 `expected_case_automatic_checks_passed`，完整记录同时保存失败、求助或未知。Z3 生成与素材核验分别使用 `build_pre_abc_evidence.py`、`verify_pre_abc_evidence.py`，参数可通过 `--help` 查看。
