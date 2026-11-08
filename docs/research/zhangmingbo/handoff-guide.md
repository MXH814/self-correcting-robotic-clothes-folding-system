# 仿真最小交接：Fold Tops

负责人：张茗博；2026-11-06。此包交接已有工作和未解决问题，等待组长审查；第二人复跑尚未进行。依据[交接待办](handoff-tasks.md)、[环境报告](environment-feasibility.md)及[复现状态](reproduction-status.md)。

审查更新（2026-11-07）：PR #2及相对路径修复已复审通过合并，启动器轻量回归通过；下表的“待审”为原提交状态，不代表目前仍等待批准。H03/H04/H05的运行/数据缺口仍成立。完整轨迹纯数值导出与下一步入口见[马祥珲接入进展](../ma-data-intake-progress.md)。

## 2026-11-08 交接更新

- 两份已上传的纯数值数据包和逐文件清单：[私有 GitHub Release](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/releases/tag/handoff-fold-tops-20261108)；GitHub 附件显示大小及 SHA-256 与作者机一致，接收方下载/验证待确认。
- 组长选择**另一台电脑安装**；[第二台电脑复跑准备](second-machine-install.md)给出来源、步骤与仍待提供的精确源码归档和依赖。独立安装和复跑尚未执行，不能当作已验证。
- 原始对象 NPZ 未上传，纯数值包可先用于离线接入；常规哈希核验不代表来源身份已认证。

## H01–H05 状态

| ID | 状态 | 已提供与缺口 |
|---|---|---|
| H01 | 已提交待审 | 仓库内启动器、两种 Python 包装和资产获取脚本；路径已参数化，修改后只做路径、语法及轻量检查，完整仿真尚未复跑。 |
| H02 | 已提交待审 | [资产清单](artifact-manifest.json)、[原资产列表](local-demo-assets.json)、[配置](../../../configs/simulation/low-resource.example.json)及原环境报告。部分许可和源码 commit 仍未知。 |
| H03 | 部分已提交，完整轨迹访问阻塞 | [真实观察数值](observation-example.json)和[对应最终图像](sample-final.png)入库；原始轨迹仅在作者机器，需要约定可访问存储或同机访问。 |
| H04 | 部分已提交待审 | [字段与动作说明](io-profile.md)给出真实样例和来源；60 个关节的名字顺序、真实时钟、逐命令 ACK、停止反馈仍待验证。 |
| H05 | 部分已提交，独立复跑待执行 | 下方提供作者机器入口和新机器准备步骤；路径检查通过并非运行或独立复跑通过，未提供远程访问能力。 |

## 可复跑入口

目前计划由组长在另一台电脑安装；纯数值数据已经通过私有 Release 提供，精确源码归档和 wheel 仍需核实获取及许可。操作者需先取得作者机器的正常使用权限，运行下列命令并自行保存日期、软硬件版本、命令、完整控制台日志、输出清单、耗时和结果。此方案仍依赖人员实际协调，不代表已经提供远程登录。另一台电脑需根据下述来源安装、确认许可并准备全部依赖与资产；该路径尚未从零验证。

