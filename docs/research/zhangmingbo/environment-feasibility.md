# DexGarmentLab 环境可行性报告（P02）

> 仓库说明：本报告记录作者实验机的历史过程；E 盘路径、原始日志和数据是该机器的本地引用，未包含在仓库中。


整理日期：2026-11-04；同日补充完整图形模式复测结果

负责人：张茗博

依据：第一阶段计划 P02、P05 及 E02。状态：**初步验证，有待独立复现和补充证据**。

## 1. 结论

在本机 Windows 原生环境，使用 Isaac Sim 4.5.0 和低资源配置，可以运行刚体、衣服、双臂、相机组件检查；官方 Fold_Tops 示例曾在无窗口模式完成一次，日志中的内置判定为 `True`。该结果说明基本链路具备可行性，不代表项目恢复功能、真实部署或正式折叠质量已经验收。

官方兼容性检查的内存项未通过，整体结果为 FAILED。本机 16 GB 内存低于检查器所要求的 32 GB。2026-11-04 完整图形折叠运行到结束，官方内置判定为 True，并生成轨迹和最终图像。单次运行通过不能证明长期稳定，也不代表项目质量验收通过。第二人复现、A800 兼容性、失败注入和系统集成仍待验证。

## 2. 设备、版本和配置

| 项目 | 本次记录 |
| --- | --- |
| 系统 | Windows 11 Pro 25H2，本机原生运行 |
| CPU | AMD Ryzen 9 7945HX，16 核 / 32 线程 |
| GPU | NVIDIA GeForce RTX 4060 Laptop，约 8 GB 显存，驱动 566.26 |
| 内存 | 约 15.7 GiB；兼容性检查器要求 32 GB |
| Isaac Sim | 4.5.0-rc.36+release.19112.f59b3005.gl |
| Isaac Python | 3.10.15；自带 NumPy 1.26.0、PyTorch 2.5.1+cu118，CUDA 可用 |
| 核心附加包 | Open3D 0.18.0、termcolor 3.3.0、av 17.1.0，独立安装到 `E:\Robotics\python-deps` |
| 测试配置 | 4 个 CPU 工作线程；单 GPU；组件相机 640×480；GPU rigid contact 和 patch 上限各 262144（上游代码默认各 10240000） |

低资源配置通过本地包装脚本应用。接触容量和线程配置可能影响较大场景及实验结果；正式实验应固定、报告并核查容量。默认线程曾产生约 19 GB 私有内存占用；4 线程的基础场景约 10 GB，数字不是硬件需求保证。

## 3. 已准备资产与来源

