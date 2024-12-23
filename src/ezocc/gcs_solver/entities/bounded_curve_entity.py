import typing

from ezocc.gcs_solver.entities.curve_entity import CurveEntity
from ezocc.gcs_solver.entities.point_entity import PointEntity
from ezocc.gcs_solver.parameter import Parameter


class BoundedCurveEntity(CurveEntity):
    """
    Represents a curve interval bounded by two points. The points are expected to be constrained to lie on the curve.
    """

    def __init__(self, params: typing.List[Parameter]):
        super().__init__(params)

    def get_p0(self) -> PointEntity:
        raise NotImplementedError()

    def get_p1(self) -> PointEntity:
        raise NotImplementedError()

    def length(self) -> float:
        raise NotImplementedError()
