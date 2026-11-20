"""Public execution, portable files and validation before work starts."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import h5py
import numpy as np
import pytest
import yaml

import eitbench as eit
from test_eit import case as case  # Explicitly re-export the shared pytest fixture.


@pytest.mark.parametrize("suffix", [".npz", ".h5", ".hdf5"])
def test_optional_provenance_and_all_case_arrays_roundtrip(case, tmp_path, suffix):
    case.data["data_kind"] = np.array("synthetic")
    case.data["measurement_mask"][0, 0] = False
    before = {name: value.copy() for name, value in case.data.items()}
    path = eit.save_case(case, tmp_path / ("case" + suffix))
    restored = eit.load_case(path)
    assert restored.source == path.resolve()
    for name, value in before.items():
        np.testing.assert_array_equal(restored.data[name], value, err_msg=name)
        np.testing.assert_array_equal(case.data[name], value, err_msg=name)
    if suffix != ".npz":
        with h5py.File(path) as handle:
            assert handle.attrs["schema"] == "eitbench.case.v1"


@pytest.mark.parametrize(
    "invalid",
    [
        "missing_field",
        "vector_thickness",
        "complex_voltage",
        "nonfinite_reference",
        "numeric_case_id",
    ],
)
def test_file_input_rejects_invalid_physical_contract(case, tmp_path, invalid):
    data = {name: value.copy() for name, value in case.data.items()}
    if invalid == "missing_field":
        data.pop("currents_A")
    elif invalid == "vector_thickness":
        data["thickness_m"] = np.array([0.07])
    elif invalid == "complex_voltage":
        data["voltages_V"] = data["voltages_V"].astype(complex) + 1j
    elif invalid == "nonfinite_reference":
        data["reference_voltages_V"][0, 0] = np.nan
    else:
        data["case_id"] = np.array(123)
    path = tmp_path / "invalid.npz"
    np.savez(path, **data)
    with pytest.raises(ValueError):
        eit.load_case(path)


def test_explicit_wrong_hdf5_schema_and_unsupported_extensions(case, tmp_path):
    path = eit.save_case(case, tmp_path / "wrong.h5")
    with h5py.File(path, "r+") as handle:
        handle.attrs["schema"] = "eitbench.result.v1"
    with pytest.raises(ValueError):
        eit.load_case(path)
    for operation in (eit.load_case, lambda p: eit.save_case(case, p)):
        with pytest.raises(ValueError):
            operation(tmp_path / "case.bin")
    assert not (tmp_path / "case.bin").exists()


@pytest.mark.parametrize("entry", ["run", "save"])
def test_mutated_python_case_is_revalidated_before_output(case, tmp_path, entry):
    case.data["voltages_V"][0, 0] = np.nan
    target = tmp_path / ("run" if entry == "run" else "case.h5")
    with pytest.raises(ValueError):
        if entry == "run":
            eit.run(
                case=case, config={"run_controls": {"max_iterations": 0}}, out=target
            )
        else:
            eit.save_case(case, target)
    assert not target.exists()


@pytest.mark.parametrize("invalid", [False, 0, []])
def test_config_requires_a_mapping(invalid):
    with pytest.raises(ValueError):
        eit.prepare_config(invalid)


@pytest.mark.parametrize(
    "caps",
    [
        {"max_iterations": -1},
        {"max_iterations": 2.5},
        {"max_iterations": True},
        {"max_iterations": float("inf")},
        {"max_elapsed_s": float("nan")},
        {"unsupported": 1},
    ],
)
def test_host_caps_are_validated_even_when_the_request_is_smaller(caps):
    with pytest.raises(ValueError):
        eit.prepare_config({"run_controls": {"max_iterations": 0}}, host_caps=caps)


def test_typed_config_is_revalidated_after_mutation():
    config = eit.prepare_config()
    config.parameters.alpha = -1
    with pytest.raises(ValueError):
        eit.prepare_config(config)


def test_saved_run_retains_inputs_and_reports_independently_computed_residual(
    case, tmp_path
):
    case.data["measurement_mask"][0, 0] = False
    before = {name: value.copy() for name, value in case.data.items()}
    out = tmp_path / "run"
    result = eit.run(case=case, config={"run_controls": {"max_iterations": 2}}, out=out)
    assert result.status in {"converged", "max_iterations"}
    for name, value in before.items():
        np.testing.assert_array_equal(case.data[name], value, err_msg=name)
    with h5py.File(out / "result.h5") as handle:
        for dataset, source in (
            ("observed_voltages_V", "voltages_V"),
            ("reference_voltages_V", "reference_voltages_V"),
            ("measurement_mask", "measurement_mask"),
            ("nodes", "nodes"),
            ("triangles", "triangles"),
        ):
            np.testing.assert_array_equal(handle[dataset][()], before[source])
        np.testing.assert_array_equal(
            handle["conductivity_S_m"][()], result.conductivity_S_m
        )
        np.testing.assert_array_equal(
            handle["predicted_voltages_V"][()], result.predicted_voltages_V
        )
    mask = before["measurement_mask"]
    residual = (
        result.predicted_voltages_V
        - result.baseline_voltages_V
        - before["voltages_V"]
        + before["reference_voltages_V"]
    )[mask]
    metrics = eit.evaluate(out)
    assert metrics["difference_voltage_rmse_V"] == pytest.approx(
        np.sqrt(np.mean(residual**2))
    )
    assert metrics["n_measurements"] == int(mask.sum())
    assert all(
        (out / name).is_file()
        for name in ("result.h5", "index.json", "metrics.json", "run.json")
    )


@pytest.mark.parametrize("problem", ["duplicate", "invalid_later", "empty"])
def test_suite_preflights_all_inputs_before_writing(
    case, tmp_path, monkeypatch, problem
):
    from eitbench.benchmark import runner

    second = copy.deepcopy(case)
    cases = [case, second]
    if problem == "invalid_later":
        second.data["case_id"] = np.array("second")
        second.data["voltages_V"][0, 0] = np.nan
    elif problem == "empty":
        cases = []
    monkeypatch.setattr(
        runner, "run", lambda *a, **kw: pytest.fail("work before suite preflight")
    )
    out = tmp_path / "suite"
    with pytest.raises(ValueError):
        eit.suite(cases, out=out)
    assert not out.exists()


def test_suite_uses_independent_case_budgets_and_saves_a_completed_summary(
    case, tmp_path
):
    second = copy.deepcopy(case)
    second.data["case_id"] = np.array("second")
    out = tmp_path / "suite"
    records = eit.suite(
        [case, second],
        config={"run_controls": {"max_iterations": 10}},
        host_caps={"max_iterations": 0},
        out=out,
    )
    assert [row["case_id"] for row in records] == ["synthetic", "second"]
    assert [row["directory"] for row in records] == ["000", "001"]
    summary = json.loads((out / "summary.json").read_text())
    assert summary == {"completed": True, "cases": records}
    work = []
    for row in records:
        directory = out / row["directory"]
        saved = json.loads((directory / "run.json").read_text())
        assert saved["optimization"]["iterations"] == 0
        assert (directory / "result.h5").is_file()
        work.append(saved["work"]["forward_calls"])
    assert work[0] == work[1] and work[0] > 0


def test_numerical_failure_is_recorded_without_a_false_reconstruction(
    case, tmp_path, monkeypatch
):
    from eitbench.algorithms.lbfgsb_tv import LBFGSBTV

    def fail(*args):
        raise FloatingPointError("injected FEM failure")

    monkeypatch.setattr(LBFGSBTV, "run", fail)
    out = tmp_path / "failed"
    result = eit.run(case=case, out=out)
    assert result.status == "numerical_error"
    assert result.conductivity_S_m is None
    assert "injected FEM failure" in result.stopping_reason
    assert (out / "run.json").is_file()
    assert not (out / "result.h5").exists()
    assert not (out / "index.json").exists()


def test_overflowing_reference_norm_is_a_structured_numerical_failure(case, tmp_path):
    # Each input is finite, but normalizing by sum(reference**2) would overflow.
    case.data["reference_voltages_V"][:] = 1e200
    out = tmp_path / "overflow"
    with np.errstate(over="ignore", invalid="ignore"):
        result = eit.run(case=case, out=out)
    assert result.status == "numerical_error"
    assert result.conductivity_S_m is None
    assert json.loads((out / "run.json").read_text())["status"] == "numerical_error"
    assert not (out / "result.h5").exists()
    assert not (out / "index.json").exists()


def saved_input_record(case, out):
    result = eit.run(
        case=case, config={"run_controls": {"max_forward_calls": 0}}, out=out
    )
    assert result.status == "resource_exhausted"
    record = json.loads((out / "run.json").read_text())["input"]
    assert record["source_file_hash_timing"] == "artifact_save"
    assert len(record["content_sha256"]) == 64
    int(record["content_sha256"], 16)
    assert set(record["arrays"]) == set(case.data)
    for name, array in case.data.items():
        description = record["arrays"][name]
        assert np.dtype(description["dtype"]) == array.dtype
        assert description["shape"] == list(array.shape)
        assert len(description["sha256"]) == 64
        int(description["sha256"], 16)
    return record


def test_provenance_distinguishes_modified_memory_from_the_same_source(case, tmp_path):
    source = eit.save_case(case, tmp_path / "source.npz")
    original = eit.load_case(source)
    modified = eit.load_case(source)
    modified.data["voltages_V"][0, 0] += 0.01
    before = saved_input_record(original, tmp_path / "original")
    after = saved_input_record(modified, tmp_path / "modified")
    assert before["path"] == after["path"] == str(source.resolve())
    assert before["sha256"] == after["sha256"]
    assert before["sha256"] is not None
    assert before["content_sha256"] != after["content_sha256"]
    assert (
        before["arrays"]["voltages_V"]["sha256"]
        != after["arrays"]["voltages_V"]["sha256"]
    )
    for name in set(original.data) - {"voltages_V"}:
        assert before["arrays"][name] == after["arrays"][name]


def test_memory_only_case_has_content_provenance(case, tmp_path):
    assert case.source is None
    record = saved_input_record(case, tmp_path / "memory")
    assert record["path"] is None
    assert record["sha256"] is None


def test_deleted_source_does_not_prevent_saving_an_admitted_case(case, tmp_path):
    source = eit.save_case(case, tmp_path / "source.npz")
    loaded = eit.load_case(source)
    source.unlink()
    record = saved_input_record(loaded, tmp_path / "deleted")
    assert record["path"] == str(source.resolve())
    assert record["sha256"] is None


def cli_json(cwd, *arguments):
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    environment.update(
        OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1"
    )
    process = subprocess.run(
        [sys.executable, "-m", "eitbench", *arguments],
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    return json.loads(process.stdout)


def test_cli_discovery_inspection_and_portable_yaml_benchmark(case, tmp_path):
    project = tmp_path / "inputs"
    eit.save_case(case, project / "case.h5")
    (project / "config.yaml").write_text(
        yaml.safe_dump({"run_controls": {"max_iterations": 0}})
    )
    (project / "suite.yaml").write_text(
        yaml.safe_dump({"cases": ["case.h5"], "config": "config.yaml"})
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    assert cli_json(elsewhere, "list-algorithms") == ["lbfgsb_tv"]
    described = cli_json(elsewhere, "list", "--json")
    assert described[0]["algorithm_id"] == "lbfgsb_tv"
    inspected = cli_json(elsewhere, "inspect", "--case", str(project / "case.h5"))
    assert inspected["case_id"] == case.case_id
    assert inspected["voltage_shape"] == list(case.data["voltages_V"].shape)
    output = tmp_path / "benchmark"
    records = cli_json(
        elsewhere, "bench", "--suite", str(project / "suite.yaml"), "--out", str(output)
    )
    assert records[0]["status"] == "max_iterations"
    metrics = cli_json(elsewhere, "evaluate", "--run", str(output / "000"))
    assert metrics["n_measurements"] == int(case.data["measurement_mask"].sum())


def test_rasterization_preserves_nonconvex_domain_and_linear_conductivity():
    from eitbench.operators.fem import Mesh
    from eitbench.viz import rasterize

    # Three unit squares form an L; the upper-right square is outside the domain.
    nodes = np.array(
        [[0, 0], [1, 0], [2, 0], [0, 1], [1, 1], [2, 1], [0, 2], [1, 2]], float
    )
    triangles = np.array(
        [[0, 1, 4], [0, 4, 3], [1, 2, 5], [1, 5, 4], [3, 4, 7], [3, 7, 6]]
    )
    edges = np.array([[0, 1], [1, 2], [2, 5], [5, 4], [4, 7], [7, 6], [6, 3], [3, 0]])
    mesh = Mesh(nodes, triangles, edges, np.full(len(edges), -1))
    conductivity = 0.03 + 0.005 * nodes[:, 0] + 0.003 * nodes[:, 1]
    image, mask = rasterize(mesh, conductivity, size=9)
    x, y = np.meshgrid(np.linspace(0, 2, 9), np.linspace(2, 0, 9))
    np.testing.assert_array_equal(mask, (x <= 1) | (y <= 1))
    np.testing.assert_allclose(image[mask], (0.03 + 0.005 * x + 0.003 * y)[mask])
