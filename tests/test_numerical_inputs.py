"""Reject invalid physical inputs and preserve zero-change reconstructions."""

import json

import numpy as np
import pytest

import eitbench as eit
from eitbench.algorithms.lbfgsb_tv import Objective
from eitbench.operators.eit import EITForwardOperator
from eitbench.operators.fem import disk_mesh
from eitbench.operators.forward import ForwardModel
from eitbench.operators.regularization import smooth_tv
from eitbench.models.conductivity import RelativeConductivity
from eitbench.solvers.tv import LBFGSBTVSolver


@pytest.fixture
def physical_case():
    mesh = disk_mesh(electrodes=4, rings=2)
    currents = 1e-3 * np.array([[1, 0, -1], [-1, 1, 0], [0, -1, 1], [0, 0, 0.0]])
    measurement = np.eye(4) - np.roll(np.eye(4), 1, axis=1)
    forward = ForwardModel(mesh, currents, measurement)
    reference, _, _ = forward.solve(np.full(forward.n, 0.03))
    return forward, reference


@pytest.mark.parametrize("value", [0, -0.03, np.nan, np.inf, 0.03 + 10j])
def test_forward_rejects_invalid_conductivity(physical_case, value):
    forward, _ = physical_case
    with pytest.raises(ValueError):
        forward.solve(np.full(forward.n, value))


@pytest.mark.parametrize("field", ["currents", "measurement", "thickness", "contact"])
def test_protocol_rejects_complex_inputs(physical_case, field):
    forward, _ = physical_case
    values = dict(
        currents=forward.currents,
        measurement=forward.measurement,
        thickness=forward.thickness,
        contact=forward.contact,
    )
    values[field] = np.asarray(values[field], dtype=complex) + 1j
    with pytest.raises(ValueError, match="real"):
        ForwardModel(forward.mesh, **values)


@pytest.mark.parametrize("thickness", [0, -1, np.nan, np.inf, [0.07], 0.07 + 1j])
def test_mesh_stiffness_rejects_invalid_thickness(physical_case, thickness):
    forward, _ = physical_case
    with pytest.raises(ValueError):
        forward.mesh.stiffness(np.full(forward.n, 0.03), thickness)


@pytest.mark.parametrize("empty", ["currents", "measurement"])
def test_forward_rejects_empty_protocol(physical_case, empty):
    forward, _ = physical_case
    currents = forward.currents[:, :0] if empty == "currents" else forward.currents
    measurement = (
        forward.measurement[:0] if empty == "measurement" else forward.measurement
    )
    with pytest.raises(ValueError, match="nonempty"):
        ForwardModel(forward.mesh, currents, measurement)


@pytest.mark.parametrize("bad_mask", ["nan", "numeric", "empty", "shape"])
def test_solver_rejects_invalid_masks(physical_case, bad_mask):
    forward, reference = physical_case
    mask = {
        "nan": np.full(reference.shape, np.nan),
        "numeric": np.full(reference.shape, 2.0),
        "empty": np.zeros(reference.shape, dtype=bool),
        "shape": np.ones(reference.shape[::-1], dtype=bool),
    }[bad_mask]
    with pytest.raises(ValueError, match="boolean"):
        LBFGSBTVSolver(max_iterations=0).solve(reference, forward, mask=mask)


@pytest.mark.parametrize("field", ["measurement", "reference", "background"])
def test_solver_rejects_complex_values(physical_case, field):
    forward, reference = physical_case
    values = dict(measurement=reference, reference=reference, background=0.03)
    values[field] = np.asarray(values[field], dtype=complex) + 1j
    with pytest.raises(ValueError, match="real"):
        LBFGSBTVSolver(max_iterations=0).solve(operator=forward, **values)


def test_operator_rejects_complex_baseline_and_derivatives(physical_case):
    forward, reference = physical_case
    with pytest.raises(ValueError, match="real"):
        EITForwardOperator(forward, baseline=reference.astype(complex))
    linearization = EITForwardOperator(forward).linearize(np.full(forward.n, 0.03))
    with pytest.raises(ValueError, match="real"):
        linearization.adjoint(reference.astype(complex))


def test_direct_adjoint_validates_shape_and_reality(physical_case):
    forward, reference = physical_case
    _, state, lu = forward.solve(np.full(forward.n, 0.03))
    with pytest.raises(ValueError, match="real"):
        forward.adjoint_gradient(state.astype(complex), lu, reference)
    with pytest.raises(ValueError, match="match"):
        forward.adjoint_gradient(state, lu, reference[:, 0])


def test_continuum_rejects_complex_flux(physical_case):
    forward, _ = physical_case
    continuum = ForwardModel(
        forward.mesh, forward.currents, forward.measurement, model="continuum"
    )
    with pytest.raises(ValueError, match="real"):
        continuum.continuum_flux(
            np.full(continuum.n, 0.03), np.ones(continuum.n, dtype=complex)
        )


