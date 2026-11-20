"""Relative conductivity m maps to physical sigma in S/m."""

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class RelativeConductivity:
    background_S_m: float

    def __post_init__(self):
        background = np.asarray(self.background_S_m)
        if np.iscomplexobj(background) or background.shape != ():
            raise ValueError("background conductivity must be a real scalar")
        try:
            value = float(background)
        except (TypeError, ValueError) as exc:
            raise ValueError("background conductivity must be a real scalar") from exc
        if not np.isfinite(value) or value <= 0:
            raise ValueError("background conductivity must be finite and positive")
        object.__setattr__(self, "background_S_m", value)

    def __call__(self, m):
        if np.iscomplexobj(m):
            raise ValueError("relative conductivity must be real")
        try:
            m = np.asarray(m, dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError("relative conductivity must contain real numbers") from exc
        if m.ndim != 1 or m.size == 0 or not np.isfinite(m).all() or np.any(m <= 0):
            raise ValueError(
                "relative conductivity must be positive finite nonempty [N]"
            )
        with np.errstate(over="ignore", under="ignore", invalid="ignore"):
            conductivity = self.background_S_m * m
        if not np.isfinite(conductivity).all() or np.any(conductivity <= 0):
            raise FloatingPointError(
                "mapped conductivity must remain finite and positive"
            )
        return conductivity
