"""Low-level measurement/operator API for the supplied L-BFGS-B + FEM TV method."""

import numpy as np
from .base import InverseProblemSolver
from .lbfgsb import optimize
from ..core.run_controls import RunControls, WorkLedger
from ..operators.forward import ForwardModel, _real_array


class LBFGSBTVSolver(InverseProblemSolver):
    """Fixed-background solve; use the public run API for reference calibration."""

    def __init__(
        self,
        max_iterations=500,
        alpha=0.03,
        tv_epsilon=0.1,
        lower=0.05,
        upper=5.0,
        ftol=1e-8,
        gtol=1e-6,
    ):
        from ..algorithms.parameters import Parameters

        self.parameters = Parameters(
            alpha=alpha,
            tv_epsilon=tv_epsilon,
            lower=lower,
            upper=upper,
            ftol=ftol,
            gtol=gtol,
        )
        self.controls = RunControls(max_iterations=max_iterations)
        self.last_info = None

    def solve(
        self, measurement, operator, *, background=0.03, reference=None, mask=None
    ):
        from ..algorithms.lbfgsb_tv import Objective
        from ..models import RelativeConductivity

        background = _real_array(background, "background")
        if background.shape != ():
            raise ValueError("background must be scalar")
        background = RelativeConductivity(float(background)).background_S_m
        physics = getattr(operator, "physics", operator)
        ledger = WorkLedger(self.controls)
        f = ForwardModel(
            physics.mesh,
            physics.currents,
            physics.measurement,
            physics.thickness,
            physics.model,
            physics.contact,
            ledger,
        )
        measured = _real_array(measurement, "measurement")
        expected = (physics.measurement.shape[0], physics.currents.shape[1])
        if measured.shape != expected or not np.isfinite(measured).all():
            raise ValueError("measurement must be finite and match the protocol")
        active = (
            np.ones_like(measured, dtype=bool) if mask is None else np.asarray(mask)
        )
        if active.dtype.kind != "b" or active.shape != expected or not active.any():
            raise ValueError("measurement mask must be nonempty boolean [Q,P]")
        baseline = None
        if reference is not None:
            reference = _real_array(reference, "reference")
            if reference.shape != expected or not np.isfinite(reference).all():
                raise ValueError("invalid reference")
            measured = measured - reference
            baseline = f.solve(np.full(f.n, background))[0]
        p = self.parameters
        objective = Objective(
            f,
            measured,
            active,
            background,
            p.alpha,
            p.tv_epsilon,
            baseline,
            reference=reference,
        )
        record, info = optimize(
            objective,
            np.ones(f.n),
            [(p.lower, p.upper)] * f.n,
            ledger,
            maxiter=self.controls.max_iterations,
            ftol=p.ftol,
            gtol=p.gtol,
        )
        self.last_info = {**info, "work": ledger.snapshot()}
        if record is None:
            raise RuntimeError(info["message"])
        return background * record.x
