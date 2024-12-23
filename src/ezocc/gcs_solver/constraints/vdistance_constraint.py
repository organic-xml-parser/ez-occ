from __future__ import annotations

import math
import typing

from ezocc.gcs_solver.constraints.constraint import Constraint
from ezocc.gcs_solver.entities.point_entity import PointEntity
from ezocc.gcs_solver.parameter import Parameter
from ezocc.gcs_solver.system import System


class VDistanceConstraint(Constraint):

    @staticmethod
    def create(system: System,
               p0: PointEntity,
               p1: PointEntity, dist: typing.Union[float, Parameter]) -> VDistanceConstraint:
        dist = dist if isinstance(dist, Parameter) else system.add_parameter(dist, fixed=True)

        cons = VDistanceConstraint(
            dist,
            p0.y,
            p1.y
        )

        system.add_constraint(cons)

        return cons

    def __init__(self, dist: Parameter, y0: Parameter, y1: Parameter):
        super().__init__({dist, y0, y1})
        self.dist = dist
        self.y0 = y0
        self.y1 = y1

    def get_error(self) -> float:
        return math.fabs(self.dist.value - math.fabs(self.y1.value - self.y0.value))

    def dof_restricted(self) -> int:
        return 1

    def __str__(self):
        return f"VDistance: ({self.y0}) -- {self.dist} -- ({self.y1})"
