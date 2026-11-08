# 第一袖失败中段重放与状态恢复探针

沿用第一袖扰动脚本和 TCLC_018 场景，重复三次「正常接近、闭手、抬起、持有期提前开手」前缀。每次在持有采样窗结束后取网格与双臂状态，随后直接调用固定转移和计划释放，期间不调用重抓或其他恢复候选。这个探针将同一控制前缀的重复运行与直接设置状态分开记录。

固定接续入口为 `garment_fault_probe.py` 中的 `fixed_transfer` 及 `planned_release`，从第一袖持有采样窗后开始。原始动作参数、上游 IK 结果和时间保存在同次 JSON。该入口只覆盖第一袖，整任务质量留空。

## 已验证

运行 ID 为 `13bc382c-d4b8-4031-bf6e-8bf5011ada10`。三个中段读数均对应 **5.7833 仿真秒**。位置和速度误差均相对于首次运行。

| 复跑 | 网格位置最大 / RMS 差 | 网格差分速度最大 / RMS 差 | 固定转移末衣片高度增量 |
| --- | ---: | ---: | ---: |
| 首次 | 0 / 0 mm | 0 / 0 m/s | 167.9 mm |
| 第二次 | 30.55 / 7.11 mm | 0.703 / 0.037 m/s | 112.4 mm |
| 第三次 | 70.69 / 8.62 mm | 3.165 / 0.142 m/s | 145.7 mm |

双臂 60 个关节在同时间点的读数相同。直接写入也使关节位置与速度的立即读回误差为零。尝试初始化布料张量接口时，Isaac 报告当前 CPU SimulationView 未实现 `createParticleClothView`，随后取得空句柄。布料位置和速度均未写入。这里的 CPU 视图是当前配置的接口限制，尚未验证改用 GPU 张量管线的结果。

[原始记录](garment-midstate-20261108/fault-evidence.json) · [图片与 SHA-256 清单](garment-midstate-20261108/manifest.json)

## 未验证与可用范围

接触状态和仿真随机状态均不可用。尽管关节相同，布料最大差异超过 70 mm，固定接续的衣片末高度也变化约 55.5 mm。因此本次重复是独立轨迹，不能组成可比的同根候选池。该结果可供马判断分块独立试次是否值得推进，并确定下一次重置验证的观察指标。尚未解锁合法候选覆盖、局部标签或整任务结果。

## 复跑

```powershell
$env:ROBOTICS_MIDSTATE_PROBE = '1'
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\simulation\run_local.ps1 -Stage garment-fault -Headless -OutputRoot 'E:\Robotics\garment-midstate-results'
Remove-Item Env:ROBOTICS_MIDSTATE_PROBE
```

仿真网格速度通过相邻一步的网格位置差估算，双臂位置和速度由 Isaac 直接读取。直接恢复只在当前求解器的粒子布局与网格坐标对应检查通过后才尝试写入布料状态。关节写入单独检查。接触缓存和仿真随机状态未恢复，无法据此声称相同物理起点。
