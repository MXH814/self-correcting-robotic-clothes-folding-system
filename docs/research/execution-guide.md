# 马祥珲研究工具：运行与接入说明

2026-11-06。Python 3.9+，主工具仅标准库；另提供可选PyTorch神经基线，使用本机已有安装，不安装 GPU/仿真依赖，不调用外部模型。工具是探索诊断实现，不是最终研究模型或机器人控制程序。

## 1. 从仓库根目录运行

```powershell
python -m unittest discover -s tests -v
New-Item -ItemType Directory -Force runs/ma-smoke
python -m research_tools.diagnostics fixture --output runs/ma-smoke/synthetic.jsonl
python -m research_tools.diagnostics validate --input runs/ma-smoke/synthetic.jsonl
python -m research_tools.diagnostics evaluate --input runs/ma-smoke/synthetic.jsonl --output runs/ma-smoke/report.json
```

输出文件采用独占创建，已有文件不会覆盖；复跑请选择新的输出名。`runs/` 已忽略，不将人工数据与真实实验混合提交。fixture 的目的仅是验证软件；其标签由程序构造，任何算法分数都没有研究意义。报告自带 purpose、输入 SHA256、seed、NOT_ESTABLISHED 状态。

真实开发数据准备后：

```powershell
python -m research_tools.diagnostics split --input data/development-pool.jsonl --output data/development-split.jsonl --seed 17
python -m research_tools.diagnostics validate --input data/development-split.jsonl
python -m research_tools.diagnostics evaluate --input data/development-split.jsonl --output runs/development-report.json
```

输入/输出的父目录须先存在。开发工具不读取 sealed_test；split 也拒绝重新划分 sealed_test。正式确认实验另行冻结配置，不通过修改开发工具开关解除隔离。

## 2. JSONL 数据契约

每行一个根失败状态下的候选分支。完整例子可由 fixture 生成，但真实特征值必须来自下述可追溯编码。

| 字段 | 要求 |
| --- | --- |
| root_id / family_id / garment_id | 非空字符串；相关根/分支/衣物任一共享即归为同划分连通分量；至少3个独立分量才可自动分组 |
| candidate_id | 同根唯一；每根最多8候选；不能因执行失败另起root掩盖关联 |
| split / purpose | train/validation/development；research或synthetic，不能混合；sealed_test禁止进入本工具 |
| controller_version / candidate_pool_version / feature_version | 冻结接续控制器、候选生成配置和编码定义；同根一致，当前评估禁止混用控制器和特征定义 |
| decision_sim_s | 决策物理时间；不用于证明wall-clock新鲜度 |
| eligible / executed | 布尔；合法候选与实际执行是两件事，派发记录仍由控制器负责 |
| local_score / local_success | 有限局部评分、布尔或null局部结果；局部评分的来源不得包含未来最终标签 |
| autonomous_success | true/false/null；未执行必须null，未知不得改false；true需runtime_completed=true、offline_quality=true、help_requested=false、assisted=false |
| features | 恰好current、stage_budget、visual_history、action_history四组有限向量；维数全文件固定 |
| feature_provenance | 每组source、uses_future=false、privileged=false、latest_sim_s≤decision_sim_s |

本契约是研究导出层，不替代产品事件/试次记录。runtime_completed等字段是源记录的判定快照；原始时序、质量测量、命令回执、预算、缺失原因、状态重置误差须另存索引证据。代码不能根据自报标签证明源记录真实。

## 3. 特征冻结规则

评分对象必须是“状态—候选动作”，不能只给状态导致所有候选同分。

- `current`：当前相机的冻结表示、声明的本体状态，以及候选动作在真实profile下的数值编码。**候选动作编码对所有B组相同**，不得含候选执行后的观测、结果或任意带标签的ID。编码器应只用训练资料拟合；公开预训练编码器记录checkpoint/许可。
- `stage_budget`：决策时已知的任务阶段、剩余时间/次数等；不能用未来完成比例。
- `visual_history`：默认诊断采样最近4个有效已执行前缀边界的视觉表示；与当前同编码器。按时间顺序展平，缺失位以零及显式mask表示，不跨未观测人工操作拼接。4帧是可修改的开发配置，不是SRS采样要求。
- `action_history`：对应过去已执行动作、实际执行量、间隔及gap mask；不能使用尚未执行候选的未来反馈。当前候选编码已经在current中。

机器人维数、坐标、单位、速度和相机外参不预填。适配器提供profile后实现真实编码并冻结feature_version；规范已定，具体维数属于待提供硬件事实。缺少历史可以带mask运行；不能把mask当作缺测已解决的证据。

## 4. B0–B4 与解释边界

