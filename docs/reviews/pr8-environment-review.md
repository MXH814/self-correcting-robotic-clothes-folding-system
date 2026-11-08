# PR 8：固定环境准备材料审查

2026-11-08。[PR #8](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/8)，核对提交`51b72e0`，已批准并合并。[批准记录](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/8#pullrequestreview-5816836350)，[普通评论区后续事项](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/8#issuecomment-6717994967)。未发现阻碍本批材料入库的问题；目标机实际部署和恢复实验不在本次通过范围内。

## 已独立执行

- 在隔离worktree复跑41项Python测试、PowerShell启动器回归和交接样例审核。启动器测试包含退出码7的预期失败夹具，已打印`SIMULATION_LAUNCHER_TESTS_PASSED`；调用者残留`LASTEXITCODE`不等于断言失败。
- 通过官方GitHub API核对固定commit `e4e298e696bae5d866ded3b31e0ae27becea5376`的完整树：761个blob，未截断。原作者归档逐个匹配该树属于作者记录，本机未取得原归档，不代称重新完成761项payload比较。
- 逐项读取官方PyPI版本元数据：50个指定wheel文件名和SHA-256均匹配，Python 3.10.15满足其`requires_python`声明。没有下载/安装这些wheel；这些检查不证明全部传递依赖或导入成功。
- 584项资产路径集合及archive归属与既有下载清单一致；无重复路径，字节合计296,488,662；SHA256格式、JSON和变更文档的28个本地链接、代码围栏及diff检查通过。真实资产未在本机获取，不代签584项文件内容核验。

证据摘要及逐项wheel元数据核验见[机器可读记录](../research/evidence/pr8-environment-review-20261108.json)。

## 对当前任务的影响

**固定源码、带哈希依赖和资产获取/核验入口已补齐。** 不再重复要求作者分享旧main ZIP或全部wheel包，可按[目标机准备步骤](../research/zhangmingbo/second-machine-install.md)开始实际部署。

接下来分别记录：目标机安装/独立复跑；运行时关节/单位/时钟、命令/ACK和停止测量；抓偏/滑移、可比重置、合法恢复候选及固定控制器接续结果。后两项仍由张茗博提供运行与采集支持，胡知鱼审核标签，马祥珲接入算法和诊断。目标机操作、作者机测试、正常数据编码和恢复性能是四种不同证据。

作者使用重建依赖的无窗口测试由人工停止，未得到通过标志；不能据此认定成功、程序错误或根因。41项为PR分支测试数量，合并马祥珲新增代码后以最新整合测试记录为准。
