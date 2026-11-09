# 三条匹配相机的正常观测数据交付

交付已有的三条完整 Fold Tops 正常采集记录，供当前固定 640×480 RGB 观测分支接入、审核和划分数据。保持 GAM＋原脚本控制器，无故障注入，检测及恢复关闭。三条记录的相机参数、控制器指纹和执行配置逐项一致。

## 下载

从[团队私有仓库的数据附件](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/releases/tag/zhang-matched-normal-data-20261109)下载 [rnd-oe-normal-observations.zip](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/releases/download/zhang-matched-normal-data-20261109/rnd-oe-normal-observations.zip)。需要仓库访问权限。

- 大小：480,177,447 字节。
- SHA-256：`a2e4c4e22641b37108b90b14b658730f0a085c5185b8bb822b1c604ff2e5b5ac`。
- 上传仅改为英文附件名；与本地 `RND-OE_正常观测交接.zip` 原字节完全一致。机器可读信息见 [package.json](package.json)。

| 目录 | 完整试次 ID | RGB 帧 | 观测记录 | 动作派发及对应反馈 |
| --- | --- | ---: | ---: | ---: |
| normal-01 | eff5d921-804f-4aeb-b1cb-2fe6d462ee23 | 468 | 476 | 778 |
| normal-02 | a4d9c33f-d5e9-40d2-985d-0b06f5f3a61e | 466 | 474 | 767 |
| normal-03 | c9eb5255-24f9-451e-88c1-837a1842b73a | 467 | 478 | 773 |
| 合计 | 3 个独立试次 | 1,401 | 1,428 | 2,318 |

包内每条 `normal-XX/raw/` 包含原始 RGB 数组、观测/动作时序、事件、相机与控制器上下文、采集配置及逐文件 SHA-256 清单。`export/observations.jsonl` 提供可移植的逐观测索引；`producer-sources/` 保存实际采集代码，启动命令和日志在各试次目录。原始采集文件名中的 `fold-recovery` 是沿用的存储格式，实际记录明确为正常采集且 `recovery_enabled=false`。

## 校验与读取

先核验下载文件，再解压，例如在 PowerShell 中：

```powershell
Get-FileHash .\rnd-oe-normal-observations.zip -Algorithm SHA256
Expand-Archive .\rnd-oe-normal-observations.zip -DestinationPath .\matched-normal-data
```

安装 NumPy 和 Pillow 后，在仓库根目录逐条核验（审核输出目录应为新目录）：

```powershell
python tools/simulation/verify_pre_observations.py .\matched-normal-data\normal-01\raw .\normal-audit-01
python tools/simulation/verify_pre_observations.py .\matched-normal-data\normal-02\raw .\normal-audit-02
python tools/simulation/verify_pre_observations.py .\matched-normal-data\normal-03\raw .\normal-audit-03
```

从仓库根目录的 Python 程序读取：

```python
from tools.simulation.pre_observation_reader import iter_observations

for packet in iter_observations("matched-normal-data/normal-01/raw"):
    rgb = packet["rgb"]  # uint8, [480, 640, 3]
    trial_id = packet["trial_id"]
    frame_index = packet["frame_index"]
    rendering_time_s = packet["rendering_time_s"]
    # 将 RGB、时钟及当前本体观测交给同一编码/检测实现。
```

每次加载一条试次；NPZ 使用 `allow_pickle=False`。同一渲染帧可能有多次阶段边界读取，因此 1,428 次观测对应 1,401 张唯一 RGB 图像。检测窗口是否按唯一帧推进须与在线实现一致。`phase` 是控制意图，不是独立正常/异常标签；仿真时刻和本进程 monotonic 时钟不能跨时钟域或跨试次相减。读取器不暴露故障注入、最终代理评价或未来结果。

## 已核验范围与后续接入

2026-11-09 核验通过：ZIP CRC、包哈希、包内原始文件与逐文件清单、三条试次身份、RGB 类型/尺寸及有效性、观测与派发/反馈时序、三个折叠阶段及计划释放、导出索引与原始观测一致性。三条相机、控制器及执行配置完全一致。见 [verification.json](verification.json)、[trial-index.json](trial-index.json)、[camera.json](camera.json) 和[采集源码指纹](producer-sources.json)。

此次交付保留原始 `dataset_use=unassigned`、`independent_review=pending`，供接收方独立审核后按**完整试次**分配拟合、校准和开发用途，禁止将同一试次相邻帧分到不同用途。后续审核/划分请另存记录并引用这三个试次 ID，保留原始包不变。三条数据不构成统计保证；区域代理通过也不代表 SRS 折叠质量验收。

该包提供正常观测输入，不包含已校准的 RND-OE 模型、阈值或在线检测成绩。采集时未运行检测，不能据此将 A/B 场景标为通过；本 PR 不含 C、Z3 或 A/B 中间开发代码。与胡已通过 PR #25 的旧视角首袖探针区分使用，不混合视角。
