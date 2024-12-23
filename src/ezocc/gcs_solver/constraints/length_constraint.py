import typing

from OCC.Core.gp import gp_Vec

from ezocc.gcs_solver.constraints.constraint import Constraint
from ezocc.gcs_solver.entities.bounded_curve_entity import BoundedCurveEntity
from ezocc.gcs_solver.entities.curve_entity import CurveEntity
from ezocc.gcs_solver.entities.point_entity import PointEntity
from ezocc.gcs_solver.parameter import Parameter


class LengthConstraint(Constraint):

    def __init__(self, length: Parameter, *curves: BoundedCurveEntity):
        params = set()
        for c in curves:
            for p in c.params:
                params.add(p)

        params.add(length)

        super().__init__(params)

        self.length = length
        self.curves = curves

    def dof_restricted(self) -> int:
        return 1 # is this actually 1?!

    def get_error(self) -> float:
        total_length = sum(c.length() for c in self.curves)

        return self.length.value - total_length

    def __str__(self):
        return f"Length: ({self.length}): [{self.curves}])"

