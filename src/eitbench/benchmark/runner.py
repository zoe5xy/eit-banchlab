"""Validated single-case and sequential batch execution."""

from pathlib import Path
from time import perf_counter
import numpy as np
from ..core.config import prepare_config
from ..core.io import load_case
from ..core.registry import get_algorithm
from ..core.schema import EITCase, ReconstructionResult
from .artifacts import save_result, write_json


def _admit_case(case):
    return case.validated_copy() if isinstance(case, EITCase) else load_case(case)


def _empty_output(target):
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ValueError(f"output must be an empty directory: {target}")


def run(
    algorithm="lbfgsb_tv", *, case, config=None, out=None, host_caps=None, preview=False
):
    method = get_algorithm(algorithm)
    resolved = prepare_config(config, host_caps=host_caps)
    case = _admit_case(case)
    target = Path(out).resolve() if out is not None else None
    if target is not None:
        _empty_output(target)
        target.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    try:
        result = method.run(case, resolved)
    except (ValueError, ArithmeticError, RuntimeError, np.linalg.LinAlgError) as exc:
        # Admission errors raise before creating output; numerical failures after
        # admission remain inspectable, even before an initial checkpoint exists.
        result = ReconstructionResult(
            None,
            None,
            None,
            None,
            "numerical_error",
            str(exc),
            work={"elapsed_s": perf_counter() - started},
            metadata={
                "stopped_phase": "algorithm",
                "exception_type": type(exc).__name__,
                "work_counts_available": False,
            },
        )
    if target is not None:
        save_result(target, case, resolved, result, preview=preview)
    return result


def suite(
    cases, *, algorithm="lbfgsb_tv", config=None, out, preview=False, host_caps=None
):
    get_algorithm(algorithm)
    resolved = prepare_config(config, host_caps=host_caps)
    if isinstance(cases, (str, Path)):
        raise ValueError("cases must be a sequence of case objects or paths")
    admitted = [_admit_case(source) for source in cases]
    if not admitted:
        raise ValueError("suite requires at least one case")
    seen = set()
    for case in admitted:
        if case.case_id in seen:
            raise ValueError("duplicate suite case ID: " + case.case_id)
        seen.add(case.case_id)
    target = Path(out).resolve()
    _empty_output(target)
    target.mkdir(parents=True, exist_ok=True)
    records = []
    write_json(target / "summary.json", {"completed": False, "cases": records})
    for i, case in enumerate(admitted):
        # Calibration and budgets are independent for every case.
        folder = f"{i:03d}"
        result = run(
            algorithm, case=case, config=resolved, out=target / folder, preview=preview
        )
        records.append(
            dict(
                case_id=case.case_id,
                directory=folder,
                status=result.status,
                stopping_reason=result.stopping_reason,
            )
        )
        write_json(
            target / "summary.json",
            {"completed": i == len(admitted) - 1, "cases": records},
        )
    return records


def bench(suite_config, *, out, preview=False):
    """Run a YAML suite; all file references are relative to the suite file."""
    import yaml

    path = Path(suite_config).resolve()
    specification = yaml.safe_load(path.read_text(encoding="utf-8"))
    allowed = {"algorithm", "config", "cases"}
    if not isinstance(specification, dict) or set(specification) - allowed:
        raise ValueError("suite YAML accepts only algorithm, config and cases")
    cases = specification.get("cases")
    if (
        not isinstance(cases, list)
        or not cases
        or not all(isinstance(p, str) for p in cases)
    ):
        raise ValueError("suite cases must be a nonempty list of paths")
    config = specification.get("config")
    if isinstance(config, str):
        config = path.parent / config
    return suite(
        [path.parent / p for p in cases],
        algorithm=specification.get("algorithm", "lbfgsb_tv"),
        config=config,
        out=out,
        preview=preview,
    )
