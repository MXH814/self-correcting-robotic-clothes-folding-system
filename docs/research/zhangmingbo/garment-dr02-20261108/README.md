# DR02 指尖近景与标签复核

本批独立采集 TCLC_018 的正常持有和合法释放对照、抓偏候选、闭手部分滑移候选。原有试次 ID 和标签保持原样。[下载原始证据](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/releases/tag/zhang-garment-observation-20261108) · [ZIP 大小和 SHA256](packages.json) · [标签提案及测量](label-review.json)

## 标签提案

| 试次 | 提交审核的判断 | 证据 |
| --- | --- | --- |
| 正常持有与合法释放 | 正常对照、预定释放对照 | 近景显示闭手夹住并抬升衣片。对照持有期原补丁相对手指的位移最大 **1.92 mm**。预定开手后的窗口内没有布料顶点同时留在两指近邻带。 |
| 抓偏候选 | `OFFSET`，待独立复核 | 近景显示闭手后夹住布料并抬升。抬升窗口内有一组稳定的双指近邻顶点，其在平铺衣物上的中心距正常对照 **43.18 mm**，超过暂定门槛 **23.28 mm**。 |
| 闭手滑移候选 | `SLIP`，待独立复核 | 扰动前两指附近同一组材料顶点持续随手抬升。闭手扰动后，原顶点在两指各自坐标系中持续位移 **44.71–46.84 mm**，超过暂定门槛 **18.62 mm**。原顶点离开双指近邻带，同时另有材料顶点进入或留在该带，近景仍可见布料夹在手指间。 |

两项候选写入 `proposed_dr02_label`。正式 `dr02_label` 留待胡知鱼独立复核。几何方法用拇指和食指远端碰撞网格的凸包支撑面计算近邻带，近邻带宽 12 mm。位移在两指各自的局部坐标系中单独计算，跟踪材料顶点编号保持固定。近景与几何共同提供审核证据。接触力和求解器事件未采集。[NVIDIA 粒子接触报告说明](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/107.3/dev_guide/guides/current_limitations.html)

按项目数据设计，参考宽度取肩部与下摆躯干宽的平均值。两个拟注册截面分别测得 **455.90 mm** 和 **475.24 mm**，暂定 (W_0=465.57) mm。端点编号、世界坐标和原始顶点指纹见 `label-review.json`。正常夹持补丁与脚本点对应的预期顶点中心已相差 **55.28 mm**，所以本批先用独立正常对照的夹持补丁提出预期材料位置，再比较抓偏候选。复核需确认两个截面和这个预期夹持区域定义。旧包的暂定值来自单个下摆截面，仍作为历史记录保留。判定窗口以仿真时间为准，每窗 8 个物理样本，间隔约 0.05 仿真秒，跨度约 0.35 仿真秒。[项目数据设计](../../../design/data-design.md)

## 复算与接入

- `dr02-samples.npz` 提供近景 RGB、布料顶点、手指和碰撞网格的姿态。按 `dr02-samples.json` 的样本顺序索引几何，按 `frame_index` 索引图像。渲染时间与物理样本时间都在仿真域，读开始和结束是本地单调时钟。帧和物理样本可能相差几个仿真步。
- `observation-trace.json` 与 `rgb-frames.npz` 提供同一试次的动作前 RGB、命名关节状态、实际关节派发和后续反馈。三组共有 **408 帧 RGB** 和 **448 条实际派发及反馈**。近景相机随手跟拍。网格、碰撞几何、干预条件和标签提案留作离线审核。
- `near-*.png` 是从窗口中导出的原始近景帧。每组提供一个约三秒的连续片段索引和待审核的时间锚点。较短的量化窗口用来复核判据，正式片段的冻结和留出样本规模由评估协议另行验收。

离线复算需要 Python、NumPy 和 SciPy。

```powershell
powershell -ExecutionPolicy Bypass -File tools/simulation/run_local.ps1 -Stage garment-fault -GarmentTraceCase closed_hand_slip_candidate -Dr02Evidence -Headless -OutputRoot <output-directory>
python tools/simulation/verify_garment_observation_trace.py <extracted-trial-directory>
python tools/simulation/audit_dr02_geometry.py <extracted-trial-directory> --reference <extracted-normal-directory>/settled-vertices.npz
```