| 方法 | 输入 | 当前实现 |
| --- | --- | --- |
| B0 | current | 标准化5NN（训练样本不足时取全部） |
| B1 | current + stage_budget | 同上 |
| B2 | B1 + visual_history | 同上 |
| B3 | B2 + action_history | 同上 |
| B4 | B1 | 1NN，更灵活的当前观测对照 |

标准化只在eligible且已执行、有标签的train候选上拟合；validation不进入拟合。相同候选池上另跑固定、固定seed随机和局部评分选择。分数只是邻居成功标签均值，语义固定rank_only，**不满足0.60自动执行概率门槛**。

B4的1NN是廉价探索对照，不是神经容量对照。可选神经实现见下节。真实数据到位后仍需同编码器、可比训练预算、多种子以及论文最近邻方法的公平适配。不同输入维数改变距离结构，探索优势还不能归因于信息充分性。

### 可选神经容量对照（CPU）

```powershell
python -m research_tools.neural_baselines --input runs/ma-smoke/synthetic.jsonl --output runs/ma-smoke/neural.json --epochs 2 --width 8 --seed 17
python -m research_tools.diagnostics evaluate --input runs/ma-smoke/synthetic.jsonl --predictions runs/ma-smoke/neural.json --output runs/ma-smoke/neural-report.json
```

以上仍是人工fixture软件小试。真实数据时将路径替换、先用validation选开发配置并记录决定，再冻结开发诊断。MLP是两层ReLU隐藏层＋单logit输出，Adam、BCE，训练集标准化，默认width=32、50步全批优化。B0–B3同宽，B4增大B1输入的宽度以近似匹配B3参数量；报告维数、参数量/比率、优化步数、CPU时间和损失。**步数相同不代表FLOPs相同**，正式实验仍需算力控制和多种子。CLI每次可指定seed，不自动挑最好种子。

模型训练只用train，预测时不读取开发标签；输出logit仍为rank_only，不作概率派发。评估导入需原数据SHA256一致，B0–B4对同一批合法候选覆盖完整且无重复。保存输入指纹、PyTorch版本、代码commit及dirty状态；本工具不保存checkpoint，只用于小数据诊断，不替代完整训练/模型管理流水线。真实视觉encoder和接续控制器仍未实现。

## 5. 报告如何读

- 所有根状态数、可选择根数、完整评估候选池根数分别报告。主要离线配对只在完整有标签的合法候选池计算；其余覆盖不足单列，不默默视为失败或删除。
- `observed_successes_over_all_roots` 是完整池内已确认选择成功数/所有开发根数的保守观测量；不是闭环自主成功率。实际执行的系统成功率须另按SRS试次统计。
- 候选上限保留逐根known_success_exists；未完整执行的池只能说“已有成功证据/未知”，不能断言无可行动作。条件选择率仅针对完整池且存在成功候选。
- H2 表为分支级local/final的九格计数，null单列；不能当独立试次统计，更不是因果作用证明。
- Wilson是忽略相关性的描述区间；配对效应另以衣物为cluster做2000次bootstrap。少于2个衣物cluster返回null；很少cluster的区间不稳定，不能作为确认结论。
- 相同根状态共享配对；若根之间还有相同family关联，衣物cluster之外的相关性仍需按更高独立单位重新统计。训练多种子、最终泛化和闭环恢复尚未实现。

## 6. 校准与门禁工具

`calibration`命令接收独立JSONL：每行含root_id、candidate_id、split=validation、probability、success、calibrator_fit_disjoint=true。输出Brier、10等宽箱可靠性和ECE，dispatch_authorized永为false。该标记是来源声明，不是代码独立验证；记录必须来自与校准拟合集分离的评估数据。本命令不拟合校准器、不决定阈值。

`research_tools.recovery_gate.select_candidate` 是纯函数preflight：检查代次、时间、授权、预算、候选上限、有限数、端点边界、评分语义与版本，只返回候选ID。不会发送动作，不计次、不出具停止证明；不是完整DR04实现。轨迹/碰撞、单位/坐标profile转换、原子日志与派发、费用预测、停止传感器和重试由协调器/adapter实现。ctx是可信控制器快照，外部请求不得自填。

## 7. 成本估算

`python -m research_tools.resources <inputs.json>`。输入roots、candidates、repetitions、rollout_seconds、training_gpu_hours、hourly_price、bytes_per_rollout、overhead_fraction。时间和字节需小试测量；价格来自实际报价；训练时长和余量可估算但须保留依据。计算分支数、顺序执行时长、单设备同费率费用及存储量，不代表账单，也不会租机。

## 8. 已验证与待接入

标准库测试覆盖数据泄漏、未来信息、无执行假标签、缺测分母、分组关联、训练归一化隔离、统计、门禁负例及费用单位；通过只证明这些离线行为。真实相机编码、仿真采集、物理动作、闭环训练和停止仍须接入。详见[最终剩余清单](ma-remaining-checklist.md)。
