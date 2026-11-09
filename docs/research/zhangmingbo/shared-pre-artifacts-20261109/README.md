# 新分阶段模型与完整原始观测共享

本次交接提供 PR29 对应的已有原始材料，供团队独立分数复算和新增正常案例审核。模型包 ID 为 `b9df07d40a29968947949a7a202e89b31d1fb37771fb4c2ff5094fc73ff3eb1b`。

## 下载与指纹

| 附件 | 字节数 | SHA-256 |
| --- | ---: | --- |
| [detector-b9df07d4.zip](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/releases/download/zhang-pre-shared-b9df07d4-20261109/detector-b9df07d4.zip) | 132732878 | `72fd4cf58d73ad03c4b480039ef4d3506e00580bcc20ef77acb0474efa1e22a0` |
| [normal-calibration-v2.zip](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/releases/download/zhang-pre-shared-b9df07d4-20261109/normal-calibration-v2.zip) | 320068396 | `d63076a66c7e0f6e35954c7276f1a147c523e72324c53974ade9957ad2494ba0` |
| [official-A-db18b274.zip](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/releases/download/zhang-pre-shared-b9df07d4-20261109/official-A-db18b274.zip) | 159026335 | `85bcebe8407f3ca99d4ea8ac828fa216c7078ccbdf93c58bd6223dadb8dc7c0d` |
| [official-B-b5e90454.zip](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/releases/download/zhang-pre-shared-b9df07d4-20261109/official-B-b5e90454.zip) | 189719298 | `4875a95d7a21f2e885a79f3eb6240d8eb9b0c7048c4c212c84ae334ce547fa58` |

每个 ZIP 内文件的完整大小与 SHA-256 均见 [归档清单](archive-manifest.json)。五个附件的服务端 SHA-256 和大小均与本机一致，登录凭据下的分段下载返回 206，ZIP／JSON 文件头正确。[服务端与下载核验记录](release.json)包含正式链接。仓库为私有仓库，团队成员需要登录有仓库访问权限的 GitHub 账号下载。

## 内容与读取

- `detector-b9df07d4/` 含冻结的 detector.pt 和 manifest.json，左右袖阈值分别为 1.2066080808639525、1.311397171020508。完整预测器的模型和包哈希由现有 `load_package` 校验。
- `official-A-db18b274/` 与 `official-B-b5e90454/` 含最终 A/B 完整 RGB、观测／动作、实跑源码快照、事件、配置和结局。B 还含实际材料片测量与前检记录。
- `normal-calibration-v2/normal-01/`、`normal-02/` 含两条新增正常原始试次和原始核验记录。其用途为第二轮正常校准，独立正常性审核 pending。
- 每条试次的 `rgb-frames.npz` 内 `rgb` 为 uint8、N×480×640×3，使用 `np.load(..., allow_pickle=False)` 读取。`observation-trace.json` 的 frame_index 对应 RGB 下标。同一渲染帧可有多个观测，编码前按渲染帧去重。
- 相机、控制器、时钟和源码在 `continuation-context.json`、`manifest.json` 及 source-snapshot 中。历史绝对路径作为来源记录保留，读取时使用实际解压目录。

普通文件核验和 RGB 读取只需 Python/NumPy。离线分数复算另外使用既有 Torch 和 PIL 编码接口。编码器权重通过仓库已有命令取得并校验。

```powershell
python -m research_tools.detection_encoder fetch-weights --output resnet18-f37072fd.pth
python tools/simulation/verify_official_ab.py "<解压后的A或B中fold-recovery目录>" --output "<新的核验JSON路径>"
python tools/simulation/verify_pre_observations.py --help
```

模型上下文和阶段映射以 [PR29 最终报告](../pre-ab-revision2-20261109.md)为准。PR27 使用其封存包和用途划分。b9df07d4 使用左右袖阶段、五帧过去窗口、原正常校准下限，并已将原 normal-03 转作二轮校准。复算时使用本次包清单及其 context_reference。

## 核验器改进

几何复算仅对 distance_m、cloth_height_m 使用绝对容差 1e-12 米、相对容差 0。键集合、试次身份、代次、时刻、窗口、状态、样本数继续严格比较。4 项回归覆盖平台尾差、超容差、非有限数、身份／状态／时间改变及键集合改变。真实 B 的几何和完整结局已用修订后的核验器复算通过。

## 交接后的审核

马可据完整 checkpoint 和 RGB 独立复算新包分数。胡可审核两条新增正常试次、最新 A/B/C 可见现象及 B 的人工异常时间区间。机器核验及材料共享完成记录与成员独立签核分别保存。最终区域代理、仿真几何持有、正式叠衣质量和物理停车仍保留各自适用范围。

用户本轮要求先处理归档和核验器，中文 PPT／讲稿整合后续继续。实际计时排练、上传、出席和课堂反馈目前未见新增完成记录。
