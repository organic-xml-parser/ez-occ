import math
import typing

from ezocc.gcs_solver.constraints.constraint import Constraint
from ezocc.gcs_solver.entities.curve_entity import CurveEntity
from ezocc.gcs_solver.entities.point_entity import PointEntity
from ezocc.gcs_solver.parameter import Parameter
from ezocc.gcs_solver.system import System


class IncidenceConstraint(Constraint):
    """
    Constrains a point to lie on a curve
    """

    def __init__(self, point: PointEntity, curve: CurveEntity):
        super().__init__({*point.params, *curve.params})
        self.point = point
        self.curve = curve

    def get_error(self) -> float:
        return self.curve.distance_from_curve(self.point.get_p3d_like())

    @staticmethod
    def create(system: System, point: PointEntity, curve: CurveEntity):
        system.add_constraint(IncidenceConstraint(point, curve))
