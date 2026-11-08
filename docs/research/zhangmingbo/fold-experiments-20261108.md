# Fold Tops 取景、投影、停止与重置实测

2026-11-08 在张茗博的 Windows 实验机上执行。使用 Isaac Sim 4.5.0、固定 TCLC_018、已有 DexGarmentLab 和 GAM 资产。上游版本和依赖见[环境交接](second-machine-install.md)。

## 完整折叠与取景

使用仓库启动器的 `fold-camera` 模式。保留上游相机与三阶段控制，关闭随机选衣和视频。上游判定 `True`，新轨迹 `data_4.npz` 含 27、27、23 帧。77 帧均为 640×480 非均匀 RGB，每帧都检出画面内部的可见橙色衣物像素。该颜色统计用于检查取景和裁切，无法估计被手遮挡的布料面积。人工看过三个阶段的取样图和最终帧。最终帧中双臂由上游流程隐藏。

[逐帧取景核验](fold-experiments-20261108/trajectory-rgb-audit.json) · [阶段一](fold-experiments-20261108/stage-1.png) · [阶段二](fold-experiments-20261108/stage-2.png) · [阶段三](fold-experiments-20261108/stage-3.png) · [最终图](fold-experiments-20261108/final.png)

原始 NPZ 留在实验机上游 `Data/Fold_Tops/train_data`，大小 27,050,765 字节，SHA-256 为 `5a13bdd95bee808d6ef52bd1505e6e4af1ea673e5c14590477e42b162299f32c`。上游成功标志和图像可用于复核本次示范流程。SRS 最终质量和自主成功仍需按项目口径独立评估。

## 相机投影复核

折叠判定和原始轨迹写盘后，在相机前放入三个已知世界坐标的彩色球。将 Isaac Sim 相机内参及世界至 ROS 相机变换投影结果，与图中球的像素质心对比，采用 3 像素的单次检查门槛。首次按全图颜色筛选时红色质心误差 7.24 像素，筛进了与衣物变化有关的离散像素。保留原始结果与原图，使用同一个颜色规则，只取每种颜色最大的连通区域复算，误差为 **1.00、0.65、0.58 像素**。该检查覆盖同一模拟相机三个位置和深度。完整视野误差、畸变和跨传感器时间标定待验证。

[投影原始与复算数值](fold-experiments-20261108/fold-evidence.json) · [标靶图](fold-experiments-20261108/calibration.png)

## 停止、去重和代次屏障

使用无衣物的单进程双臂探针。探针适配器实际调用 Isaac articulation，先记录派发意图，再返回组件 ACK。重复 ID 被去重；暂停和终止时先撤权并更新代次，再将双臂位置目标设为当前实测位置。旧代命令和撤权期间的新代命令都被拒绝。仿真继续推进，直接读取双臂 60 个关节的速度；本试验的同步派发没有消息队列。

| 操作 | 请求到确认 | 合格窗口 | 合格样本 | 窗口内最大绝对速度 |
| --- | ---: | ---: | ---: | ---: |
| 暂停 | 0.676 s | 0.100 s | 7 | 0.000321 rad/s |
| 终止 | 0.692 s | 0.116 s | 8 | 0.000321 rad/s |

两次窗口的相邻样本间隔都不超过 20 ms。此结果覆盖组件探针路径；产品协调器、真实传输队列、适配器失联和迟到反馈仍待集成后验证。

[派发、撤权及实测速度](fold-experiments-20261108/control-evidence.json)

后续使用进程内故障注入验证了撤权清队列、重连锁定及迟到反馈拒绝，并保留新的实测停止证据。[适配器故障注入记录](adapter-fault-probe-20261108.md)

## 重置与资源

同一个小型衣物场景连续重置三次，每次以同一位置和姿态开始。在重置后第 2 步和第 100 步分别与第一轮比较。使用世界坐标的 USD 网格顶点和单步差分速度；首次直接调用未初始化的粒子视图，失败后改用网格观测。两次复测的初态最大顶点误差约 0.032、0.025 mm，沉降后增至 **31.37、31.68 mm**，双臂关节在这组无动作重置中一致。尚无接触、随机状态和任务中段快照的恢复证据。此偏差需要在设计配对分支前处理。

完整折叠约 287 秒，包含应用启动和场景加载。运行中途开始采样，共 16 次。观察到的最低系统提交余量约 0.81 GiB，Kit 私有内存最高约 10.08 GiB，整卡显存最高 4938 MiB。这些是区间内的采样值。没有用这次记录外推论文训练吞吐。

[三轮重置原始误差](fold-experiments-20261108/garment-reset-result.json) · [资源采样](fold-experiments-20261108/resource-samples.json)

## 复跑

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\simulation\run_local.ps1 -Stage fold-camera -Headless -OutputRoot 'E:\Robotics\fold-camera-results'
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\simulation\run_local.ps1 -Stage runtime-control -Headless -OutputRoot 'E:\Robotics\runtime-control-results'
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\simulation\run_local.ps1 -Stage garment-reset -Headless -OutputRoot 'E:\Robotics\garment-reset-results'
```

逐项串行运行。完整折叠另按上游命名规则在 `ProjectRoot/Data/Fold_Tops` 中新增文件。

`fold-camera` 写完三个阶段、最终和标靶图像及投影记录后才确认完成。`garment-reset` 写完三轮重置记录后确认完成。两者都检查本次调用的唯一完成标记。上游折叠判定为 `False`、靶点偏差超过门槛或重置误差偏大时，只要记录齐全，实验仍可正常交付。

## 待验收

- **D03 抓偏与滑移**仍缺两个按阶段持有意图、实测接触或漂移、阈值和持续窗口记录的失败案例。需要可复核的接触/衣片跟踪记录及标签审核。正常轨迹和橙色像素检查不产生失败标签。
- **D04 任务中段可比重置**仍缺相同失败状态的恢复验证。本次可复跑的初态重置测出了沉降差异。
- **D05 产品控制闭环**需将组件适配器的实测通道接入项目协调器，验证队列清空、失联和迟到反馈。
- **D06 恢复分支**仍缺经审核的根失败状态和合法候选、可比起点及固定接续控制器的配对记录。现有上游正常示范和组件停机结果均不计入恢复成功率。
