# Source provenance and redistribution contents

## Inputs to this library

This standalone project adapts the EIT material supplied as `eit_submission.zip` and reuses benchmark infrastructure from the local `eit-framework` implementation. The attachment's original implementation consists of `eit_core.py` (mesh, FEM, boundary models, adjoints), `inverse.py` (calibration and reconstruction), and the run, forward, verification, and data-preparation wrappers. `ALGORITHM.md` and `README.md` describe its mathematical and experimental conventions.

The original EIT material declares that its FEM, CEM, continuum boundary model, TV, and adjoint code were written for that submission, with sparse linear algebra and L-BFGS-B supplied by SciPy. It states that it did not copy EIDORS, pyEIT, or another EIT repository and includes no learned weights. This library records those statements as source information; the original paper authors are not assigned authorship of the implementation.

`SOURCE.json` contains the recorded source identities and adaptations. File hashes identify the supplied or reused revisions; a local source path is provenance, not a runtime dependency. Run records additionally hash the installed package's Python source and the actual admitted case arrays, including dtype and shape. The original source path and its file hash at artifact-save time are recorded separately; a source file may differ from an edited in-memory case.

## Adaptation boundaries

The mathematical reconstruction remains one method: `lbfgsb_tv`. CEM/continuum and difference/absolute are its boundary and data-objective settings. The organized library separates case validation and I/O, finite-element physics, calibration, bounded optimization, configuration/discovery, work budgets, evaluation, and result artifacts.

The `eitbench` package has independent imports and includes the physical kernel it needs. It does not import sibling USCT, FTTT, or framework packages. The independent-folder check and validation evidence are described in [VALIDATION.md](VALIDATION.md).

This organization also records accepted-iterate state when a budget interrupts optimization, gives calibration and target reconstruction distinct statuses, and saves voltage-domain evidence with the mesh-node reconstruction. These changes should be evaluated using the current library's verification record; performance figures in the original submission are historical context only.

## Software notice and dataset authorization

These are separate sources with separate notices:

| Content | Recorded notice |
| --- | --- |
| Reused benchmark framework code | Existing MIT copyright and permission notice retained in `LICENSE`, including `Copyright (c) 2026 usct-benchlab contributors` |
| User-supplied EIT submission | No separate software `LICENSE` file was included in the attachment; its documentation describes the implementation as original but provides no additional software license declaration |
| Original and derived experimental data and photos | Hauptmann et al. (2017), Zenodo dataset v1.0.0, CC BY 4.0, with attribution and changes recorded in `THIRD_PARTY_NOTICES.md` and `data/manifest.json` |
| Installed Python dependencies | Their own project licenses; installed separately, not vendored into this folder |

Retaining the framework's MIT notice does not assert that the attachment contained an MIT license, does not invent a copyright holder for the submission, and does not replace the dataset's CC BY attribution. `CITATION.cff` describes the experimental dataset and its actual authors, not software authorship.

## What to share

Share the entire `eit-benchlab` directory, including source, configuration, tests, examples, documentation, `LICENSE`, `THIRD_PARTY_NOTICES.md`, `SOURCE.json`, `CITATION.cff`, and `data/`. The recipient installs normal Python dependencies and can run the bundled cases offline. A copied directory or its own Git repository is sufficient; no source archive or sibling repository is needed.

Transient virtual environments, Python caches, editable-install metadata, build artifacts, and local `artifacts/` outputs are not part of the reproducible source delivery. The supplied raw MAT files, photographs, metadata, derived NPZ files, and manifest are useful to preserve traceability and offline examples.
