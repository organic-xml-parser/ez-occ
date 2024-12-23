import math
import typing

from ezocc.gcs_solver.constraints.constraint import Constraint
from ezocc.gcs_solver.parameter import Parameter


class EqualityConstraint(Constraint):
    """
    Constrains two parameters to have the same value.
    """

    def __init__(self, y0: Parameter, y1: Parameter):
        super().__init__({y0, y1})
        self.y0 = y0
        self.y1 = y1

    def dof_restricted(self) -> int:
        return 1

    def get_error(self) -> float:
        return math.fabs(self.y0.value - self.y1.value)
