# PR30 与 PR31 接收端独立审阅

审阅日期：2026-11-09。PR30 核定提交 `c80ca406f2288e6927957cfcea25e85ff907a9ad`，PR31 核定提交 `30ba4a34af0e7c777e2d70260a1fa3b5c95996f2`。两项已批准并合并，分别为 `d0f5b5c`、`b9a571a`。

## 结论

胡的新 A/B/C 判读与展示表可用；张的新模型、全部 A/B RGB 和新增两条正常材料交接已关闭。组长已据完整原始 RGB、官方编码器和冻结 checkpoint 完成 A/B 全部记录调用的独立分数复算，无需再等同一份材料。尚未关闭的是新增正常性的独立审核、真实个人确认和课堂事实，以及后续产品/统计验收。

## PR30 案例与图像

查看了九帧局部图与结果页，并逐项核对原始 Z3 CSV。视频帧340、342、344对应B源帧72、74、76，渲染时刻分别6.683333682、6.783333687、6.883333692秒。图像支持投影分离区间，未把它包装为精确接触真值。五份主流告警、一次额外前检刷新和一次恢复请求分开登记。A是正常对照，C是缺包求助后零新增派发；正式质量、物理静止和人工权限没有被图像代签。

[案例判读及素材](../design/hu-abc-case-review.md)保留尚待本人确认的归属。压缩远景判读不作为正式检测延迟的分母或精确故障起点。

## PR31 大文件与完整重算

从私有 Release 实际下载四个 ZIP，共 **801,546,907 字节**。归档清单 SHA 与提交/发布一致，228个内部文件逐项核大小与SHA，完整读取压缩流后才解压到新目录。没有改写原始文件。

| 内容 | 核验结果 |
| --- | --- |
| 当前 checkpoint | 132,726,810字节，SHA `6decf0155074222b7fd69a720db103b9bbd87e3b7f3034b4b193db74745b4dd4`；包ID、模型元数据及张量严格加载通过 |
| A 全部主检测 | 465次，从完整RGB逐次编码和推理；身份、代次、包、上下文、阈值、状态、原因及观测时刻完全一致 |
| B 全部主检测及前检刷新 | 492次主检测加1次刷新；按捕获顺序重建同一因果窗口，判定字段完全一致 |
| A 数值尾差 | 原始分数最大绝对差 `2.6226043701171875e-6`，聚合分数 `1.0013580322709714e-6` |
| B 数值尾差 | 原始分数最大绝对差 `2.1457672119140625e-6`，聚合分数 `9.29832458362867e-7` |
| 完整执行复核 | A/B原始轨迹、源码指纹、记录、点云通过；B宏后13次、接续23次几何重新计算通过 |
| 软件回归 | 本机205项通过，无跳过。首次运行缺少imageio，接入先前已存在的临时依赖后完整运行通过，未修改系统安装 |
| 新增正常机械接收 | 两条试次分别466/467 RGB帧、474/475观测、767/775派发；身份、相机和完整正常流程可读取，未代签正常性判断 |

数值复算预先采用绝对容差 `1e-5`，仅用于模型分数。离散判定与阈值全部严格相等。重算使用 batch=1 和同一官方ResNet18权重，没有重新训练或调整阈值。它验证记录的RGB到分数/判定链，不是在线时延重测或原论文完整复现。

几何核验修复只给 `distance_m`、`cloth_height_m` 绝对容差 `1e-12`米，相对容差0。身份、时间、窗口、状态及样本数继续严格比较；新增四项回归覆盖正常尾差和错误反例。没有降低实际物理判断的阈值。

## 可重做的证据

- [完整归档核验](evidence/pr31-archive-audit.json)。
- [A全部检测重算](evidence/pr31-A-detector-replay.json)与[B全部检测和刷新重算](evidence/pr31-B-detector-replay.json)。
- [A完整执行核验](evidence/pr31-A-execution-audit.json)与[B完整执行核验](evidence/pr31-B-execution-audit.json)。
- [解压/指纹工具](../../tools/analysis/verify_shared_pre_archives.py)与[RGB逐次重算工具](../../tools/analysis/replay_pre_detector.py)。
- [下载与原始指纹](../research/zhangmingbo/shared-pre-artifacts-20261109/README.md)。

重算命令，输出文件须为新的路径：

```powershell
python tools/analysis/verify_shared_pre_archives.py <archive-manifest.json> <ZIP目录> <新解压目录> --report <新报告.json>
python tools/analysis/replay_pre_detector.py <A或B的fold-recovery目录> --package <detector-b9df07d4目录> --encoder-weights checkpoints/detection/resnet18-f37072fd.pth --output <新重算.json>
python tools/simulation/verify_official_ab.py <A或B的fold-recovery目录> --output <新执行核验.json>
```

## 后续归属

胡继续审核两条新增正常记录的持有、计划释放、歧义与范围；张统筹最终PPT/讲稿、实际排练、上传及反馈记录。马同步现行设计、版本和技术结论并终审。不用重新采相同A/B、换机安装或重复交模型。正式统计检测效果、SRS质量与产品停车仍需各自证据。
