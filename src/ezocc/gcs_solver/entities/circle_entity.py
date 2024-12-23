from __future__ import annotations

import math

from ezocc.data_structures.point_like import P3DLike
from ezocc.gcs_solver.entities.curve_entity import CurveEntity
from ezocc.gcs_solver.entities.entity import Entity
from ezocc.gcs_solver.entities.point_entity import PointEntity
from ezocc.gcs_solver.parameter import Parameter
from ezocc.gcs_solver.system import System
from ezocc.part_manager import PartCache, Part, PartFactory


class CircleEntity(CurveEntity):

    def __init__(self, center: PointEntity, radius: Parameter):
        super().__init__([*center.params, radius])

        self.center = center
        self.radius = radius

    def __str__(self):
        return f"Circle({self.center}, r={self.radius})"

    def tangent_at_point(self, point_input: P3DLike) -> P3DLike:

        # project to a point on the circle
        x = point_input.x - self.center.x.value
        y = point_input.y - self.center.y.value

        # create a normal vector
        rnorm = math.hypot(x, y)

        if rnorm == 0:
            return P3DLike(1, 0, 0)

        x /= rnorm
        y /= rnorm

        # rotate 90 deg to compute tangent direction
        cn = math.cos(math.radians(90))
        sn = math.sin(math.radians(90))
        xr = cn * x - sn * y
        yr = sn * x + cn * y

        return P3DLike(xr, yr, 0)


    def distance_from_curve(self, point: P3DLike) -> float:
        distance_from_center = math.hypot(
            point.x - self.center.x.value,
            point.y - self.center.y.value)

        return math.fabs(distance_from_center - self.radius.value)

    def get_part(self, cache: PartCache) -> Part:
        return PartFactory(cache).circle(self.radius.value).tr.mv(self.center.x.value, self.center.y.value)

    @staticmethod
    def create(system: System, center: PointEntity, radius: float) -> CircleEntity:
        pr = system.add_parameter(radius)

        result = CircleEntity(center, pr)
        system.add_entity(result)
        return result

