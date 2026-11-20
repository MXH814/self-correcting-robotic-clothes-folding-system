# 课堂版五屏原型 UI-20261120-R2

在 Edge 或 Chrome 中打开 `prototypes/ui/index.html`。“查看真实折叠记录”打开回放，两个 A/B/C 入口都指向 Z3 视频和逐帧来源。阶段取景页可读正常折叠实验及撤权与停车记录。仓库自带 Z3 视频、四张阶段取景和九试次检测回放。data_2、data_3 完整逐帧记录由团队轨迹包导入，导入命令见阶段取景页。课堂交付 ZIP 已含这两条轨迹。

## 单独导出

在仓库根目录运行 `python tools/ui-verification/export_ui.py classroom-ui.zip`。脚本把原型及回放引用的本地材料复制到新 ZIP，重写两个回放页和取景脚本的相对路径。解压后打开 `prototype/index.html`。若已导入 data_2、data_3，导出时会一并收录。

## 复跑交互流程

需要 Node.js、可供脚本加载的 Playwright，以及 Microsoft Edge。新建一个空目录，在其中运行 `node "<仓库路径>/tools/ui-verification/ui-recheck.cjs"`。如需检查导出副本，在命令末尾加上解压后的 prototype 目录。脚本在当前目录写入截图、界面文本和 recheck-verification.json。随本目录保存的结果来自仓库版的模拟事件检查，覆盖就绪、启动受阻、异常、等待静止、接管、归还检查、归还被拒、重新接管及结果页。首次使用者走查继续按 docs/design/user-walkthrough.md 记录。

prototype-version.json 记录课堂快照原始来源及三个核心文件的 SHA-256。
