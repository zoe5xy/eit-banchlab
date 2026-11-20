# EIT Benchlab

[English](README.md) | [简体中文](README.zh-CN.md)

A standalone CPU benchmark library for two-dimensional electrical impedance tomography (EIT), organized in the same discovery, configuration, run, and evaluation style as the USCT/FTTT benchmark libraries. This folder contains its own implementation and experimental examples; it does not import another local code repository.

The library exposes **one non-learning reconstruction algorithm**, `lbfgsb_tv`: P1 finite elements, an exact discrete adjoint, bounded L-BFGS-B optimization, and smoothed isotropic total variation (TV). It needs no training data, neural network, GPU, or model weights.

| Setting | Choices | Meaning |
| --- | --- | --- |
| Boundary model, `parameters.variant` | `cem`, `continuum` | Complete electrode model or prescribed boundary flux with electrode-region average observations |
| Inversion mode, `parameters.mode` | `difference`, `absolute` | Nonlinear difference-data or absolute-data objective |

These settings are variants of the same algorithm. The two primary presets use difference inversion; the companion `*_absolute.yaml` presets use absolute inversion with the material’s demonstration coefficient `alpha=0.0003`. The continuum approximation has no contact-impedance layer or electrode equipotential constraint and is distinct from CEM.

## Install and run

Use a Python environment compatible with [pyproject.toml](pyproject.toml). Run these commands from the `eit-benchlab` folder:

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

The bundled `data/example.npz` is byte-identical to `data/phantom_1_1.npz`. It is a real water-tank measurement, and the example runs offline after Python dependencies have been installed. Always select a new or empty output directory.

PNG previews are optional: install `python -m pip install -e '.[viz]'` and add `--preview` to a run, suite, or benchmark command.

Use the other boundary model by selecting its configuration:

```bash
eit run lbfgsb_tv \
  --case data/example.npz \
  --config configs/algorithms/lbfgsb_tv_continuum.yaml \
  --out artifacts/example-continuum
```

Run the ten fixed experimental cases as a suite:

```bash
eit suite \
  --cases data/phantom_*.npz \
  --config configs/algorithms/lbfgsb_tv_cem.yaml \
  --out artifacts/ten-cem
```

The shell expands the wildcard in this command. A suite runs cases sequentially with a separate calibration and budget for each case. It saves each case in a numbered subdirectory and writes `summary.json`.

Alternatively, use the fixed benchmark manifest, whose case and configuration paths resolve relative to its YAML file:

```bash
eit bench --suite configs/benchmarks/kit4.yaml --out artifacts/kit4
```

