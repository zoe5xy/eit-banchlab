# EIT case and result format

## Case arrays

Cases are read from NPZ (with `allow_pickle=False`) or HDF5. The public case fields below are stored as root arrays/datasets; indices are zero based. `EITCase` retains physical mesh and boundary domains rather than treating an image as the primary unknown.

| Field | Shape | Meaning and units |
| --- | --- | --- |
| `nodes` | `[N,2]` | Finite `(x,y)` coordinates in m; x right, y up |
| `triangles` | `[T,3]` | Integer triangle-node indices |
| `boundary_edges` | `[B,2]` | Integer edge-node indices describing the mesh exterior |
| `electrode_ids` | `[B]` | Integer electrode label `0..L-1`, or `-1` for an insulated gap |
| `currents_A` | `[L,P]` | Electrode currents in A; each pattern/column sums to zero |
| `measurement_matrix` | `[Q,L]` | Voltage-difference coefficients; each row sums to zero |
| `voltages_V` | `[Q,P]` | Signed target voltage differences in V |
| `reference_voltages_V` | `[Q,P]` | Signed homogeneous-reference voltage differences in V |
| `measurement_mask` | `[Q,P]` | Boolean retained-observation mask, with at least one true value |
| `thickness_m` | scalar | Positive 2D thickness in m |
| `contact_impedance_ohm_m2` | scalar or `[L]` | Positive physical contact-impedance initial values in Ω·m² |
| `background_conductivity_S_m` | scalar | Positive background calibration initial value in S/m |
| `case_id` | scalar string | Case identifier; must be unique within a suite |

The source NPZ files also include the optional scalar string `data_kind="experimental"`, which is retained by the public loader/save interface when present. Other extra source annotations need not survive a load/save cycle. HDF5 cases written by `save_case` carry the schema attribute `eitbench.case.v1`.

The loader validates finite real-valued arrays, index types and ranges, mesh exterior consistency, nondegenerate triangles, finite positive physical parameters, protocol compatibility, balanced currents, gauge-invariant measurements, matching voltage dimensions, and a nonempty Boolean mask. Reference measurements are required for reference-only calibration in both inversion modes.

```python
from eitbench import load_case, save_case

case = load_case("data/example.npz")
save_case(case, "artifacts/example-case.h5")
```

## Bundled experiment

The bundled mesh has `N=609`, `T=1056`, `B=160`, `L=16`, `P=79`, and `Q=16`. Each target mask retains 966 values. These include reciprocal redundancy and should not be described as 966 independent measurements.

The water-tank radius is 0.14 m, electrode arc width 0.025 m, and water depth 0.07 m. Electrode index 0 is at the top; indices proceed clockwise. The supplied P1 mesh is fixed in each NPZ; no meshing tool or online download is needed to run it. Straight boundary edges approximate circular arcs.

| Case | Objects |
| --- | --- |
| `1_1` | One plastic circle |
| `1_2` | One hollow metal circle |
| `2_1` | Plastic triangle and circle |
| `2_3` | Two hollow metal circles |
| `3_1` | Plastic rectangle, triangle, and circle |
| `3_4` | Three hollow metal circles |
| `4_1` | Metal circle and plastic triangle |
| `4_3` | Metal circle and plastic circle |
| `5_1` | One metal and two plastic objects |
| `5_2` | Two metal and one plastic object |

The ten targets were fixed before inversion to cover object diversity and use the same baseline settings. The homogeneous `1_0` state is their shared reference and is not counted as an eleventh reconstruction target. `example.npz` duplicates `phantom_1_1.npz`; do not pass both into one suite because their IDs are identical.

## Preprocessing and scale

The data are from Hauptmann et al., *2D electrical impedance tomography dataset*, version 1.0.0, [DOI 10.5281/zenodo.1203914](https://doi.org/10.5281/zenodo.1203914), with experimental description in [arXiv:1704.01178](https://arxiv.org/abs/1704.01178).

1. Read the original target and homogeneous-reference MAT files and check matching protocols.
2. Multiply `CurrentPattern` by `1e-3`, using the mA-to-A convention. Preserve stored nonzero values `±sqrt(2)` instead of replacing them with `±2`.
3. Transpose `MeasPattern`, whose original columns specify measurement channels, to form `[Q,L]`.
4. Keep `Uel` signed and interpret it in V; retain array ordering `[Q,P]`.
5. For each current pattern, exclude voltage-difference channels touching either current-carrying electrode. Keep remaining channels equally weighted.
6. Attach the fixed 2D mesh, geometry, initial conductivity and contacts, and retain references and source hashes.

No absolute value, logarithm, sign inversion, targetwise normalization, rotation, or replacement of measured voltages by simulation is applied. The report's 2 mA amplitude and the MAT files' `sqrt(2)` amplitude admit an inferred RMS interpretation; that correspondence is not established by the files themselves. Absolute calibrated S/m depends on the adopted current scale. Use relative background changes with this limitation in mind.

`data/source/` preserves ten original target MAT files, the reference MAT, the author's `LoadData.m`, and the dataset metadata snapshot. `data/photos/` preserves the corresponding original JPEGs. `data/manifest.json` records DOI, license, selection, preprocessing, archive checksums, source and photo checksums, and upstream download URLs. Original files remain unmodified. NPZ files are derived representations. See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) for attribution and authorization.

The supplied conversion utility is optional; ordinary reconstruction uses the bundled data. Rebuilding from a local official archive or fetching official archives is separate from running the benchmark. Do not overwrite the bundled reference data when experimenting with new cases.

## Reconstruction results

`result.h5` uses the schema attribute `eitbench.result.v1`. The physical reconstruction is `conductivity_S_m[N]`, with coordinates `nodes[N,2]` and topology `triangles[T,3]`. Potentials have shape `potential_nodes_V[N,P]`; predicted, modeled-background, target, and reference voltages have shape `[Q,P]`. `measurement_mask[Q,P]` identifies retained observations.

`conductivity_image_S_m[128,128]` is a linear interpolation for display. Columns progress from low to high x and rows from high to low y. Values outside the interpolation domain are zero; `domain_mask` is the authoritative valid-region mask. Domain-exterior zeros are not zero-conductivity estimates.

The separate `run.json` stores the exact configuration, calibration status and fitted values, target optimization state and history, budgets/work, code and input hashes, and versions. `metrics.json` reports masked voltage errors, conductivity extrema, and the optimizer-success flag. Missing `result.h5` means no valid target reconstruction was retained, for example when a budget was exhausted during reference calibration; consult `run.json` rather than treating the background as an output reconstruction.

Normally the objective is normalized by the squared norm of its retained measurements. For zero or tiny difference data (squared norm below `1e-24`), it falls back to the reference voltage squared norm on the same retained channels. This makes an unchanged target a valid case. `run.json` records the selected normalization in `metadata.voltage_normalization_source` (`measurement` or `reference`). This masked fallback differs from calibration, which fits the complete reference voltage array. If both candidate norms are tiny or nonfinite, the case is rejected for normalized inversion.

Experimental photos do not supply quantitative conductivity labels. The evaluation API therefore does not compute PSNR or SSIM for these examples. A voltage residual assesses boundary-data fit and does not independently validate the image.
