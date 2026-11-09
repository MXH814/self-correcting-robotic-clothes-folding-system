# 匹配相机的 RND-OE 检测包和独立正常复验

[下载检测包及三份逐帧报告](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/releases/download/hzy-matched-detector-20261109-v1/hzy-matched-detector-20261109-v1.zip) · [附件指纹](evidence/matched-normal-detector/release.json) · [模型 manifest](evidence/matched-normal-detector/manifest.json) · [独立复验曲线](evidence/matched-normal-detector/normal-03.png)

固定阈值 **1.1895795584**。独立正常试次 normal-03 的 46 个可判窗口中，36 个在阈值内、10 个连续越线，形成 **一次误报片段**（HOLD，14.917–15.367 仿真秒，峰值 1.296235）。该试次无注入或恢复，采集时检测关闭。结果来自离线加载后的因果重放。保留此结果交马复核，尚无异常新试次或告警驱动的仿真恢复结果。[逐帧开发报告](evidence/matched-normal-detector/normal-03-scores.jsonl)

## Normal review

张的[原始交付](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/tree/d777879/docs/research/zhangmingbo/matched-normal-data-20261109)含三个不同试次 ID，原始 ZIP 为 480,177,447 字节，SHA-256 为 `a2e4c4e22641b37108b90b14b658730f0a085c5185b8bb822b1c604ff2e5b5ac`。接收端核了哈希、ZIP CRC、每条 manifest 指纹、连续图像／读时钟、动作反馈和三阶段结束。三次均记录无注入、未执行恢复宏。对照两臂提起、移送、计划释放及末态画面，未发现足以排除其中某次的宏观异常，故按正常采集用于本轮开发。远景和末态区域代理不能证明持续接触或产品质量。[原始帧抽查](evidence/matched-normal-detector/normal-review.jpg)

与 #24 目标记录逐项比较，相机、照明、执行配置、预处理和上游控制源码指纹一致，衣物为 TCLC_018。三条正常记录彼此使用相同采集包装；该包装与 #24 的恢复采集包装指纹有差异。模型 manifest 绑定该次正常采集的上下文，后续部署应核实本机上下文再接入。[完整配置](evidence/matched-normal-detector/sensor-context.json)

| 用途 | 试次 | 唯一帧 | 计划提起／持有帧 | 可判窗口 |
| --- | --- | ---: | ---: | ---: |
| 拟合 normal-01 | eff5d921-804f-4aeb-b1cb-2fe6d462ee23 | 468 | 63 | 47 |
| 校准 normal-02 | a4d9c33f-d5e9-40d2-985d-0b06f5f3a61e | 466 | 61 | 45 |
| 独立开发复验 normal-03 | c9eb5255-24f9-451e-88c1-837a1842b73a | 467 | 62 | 46 |

三条按目录顺序预先分工，保持整试次、原始数据源及血缘隔离。按采集代码中左右臂 `lift` 与 `transfer` 的控制意图映射至 LIFT 和 HOLD，计划开手另标 RELEASE。模型只读当前 RGB 编码和允许阶段。显式按唯一渲染帧去重，每次阶段切换重新暖窗；各试次 16 个暖窗帧、405 个非支持阶段帧均为 UNKNOWN。正常释放处按设计豁免。每个用途仅一条试次，阈值等于唯一校准试次的窗口峰值。不能据此估计总体误报率或检出率。[分配与源指纹](evidence/matched-normal-detector/review.json)

## 运行与交接

在仓库根目录运行。原始 ZIP 解压目录下应能看到 normal-01、normal-02、normal-03。使用项目已有的 ResNet18 官方权重，程序校验其完整指纹。

```powershell
python -m research_tools.detection_encoder fetch-weights --output resnet18-f37072fd.pth
python -m research_tools.matched_normal_detector --source D:/evidence/matched-normal --weights resnet18-f37072fd.pth --output D:/evidence/matched-fit
```

调用 main 的完整 `fit`、`load_package` 和 `OnlineObservationDetector.detect`。保持默认 10 个 epoch、512 维编码、128 维目标、连续五帧均值和经验分位 0.95。输出包含特征文件、相对路径划分清单、完整模型和逐帧报告；源码不写回采集记录。在线加载请将解压出的 `package` 目录、官方编码器权重和经实际配置核实的 context_reference 传入[马的运行时](../../research_tools/detection_runtime.py)。先复核误报片段，再由张在新正常／异常试次记录在线行为。模型不授予执行权限；本轮按原阈值封存，不在 normal-03 上反复调参。