## Python interface

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
conductivity = result.conductivity_S_m  # [N], S/m; None if no iterate was produced
```

To use absolute inversion, select `configs/algorithms/lbfgsb_tv_cem_absolute.yaml` or `lbfgsb_tv_continuum_absolute.yaml`. Its data normalization differs from difference inversion, so its TV coefficient should be selected separately; `alpha: 0.0003` is the original material's demonstration setting, not a generally optimal value. Both modes use the supplied reference measurement to calibrate the background first.

## Data and physical quantities

The package includes ten fixed phantom cases and one shared homogeneous reference from the **2D electrical impedance tomography dataset**, version 1.0.0, Hauptmann et al. (2017), [DOI: 10.5281/zenodo.1203914](https://doi.org/10.5281/zenodo.1203914). The data and photographs are distributed under CC BY 4.0. The ten cases form this benchmark's fixed subset, not an official train/test split.

Each case has 609 mesh nodes, 1056 triangles, 16 electrodes, 79 current patterns, and 16 voltage channels. Its mask retains 966 values, including reciprocal redundancy. Coordinates and thickness use **m**, conductivity **S/m**, current **A**, voltage **V**, and physical contact impedance **Ω·m²**. Voltages are signed arrays of shape `[channel, current pattern]`; conductivity is represented at mesh nodes.

The original `CurrentPattern` values are multiplied by `10^-3`, preserving the stored `sqrt(2)` amplitude; `MeasPattern` is transposed and `Uel` is retained as signed volts. The report states a 2 mA amplitude whereas the MAT files store `sqrt(2)`; an RMS interpretation is inferred, so absolute conductivity depends on this current-scale convention. The benchmark calibrates its background from the homogeneous reference and supports interpreting changes relative to it.

Photographs are for visual comparison and are not quantitative conductivity truth. The benchmark reports voltage residuals and conductivity ranges, without PSNR/SSIM against photographs. See [data format](docs/DATA_FORMAT.md), [data manifest](data/manifest.json), and [third-party notices](THIRD_PARTY_NOTICES.md).

## Results and controls

An ordinary run saves:

| Artifact | Contents |
| --- | --- |
| `result.h5` | Mesh-node conductivity, potentials, predicted/background/observed/reference voltages, mesh, measurement mask, display image, and domain mask |
| `run.json` | Resolved configuration, calibration and optimizer status, objective history, work counts, versions, input/code hashes, and stop reason |
| `metrics.json` | Difference/absolute voltage errors, voltage RMSE, conductivity range, and optimizer success |
| `index.json` | Links to the run's saved artifacts |
| `preview.png` | Optional conductivity preview, enabled by `--preview` |

The input record hashes the actual admitted arrays (values, dtype, and shape), including cases created or edited in Python; the source-file hash is recorded separately at artifact-save time. The primary result is positive node conductivity in S/m. The interpolated 128 × 128 image is for display; its first row is at the top and values outside the mesh are zero. Use `domain_mask` for image analysis.

`run_controls` supports target iteration, elapsed-time, forward-call, and adjoint-call limits. Forward/adjoint counts and elapsed time cover calibration, baseline prediction, and target reconstruction together; one call solves all current-pattern right-hand sides. `calibration_max_iterations` controls the separate reference-calibration iteration limit. Time limits are checked between work units. An interrupted run retains only a completely evaluated optimizer-accepted iterate. If calibration stops before a reconstruction is available, the run records its status without `result.h5`.

For unchanged or tiny difference data, objective normalization falls back to the reference-voltage norm on the retained channels; the run records which normalization it used.

`max_iterations` and `resource_exhausted` are stop states, not claims of convergence. A small voltage residual alone does not establish an accurate conductivity image. The model is limited to known 2D geometry and positive, real, scalar, isotropic conductivity; it does not recover 3D structure, complex admittivity, or unknown boundary shape.

The CLI exits with 1 for input/configuration admission failures, 2 for recorded numerical errors, and 0 for completed execution including iteration/budget stops. Inspect `status` and `stopping_reason` in `run.json`; exit code 0 alone does not mean convergence. Admission failures are rejected before creating an output directory.

## Layout, verification, and provenance

```text
configs/algorithms/   CEM and continuum presets
configs/benchmarks/   fixed experimental benchmark manifest
src/eitbench/
  core/              case schema, I/O, configuration, registry, and budgets
  operators/         P1 FEM, boundary models, and discrete adjoints
  models/            relative-to-physical conductivity mapping
  solvers/           bounded optimizer and TV utilities
  algorithms/        calibration and the lbfgsb_tv reconstruction method
  benchmark/         single runs, suites, and artifacts
  evaluation/        voltage-domain metrics
data/                offline cases, source MAT files, photos, and manifest
docs/                equations, data contract, provenance, and validation
tests/               physical, derivative, interface, and independence checks
```

`models/` contains a physical-variable mapping; it does not contain learned networks. A direct forward example is available as `python examples/forward_demo.py`; the inverse example is `python examples/eit_demo.py`. Run the verification suite with:

```bash
python -m pytest -q
python scripts/verify_sources.py
```

See [algorithm equations](docs/ALGORITHM.md), [provenance](docs/PROVENANCE.md), and [validation record](docs/VALIDATION.md) for scope and evidence. The material's reported historical metrics are not new validation results for this package.

[LICENSE](LICENSE) retains the MIT copyright and permission notice accompanying the reused benchmark framework code. The supplied EIT submission contained no separate software license file; this library records that fact without attributing a new license declaration to the submission. Dataset authorization is separate, as described in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). [SOURCE.json](SOURCE.json) records source identities and adaptations; [CITATION.cff](CITATION.cff) provides the experimental dataset citation.

To share the project, send this whole folder or publish it as its own repository. Install its Python dependencies on the receiving computer; sibling USCT, FTTT, and framework repositories are not needed.
