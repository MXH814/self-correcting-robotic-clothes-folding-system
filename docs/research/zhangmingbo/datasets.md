# DexGarmentLab 数据集及下载链接

本项目当前使用 DexGarmentLab 官方的 **Fold Tops 上衣折叠示范数据**，用于仿真流程和训练数据准备；它是官方数据集中的一个任务数据包。

- [DexGarmentLab 官方数据集主页](https://huggingface.co/datasets/wayrise/DexGarmentLab)
- [官方数据集文件列表](https://huggingface.co/datasets/wayrise/DexGarmentLab/tree/main)
- [Fold_Tops.zip 文件页面](https://huggingface.co/datasets/wayrise/DexGarmentLab/blob/main/Fold_Tops.zip)
- [直接下载 Fold_Tops.zip](https://huggingface.co/datasets/wayrise/DexGarmentLab/resolve/main/Fold_Tops.zip?download=true)
- [Garment.zip 衣物资产文件页面](https://huggingface.co/datasets/wayrise/DexGarmentLab/blob/main/Garment.zip)
- [DexGarmentLab 官方代码仓库](https://github.com/wayrise/DexGarmentLab)

## 当前本机数据

此前下载的 Fold Tops 包大小为 2,667,837,749 字节（约 2.67 GB），包含 100 条示范轨迹，以及对应的 100 张图片和 100 个视频。检查到 72 个不同的衣物资产路径；100 条示范不代表 100 件不同的衣物。原始下载包的 SHA-256 为：

`0624b8f40809f017367168d71d16bf0ebe329f75d78e994d7f623f7d56dbe07b`

本机已将示范数据处理为三个阶段的 Zarr 数据，用于训练流程的短时可行性测试。当前结果不代表已经完成论文全部训练或实验复现。

**区分数据与资产：** Fold_Tops.zip 是上衣折叠示范数据；Garment.zip 是衣物仿真资产，不能当作同一个数据包。具体使用与许可请查看官方页面和相应资源说明。

链接核对日期：2026-11-06。仓库只记录来源链接和说明，数据包保留在实验机本地。
