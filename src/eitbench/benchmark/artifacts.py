import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import h5py
import numpy as np

from ..evaluation.metrics import measurement_metrics
from ..viz import rasterize, save_preview


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def input_fingerprint(case):
    """Hash the admitted array snapshot, including shape and dtype information."""
    arrays = {}
    for name, value in sorted(case.data.items()):
        array = np.asarray(value)
        arrays[name] = dict(
            dtype=array.dtype.str,
            shape=list(array.shape),
            sha256=hashlib.sha256(array.tobytes(order="C")).hexdigest(),
        )
    encoded = json.dumps(arrays, sort_keys=True, separators=(",", ":")).encode("utf-8")
    source_hash = None
    if case.source is not None:
        try:
            source_hash = hashlib.sha256(case.source.read_bytes()).hexdigest()
        except OSError:
            pass
    return dict(
        path=str(case.source) if case.source else None,
        sha256=source_hash,
        source_file_hash_timing="artifact_save",
        content_sha256=hashlib.sha256(encoded).hexdigest(),
        arrays=arrays,
        content_hash_schema="eitbench.case-arrays.v1",
    )


def save_result(out, case, config, result, *, preview=False):
    metrics = {}
    files = {}
    if result.conductivity_S_m is not None:
        sigma = result.conductivity_S_m
        if (
            sigma.shape != (len(case.mesh.nodes),)
            or not np.isfinite(sigma).all()
            or np.any(sigma <= 0)
        ):
            raise FloatingPointError("invalid conductivity reconstruction")
        image, mask = rasterize(case.mesh, sigma)
        temporary = out / "result.h5.tmp"
        with h5py.File(temporary, "w") as h:
            h.attrs["schema"] = "eitbench.result.v1"
            h.attrs["primary_quantity"] = "conductivity_S_m at mesh nodes"
            h.attrs["case_id"] = case.case_id
            h.attrs["status"] = result.status
            if "data_kind" in case.data:
                h.attrs["data_kind"] = str(case.data["data_kind"].item())
            h.attrs["image_axes"] = "y decreases, x increases; display only"
            arrays = dict(
                conductivity_S_m=sigma,
                potential_nodes_V=result.potential_nodes_V,
                predicted_voltages_V=result.predicted_voltages_V,
                baseline_voltages_V=result.baseline_voltages_V,
                observed_voltages_V=case.data["voltages_V"],
                reference_voltages_V=case.data["reference_voltages_V"],
                measurement_mask=case.data["measurement_mask"],
                nodes=case.mesh.nodes,
                triangles=case.mesh.triangles,
                boundary_edges=case.mesh.boundary_edges,
                electrode_ids=case.mesh.electrode_ids,
                currents_A=case.data["currents_A"],
                measurement_matrix=case.data["measurement_matrix"],
                thickness_m=case.data["thickness_m"],
                conductivity_image_S_m=image,
                domain_mask=mask,
            )
            for key, value in arrays.items():
                h.create_dataset(key, data=value)
        temporary.replace(out / "result.h5")
        metrics = measurement_metrics(
            sigma,
            result.predicted_voltages_V,
            result.baseline_voltages_V,
            case.data["voltages_V"],
            case.data["reference_voltages_V"],
            case.data["measurement_mask"],
        )
        files["result"] = "result.h5"
        if preview:
            try:
                save_preview(
                    out / "preview.png",
                    image,
                    mask,
                    result.calibration["background_conductivity_S_m"],
                )
                files["preview"] = "preview.png"
            except (ImportError, OSError, ValueError) as exc:
                # An optional display step must not destroy numerical evidence.
                result.metadata["preview_error"] = f"{type(exc).__name__}: {exc}"
    metrics.update(optimizer_success=result.optimization.get("success", False))
    write_json(out / "metrics.json", metrics)
    record = dict(
        schema="eitbench.run.v1",
        algorithm="lbfgsb_tv",
        case_id=case.case_id,
        data_kind=str(case.data["data_kind"].item())
        if "data_kind" in case.data
        else None,
        status=result.status,
        stopping_reason=result.stopping_reason,
        configuration=config.model_dump(),
        calibration=result.calibration,
        optimization=result.optimization,
        work=result.work,
        metadata=result.metadata,
        budget_scope="calibration + baseline + target reconstruction; batched RHS per call",
        checkpoint_policy="only complete optimizer-accepted iterates; calibration-only is not a reconstruction",
        input=input_fingerprint(case),
        versions={
            name: importlib.metadata.version(name)
            for name in ("numpy", "scipy", "h5py", "pydantic")
        },
        python=platform.python_version(),
        code_sha256={
            str(p.relative_to(Path(__file__).resolve().parents[1])): hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
            for p in Path(__file__).resolve().parents[1].rglob("*.py")
        },
        artifacts=files,
    )
    write_json(out / "run.json", record)
    if files:
        write_json(
            out / "index.json",
            dict(
                case_id=case.case_id,
                status=result.status,
                artifacts=files,
                run="run.json",
                metrics="metrics.json",
            ),
        )
    return record
