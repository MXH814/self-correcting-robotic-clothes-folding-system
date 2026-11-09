# 目标相机检测包与 A/B 接线：技术审核草稿

这份快照供马审核，包含本机开发检测包、训练和校准证据、逐帧分数，以及 A/B 仿真入口的当前代码。A/B 联调仍在进行，当前 PR 不代表 A/B 验收通过。

## 与胡的交付的关系

胡的目标相机检测包见 [PR #27](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/27)。本目录保留的是张侧本机独立开发的另一份包，阈值、分数和文件哈希均应按本目录记录识别；请马比较两份实现和误报，不将两份结果混用。

三条正常观测原始数据已由 [PR #26](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/26) 提供，数据附件 SHA-256 为 `a2e4c4e22641b37108b90b14b658730f0a085c5185b8bb822b1c604ff2e5b5ac`。

## 需审核的文件

- `package/detector.pt` 和 `package/manifest.json` 是完整开发包；`resnet18-f37072fd.pth` 是编码器权重。大文件由 Git LFS 保存，检出后执行 `git lfs pull`。
- `partition-plan.json` 固定 normal-01 用于拟合、normal-02 用于校准、normal-03 用于留出开发验证，按完整试次划分。`technical-review.json` 记录的是本次代理抽样技术审核，独立人工审核仍待完成。
- `normal-*-phase-map.json`、`normal-*-features.jsonl`、`normal-*-review.jpg` 保存逐帧阶段、视觉特征和抽样画面。`intake.json` 与 `shared-context.json` 保存数据来源和上下文。
- `train.log`、`original-fit-manifest.json`、`runtime-parity.log`、`runtime-parity-result.json`、`normal-*-runtime-parity-scores.jsonl` 记录训练、经验阈值、数值路径对齐和逐帧输出。输出头以外的预测器也参加训练。拟合仅使用 01，阈值来自 02 的窗口最大值；03 没有用于选阈值。
- 原拟合阈值 `1.2066079378128052` 与按在线 batch=1 重新计算的 `1.2066080808639525` 相差约 `1.43e-7`。重新计算使用原校准试次，模型参数未更改，`package/manifest.json` 记录父包及调整原因。请重点审核这个数值一致性处理是否适合当前实验。
- 留出试次 normal-03 有 10 个报警观测点，仿真时间 14.916667–15.416667 秒。请结合图像和阶段判断原因；单条校准试次无法支持统计误报保证。
- `partitions.json` 和模型元数据保留生成时的本机绝对路径以保护包身份。外机复跑应在新文件中将特征与审核记录路径改为该目录下的对应文件，保留原始哈希，不改写已绑定的模型元数据。

## 接线与验证

`tools/simulation/official_ab_evidence.py`、`official_pre_adapter.py`、`pre_execution_support.py` 和 `run_official_ab.ps1` 是当前连续监测、恢复许可和仿真入口。正常释放阶段由控制意图映射；故障注入不作为检测器输入。请核对动作门禁、告警新鲜度、测量前检、宏执行和独立的宏后几何持续窗。

几何检查使用仿真内部材料点和诊断阈值。前检记录同步脚本、关节状态、队列和采样 IK 的证据，产品权限、碰撞与接触力限制仍需独立验收。

本次隔离快照的专项测试结果为 37 项通过，覆盖 A/B 入口、适配器、执行前测量和阶段映射。此前 63 项包括观察检测器测试，日志在原本机 `AB_detector_dev/validation/targeted-suite.log`。所有测试中的合成输入和许可属于软件 fixture。

A 的首次入口试验暴露 SDK 参数兼容问题，已修改；第二次试验在进入折叠前因相机图像缺失或均匀而中止。主聊天继续联调，后续结果以同一试次的原始日志与核验为准。
