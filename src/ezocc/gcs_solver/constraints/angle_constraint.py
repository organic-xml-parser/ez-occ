from __future__ import annotations

import math
import typing

from ezocc.gcs_solver.constraints.constraint import Constraint
from ezocc.gcs_solver.entities.point_entity import PointEntity
from ezocc.gcs_solver.parameter import Parameter
from ezocc.gcs_solver.system import System


class AngleConstraint(Constraint):

    @staticmethod
    def create(system: System,
               p_origin: PointEntity,
               p0: PointEntity,
               p1: PointEntity,
               angle: float) -> AngleConstraint:
        cons = AngleConstraint(
            p_origin,
            p0,
            p1,
            system.add_parameter(angle, fixed=True))

        system.add_constraint(cons)

        return cons

    def __init__(self, p_origin: PointEntity, p0: PointEntity, p1: PointEntity, angle: Parameter):
        super().__init__({*p_origin.params, *p0.params, *p1.params, angle})
        self.angle = angle
        self.p_origin = p_origin
        self.p0 = p0
        self.p1 = p1

    def get_error(self) -> float:
        dp0 = [self.p0.x.value - self.p_origin.x.value, self.p0.y.value - self.p_origin.y.value]
        dp1 = [self.p1.x.value - self.p_origin.x.value, self.p1.y.value - self.p_origin.y.value]

        dot_product = dp0[0] * dp1[0] + dp0[1] * dp1[1]

        actual_angle = math.acos(dot_product / (math.hypot(*dp0) * math.hypot(*dp1)))

        return self.angle.value - actual_angle

    def __str__(self):
        return f"Angle: ({self.p_origin} -- {math.degrees(self.angle.value)} -- {self.p0}, {self.p1})"
