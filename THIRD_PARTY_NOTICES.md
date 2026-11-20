# Third-party notices / 第三方声明

## Experimental dataset / 实验数据

Hauptmann, Andreas; Kolehmainen, Ville; Mach, Nguyet Minh; Savolainen, Tuomo; Seppänen, Aku; Siltanen, Samuli (2017). **2D electrical impedance tomography dataset**, version 1.0.0. Zenodo. [DOI: 10.5281/zenodo.1203914](https://doi.org/10.5281/zenodo.1203914).

Experimental report / 实验报告：the same authors, **Open 2D Electrical Impedance Tomography data archive**, [arXiv:1704.01178](https://arxiv.org/abs/1704.01178).

License / 授权：[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/). The supplied metadata snapshot at `data/source/dataset_metadata.json` records `license.id = cc-by-4.0` and its [Zenodo metadata source](https://zenodo.org/api/records/1203914).

- `data/source/*.mat` and `data/photos/*.jpg` preserve unmodified files from the official archives: ten selected target cases and one homogeneous reference. `LoadData.m` is retained from the original dataset archive. / 这些文件保留官方归档中的原始内容，选取十个目标及一个均匀参考，并保留原数据归档中的 `LoadData.m`。
- The NPZ files are derived representations: mA-to-A current conversion with the stored `sqrt(2)` amplitude preserved, transposed measurement protocol, signed voltages, drive-electrode channel exclusion, and an added fixed 2D P1 mesh. No target-specific voltage normalization or simulated replacement data is used. / NPZ 为派生格式，进行了单位转换、协议转置、通道筛选，并新增固定二维网格；未按目标逐例归一化或用模拟电压替换测量。
- Photographs support visual comparison and are not conductivity ground truth or inversion inputs. / 照片用于外观对照，不是电导率真值，也不作为反演输入。
- `data/manifest.json` records official URLs, archive MD5/SHA256, individual source/photo SHA256, selection, and preprocessing. The ten targets are a benchmark-specific fixed subset, not an official training/test split. / 清单记录来源、校验值、选取与处理过程；十例不是官方训练／测试划分。

When distributing these original files or derived data, preserve the attribution, source links, CC BY 4.0 license link, and indication of the modifications above. When using the experimental data in a publication, cite the dataset and its report. The same information is available in `CITATION.cff`.

分发原始文件或派生数据时，应保留作者、来源、CC BY 4.0 链接及上述修改说明；使用实验数据发表成果时，请引用原数据集和报告。

## Reused software framework / 复用的软件框架

The benchmark organization reuses code from the existing `eit-framework` implementation. Its existing copyright and MIT permission notice are retained in `LICENSE`:

> Copyright (c) 2026 usct-benchlab contributors

This is the notice accompanying the reused framework code. It is not an attribution to the dataset authors or a claim that the supplied EIT attachment declared an MIT license. Source identities and adaptations are recorded in `SOURCE.json` and `docs/PROVENANCE.md`.

本库复用现有 `eit-framework` 的基准框架代码，其已有 MIT 版权及许可声明保留在 `LICENSE`。该声明不用于声明数据作者的软件著作权，也不表示用户提供的 EIT 附件自带 MIT 授权。

## Supplied EIT submission / 用户提供的 EIT 材料

The supplied `eit_submission.zip` contains its own notice describing its FEM, CEM, continuum boundary model, TV, and adjoint implementation as original to that submission, and states that it did not copy EIDORS, pyEIT, or another EIT repository. It contains no third-party training weights. It does not include a separate software license file or an additional software license declaration. This project preserves that distinction without inventing an extra copyright attribution or permission grant for the submission.

用户提供的 EIT 材料说明其中的有限元、两类边界模型、TV 与伴随实现为该提交编写，没有复制 EIDORS、pyEIT 等仓库，也没有第三方训练权重。附件没有单独的软件许可证文件或额外的软件授权声明；本库如实记录，不替材料补写版权归属或许可授予。

## Python dependencies and mathematical references / Python 依赖与数学文献

NumPy, SciPy, h5py, Pydantic, PyYAML, Pillow, and development dependencies are installed from their own distributions and retain their respective licenses. Their source and binary distributions are not vendored into this repository. Sparse factorization and bounded L-BFGS-B are provided by SciPy.

Classical mathematical references include [Jin & Maass (2012)](https://doi.org/10.1051/cocv/2011193) and [Gehre, Jin & Lu (2014)](https://arxiv.org/abs/1312.1390). These citations explain established models and methods; they do not imply endorsement by those authors or reproduction of their published experimental settings.

上述 Python 软件从各自发行包安装，遵循各自许可证，本库不内嵌其源码或二进制发行包。数学文献用于说明经典模型与方法，不表示原作者认可本实现，也不表示本库逐参数复现论文实验。
