"""Forward-operator interfaces for NumPy FEM values."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable
import numpy as np


class ForwardOperator(ABC):
    domain_shape: tuple
    range_shape: tuple

    @abstractmethod
    def forward(self, model):
        """Evaluate the physical measurement map."""

    def __call__(self, model):
        return self.forward(model)


@dataclass(frozen=True)
class Linearization:
    value: np.ndarray
    adjoint: Callable
