from __future__ import annotations

import math
import typing

from ezocc.gcs_solver.constraints.constraint import Constraint
from ezocc.gcs_solver.entities.point_entity import PointEntity
from ezocc.gcs_solver.parameter import Parameter
from ezocc.gcs_solver.system import System


class SymmetryConstraint(Constraint):

    def __init__(self,
                 p0: PointEntity,
                 p1: PointEntity,
                 p_center: PointEntity):
        x0 = p0.x
        y0 = p0.y
        x1 = p1.x
        y1 = p1.y
        x_center = p_center.x
        y_center = p_center.y
        super().__init__({x0, y0, x1, y1, x_center, y_center})
        self.x0 = x0
        self.x1 = x1
        self.y0 = y0
        self.y1 = y1
        self.x_center = x_center
        self.y_center = y_center

    def get_error(self) -> float:
        dist_0 = math.hypot(
            self.x0.value - self.x_center.value,
            self.y0.value - self.y_center.value
        )

        dist_1 = math.hypot(
            self.x1.value - self.x_center.value,
            self.y1.value - self.y_center.value
        )

        return math.fabs(dist_0 - dist_1)

    def __str__(self):
        return f"Symmetry: ({self.x0}, {self.y0}) -- {self.x_center}, {self.y_center} -- ({self.x1}, {self.y1})"
