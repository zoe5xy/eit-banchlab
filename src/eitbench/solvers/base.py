"""Shared measurement/operator solver convention, matching the reference layout."""

from abc import ABC, abstractmethod


class InverseProblemSolver(ABC):
    @abstractmethod
    def solve(self, measurement, operator, **kwargs):
        """Recover a model from a measurement and physical operator."""
