# 第二台电脑复跑入口（准备方案，尚未独立验证）

2026-11-08；张茗博提供。组长选择在另一台电脑安装。本文使安装、验证和未解决的版本获取问题可追踪；**尚未证明从零安装成功，也不代表组长已下载或复跑。** 当前路径示例针对 Windows，按实际磁盘位置修改。

## 0. 组长现在可以先取得数据

从[私有 GitHub Release](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/releases/tag/handoff-fold-tops-20261108)下载 data2、data3 及各自文件清单。需要用有该仓库访问权的 GitHub 账号登录。Release 的附件大小和 GitHub 返回的 SHA-256 已与作者机相符；是否收到、能否解压和独立核验由接收者记录。

```powershell
Get-FileHash -Algorithm SHA256 '<下载目录>\fold-tops-data2-numeric-20261107.zip'
Get-FileHash -Algorithm SHA256 '<下载目录>\fold-tops-data3-evidence-20261108.zip'
```

data2 应为 `6584a58167d25bef6da25eecdaf8436df8b93b1ad9cea6d8fe01f9fb70986a16`；data3 应为 `4808365cf9caf7454bec5ef3ca1a077bed86e7f6c8d1e5b20b7f9ccbb288cfa9`。两份清单列各文件哈希；解压后依据[数据接入说明](../ma-data-intake-progress.md)运行 `research_tools.legacy_observations`。来源确认和普通哈希一致性是不同检查。data3 中第 81 项是 `READ_ME_交接.txt`：76 RGB＋观测记录＋manifest＋最终图＋脱敏日志＋交接说明。

## 1. 环境与资产获取

1. 组长确认目标机 Windows、NVIDIA GPU/驱动、空闲空间、RAM 与 Isaac 4.5 兼容，并查阅 [NVIDIA 安装说明](https://docs.isaacsim.omniverse.nvidia.com/4.5.0/installation/install_workstation.html)及许可。作者机器是 16 GB RAM、RTX 4060 Laptop 约 8 GB、驱动 566.26，官方检查的内存项未通过；这些不是推荐配置保证。
2. 在独立根目录准备 Isaac Sim 4.5 Windows standalone，例如 `<ROOT>\isaacsim-4.5.0`。作者的安装包 7,013,544,567 字节，SHA-256 `29171fe52efa1923162c215d42907f7f1363dfcff2b4e25a12428ab6cbd08fc8`。若官方文件不匹配，应记录版本差异，不标记相同环境。
3. 从 [DexGarmentLab 官方仓库](https://github.com/wayrise/DexGarmentLab)获取源码并放在 `<ROOT>\DexGarmentLab`。作者所用 ZIP 的 SHA-256 为 `c5d87aad847bb0bec691d68364481a653ef5a0013035b03146d7a7af27df385c`；**来源是当时下载的 main 压缩包，commit 未知，当前上游 main 不保证相同。** 原始相同 ZIP 及组件许可目前尚无团队下载入口；若官方获取文件不匹配，先联系张茗博确认许可及相同版本可否交接，再决定是作为不同版本运行还是等待归档，不得冒称完全复现。
4. 依[官方数据资产页面](https://huggingface.co/datasets/wayrise/DexGarmentLab/tree/main)准备 TCLC_018、机器人和默认场景；所需文件详见 [local-demo-assets.json](local-demo-assets.json) 与 [artifact-manifest.json](artifact-manifest.json)。作者源码包内含 GAM 长袖 checkpoint，其文件 SHA-256 为 `c44f79c0bd7aab1f8c3dc5820f02f7b97f0763ced3baeba6c3dee3323e0142d9`；这个 checkpoint 不代表三阶段 SADP_G 策略权重。各组件许可单独核对。
5. 附加依赖安装到独立 `<ROOT>\python-deps`，保留 Isaac 自带 NumPy/Torch。作者 wheel 文件名及版本列于 [wheels-local-filenames.txt](../../../configs/simulation/wheels-local-filenames.txt)；该列表不是锁文件。按目标平台获取匹配 wheel 并检查来源后，可用 Isaac Python 的 pip 在目标独立目录安装，避免覆盖原始环境。作者 wheel 包尚未共享，换机安装完整依赖尚未验证。

例如，已在 `<WHEEL_DIR>` 准备并核验清单中全部适用于 Isaac Python 3.10/Windows 的 wheel 后，可以在 PowerShell 中使用下面的**候选安装命令**；它不自动下载或验证 wheel，且尚未在第二台机器运行：

```powershell
$root = 'D:\Robotics'
$wheelDir = 'D:\Robotics\wheels'
$deps = Join-Path $root 'python-deps'
$wheels = @(Get-ChildItem -LiteralPath $wheelDir -Filter '*.whl' -File | ForEach-Object { $_.FullName })
if ($wheels.Count -eq 0) { throw 'No wheel files found' }
& (Join-Path $root 'isaacsim-4.5.0\python.bat') -m pip install --no-deps --target $deps @wheels
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
```

`--no-deps` 不会自动补齐依赖；须逐项核对 wheel 列表与导入结果。不要将训练依赖及其可能携带的 NumPy/Torch 混装到 Isaac 的核心目录；出错先记录具体缺项。

## 2. 代码入口（安装并准备好资产后）

从团队仓库获取当前 `main`（或组长认可的冻结 commit），进入仓库根目录。例如根目录实际为 `D:\Robotics`：

```powershell
$root = 'D:\Robotics'
& .\tools\simulation\run_local.ps1 -RoboticsRoot $root -Stage fold -Headless -CheckOnly
& .\tools\simulation\run_local.ps1 -RoboticsRoot $root -Stage engine -Headless
& .\tools\simulation\run_local.ps1 -RoboticsRoot $root -Stage garment -Headless
& .\tools\simulation\run_local.ps1 -RoboticsRoot $root -Stage fold -Headless
# 图形运行；完成后保留窗口，关闭窗口退出
& .\tools\simulation\run_local.ps1 -RoboticsRoot $root -Stage fold -KeepOpen
```

若 Isaac、源码、依赖位置不符合默认结构，另传 `-IsaacRoot`、`-ProjectRoot`、`-DependencyRoot`、`-OutputRoot`。`-CheckOnly` 只核路径存在，不检验导入或仿真。组件检查关注 `LOCAL_SMOKE_TEST_PASSED`；折叠检查 `LOCAL_FOLD_PROFILE`、`final result` 与新生成轨迹/最终图。上游折叠输出写在源码目录 `Data/Fold_Tops` 并追加采集日志，开始前确认不覆盖团队已有数据；参见[交接指南](handoff-guide.md)。

在新机器上，组长记录实际机器/驱动、源码及资产指纹、命令/配置、运行时间、完整日志、输出及失败或结果。上游 True 是脚本自带判定，不等同独立 SRS 质量或恢复验收。若安装失败，保留步骤和错误；作者负责协助确认缺失资源、版本和许可，不代签独立复跑结果。