1. 获取本项目代码及本分支；安装 [Isaac Sim 4.5](https://docs.isaacsim.omniverse.nvidia.com/4.5.0/installation/install_workstation.html) Windows standalone，并确认显卡/驱动、RAM 和许可。作者机器为 Windows 11、RTX 4060 Laptop 8 GB、RAM 16 GB；官方兼容检查内存要求 32 GB，整体未通过。
2. 准备 [DexGarmentLab 源码](https://github.com/wayrise/DexGarmentLab)和[官方资产](https://huggingface.co/datasets/wayrise/DexGarmentLab/tree/main)。本次使用的源码 ZIP SHA-256 和模型等见清单；同一上游 main 未来可能变化，不可仅凭分支名断言相同版本。GAM 检查点包含在本次源码 ZIP；三阶段 SADP_G 权重尚未确认。
3. 把所需附加包安装到**独立**的 `python-deps`，保留 Isaac 自带 NumPy/Torch；作者使用 Open3D 0.18.0、termcolor 3.3.0、av 17.1.0、imageio 2.38.0。[作者 wheels 文件名列表](../../../configs/simulation/wheels-local-filenames.txt)记录所用安装材料，不是经过另一机器验证的安装锁文件。安装和资产获取失败时记录缺项，不要用 `pip` 覆盖 Isaac 核心环境。
4. `tools/simulation/download_demo_assets.py` 是作者的按需远程 ZIP 提取器，当前会获取全部 Robots.zip、TCLC_018 和默认场景；使用 `ROBOTICS_PROJECT_ROOT` 指定源码目录。仅在准备好的新目录执行；已有同名清单直接拒绝，已有文件同大小会跳过（并未校验文件哈希），大小不一致则拒绝覆盖。逐项许可及内容仍须核对。示例：

```powershell
$env:ROBOTICS_PROJECT_ROOT = 'E:\Robotics\DexGarmentLab'
& 'E:\Robotics\isaacsim-4.5.0\python.bat' 'tools\simulation\download_demo_assets.py'
```

5. 从仓库根目录运行下列命令；`-RoboticsRoot`、`-IsaacRoot`、`-ProjectRoot`、`-DependencyRoot`、`-OutputRoot` 可调整。引号中的路径按机器实际情况修改。`-CheckOnly` 只验证路径存在：

```powershell
& .\tools\simulation\run_local.ps1 -Stage fold -Headless -CheckOnly
& .\tools\simulation\run_local.ps1 -Stage engine -Headless
& .\tools\simulation\run_local.ps1 -Stage garment -Headless
& .\tools\simulation\run_local.ps1 -Stage fold -Headless
# 可选图形界面；完成后自行关闭，不加 KeepOpen 时不主动保留窗口
& .\tools\simulation\run_local.ps1 -Stage fold -KeepOpen
```

组件测试检查 `LOCAL_SMOKE_TEST_PASSED` 及 `OutputRoot` 结果文件；折叠检查 `LOCAL_FOLD_PROFILE`、`final result`、轨迹与最终图像。上游折叠脚本将轨迹/图像写入 `ProjectRoot/Data/Fold_Tops`，不受 `OutputRoot` 控制，还会追加 `data_collection_log.txt`；运行前检查磁盘、权限和已有输出，切勿把官方训练数据目录当工作目录。不能仅凭进程退出码判断实验成功。`-KeepOpen` 要求图形模式；运行时不要停止仿真时间线。

## 真实样本与访问

图形运行于 2026-11-04，`garment_random_flag=False`，TCLC_018，初始 `pos=[0,0.8,0.2]`、`ori=[0,0,0]`。日志同时记录官方 `final result: True`、`data_2.npz` 与 `img_2.png`；这是上游脚本生成的自采示范，不是 SADP_G 策略评测。图像是环境相机最终 640×480 RGB，不是 stage_1 第 0 帧。轨迹 27/27/23 帧，无原始时间戳，阶段间没有连续记录；详见 [I/O](io-profile.md)。

原始轨迹作者机路径 `E:\Robotics\DexGarmentLab\Data\Fold_Tops\train_data\data_2.npz`，26,983,793 字节；其 SHA-256 和对应图像的哈希见[清单](artifact-manifest.json)。该原始 NPZ 路径对其他机器不可访问；对应的纯数值导出包可在本页更新中的私有 Release 下载。数据包含 Python 对象数组；仅对**自行确认可信来源**且哈希匹配的文件运行以下导出器（匹配 hash 本身不能使恶意 pickle 安全）：

```powershell
python .\tools\simulation\export_observation.py --input '<可信的 data_2.npz>' --sha256 2309165bccd101c6ad65460716844d4f47d4b71e2f2f3dd775ecf37c47dac552 --output '<新建的 observation.json>'
```

上游判定不等于 SRS 质量或自主成功；由实际第二人单独记录复跑及验收。当前无失败注入、停止确认、完整状态快照和新时钟样本的实测证据；它们属于后续工作，不能由这次交接推断完成。

## 脚本来源与本次变更

- `run_local.ps1`、`run_fold_local.py`、`smoke_test.py`、`download_demo_assets.py` 由此前本机验证时编写，并非上游源码；本次改为从参数/环境变量读取路径。资产获取器新增拒绝覆盖检查，组件输出位置改为 `OutputRoot`。
- `export_observation.py` 是本次新增的受信任样本数值导出工具；使用该工具时操作人负责确认来源。`low-resource.example.json` 是记录用快照，运行参数目前由包装脚本实现，并非由该 JSON 自动加载。
- 上游 `Fold_Tops_Env.py`、`BaseEnv.py`、机器人与相机实现未由此交接包修改；它们随另外获取的上游源码提供。已验证的历史日志来自此前旧版本包装脚本；新版包装尚未进行完整仿真复跑。
