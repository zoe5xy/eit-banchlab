# EIT Benchlab

[English](README.md) | [简体中文](README.zh-CN.md)

一个可以独立运行和分享的二维电阻抗层析成像（EIT）CPU 代码库，沿用 USCT／FTTT 代码库的算法查询、配置、运行和评估组织方式。本文件夹包含自身实现与实验示例，运行时不导入其他本地代码仓库。

本库公开 **1 个非学习类重建算法** `lbfgsb_tv`：P1 有限元正演、精确离散伴随梯度、带上下界的 L-BFGS-B 优化，以及平滑各向同性总变分（TV）正则化。无需训练数据、神经网络、GPU 或模型权重。

| 设置 | 可选值 | 含义 |
| --- | --- | --- |
| 边界模型 `parameters.variant` | `cem`、`continuum` | 完整电极模型，或给定边界通量并观测电极区域平均电位的连续模型 |
| 反演模式 `parameters.mode` | `difference`、`absolute` | 非线性差分数据目标函数，或绝对数据目标函数 |

这些设置属于同一个算法的不同配置。两个主要预设使用差分反演；另有两个 `*_absolute.yaml` 绝对反演预设，采用材料中的演示系数 `alpha=0.0003`。连续边界近似不包含接触阻抗层和电极等势约束，与 CEM 的物理模型不同。

## 安装与首次运行

使用符合 [pyproject.toml](pyproject.toml) 要求的 Python 环境，在 `eit-benchlab` 文件夹中执行：

```bash
python -m pip install -e '.[dev]'

eit list
eit describe lbfgsb_tv
eit inspect --case data/example.npz

eit run lbfgsb_tv \
  --case data/example.npz \
  --config configs/algorithms/lbfgsb_tv_cem.yaml \
  --out artifacts/example-cem
```

随包的 `data/example.npz` 与 `data/phantom_1_1.npz` 字节完全一致，使用真实水槽实验测量。安装 Python 依赖后，示例运行无需联网。每次运行请指定新目录或空目录。

PNG 预览为可选功能：执行 `python -m pip install -e '.[viz]'`，然后在单例、批量或基准命令后添加 `--preview`。

切换连续边界模型时，改用相应预设：

```bash
eit run lbfgsb_tv \
  --case data/example.npz \
  --config configs/algorithms/lbfgsb_tv_continuum.yaml \
  --out artifacts/example-continuum
```

一次运行固定的十个实验案例：

```bash
eit suite \
  --cases data/phantom_*.npz \
  --config configs/algorithms/lbfgsb_tv_cem.yaml \
  --out artifacts/ten-cem
```

此命令中的通配符由 shell 展开。批量实验依次运行各案例，每例独立标定并使用独立预算；结果保存在编号子目录中，另生成 `summary.json`。

也可以直接使用固定基准清单，案例和配置路径相对于该 YAML 文件解析：

```bash
eit bench --suite configs/benchmarks/kit4.yaml --out artifacts/kit4
```

## Python 接口

```python
from eitbench import describe, list_algorithms, load_case, run

print(list_algorithms())  # ["lbfgsb_tv"]
print(describe("lbfgsb_tv"))
case = load_case("data/example.npz")
result = run(
    "lbfgsb_tv",
    case=case,
    config="configs/algorithms/lbfgsb_tv_cem.yaml",
    out="artifacts/python-example",
)
print(result.status, result.stopping_reason)
conductivity = result.conductivity_S_m  # [N]，S/m；未产生有效迭代结果时为 None
```

使用绝对反演时，选择 `configs/algorithms/lbfgsb_tv_cem_absolute.yaml` 或 `lbfgsb_tv_continuum_absolute.yaml`。绝对反演与差分反演的数据项归一化不同，需要分别选择 TV 系数；`alpha: 0.0003` 是原材料的演示设置，不是通用最优值。两种模式均先用提供的参考测量进行背景标定。

## 数据与物理量

