import numpy as np
from ..core.run_controls import BudgetExhausted, WorkLedger
from ..core.schema import ReconstructionResult
from ..operators.forward import ForwardModel, _real_array
from ..solvers.lbfgsb import optimize
from .calibration import calibrate


class Objective:
    def __init__(
        self,
        forward,
        measured,
        mask,
        background,
        alpha=0.03,
        tv_epsilon=0.1,
        baseline=None,
        reference=None,
    ):
        self.forward = forward
        self.measured = _real_array(measured, "measurement")
        self.mask = np.asarray(mask)
        expected = (len(forward.measurement), forward.currents.shape[1])
        if self.measured.shape != expected:
            raise ValueError("measurement must match the protocol")
        if (
            self.mask.dtype.kind != "b"
            or self.mask.shape != expected
            or not self.mask.any()
        ):
            raise ValueError("measurement mask must be nonempty boolean [Q,P]")
        values = (
            _real_array(background, "background"),
            _real_array(alpha, "TV weight"),
            _real_array(tv_epsilon, "TV epsilon"),
        )
        if any(value.shape != () for value in values):
            raise ValueError("background, TV weight and TV epsilon must be scalar")
        self.background, self.alpha, self.tv_epsilon = map(float, values)
        if self.background <= 0 or self.alpha < 0 or self.tv_epsilon <= 0:
            raise ValueError(
                "positive background/TV epsilon and nonnegative TV weight required"
            )
        self.baseline = (
            np.zeros_like(self.measured)
            if baseline is None
            else _real_array(baseline, "baseline")
        )
        if self.baseline.shape != expected:
            raise ValueError("baseline must match the protocol")
        if reference is not None:
            reference = _real_array(reference, "reference")
            if reference.shape != expected:
                raise ValueError("reference must match the protocol")
        with np.errstate(over="ignore", invalid="ignore"):
            self.norm2 = float(np.sum(self.measured[self.mask] ** 2))
        self.normalization_source = "measurement"
        if self.norm2 < 1e-24 and reference is not None:
            with np.errstate(over="ignore", invalid="ignore"):
                self.norm2 = float(np.sum(reference[self.mask] ** 2))
            self.normalization_source = "reference"
        if not np.isfinite(self.norm2) or self.norm2 < 1e-24:
            raise ValueError(
                "measurement/reference norm is too small or nonfinite "
                "for normalized inversion"
            )

    def __call__(self, m):
        predicted, state, lu = self.forward.solve(m * self.background)
        residual = predicted - self.baseline - self.measured
        weighted = np.where(self.mask, residual / self.norm2, 0.0)
        gradient, _ = self.forward.adjoint_gradient(state, lu, weighted)
        value = 0.5 * float(np.sum(residual[self.mask] ** 2)) / self.norm2
        tv, tv_grad = self.forward.mesh.tv(m, self.tv_epsilon)
        return (
            value + self.alpha * tv,
            self.background * gradient + self.alpha * tv_grad,
            dict(predicted=predicted, state=state),
        )


class LBFGSBTV:
    def run(self, case, config):
        parameters, controls = config.parameters, config.run_controls
        ledger = WorkLedger(controls)
        calibration, cal_info = calibrate(case, parameters, ledger)
        if calibration is None or cal_info["status"] in {
            "resource_exhausted",
            "numerical_error",
        }:
            return ReconstructionResult(
                None,
                None,
                None,
                None,
                cal_info["status"],
                cal_info["stopping_reason"],
                calibration=cal_info,
                work=ledger.snapshot(),
                metadata={"stopped_phase": "calibration"},
            )
        background, contact = (
            calibration.payload["background"],
            calibration.payload["contact"],
        )
        data = case.data
        forward = ForwardModel(
            case.mesh,
            data["currents_A"],
            data["measurement_matrix"],
            float(data["thickness_m"]),
            parameters.variant,
            contact,
            ledger,
        )
        try:
            baseline, _, _ = forward.solve(np.full(forward.n, background))
        except (BudgetExhausted, FloatingPointError, RuntimeError) as exc:
            status = (
                "resource_exhausted"
                if isinstance(exc, BudgetExhausted)
                else "numerical_error"
            )
            return ReconstructionResult(
                None,
                None,
                None,
                None,
                status,
                str(exc),
                calibration=cal_info,
                work=ledger.snapshot(),
                metadata={"stopped_phase": "baseline"},
            )
        difference = parameters.mode == "difference"
        measured = (
            data["voltages_V"] - data["reference_voltages_V"]
            if difference
            else data["voltages_V"]
        )
        objective = Objective(
            forward,
            measured,
            data["measurement_mask"],
            background,
            parameters.alpha,
            parameters.tv_epsilon,
            baseline if difference else None,
            reference=data["reference_voltages_V"] if difference else None,
        )
        record, info = optimize(
            objective,
            np.ones(forward.n),
            [(parameters.lower, parameters.upper)] * forward.n,
            ledger,
            maxiter=controls.max_iterations,
            ftol=parameters.ftol,
            gtol=parameters.gtol,
        )
        conductivity = None if record is None else background * record.x
        if record:
            info.update(
                hit_lower_fraction=float(np.mean(record.x <= parameters.lower + 1e-6)),
                hit_upper_fraction=float(np.mean(record.x >= parameters.upper - 1e-6)),
            )
        return ReconstructionResult(
            conductivity,
            record.payload["predicted"] if record else None,
            baseline,
            record.payload["state"][: forward.n] if record else None,
            info["status"],
            info["stopping_reason"],
            cal_info,
            info,
            ledger.snapshot(),
            metadata={
                "stopped_phase": "reconstruction",
                "voltage_normalization_source": objective.normalization_source,
            },
        )
