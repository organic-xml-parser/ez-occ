import typing

from ezocc.data_structures.point_like import P3DLike
from ezocc.gcs_solver.entities.entity import Entity
from ezocc.gcs_solver.entities.point_entity import PointEntity
from ezocc.gcs_solver.parameter import Parameter


class CurveEntity(Entity):

    def __init__(self, params: typing.List[Parameter]):
        super().__init__(params)

    def tangent_at_point(self, point: P3DLike) -> P3DLike:
        """
        @param point: a point on the curve
        @return: the tangent vector to the specified point. The point is assumed to lie on the curve
        """

        raise NotImplementedError()

    def distance_from_curve(self, point: P3DLike) -> float:
        """
        @return: 0 if the specified point lies on the curve, distance from the nearest point on the curve otherwise
        """
        raise NotImplementedError()
