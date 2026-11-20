"""Conductivity-to-voltage interface with a per-evaluation discrete adjoint."""

import numpy as np
from .base import ForwardOperator, Linearization
from .forward import _real_array


class EITForwardOperator(ForwardOperator):
    def __init__(self, physics, *, baseline=None):
        self.physics = physics
        self.domain_shape = (physics.n,)
        self.range_shape = (physics.measurement.shape[0], physics.currents.shape[1])
        self.baseline = (
            np.zeros(self.range_shape)
            if baseline is None
            else _real_array(baseline, "baseline").copy()
        )
        if (
            self.baseline.shape != self.range_shape
            or not np.isfinite(self.baseline).all()
        ):
            raise ValueError("baseline must be finite and match voltage shape")

    def forward(self, conductivity):
        return self.physics.solve(conductivity)[0] - self.baseline

    def linearize(self, conductivity):
        value, state, lu = self.physics.solve(conductivity)

        def adjoint(voltages):
            v = _real_array(voltages, "voltage derivative")
            if v.shape != self.range_shape or not np.isfinite(v).all():
                raise ValueError(
                    "voltage derivative must be finite and match measurements"
                )
            return self.physics.adjoint_gradient(state, lu, v)[0]

        return Linearization(value - self.baseline, adjoint)
