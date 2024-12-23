from __future__ import annotations

import math

import numpy

from ezocc.data_structures.point_like import P3DLike
from ezocc.gcs_solver.entities.entity import Entity
from ezocc.gcs_solver.parameter import Parameter
from ezocc.gcs_solver.system import System
from ezocc.part_manager import PartCache, Part, PartFactory


class PointEntity(Entity):

    def __init__(self, x: Parameter, y: Parameter):
        self.x = x
        self.y = y

        super().__init__([x, y])

    def __str__(self):
        return f"Point({self.x}, {self.y})"

    def get_p3d_like(self) -> P3DLike:
        return P3DLike(float(self.x.value), float(self.y.value), 0.0)

    def get_part(self, cache: PartCache) -> Part:
        return PartFactory(cache).vertex(self.x.value, self.y.value, 0)

    def distance_to(self, other: PointEntity) -> float:
        return math.hypot(self.x.value - other.x.value, self.y.value - other.y.value)

    @staticmethod
    def create(system: System, x: float, y: float) -> PointEntity:
        px = system.add_parameter(x)
        py = system.add_parameter(y)

        result = PointEntity(px, py)
        system.add_entity(result)
        return result