def test_zero_change_uses_reference_norm_and_keeps_uniform_conductivity(physical_case):
    forward, reference = physical_case
    mask = np.ones(reference.shape, dtype=bool)
    objective = Objective(
        forward,
        np.zeros_like(reference),
        mask,
        0.03,
        baseline=reference,
        reference=reference,
    )
    assert objective.normalization_source == "reference"
    assert objective.norm2 == pytest.approx(np.sum(reference**2))
    value, gradient, _ = objective(np.ones(forward.n))
    assert value == pytest.approx(0.0, abs=1e-15)
    np.testing.assert_allclose(gradient, 0, atol=1e-12)
    rng = np.random.default_rng(9)
    relative = rng.uniform(0.8, 1.2, forward.n)
    direction = rng.normal(size=forward.n)
    delta = 1e-6
    difference = (
        objective(relative + delta * direction)[0]
        - objective(relative - delta * direction)[0]
    ) / (2 * delta)
    np.testing.assert_allclose(
        difference, objective(relative)[1] @ direction, rtol=2e-5, atol=1e-8
    )
    solver = LBFGSBTVSolver(max_iterations=0)
    recovered = solver.solve(reference, forward, reference=reference, mask=mask)
    np.testing.assert_allclose(recovered, 0.03)
    assert solver.last_info["status"] == "max_iterations"


@pytest.mark.parametrize("reference_kind", ["absent", "zero"])
def test_zero_measurement_without_usable_reference_is_rejected(
    physical_case, reference_kind
):
    forward, reference = physical_case
    kwargs = (
        {} if reference_kind == "absent" else {"reference": np.zeros_like(reference)}
    )
    with pytest.raises(ValueError, match="norm"):
        Objective(
            forward,
            np.zeros_like(reference),
            np.ones(reference.shape, dtype=bool),
            0.03,
            **kwargs,
        )


def test_public_run_accepts_uniform_target(physical_case, tmp_path):
    forward, reference = physical_case
    mesh = forward.mesh
    case = eit.EITCase(
        mesh,
        dict(
            nodes=mesh.nodes,
            triangles=mesh.triangles,
            boundary_edges=mesh.boundary_edges,
            electrode_ids=mesh.electrode_ids,
            currents_A=forward.currents,
            measurement_matrix=forward.measurement,
            voltages_V=reference,
            reference_voltages_V=reference.copy(),
            measurement_mask=np.ones(reference.shape, dtype=bool),
            thickness_m=np.array(forward.thickness),
            contact_impedance_ohm_m2=forward.contact,
            background_conductivity_S_m=np.array(0.03),
            case_id=np.array("uniform"),
        ),
    )
    result = eit.run(
        case=case,
        config={
            "parameters": {"calibration_max_iterations": 1},
            "run_controls": {"max_iterations": 0},
        },
        out=tmp_path / "uniform",
    )
    assert result.status == "max_iterations"
    assert result.metadata["voltage_normalization_source"] == "reference"
    np.testing.assert_allclose(result.conductivity_S_m, 0.03)
    assert (tmp_path / "uniform" / "result.h5").is_file()
    record = json.loads((tmp_path / "uniform" / "run.json").read_text())
    assert record["metadata"]["voltage_normalization_source"] == "reference"


@pytest.mark.parametrize("epsilon", [0, -0.1, np.nan, 0.1 + 1j])
def test_tv_rejects_invalid_smoothing(physical_case, epsilon):
    forward, _ = physical_case
    with pytest.raises(ValueError):
        forward.mesh.tv(np.ones(forward.n), epsilon)


@pytest.mark.parametrize("background", [0, -0.03, np.inf, np.nan, 0.03 + 1j, [0.03]])
def test_conductivity_model_rejects_invalid_background(background):
    with pytest.raises(ValueError):
        RelativeConductivity(background)


@pytest.mark.parametrize(
    "relative", [0.5, [], [[1.0]], [0], [-1], [np.inf], [np.nan], [1.0 + 0j]]
)
def test_conductivity_model_rejects_invalid_relative_field(relative):
    with pytest.raises(ValueError):
        RelativeConductivity(0.03)(relative)


@pytest.mark.parametrize("background, relative", [(1e308, [10.0]), (1e-308, [1e-308])])
def test_conductivity_model_rejects_nonphysical_mapping_overflow(background, relative):
    with pytest.raises(FloatingPointError):
        RelativeConductivity(background)(relative)


def test_conductivity_model_maps_nodal_values_without_mutating_them():
    relative = np.array([0.5, 1.0, 2.0])
    conductivity = RelativeConductivity(0.03)(relative)
    np.testing.assert_allclose(conductivity, [0.015, 0.03, 0.06])
    np.testing.assert_array_equal(relative, [0.5, 1.0, 2.0])


@pytest.mark.parametrize("field", ["complex", "nonfinite", "shape"])
def test_direct_tv_entry_rejects_invalid_nodal_fields(physical_case, field):
    forward, _ = physical_case
    values = {
        "complex": np.ones(forward.n, dtype=complex),
        "nonfinite": np.full(forward.n, np.nan),
        "shape": np.ones((forward.n, 1)),
    }
    with pytest.raises(ValueError):
        smooth_tv(forward.mesh, values[field], 0.1)


@pytest.mark.parametrize("epsilon", [0, -0.1, np.nan, np.inf, 0.1 + 0j, [0.1]])
def test_direct_tv_entry_rejects_invalid_epsilon(physical_case, epsilon):
    forward, _ = physical_case
    with pytest.raises(ValueError):
        smooth_tv(forward.mesh, np.ones(forward.n), epsilon)


def test_direct_tv_detects_numerical_overflow(physical_case):
    forward, _ = physical_case
    field = np.linspace(-1e200, 1e200, forward.n)
    with pytest.raises(FloatingPointError, match="nonfinite"):
        smooth_tv(forward.mesh, field, 0.1)
