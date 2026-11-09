# Z1/Z2：RND-OE 观测分支仿真接入交接

2026-11-08。按用户提供的新版《第三组_Pre核心演示完善与三人分工(1).md》及其后明确指令执行。张负责真实观测、仿真接口和场景运行；马负责视觉编码及在线检测；胡负责正常数据拟合、校准和离线验证。PPT 工作暂后，先推进 Z1/Z2。

## 方法边界

保留现有 GAM＋官方脚本 Fold Tops 控制器。只适配 FIPER 的 RND-OE 观测异常分支，**不要求 SADP_G、VLA、生成式动作采样或 ACE**。不复制脚本动作形成伪预测样本。未载入编码器、RND 和阈值时输出 UNKNOWN 并拒绝恢复；正常数据采集是独立、显式的“恢复关闭”模式，不冒充检测验收。

作者代码：[learnsyslab/fiper](https://github.com/learnsyslab/fiper)，核对提交 `13d79c5c3069def843e454787ff128defc249838`，MIT。`configs/eval/rnd_oe.yaml` 仅要求 `obs_embeddings`；`evaluation/method_eval_classes/rnd_eval.py` 实现 RND 推理；窗口及校准位于 `base_eval_class.py` 和 `evaluation/utils.py`。本交付不复制作者算法，也不代替马/胡完成模型和阈值。

## 当前观测与兼容性

沿用完整恢复链的固定环境相机：640×480、uint8、RGB，位置约 `[0,3.6,3.2]`，朝向 `[0,0.5,0.6]`，焦距/水平孔径 2.4，DomeLight 1000；预热12物理步，物理步长1/60秒，每3步采样，并在阶段边界补采。每次记录实际相机矩阵、内参和位姿，不以文档近似值替代文件。

每个观测有试次ID、观测ID、图像索引、相机渲染仿真时刻、读取起止的仿真/本进程 monotonic 时钟、60个具名关节位置及60个速度。墙钟与仿真时钟不直接相减。约20Hz是配置采样目标，实际间隔由每条 trace 核验。

可用特征：原始图像921600个 uint8 值；本体状态120维。已有离线 `rgb_grid/8` 为192维均值格编码，与120维本体组合为312维；这是输入接线基线，**不是新交付的视觉编码器或已选定的RND特征**。新的视觉embedding及其维数、归一化、权重和预处理引用均由马提供，目前留空。GAM用于初始化操作点，不宣称当前已导出逐帧GAM特征。

官方100条示范尚未逐条确认与本相机、灯光、连续采样和阶段口径匹配，不能直接纳入正常分布。既有data2/data3为稀疏记录且缺原始时钟；#18是240×180视角，#22是移动近景。本批重新导出匹配相机的完整正常试次，不把旧数据静默混入。

## 入口和导出

```powershell
python tools/simulation/run_pre_normal_batch.py <新的批次目录>
python tools/simulation/verify_pre_observations.py <单试次目录> <新的导出目录>
```

批次固定3次独立进程、不注入故障、不自动重试。每次先保存采集源码原字节快照、启动参数；再输出 `rgb-frames.npz`、`observation-trace.json`、`pre-demo-events.jsonl`、`continuation-context.json`、`pre-observation-config.json`、最终代理点云及哈希清单。名称中的 `fold-recovery-*` 和 `full-fold-recovery.json` 复用旧存储格式；实际模式以 `collection_mode=normal_controller_only`、`recovery_enabled=false` 及 trace scope 为准。

正常控制阶段包含首袖/第二袖/衣身阶段边界，以及抓取趋近、提起、移送和计划释放意图。阶段表示控制器意图，不是独立检测标签。`observations.jsonl` 将逐帧图像、时钟、阶段和相机引用导出供马/胡读取；原始RGB保存在NPZ内，使用 `allow_pickle=False`。

整条试次保持 `dataset_use=unassigned`；胡分配拟合/校准/开发用途，同一试次不得按相邻帧拆分。三条小样本不支持论文统计保证。即使官方区域代理通过，仍需胡核正常性和适用范围。

## 观测—恢复接口

`tools/simulation/pre_runtime_bridge.py` 提供显式回调：`detect(packet)`、`execute_macro(obs, report)`、`observe_after()`、`check_after(fresh)`。其中 `execute_existing_macro()` 直接连接既有提前提案和五操作执行器。

马接线时可直接调用 `bind_existing_runtime(chain, robot, original_move, pick, lift, orientation, detect=detect, check_after=check_after, emit=emit)`。它绑定既有宏，并在宏后推进3个物理步取得新图像；调用 `bridge.handle(observe_live(chain), expected_hold=True)` 后仅在返回 `CONTINUE` 或 `CONTINUE_AFTER_RECOVERY` 时允许原控制器接续。UNKNOWN返回 `HELP_NO_NEW_DISPATCH`。拟合和离线推理用 `pre_observation_reader.iter_observations(trial_directory)`，与在线 `observe_live(chain)` 使用相同RGB/观测字段；编码及窗口处理继续复用马同一实现，不在张侧另外训练。

检测器只收到白名单：`trial_id, observation_id, rgb, capture_clock, phase, joint_state, camera_reference`；不传入注入条件、注入时刻、未来结局。检测返回同试次/同观测的 `NORMAL/ANOMALY/UNKNOWN`，以及 `method, score, threshold, model_ref, threshold_ref, preprocessing_ref`；未知时分数/阈值可空。方法标识应写“FIPER-RND-OE观测分支适配”，不写完整FIPER复现。

图像另带 `frame_index`、`rendering_time_s`，同一渲染帧可能因动作/阶段边界读取多次。马/胡决定窗口按唯一图像还是观测记录推进时应保持离线/在线一致，不能在两侧采用不同去重规则。恢复后检查若使用几何备用，独立方法标识与参数引用不得写成RND分数。

只有有效异常事件、授权、无在途动作且预算有余时才调用宏。宏实际完成后读取新的同试次观测，恢复检查通过才接续。缺方法/阈值、旧观测、跨试次、异常或未知检查、执行异常均锁定新派发并记求助；重复观测不重复执行。该锁定不证明物理静止、不授予人工操作权限。

当前接口分支测试使用明确的 `SOFTWARE_STUB`，不是仿真检测成绩；马/胡参数到位后才开展A/B实跑。C使用 `run_fiper_pre.ps1` 实跑缺检测条件的拒绝分支，真实结果另附索引。

## 最新任务状态

- Z1：采集入口、原始观测导出、相机/阶段记录、恢复回调接口已实现。3个完整正常试次均通过逐文件指纹、RGB有效性、时钟/反馈与三阶段完整性校验，共1401帧RGB、1428次观测、2318条派发/反馈。独立正常性审核及用途划分仍交胡完成。见[试次索引](pre-rnd-oe-20261108/trial-index.json)、[实际样例](pre-rnd-oe-20261108/observation-sample.json)、[相机配置](pre-rnd-oe-20261108/camera.json)。
- Z2 A/B：等待马的编码/检测回调和胡的已验证模型/阈值；不预填通过。
- Z2 C：新版观测分支已实跑并核验。试次`70e36c5e-c0cc-458e-8c43-0ace14b91fc2`，59帧RGB，拒绝前86条派发、拒绝后0条派发、恢复0次，结果UNKNOWN并锁定新派发。缺项仅为编码/预处理、观测embedding、RND与校准引用；不要求策略或动作采样。见[实测审核](pre-rnd-oe-20261108/scenario-c-audit.json)。不把进程退出/拒绝动作称为产品物理停止验收。首次旧完整FIPER依赖试次另留本地历史，不混入新版验收。
- 系统内存或显存不足造成实验无法进行时，立即告知用户并停止后续批次，不自动重复尝试。

本轮3次正常采集及新版C运行均未发生导致中断的内存/显存不足。125项Python软件检查中115通过、10项因测试解释器无Torch等可选环境条件跳过；跳过不作通过。正常采集与C分支的真实运行另外逐文件验证，不由单元测试替代。源码在本地`feat/zhang-pre-observation-interface`分支，尚未上传；数据包480177447字节，SHA-256见[包清单](pre-rnd-oe-20261108/package.json)。

本地原始证据位置：`C:/Users/Lenovo/Desktop/系统分析与设计/output/Pre_Z交付_20261108/`。大型文件不强制加入Git；本文件和后续结果索引用于交接，尚未对外上传。
