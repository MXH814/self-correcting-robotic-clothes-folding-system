# 动作前 RGB、实际动作与测量反馈

本机 Isaac Sim 4.5.0 和固定 DexGarmentLab 环境中实跑。run ID 为 `e0b6e45c-f9c2-4b97-93d3-9c4041018655`。采集使用双臂组件场景和同进程本地接纳逻辑，动作由脚本指定。该 RGB 可与动作前本体观测关联，尚无模型依据 RGB 选择该动作的记录。

- 相机帧在约 **0.500 s 仿真时间**渲染，在约 **0.533 s** 读取。图像写盘后才读两臂各 30 个命名关节的位置和速度，再做关节类型和限位检查、持久化接纳意图、调用 articulation API。读取起止的单调时间本次相同，保留原始值。
- 实际下发 `left:shoulder_pan_joint`，运行时索引 0，绝对目标 **−1.54000005 rad**。后续保存 4 次双臂反馈。片段从仿真步 32 到 92，末次位置 **−1.54003918 rad**，实测变化约 **+0.02996087 rad**。
- 任务、观测、命令和代次 0 在记录中显式关联。相机渲染时刻和仿真步使用仿真时间；读数、接纳及派发另存同进程 `monotonic_ns`。没有建立对外时钟映射。

[动作链原始记录](preaction-chain-20261108/action-chain.json) · [动作前 PNG](preaction-chain-20261108/pre-action-rgb.png) · [接纳意图](preaction-chain-20261108/accepted-intent.json) · [文件大小与 SHA-256](preaction-chain-20261108/manifest.json)

## 复跑

从仓库根目录执行：

```powershell
$env:ROBOTICS_RECORD_ACTION_CHAIN = '1'
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\simulation\run_local.ps1 -Stage runtime-io -Headless -OutputRoot 'E:\Robotics\preaction-chain-results'
Remove-Item Env:ROBOTICS_RECORD_ACTION_CHAIN
```

配置包括四线程参数、640×480 RGB、20 Hz 相机配置和场景照明。实际相机位姿、镜头、关节限位和控制增益见 [同运行 sample.json](preaction-chain-20261108/sample.json)。上游源码及依赖版本见[固定环境记录](second-machine-install.md)，本仓库运行代码随提交保存。阶段日志和动作后图像也列入清单，动作后图像只用于复核。

已核对命名索引、值的有限性、关联 ID、动作前后时钟顺序、RGB 像素和文件指纹。该记录可供马祥珲接入动作前视觉、本体状态、接受的绝对命令和同次反馈。产品协调器接纳、跨进程时钟和恢复策略仍需另行验证。
