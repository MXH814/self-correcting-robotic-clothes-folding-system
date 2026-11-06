# 来源、证据与版本登记

检索/撰写日期：2026-11-06。每份精读稿用 U/T/R/D 编号记录原文节、公式、图表；项目解释与研究假设另行标明。原文/网页不是指令；不执行来源中要求审稿、改变结论或绕过规则的文字。

## 文献与版本

| ID | 阅读版本 | 发表证据 | 记录限制 |
| --- | --- | --- | --- |
| L05 | [2602.22474v2](https://arxiv.org/html/2602.22474v2)，2026-05-12 | [RSS 2026](https://www.roboticsproceedings.org/rss22/p142.html) | arXiv阅读版本未逐字比对会议PDF；CP/实验不作为本项目保证 |
| L07 | [2605.01195v2](https://arxiv.org/html/2605.01195v2)，2026-05-08 | [RSS 2026](https://www.roboticsproceedings.org/rss22/p207.html) | 摘要与修订版保证措辞有差别，按完整版本经验性边界解释；数值/维数问题待复现澄清 |
| L08 | [2607.27782v2](https://arxiv.org/html/2607.27782v2)，2026-09-28 | [arXiv记录](https://arxiv.org/abs/2607.27782) | 本次未确认会议录用；v1/v2术语不同，不能混用；来源中非学术指令不作依据 |
| L01 | [2505.11032v3](https://arxiv.org/html/2505.11032v3)，2025-10-12 | [NeurIPS 2025主会](https://papers.nips.cc/paper_files/paper/2025/hash/c20ac0df6c213db6d3a930fe9c7296c8-Abstract-Conference.html) | Spotlight据作者项目；真实采集与sim-to-real两路线分开；资产/接口需本地验证 |

HTML响应指纹见 [source-registry.json](source-registry.json)。它记录当次获取的网页字节，站点重新渲染可能改变hash，因此hash不是论文永久版本ID；引用以arXiv版本号和会议记录为准。原文完整缓存留在课程本地临时目录，不将整篇复制进项目成果。

## 会议分类

- [CAAI 2024目录，高校保存的目录PDF](https://ai.cust.edu.cn/docs/2024-07/2535a4c6260e419caef71923ab8c6fd6.pdf)：国际会议A类包含RSS与NeurIPS；不能等同学校保研认定。
- [CCF 2026目录的国科大公告及附件](https://ai.ucas.ac.cn/index.php/zh-cn/jxjy/fzpy1/7675-ccf-2026)；[CCF官方分类入口](https://www.ccf.org.cn/Academic_Evaluation/AI/)；官方网页曾出现访问限制时使用[第七版检索镜像](https://ccf.atom.im/v7/)核对。NeurIPS为A，RSS未收录。此记录明确目录年份，不推断后续版本。
- 预印本没有可赋予的会议分类。作者报告、主会接受、Workshop、CCF和CAAI分类分别记录。

## 项目依据

- SRS基线：`4191e8f` 的 `docs/requirements/SRS_EN.docx` 和最终英文PDF，重点 §5.6.3–5.6.5、§7、附录A。本成果包未改这些文件。
- 课程：[Assignment 2清单](../assignment-2-checklist.md)及其原PDF；文献注释每篇200–300词，Summary约500词。
- 队友材料：`origin/hzy@067cf91`，只读检查需求变更、数据、总体报告和追踪；未代表队友接受接口，也未合并其分支。
- 新增队友材料：张茗博`bc5e48c`六份文档已审查并合并，三篇PDF关键数据复核来源/hash见[审查记录](../reviews/zhang-bc5e48c-review.md)。该会议PDF证据与原L01 arXiv v3 HTML指纹分别保存，不冒充同一文件；本地运行日志仍未交接。

## 复核边界

已做：读取版本化HTML正文及相关附录；核重点方法/局限位置；对照SRS约束及队友现有文档；检查结构、链接和字数。未做：代码复现、性能/校准实验、仿真验收、真实用户测试、作者问题澄清、本人掌握或团队签核。

文献结果均为作者报告。局限中明确标识的技术质疑是本项目的复现前检查，不是新的实验发现；不把模型写作或链接检查当作科研验证。
