from __future__ import annotations

import math

import numpy as np
import OCC.Core.BRepPrimAPI
from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Lin, gp_Quaternion, gp_Trsf

from ezocc.data_structures.point_like import P3DLike
from ezocc.gcs_solver.constraints.distance_constraint import DistanceConstraint
from ezocc.gcs_solver.constraints.incidence_constraint import IncidenceConstraint
from ezocc.gcs_solver.entities.bounded_curve_entity import BoundedCurveEntity
from ezocc.gcs_solver.entities.curve_entity import CurveEntity
from ezocc.gcs_solver.entities.entity import Entity
from ezocc.gcs_solver.entities.point_entity import PointEntity
from ezocc.gcs_solver.parameter import Parameter
from ezocc.gcs_solver.system import System
from ezocc.occutils_python import WireSketcher
from ezocc.part_manager import PartCache, Part, PartFactory


class LineSegmentEntity(BoundedCurveEntity):

    def __init__(self,
                 p0: PointEntity,
                 p1: PointEntity):
        super().__init__([*p0.params, *p1.params])

        self.p0 = p0
        self.p1 = p1

    def __str__(self):
        return f"LineSegment(p0={self.p0}, p1={self.p1})"

    def tangent_at_point(self, point: P3DLike) -> P3DLike:
        # tangent of line segment is the same for all points
        tangent = gp_Vec(
            self.point_0.get(gp_Pnt),
            self.point_1.get(gp_Pnt))

        return P3DLike(tangent.Normalized())

    @property
    def point_0(self) -> P3DLike:
        return P3DLike(float(self.p0.x.value), float(self.p0.y.value), 0)

    @property
    def point_1(self) -> P3DLike:
        return P3DLike(float(self.p1.x.value), float(self.p1.y.value), 0)

    def distance_from_curve(self, point: P3DLike) -> float:
        # convert the point to local coordinates where the line is the x axis, then the following rules apply:
        # if the point.x < 0, or point.x > line_length, distance is hypot to nearest endpoint
        # else, distance is just the y coordinate
        p0_vec = gp_Vec(gp_Pnt(0, 0, 0), self.point_0.get(gp_Pnt))
        line_vec = gp_Vec(self.point_0.get(gp_Pnt), self.point_1.get(gp_Pnt))

        point_adj = point.get(gp_Pnt).Translated(p0_vec.Reversed())
        rotation_quat = gp_Quaternion(line_vec.Normalized(), gp_Vec(1, 0, 0).Normalized())
        rotation_trsf = gp_Trsf()
        rotation_trsf.SetRotation(rotation_quat)
        point_adj = point_adj.Transformed(rotation_trsf)

        if point_adj.X() < 0:
            return point_adj.Distance(gp_Pnt(0, 0, 0))
        elif point_adj.X() > line_vec.Magnitude():
            return point_adj.Distance(gp_Pnt(line_vec.Magnitude(), 0, 0))
        else:
            return math.hypot(point_adj.Y(), point_adj.Z())

    def get_part(self, cache: PartCache) -> Part:
        return (WireSketcher(self.p0.x.value, self.p0.y.value, 0)
                .line_to(self.p1.x.value, self.p1.y.value, 0)
                .get_wire_part(cache))

    def get_p0(self) -> PointEntity:
        return self.p0

    def get_p1(self) -> PointEntity:
        return self.p1

    def length(self) -> float:
        return self.p0.get_p3d_like().get(gp_Pnt).Distance(self.p1.get_p3d_like().get(gp_Pnt))

    @staticmethod
    def create(system: System, p0: PointEntity, p1: PointEntity) -> LineSegmentEntity:
        result = LineSegmentEntity(p0, p1)

        system.add_entity(result)
        return result

