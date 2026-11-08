# Fold Tops 真实轨迹纯数值导出记录

记录日期：2026-11-07；负责人：张茗博；状态：**作者机导出并上传私有 GitHub Release；接收方下载和第二人复核待确认**。该包是正常示范的历史观测，不能当作恢复实验结果。

## 来源与导出

- 来源：作者机 2026-11-04 图形演示产生的 `data_2.npz`；SHA-256 `2309165bccd101c6ad65460716844d4f47d4b71e2f2f3dd775ecf37c47dac552`，26,983,793 字节。来源和最终图像见[交接指南](handoff-guide.md)及[资产清单](artifact-manifest.json)。该数据是自采上游示范，不是 HALO 策略评测。
- 工具：组长提供的 [`export_numeric_trajectory.py`](../../../tools/simulation/export_numeric_trajectory.py)，按[数据接入说明](../ma-data-intake-progress.md)在作者机运行；仅在确认来源可信并匹配 hash 后启用对象数组读取。原始 NPZ 使用 pickle，hash 本身不能证明可信。
- 结果：`manifest.json`、`observations.jsonl` 和 77 个 RGB `.npy`；stage_1、stage_2、stage_3 分别 27、27、23 帧。纯数值图像使用 `allow_pickle=False` 读取，数据包为离线研究输入，`online_authorized=false`。

## 核验

作者机运行 `research_tools.legacy_observations.load_export`，核对 manifest、记录文件与各 RGB 哈希、形状、帧序和阶段边界；随后将 77 帧的关节值和 RGB 数组逐一与可信原始轨迹对应记录比较，均一致。第 0、2、27、54 帧的 4 帧历史窗口检查表明：历史不包含当前帧，阶段起点重置并补缺失掩码。这是数据转换核验，不是独立复跑或研究假设验证。

导出 manifest SHA-256：`b884797c0a8f85ffff94c26391f9c292b82be834222e8d1395c23b3c57c68d6c`；`observations.jsonl` SHA-256：`834bc6727f62b09a9f2681b4a28da1675726fcba1d735e57c963fdfe2ec2d19e`。导出目录文件合计 71,133,436 字节。

## 交接包及限制

作者机生成 `fold-tops-data2-numeric-20261107.zip`，24,867,984 字节，SHA-256 `6584a58167d25bef6da25eecdaf8436df8b93b1ad9cea6d8fe01f9fb70986a16`。ZIP 完整性检查通过，包含 79 个文件：77 个图像数组、记录和 manifest。

压缩包已上传[团队私有 GitHub Release](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/releases/tag/handoff-fold-tops-20261108)，仓库成员登录后可下载 data2 及逐文件清单；GitHub 显示的大小与 SHA-256 与上方一致。接收方是否已下载、校验和接入仍待确认；接收方先通过可信渠道核对 ZIP hash，再依据[数据接入说明](../ma-data-intake-progress.md)校验 manifest 和历史窗口。

原始时间、命令、ACK、动作语义、成功标签均未记录，导出保持 null；关节名称/单位和相机来源未验证。RGB 与关节值来自相同记录，不据此宣称真实时钟同步。该正常示范不能替代抓偏/滑移案例或 H1/H2 结果。
