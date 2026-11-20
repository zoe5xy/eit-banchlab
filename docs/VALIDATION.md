# Validation record / 验证记录

Validated on 2026-11-20 with Python 3.12.14 and numpy 2.5.3, scipy 1.18.1, h5py 3.16.0, pydantic 2.13.5, PyYAML 6.0.3, Pillow 12.3.0. Thread environment: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`.

## Automated checks / 自动验证

- `python -m pytest -q`: **130 passed** (5.42 s in this environment).
- `ruff check .`: passed.
- Physics: P1 analytical stiffness/energy; both boundary gauges and system residuals; CEM reciprocity and recovered currents; continuum disk refinement; scaling laws; conductivity, TV, contact, and operator-adjoint directional derivatives.
- Runtime: four boundary/mode combinations; finite positive bounded results; accepted-iterate retention under numerical/budget interruption; zero-difference normalization; reference-only calibration; invalid/complex inputs; no-budget behavior; strict configuration and host caps.
- Storage/workflow: NPZ/HDF5 array preservation; actual executed-array fingerprints; removed or absent source files; portable YAML benchmark paths; CLI exit codes; suite preflight and independent budgets; nonconvex mesh display masks; imports with sibling project names blocked.

测试覆盖物理、梯度、四种配置组合、预算与中断、输入及配置校验、读写保真、实际执行内容哈希、命令行与独立导入。

## Supplied experimental data / 附件实验数据

All **35** files under `data/` are byte-identical to the supplied attachment. All ten target cases were loaded and compared to their original MAT arrays: current scale `10^-3`, measurement transpose, signed target/reference voltages, and drive-channel exclusion mask were checked. The included example is identical to phantom 1_1. File attribution and original hashes remain in `data/manifest.json` and `SOURCE.json`.

A ten-case CEM difference suite completed with **3 target iterations per case**, independent reference calibration, and finite reconstruction artifacts. These are workflow smoke checks.

数据目录的 35 个文件与附件完全一致。十例均已完成读取、原始数组核对与 3 次目标迭代的短流程。

## Four real-data runs / 四种配置的真实数据运行

Case: `data/example.npz` (phantom 1_1). Each run requested **30 target iterations**. Default reference calibration was allowed up to 400 iterations and converged in every run. All final objectives decreased from their initial values, and all node conductivities were finite, positive, and within their configured bounds. Absolute presets use the supplied material's demonstration `alpha=0.0003`; difference presets use `alpha=0.03`.

| Boundary | Mode | α | Relative voltage residual for that mode | Target status | Forward / adjoint calls |
| --- | --- | --- | --- | --- | --- |
| cem | absolute | 0.0003 | 1.1315% | max_iterations | 348 / 347 |
| cem | difference | 0.03 | 4.8999% | max_iterations | 349 / 348 |
| continuum | absolute | 0.0003 | 1.2202% | max_iterations | 40 / 39 |
| continuum | difference | 0.03 | 4.7147% | max_iterations | 42 / 41 |

Counts include reference calibration, baseline prediction, and target inversion; every call solves all injection right-hand sides. A target status of `max_iterations` means the requested 30 iterations were reached, not optimizer convergence. The residual columns use different objectives and denominators, so they do not establish comparative image accuracy. The full 500-iteration ten-case benchmark was not run for this delivery. Raw figures, both residual definitions, objective values, and environment versions are in [validation.json](validation.json).

四种配置均完成 30 次目标迭代，目标函数降低；`max_iterations` 表示达到这次设置的迭代上限。残差不是电导率真值误差，照片不能支持定量 PSNR／SSIM。

## Independent delivery / 独立交付

A complete folder copy was installed into a temporary environment with ordinary Python dependencies. From an unrelated working directory, the installed `eit` command ran discovery and the real-data smoke benchmark; both forward and inverse examples ran. The imported package came from the temporary installation, not the original workspace. Tests also block imports of the old project package names.

Original repository hash checks found no changes: 91 recorded `eit-framework` files, 233 `usct-benchlab` files, and 94 `fttt-benchlab` files. Validation outputs and temporary environments stay outside the delivered source folder. Local validation used Python 3.12; the included CI workflow also requests Python 3.10, which was not locally exercised here.

整个文件夹已在临时环境安装并从其他目录运行；不依赖相邻仓库。原有三个代码库的已记录文件均未变化。验证输出和临时环境不随源码交付。
