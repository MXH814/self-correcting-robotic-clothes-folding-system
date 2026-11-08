# Fold Tops 环境固定资料与可选迁移步骤

**当前安排已变更（2026-11-08）：马祥珲确认已在张电脑完成基础复跑，后续仿真/采集/恢复闭环统一在张电脑运行。无需组长电脑安装、换机或重复基础复跑。** 见[执行安排](../shared-simulation-workflow.md)。本页保留固定源码/依赖/资产资料和历史迁移步骤，供必要的环境恢复或将来明确变更使用，不是当前待办。

以下安装/下载/换机测试描述为此前准备记录；没有要求现在执行这些操作，也不把同机复跑改称换机成功。

## 1. 已交接的数据

[私有 GitHub Release](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/releases/tag/handoff-fold-tops-20261108)提供两份正常示范纯数值数据和逐文件清单；组长已实际下载并完成校验，数据接入不必等待环境安装。数据不包含实际命令、ACK、时间或恢复标签。参见[接入说明](../ma-data-intake-progress.md)；不将正常示范视为恢复案例。

## 2. 硬件和 Isaac Sim

组长先确认 Windows、NVIDIA GPU/驱动、RAM 和空闲空间，查阅 [NVIDIA 官方安装文档](https://docs.isaacsim.omniverse.nvidia.com/4.5.0/installation/install_workstation.html)及许可。选择 Windows standalone 4.5.0，解压到例如 `D:\Robotics\isaacsim-4.5.0`；安装包允许通过官方渠道自行获取。作者原包 7,013,544,567 字节，SHA-256 `29171fe52efa1923162c215d42907f7f1363dfcff2b4e25a12428ab6cbd08fc8`，解压后版本 `4.5.0-rc.36+release.19112.f59b3005.gl`、Python 3.10.15。新下载的归档若 hash 不同，应核明发行版差异；不把不同归档直接当成相同包。

作者电脑约 16 GB RAM、RTX 4060 Laptop 8 GB，NVIDIA 兼容检查的内存项未通过（要求 32 GB）；小场景曾使用低资源参数运行。这不是对其他机器的兼容保证。不要用本页附加依赖覆盖 Isaac 自带 NumPy/Torch。

## 3. 获取固定上游源码

作者最初下载的 `DexGarmentLab-source.zip` 的 ZIP comment 为 `e4e298e696bae5d866ded3b31e0ae27becea5376`。2026-11-08 将压缩包内 **761 个文件**逐个计算 Git blob SHA-1，与该 commit 的官方 Git tree 比较，文件集合及内容全部一致；随后将这 761 个原文件与作者已安装目录逐项按 SHA-256 对比，未发现缺失或修改。目录中另有本地包装和下载资产等新增内容，分别由团队仓库和官方资产来源提供。归档本身 SHA-256 仍为 `c5d87aad847bb0bec691d68364481a653ef5a0013035b03146d7a7af27df385c`。

在 PowerShell 中，若 `D:\Robotics\DexGarmentLab` **尚不存在**，可运行：

```powershell
$root = 'D:\Robotics'
New-Item -ItemType Directory -Force -Path $root | Out-Null
git clone https://github.com/wayrise/DexGarmentLab.git (Join-Path $root 'DexGarmentLab')
git -C (Join-Path $root 'DexGarmentLab') checkout --detach e4e298e696bae5d866ded3b31e0ae27becea5376
git -C (Join-Path $root 'DexGarmentLab') rev-parse HEAD
```

HEAD 应为 `e4e298e696bae5d866ded3b31e0ae27becea5376`。也可从[官方固定 commit 源码页](https://github.com/wayrise/DexGarmentLab/tree/e4e298e696bae5d866ded3b31e0ae27becea5376)获取；按 commit 下载的 ZIP 名称和根目录可能不同，不能用原 `main` ZIP 的文件 SHA-256 验证另一次打包字节。上述 clone 步骤在目标机尚未执行。上游源码根目录未发现明确 LICENSE；具体使用及再分发权利需核查，不能从代码可访问推断其他组件许可。

## 4. 额外 Python 依赖（Windows x86-64，Isaac Python 3.10）

[带哈希的 50 项 wheel 清单](../../../configs/simulation/fold-tops-windows-cp310-requirements.txt)根据作者的 `wheels-local.txt` 中实际 50 个文件生成，并对每个文件计算 SHA-256。它只涵盖本次示范的作者机附加依赖，不代表完整训练/HALO 环境，也不替代第三方许可检查。

在团队仓库根目录的 PowerShell 中执行，路径按目标机器调整，确保目标目录是新目录：

```powershell
$root = 'D:\Robotics'
$isaacPython = Join-Path $root 'isaacsim-4.5.0\python.bat'
$deps = Join-Path $root 'python-deps'
$wheels = Join-Path $root 'wheels-fold-tops'
$lock = '.\configs\simulation\fold-tops-windows-cp310-requirements.txt'
if (Test-Path -LiteralPath $deps) { throw 'Dependency target already exists; choose a new empty target' }
New-Item -ItemType Directory -Force -Path $wheels | Out-Null
& $isaacPython -m pip download --index-url 'https://pypi.org/simple' --require-hashes --no-deps --only-binary=:all: -r $lock --dest $wheels
if ($LASTEXITCODE -ne 0) { throw 'Wheel download or hash validation failed' }
& $isaacPython -m pip install --no-index --find-links $wheels --require-hashes --no-deps --target $deps -r $lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency install failed' }
```

`--require-hashes` 要求文件匹配作者记录，`--no-deps` 不自行补充依赖；不能把别的 NumPy/Torch wheel 安装进 Isaac。作者机器实际完成 50 项下载和哈希校验，再在独立目录安装；`open3d 0.18.0`、`av 17.1.0`、`imageio 2.38.0`、`termcolor` 从该独立目录导入，NumPy 1.26.0 与 Torch 2.5.1+cu118 仍来自 Isaac。第二次使用显式 PyPI URL 时本地 wheel 已存在，不能据此单独声称所有文件均从该 URL 重新下载；若目标机下载失败请记录具体包、来源和错误。目标机完整安装尚未验证。

## 5. 衣物、机器人、场景及 GAM

官方 [Hugging Face 资产库](https://huggingface.co/datasets/wayrise/DexGarmentLab/tree/main)提供 `Garment.zip`、`Robots.zip`、`Scene.zip`。作者选择了 TCLC_018 衣物及贴图、机器人集合和默认场景：逐文件清单 [demo-asset-sha256.json](../../../configs/simulation/demo-asset-sha256.json) 包含 584 项、296,488,662 字节。团队仓库的资产提取器是此前作者使用的脚本，指向官方 main；上游更新或下载失败时必须以逐文件核验结果为准。

在团队仓库根目录、确认 `DexGarmentLab/local-demo-assets.json` 尚不存在的前提下：

```powershell
$root = 'D:\Robotics'
$project = Join-Path $root 'DexGarmentLab'
$env:ROBOTICS_PROJECT_ROOT = $project
& (Join-Path $root 'isaacsim-4.5.0\python.bat') .\tools\simulation\download_demo_assets.py
if ($LASTEXITCODE -ne 0) { throw 'Asset acquisition failed; inspect output' }
& (Join-Path $root 'isaacsim-4.5.0\python.bat') .\tools\simulation\verify_demo_assets.py --project-root $project --manifest .\configs\simulation\demo-asset-sha256.json
if ($LASTEXITCODE -ne 0) { throw 'Asset fingerprint mismatch' }
```

下载器按清单提取机器人集合、TCLC_018、默认场景；现有同大小文件会跳过，**大小相同不等于内容相同**，因此必须运行 SHA-256 核验。脚本仅在新环境尝试，已有 manifest 或不同大小文件会拒绝覆盖；若中途中断检查残留文件，不要盲目覆盖。584 项中包含不一定用于当前 Fold Tops 的其他机器人文件，是作者已下载集合，不代表全部为最小依赖。作者机实测全部 584 项匹配；新的远程资产获取及新机器运行未测试。数据卡、机器人和场景各组件可能有不同许可，逐项核验。

官方固定源码包含 GAM 长袖 `Model_HALO/GAM/checkpoints/Tops_LongSleeve/checkpoint.pth`，作者该文件 SHA-256 为 `c44f79c0bd7aab1f8c3dc5820f02f7b97f0763ced3baeba6c3dee3323e0142d9`。它不是三个 SADP_G 阶段策略 checkpoint，不能代表完整 HALO 权重。

## 6. 已有环境运行入口及历史迁移验证记录

从包含本 PR 的团队仓库根目录：

```powershell
$root = 'D:\Robotics'
& .\tools\simulation\run_local.ps1 -RoboticsRoot $root -Stage fold -Headless -CheckOnly
& .\tools\simulation\run_local.ps1 -RoboticsRoot $root -Stage engine -Headless
& .\tools\simulation\run_local.ps1 -RoboticsRoot $root -Stage garment -Headless
& .\tools\simulation\run_local.ps1 -RoboticsRoot $root -Stage fold -Headless
# 如果需要图形演示，完成后手动关闭窗口：
& .\tools\simulation\run_local.ps1 -RoboticsRoot $root -Stage fold -KeepOpen
```

若安装位置不同，使用 `-IsaacRoot`、`-ProjectRoot`、`-DependencyRoot` 和 `-OutputRoot` 覆盖。`-CheckOnly` 只验证路径；组件关注 `LOCAL_SMOKE_TEST_PASSED`，折叠记录 `final result` 与对应的新轨迹和图像。上游折叠输出写入源码 `Data/Fold_Tops` 并追加日志，运行前检查目录和空间。上游 True 不等于 SRS 质量或恢复验收。

作者在 2026-11-08 使用重建的隔离依赖、现有作者机源码及资产发起过无窗口 garment 测试：启动后出现线程等待提示，长时间无输出，随后**由操作者主动停止**；未看到通过标志，结果为**未完成验证**，不将人工停止记为程序错误，也不能认定仿真通过或根因。启动时日志显示约 2.2 GB 空闲内存，但无法仅凭这个快照确定原因。先前独立目录安装和 Python 导入通过，范围限于上述记录。

组长已确认在张电脑基础复跑完成，不再重复要求；后续实验仍在该电脑保存版本、配置、命令、日志和输出。真实关节映射、时钟与停止/恢复能力继续按新接口及实验任务验证。
