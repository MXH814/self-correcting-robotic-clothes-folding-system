# ADR-MA-003 · 在线信息隔离与根轨迹级数据治理

状态：Accepted as implementation baseline，2026-11-06；依据组长授权采纳来源隔离与分组策略，队友可审核修订，真实数据尚待接入。AI05/AI07是既有要求；见[执行决定](../../research/ma-owner-decisions.md)。

## 背景与备选

仿真可导出完整网格/接触/未来结果，RedFlow 的进度平滑也可以利用整轨迹。这些有利于离线标签，但会造成在线信息泄漏。连续帧随机划分会把同根状态的分支放进训练与测试。

备选 A：一份全字段记录/随机按帧划分，方便却泄漏风险高。备选 B：只保存在线帧，边界清楚但无法离线核质量和注入。备选 C：双层记录、来源白名单、根轨迹/衣物/分支族分组，兼顾研究与审计，维护成本较高。

## 拟议决定

采用 C。OnlineObservation 仅声明传感器来源，OfflineEvidence 独立路径/读取权限。大文件存受控存储，Git 保存清单、hash、配置和汇总。先分组再计算检索库、归一化、校准与超参，不跨 sealed test；相关帧/分支不作为独立统计单位。

平台已按[ADR-MA-004](ADR-MA-004-simulation-platform.md)选用Isaac Sim 4.5 / DexGarmentLab；马已确认在张电脑完成基础复跑，后续统一在该电脑执行，不新增换机或重复基础复跑。不为采用平台改变在线来源约束，未经验证的布料快照不称精确同状态对照。hzy字段仍按实际审核/映射，不自动批准变更。

## 后果与验证

代价是清单与存储权限管理、缺测/版本记录。用一个根轨迹派生两分支验证同 split；主动放入未来标签/隐藏接触字段时在线校验应拒绝；同衣物跨集冲突、重复快照、检索跨集必须被发现。质量缺失保存 NOT_ASSESSED，不填成 PASS。

后续PoC在张电脑固定seed/profile并保存观测、终态、人工、试次标签和SRS地标容差，供结果复核；不要求重复已关闭的基础复跑或另找第二台电脑。同seed不自动等于完全确定，物理误差、资产/许可不符和快照失败触发重审。

来源：[DexGarmentLab D01–D05](../../research/papers/L01-dexgarmentlab-reading-note.md)、[RedFlow R02/R03/R06](../../research/papers/L08-redflow-reading-note.md)、SRS §7.3–7.5。
