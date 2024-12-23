import math
import typing

from OCC.Core.gp import gp_Vec

from ezocc.data_structures.point_like import P3DLike
from ezocc.gcs_solver.constraints.constraint import Constraint
from ezocc.gcs_solver.entities.curve_entity import CurveEntity
from ezocc.gcs_solver.entities.point_entity import PointEntity
from ezocc.gcs_solver.parameter import Parameter


class TangencyConstraint(Constraint):

    def __init__(self, point: PointEntity, curve_a: CurveEntity, curve_b: CurveEntity):
        super().__init__({
            *curve_a.params,
            *curve_b.params
        })

        self.point = point
        self.curve_a = curve_a
        self.curve_b = curve_b

    def dof_restricted(self) -> int:
        return 1

    def get_error(self) -> float:
        t0 = self.curve_a.tangent_at_point(self.point.get_p3d_like())
        t1 = self.curve_b.tangent_at_point(self.point.get_p3d_like())

        return math.fabs(t0.get(gp_Vec).Angle(t1.get(gp_Vec)))

    def __str__(self):
        return f"Tangency: ({self.point}): {self.curve_a}, {self.curve_b})"

