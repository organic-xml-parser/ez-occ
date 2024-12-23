from __future__ import annotations

import math
import typing

from ezocc.gcs_solver.constraints.constraint import Constraint
from ezocc.gcs_solver.entities.point_entity import PointEntity
from ezocc.gcs_solver.parameter import Parameter
from ezocc.gcs_solver.system import System


class DistanceConstraint(Constraint):

    @staticmethod
    def create(system: System, p0: PointEntity, p1: PointEntity, dist: typing.Union[float, Parameter]) -> DistanceConstraint:
        dist = dist if isinstance(dist, Parameter) else system.add_parameter(dist, fixed=True)

        cons = DistanceConstraint(
            dist,
            p0.x,
            p0.y,
            p1.x,
            p1.y
        )

        system.add_constraint(cons)

        return cons

    def __init__(self, dist: Parameter, x0: Parameter, y0: Parameter, x1: Parameter, y1: Parameter):
        super().__init__({dist, x0, y0, x1, y1})
        self.dist = dist
        self.x0 = x0
        self.x1 = x1
        self.y0 = y0
        self.y1 = y1

    def dof_restricted(self) -> int:
        return 1

    def get_error(self) -> float:
        return math.fabs(math.hypot(
            self.x0.value - self.x1.value,
            self.y0.value - self.y1.value
        ) - self.dist.value)

    def __str__(self):
        return f"Distance: ({self.x0}, {self.y0}) -- {self.dist} -- ({self.x1}, {self.y1})"