| 资源 | 本地状态与边界 |
| --- | --- |
| 源码 | [DexGarmentLab 官方仓库](https://github.com/wayrise/DexGarmentLab)的 main 源码压缩包，未固定 Git commit；本次下载 ZIP SHA-256 为 `c5d87aad847bb0bec691d68364481a653ef5a0013035b03146d7a7af27df385c`。源码来自压缩包而非 Git 克隆。 |
| 模拟器 | NVIDIA 官方 Isaac Sim 4.5.0 Windows standalone，保存在 `E:\Robotics\downloads\isaac-sim-4.5.0.zip`；SHA-256 `29171fe52efa1923162c215d42907f7f1363dfcff2b4e25a12428ab6cbd08fc8`。 |
| 衣物 | 从[官方资产库](https://huggingface.co/datasets/wayrise/DexGarmentLab/tree/main)按需提取 TCLC_018 及其贴图；没有下载全部衣物。 |
| 机器人/场景 | 按需提取 Robots.zip 资源与默认场景，实际清单见 `E:\Robotics\DexGarmentLab\local-demo-assets.json`。 |
| 模型 | 本地存在 `Model_HALO/GAM/checkpoints/Tops_LongSleeve/checkpoint.pth`；该示例的 GAM 推理日志可见。其他模型和训练流程未验证。 |
| 授权 | 本地源码根目录未发现 LICENSE 文件；数据、预训练权重和 NVIDIA 软件可能各有不同条款，**使用与再分发权限待逐项核验**，不能因可下载就认为可自由再分发。 |

安装依据：下载并解压 NVIDIA 发行包和源码；用 Isaac 自带 Python，将补充依赖从本地 wheels 安装到单独目录，保留 Isaac 自带核心库；使用 `download_demo_assets.py` 从官方资产包按需提取机器人、TCLC_018 和默认场景；使用 `run_local.ps1` 和 `local_run` 包装脚本配置路径和低资源参数。保存于 E 盘的 wheels、安装包及辅助脚本可用于检查。**尚未在第二台机器从零验证完整安装流程**；源码 ZIP 哈希用于识别本次版本，不能代替 commit 记录。

## 4. 能力与证据

| 检查 | 结果 | 证据及限制 |
| --- | --- | --- |
| NVIDIA 检查器 | 未通过整体检查 | `E:\Robotics\logs\compatibility-check.log`：RAM not enough、整体 FAILED；GPU 等项通过。 |
| 基础物理 | 通过一次 | `E:\Robotics\logs\engine-limited.log`，落体与碰撞检查；不代表衣物折叠。 |
| 衣服、双臂、手与相机 | 无窗口和一次图形组件检查通过 | `E:\Robotics\logs\garment-final.log`、`garment-gui-validation.log` 和 `local_run\results\garment-result.json`；两手各 30 个关节，手和手臂命令产生变化，RGB 输出 640×480。 |
| 官方完整 Fold_Tops | 无窗口一次完成 | `E:\Robotics\logs\fold-tops.log` 中 `final result: True`；生成 `Data\Fold_Tops\train_data\data_0.npz` 和 `final_state_pic\img_0.png`。这是官方内部判定，不等于独立质量验收。 |
| 完整 Fold_Tops 图形模式 | 2026-11-04 一次完成 | `E:\Robotics\logs\fold-tops-gui-retest-20261104.log`：`final result: True`、`LOCAL_FOLD_PREVIEW`；生成 `data_2.npz`、`img_2.png`，轨迹 ZIP 完整性检查通过。 |
| 回放材料 | 已生成采样画面视频 | `fold-tops-recorded-frames.mp4` 从上次无窗口运行保存的轨迹生成：三阶段分别 27、28、23 帧，4 fps 人为设定；无原始时间戳、有阶段间缺口，不是连续屏幕录像或真实速度。 |
| 失败注入、重置和完整状态恢复 | 待验证 | 尚无经审核的偏移/滑移案例或布料接触状态恢复证据。 |
| 另一成员复现、A800 | 待验证 | 未记录独立复现或 A800 实机结果。 |

源轨迹仅为本机生成的数据，含对象数组；读取使用 `allow_pickle=True`，因此复现脚本只应读取本机可信文件，不要用它加载来源不明的 NPZ。

## 5. 当前环境复现操作

以下命令在**已有本机安装**中执行，无需激活 Conda；路径硬编码为 E 盘。操作期间不应停止仿真时间线。录像默认关闭，折叠运行会新增轨迹和结果文件。

```powershell
# 1. 组件测试：检查输出中的 LOCAL_SMOKE_TEST_PASSED
& 'E:\Robotics\run_local.ps1' -Stage garment -Headless

# 2. 图形组件预览：测试完成后保持窗口
& 'E:\Robotics\run_local.ps1' -Stage garment -KeepOpen

# 3. 官方折叠流程，无窗口；查看 final result 和新生成的轨迹
& 'E:\Robotics\run_local.ps1' -Stage fold -Headless

# 4. 图形折叠流程：2026-11-04 复测一次完成，查看官方判定和输出
& 'E:\Robotics\run_local.ps1' -Stage fold -KeepOpen
```

核验者应记录日期、机器与驱动、软件/资产版本、执行命令、参数、耗时、终端日志、输出文件，以及是否观察到错误。不要只看进程退出码：应同时检查日志、输出时间和内容；结果与原次运行不同也应记录。视频可作为动作示意，不能替代独立重跑。

### 需给第二人的复现清单

- [ ] 明确使用同一台电脑复跑还是另一台电脑全新安装；后者还要核对软硬件兼容和路径。
- [ ] 获取必要安装包、资产、附加依赖及本地包装脚本；按官方条款决定允许的分发方式。
- [ ] 核对本报告版本、ZIP 哈希、低资源参数和资产清单；确认实际安装路径。
- [ ] 运行组件检查及无窗口折叠，保存完整日志、结果路径和复现者信息。
- [ ] 独立记录成功与失败；差异与原因待核查，不能把计划写作验收结论。

现有 `run_local.ps1`、`run_fold_local.py` 和资产下载脚本包含 `E:\Robotics` 绝对路径。另一台电脑若采用其他路径，必须先修改脚本并重新验证；不是即插即用安装包。

## 6. 接口与数据能力初查

- 图像：`Recording_Camera` 组件输出 RGB；测试记录为 640×480。示例记录中还包含点云字段，具体坐标系、采样频率、延迟和可部署来源仍需核对。
- 机器人：左右 UR10e + Shadow Hand；本地测试通过手部状态指令和关节动作产生变化。更完整动作约束、失败信号和停止确认接口待设计验证。
- 轨迹：`data_0.npz` 包含 `usd_path`、`pos`、`ori` 及三阶段数据；阶段样本包含 `joint_state`、`image`、`env_point_cloud`、`garment_point_cloud` 和 `points_affordance_feature`。该示例样本未记录时间戳，不能直接满足阶段计划的完整日志契约；点云和特征来源需进一步区分相机观测与仿真特权信息。
- 固定示例和自定义接口之间仍需适配，现有检查不代表暂停、停止确认、人工接管、回放契约或恢复控制已实现。

## 7. 后续工作与验收

1. 补充官方代码、资产和权重的许可核验；记录准确的源码 commit 或其他可追溯版本。
2. 请马祥珲独立复现并保留证据；若在新机器安装，完成从零复现后修订安装指南。
3. 后续在固定配置下重复运行图形流程，记录时间线状态和资源情况，评估稳定性。
4. 评估 A800 实例的系统、驱动、渲染和显存，记录实际费用与吞吐；目前无实测。
5. 与胡知鱼和马祥珲确定评价规范、数据接口；建立正常基线及偏移/滑移两类可复现案例。
6. 为记录增加时间戳、配置/版本、状态和动作语义；验证复位、布料接触状态恢复及非确定性。

P02 的操作视频、安装与接口材料已形成初稿，但**第二人复现和许可核验未完成**；E02 还要求固定配置下复现操作、采集和两类失败，当前不能标记完成。