随包包含十个固定 phantom 案例及一个共享均匀背景参考，来源为 Hauptmann 等人（2017）的 **2D electrical impedance tomography dataset**，版本 1.0.0，[DOI：10.5281/zenodo.1203914](https://doi.org/10.5281/zenodo.1203914)。实验数据与照片采用 CC BY 4.0 授权。这十例是本基准固定选取的子集，不是原数据集规定的训练／测试划分。

每例包含 609 个网格节点、1056 个三角形、16 个电极、79 次注流和 16 个电压通道。掩模保留 966 个测量值，其中包含互易冗余。坐标与厚度单位为 **m**，电导率 **S/m**，电流 **A**，电压 **V**，物理接触阻抗 **Ω·m²**。带符号电压数组按 `[通道, 注流]` 排列，电导率定义在网格节点上。

整理时将原 `CurrentPattern` 乘 `10^-3`，保留文件存储的 `sqrt(2)` 幅值；`MeasPattern` 转置，`Uel` 保留带符号数值并按 V 使用。实验报告写注流幅值为 2 mA，而 MAT 文件存储 `sqrt(2)`，两者的 RMS 对应关系只是推断，因此绝对电导率解释依赖这一电流幅值约定。本库使用均匀参考数据标定背景，可着重观察相对背景的变化。

照片只用于外观对照，不是定量电导率真值。评估输出电压残差与电导率范围，不对照片计算 PSNR／SSIM。详见[数据格式](docs/DATA_FORMAT.md)、[数据清单](data/manifest.json)与[第三方声明](THIRD_PARTY_NOTICES.md)。

## 输出与运行控制

正常完成一次运行后生成：

| 文件 | 内容 |
| --- | --- |
| `result.h5` | 节点电导率、电位、预测／背景／目标／参考电压、网格、测量掩模、展示图及区域掩模 |
| `run.json` | 实际配置、标定及优化状态、目标函数历史、工作量、版本、输入／源码哈希及停止原因 |
| `metrics.json` | 差分／绝对电压误差、电压 RMSE、电导率范围及优化器成功标记 |
| `index.json` | 已保存结果文件的索引 |
| `preview.png` | 使用 `--preview` 时生成的电导率预览图 |

输入记录对实际校验并执行的数组内容、类型和形状生成哈希，覆盖直接在 Python 中创建或修改的案例；原文件哈希在保存结果时另行记录。主要结果是以 S/m 为单位的正节点电导率。插值得到的 128 × 128 图像用于展示，首行位于上方，网格外填 0；分析图像时应使用 `domain_mask`。

`run_controls` 支持目标反演迭代数、耗时、正演调用和伴随调用上限。调用次数和耗时覆盖参考标定、背景正演及目标反演全过程；一次正演／伴随调用同时处理全部注流右端项。参考标定的迭代上限由 `calibration_max_iterations` 单独控制。时间限制在工作单元之间检查。中断时只保留已完整计算且被优化器接受的迭代点；如果标定阶段停止、尚无重建结果，则记录状态而不生成 `result.h5`。

当差分数据为零或极小时，目标函数改用相同有效通道上的参考电压范数进行归一化，并在运行记录中注明实际选择。

`max_iterations` 和 `resource_exhausted` 表示停止状态，不表示已经收敛。较小电压残差也不能单独证明电导率图像准确。模型适用于已知二维几何以及正、实数、标量、各向同性电导率，不处理三维结构、复导纳或未知边界形变。

命令行在输入／配置准入失败时返回退出码 1，已记录的数值错误返回 2；执行完成（包括迭代数或预算停止）返回 0。请查看 `run.json` 的 `status` 和 `stopping_reason`，退出码 0 本身不表示收敛。准入失败会在创建输出目录前被拒绝。

## 目录、验证与来源

```text
configs/algorithms/   CEM 与连续边界预设
configs/benchmarks/   固定实验基准清单
src/eitbench/
  core/              数据定义、读写、配置、注册与预算
  operators/         P1 有限元、边界模型与离散伴随
  models/            相对电导率到物理电导率的映射
  solvers/           带上下界的优化器与 TV 工具
  algorithms/        背景标定及 lbfgsb_tv 重建
  benchmark/         单例、批量实验与结果保存
  evaluation/        电压域指标
data/                离线案例、原始 MAT、照片和清单
docs/                数学公式、数据契约、来源和验证记录
tests/               物理、导数、接口和独立性检查
```

`models/` 存放物理变量映射，不包含学习型网络。正演示例为 `python examples/forward_demo.py`，反演示例为 `python examples/eit_demo.py`。执行验证：

```bash
python -m pytest -q
python scripts/verify_sources.py
```

算法与验证范围见[数学说明](docs/ALGORITHM.md)、[来源记录](docs/PROVENANCE.md)与[验证记录](docs/VALIDATION.md)。原材料所报告的历史指标不能视为本代码库新完成的验证结果。

[LICENSE](LICENSE) 保留复用基准框架代码已有的 MIT 版权及许可声明。用户提供的 EIT 提交材料没有单独的软件许可证文件；本库如实记录这一点，不替原材料新增许可声明。数据授权单独列于 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。[SOURCE.json](SOURCE.json) 记录来源标识及适配信息，[CITATION.cff](CITATION.cff) 提供实验数据的引用信息。

分享时可直接发送整个文件夹，或将其作为独立仓库发布。对方安装 Python 依赖即可运行，无需相邻的 USCT、FTTT 或 framework 仓库。
