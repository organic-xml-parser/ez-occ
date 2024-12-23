import typing

from OCC.Core.gp import gp_Vec

from ezocc.gcs_solver.constraints.constraint import Constraint
from ezocc.gcs_solver.entities.bounded_curve_entity import BoundedCurveEntity
from ezocc.gcs_solver.entities.circle_arc_entity import CircleArcEntity
from ezocc.gcs_solver.entities.circle_entity import CircleEntity
from ezocc.gcs_solver.entities.curve_entity import CurveEntity
from ezocc.gcs_solver.entities.point_entity import PointEntity
from ezocc.gcs_solver.parameter import Parameter


class RadiusConstraint(Constraint):

    def __init__(self, entity: typing.Union[CircleEntity, CircleArcEntity], value: Parameter):
        super().__init__({*entity.params, value})

        self.entity = entity
        self.value = value

    def dof_restricted(self) -> int:
        return 1 # is this actually 1?!

    def get_error(self) -> float:
        return abs(self.entity.radius - self.value.value)

    def __str__(self):
        return f"Radius: ({self.entity}): [{self.value}])"

