"""Portable case storage with the same validation for files and Python objects."""

from pathlib import Path
import h5py
import numpy as np

from ..operators.fem import Mesh
from ..operators.forward import ForwardModel

PUBLIC_FIELDS = (
    "nodes",
    "triangles",
    "boundary_edges",
    "electrode_ids",
    "currents_A",
    "measurement_matrix",
    "voltages_V",
    "reference_voltages_V",
    "measurement_mask",
    "thickness_m",
    "contact_impedance_ohm_m2",
    "background_conductivity_S_m",
    "case_id",
)
OPTIONAL_FIELDS = ("data_kind",)
MESH_FIELDS = ("nodes", "triangles", "boundary_edges", "electrode_ids")


def validate_data(mesh, data):
    for name in PUBLIC_FIELDS:
        if name not in data:
            raise ValueError("input missing " + name)
        value = np.asarray(data[name])
        if (
            name not in ("case_id", "measurement_mask")
            and value.dtype.kind not in "iuf"
        ):
            raise ValueError("real numeric EIT input required: " + name)
    for name in MESH_FIELDS[1:]:
        if data[name].dtype.kind not in "iu":
            raise ValueError(name + " must contain integer indices")
    for name in MESH_FIELDS:
        if not np.array_equal(data[name], getattr(mesh, name)):
            raise ValueError("case data and mesh disagree: " + name)
    # Rebuild cached geometry after any caller-side array mutations.
    fresh = Mesh(*(data[name].copy() for name in MESH_FIELDS))
    thickness = data["thickness_m"]
    if thickness.shape != () or not np.isfinite(thickness) or thickness <= 0:
        raise ValueError("positive finite scalar thickness_m required")
    ForwardModel(
        fresh,
        data["currents_A"],
        data["measurement_matrix"],
        float(thickness),
        contact=data["contact_impedance_ohm_m2"],
    )
    shape = (len(data["measurement_matrix"]), data["currents_A"].shape[1])
    if not all(shape):
        raise ValueError("empty protocol")
    for name in ("voltages_V", "reference_voltages_V"):
        if data[name].shape != shape or not np.isfinite(data[name]).all():
            raise ValueError(name + " must be finite [Q,P]")
    mask = data["measurement_mask"]
    if mask.dtype.kind != "b" or mask.shape != shape or not mask.any():
        raise ValueError("measurement_mask must be nonempty boolean [Q,P]")
    bg = data["background_conductivity_S_m"]
    if bg.shape != () or not np.isfinite(bg) or bg <= 0:
        raise ValueError("positive finite scalar background required")
    for name in ("case_id", *OPTIONAL_FIELDS):
        if name in data:
            value = data[name]
            if (
                value.shape != ()
                or value.dtype.kind not in "SU"
                or not str(value.item()).strip()
            ):
                raise ValueError(name + " must be a nonempty scalar string")
    return fresh


def load_case(path):
    from .schema import EITCase

    path = Path(path).resolve()
    fields = PUBLIC_FIELDS + OPTIONAL_FIELDS
    if path.suffix.lower() == ".npz":
        with np.load(path, allow_pickle=False) as source:
            data = {name: np.array(source[name]) for name in fields if name in source}
    elif path.suffix.lower() in (".h5", ".hdf5"):
        with h5py.File(path, "r") as source:
            schema = source.attrs.get("schema")
            if schema is not None and schema != "eitbench.case.v1":
                raise ValueError("unsupported case schema: " + str(schema))
            data = {name: source[name][()] for name in fields if name in source}
        data = {
            key: np.asarray(value.decode() if isinstance(value, bytes) else value)
            for key, value in data.items()
        }
    else:
        raise ValueError("case extension must be .npz, .h5 or .hdf5")
    missing = set(PUBLIC_FIELDS) - set(data)
    if missing:
        raise ValueError(f"input missing {sorted(missing)}")
    mesh = Mesh(*(data[name] for name in MESH_FIELDS))
    return EITCase(mesh, data, path)


def save_case(case, path):
    case = case.validated_copy()
    path = Path(path)
    if path.suffix.lower() not in (".npz", ".h5", ".hdf5"):
        raise ValueError("case extension must be .npz, .h5 or .hdf5")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [name for name in PUBLIC_FIELDS + OPTIONAL_FIELDS if name in case.data]
    if path.suffix.lower() == ".npz":
        np.savez_compressed(path, **{name: case.data[name] for name in fields})
    else:
        with h5py.File(path, "w") as handle:
            handle.attrs["schema"] = "eitbench.case.v1"
            for name in fields:
                value = case.data[name]
                handle.create_dataset(
                    name, data=str(value.item()) if value.dtype.kind in "SU" else value
                )
    return path
