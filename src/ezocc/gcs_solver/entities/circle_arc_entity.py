from __future__ import annotations

import math
import typing

import OCC.Core.BRepBuilderAPI
import OCC.Core.BRepPrimAPI
import OCC.Core.BRepPrimAPI
import OCC.Core.GC
import OCC.Core.gp
from OCC.Core.GeomAPI import GeomAPI_ProjectPointOnCurve
from OCC.Core.gp import gp as gp
from OCC.Core.gp import gp_Pnt, gp_Vec

from ezocc.data_structures.point_like import P3DLike
from ezocc.gcs_solver.constraints.constraint import Constraint
from ezocc.gcs_solver.constraints.distance_constraint import DistanceConstraint
from ezocc.gcs_solver.constraints.gt_than_constraint import GtThanConstraint
from ezocc.gcs_solver.entities.bounded_curve_entity import BoundedCurveEntity
from ezocc.gcs_solver.entities.point_entity import PointEntity
from ezocc.gcs_solver.parameter import Parameter
from ezocc.gcs_solver.system import System
from ezocc.occutils_python import InterrogateUtils, WireSketcher
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import PartCache, Part, PartFactory, NoOpPartCache


class CircleArcEntity(BoundedCurveEntity):

    class PointConstraints(Constraint):

        def __init__(self,
                 center: PointEntity,
                 p0: PointEntity,
                 p1: PointEntity):
            super().__init__({*center.params, *p0.params, *p1.params})

            self.center = center
            self.p0 = p0
            self.p1 = p1

        def dof_restricted(self) -> int:
            return 1

        def get_error(self) -> float:
            rad = self.center.get_p3d_like().get(gp_Pnt).Distance(self.p0.get_p3d_like().get(gp_Pnt))

            rad_err = self.center.get_p3d_like().get(gp_Pnt).Distance(self.p1.get_p3d_like().get(gp_Pnt))

            return rad - rad_err

    def __init__(self,
                 center: PointEntity,
                 p0: PointEntity,
                 p1: PointEntity):
        super().__init__([*center.params, *p0.params, *p1.params])

        self.center = center
        self.p0 = p0
        self.p1 = p1

    def get_p0(self) -> PointEntity:
        return self.p0

    def get_p1(self) -> PointEntity:
        return self.p1

    def __str__(self):
        return f"CircleArc({self.center}, p0={self.p0}, p1={self.p1})"

    @property
    def radius(self):
        return self.center.get_p3d_like().get(gp_Pnt).Distance(self.p0.get_p3d_like().get(gp_Pnt))

    def _get_normalized(self, input_point: P3DLike) -> P3DLike:
        pnt = input_point.get(gp_Pnt).Translated(self.center.get_p3d_like().get(gp_Vec).Reversed())
        pnt = gp_Vec(pnt.X(), pnt.Y(), pnt.Z()).Normalized().Scaled(self.radius)
        pnt = self.center.get_p3d_like().get(gp_Pnt).Translated(pnt)

        return P3DLike(pnt)

    def get_implicit_constraints(self) -> typing.Set[Constraint]:
        return {
            CircleArcEntity.PointConstraints(self.center, self.p0, self.p1)
        }

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

        if self._is_clockwise():
            xr *= -1
            yr *= -1

        return P3DLike(gp_Pnt(xr, yr, 0))

    def distance_from_curve(self, point: P3DLike) -> float:
        # if the point lies in the segment

        distance_from_center = math.hypot(
            point.x - self.center.x.value,
            point.y - self.center.y.value)

        return math.fabs(distance_from_center - self.radius)

    def _is_clockwise(self):

        # sweep order should be
        # center -> p0 -> p1 clockwise
        # sum over edges (x2 - x1)(y2 + y1), positive result = cw curve
        # see: https://stackoverflow.com/questions/1165647/how-to-determine-if-a-list-of-polygon-points-are-in-clockwise-order

        edges = [
            (self.center, self.p0),
            (self.p0, self.p1),
            (self.p1, self.center)
        ]

        cw_sum = sum(
            (e2.x.value - e1.x.value) * (e2.y.value + e1.y.value) for e1, e2 in edges
        )


        return cw_sum > 0

    def get_part(self, cache: PartCache) -> Part:

        circ = OCC.Core.gp.gp_Circ(
            gp.XOY().Translated(OCC.Core.gp.gp_Vec(self.center.x.value, self.center.y.value, 0)), self.radius)

        if not self._is_clockwise():
            arc = OCC.Core.GC.GC_MakeArcOfCircle(
                circ,
                gp_Pnt(self.p0.x.value, self.p0.y.value, 0),
                gp_Pnt(self.p1.x.value, self.p1.y.value, 0),
                False
            )
        else:
            arc = OCC.Core.GC.GC_MakeArcOfCircle(
                circ,
                gp_Pnt(self.p1.x.value, self.p1.y.value, 0),
                gp_Pnt(self.p0.x.value, self.p0.y.value, 0),
                False
            )


        edge = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(arc.Value()).Edge()

        # edge = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(
        #    circ,
        #    gp_Pnt(self.p0.x.value, self.p0.y.value, 0),
        #    gp_Pnt(self.p1.x.value, self.p1.y.value, 0)).Shape()

        return Part.of_shape(edge, cache)
        # return Part.of_shape(edge, cache).add(
        #     PartFactory(cache).sphere(1).tr.mv(self.center.x.value, self.center.y.value, 0),
        #     PartFactory(cache).sphere(0.5).tr.mv(self.p0.x.value, self.p0.y.value, 0),
        #     PartFactory(cache).sphere(0.2).tr.mv(self.p1.x.value, self.p1.y.value, 0),
        #
        #     WireSketcher(self.p0.x.value, self.p0.y.value, 0)
        #     .line_to(*self.tangent_at_point(P3DLike(gp_Pnt(self.p0.x.value, self.p0.y.value, 0))).xyz, is_relative=True)
        #     .get_wire_part(NoOpPartCache.instance()),
        #     WireSketcher(self.p1.x.value, self.p1.y.value, 0)
        #         .line_to(*self.tangent_at_point(P3DLike(gp_Pnt(self.p1.x.value, self.p1.y.value, 0))).xyz, is_relative=True)
        #         .get_wire_part(NoOpPartCache.instance())
        # )

    def length(self) -> float:

        circ = OCC.Core.gp.gp_Circ(
            gp.XOY().Translated(OCC.Core.gp.gp_Vec(self.center.x.value, self.center.y.value, 0)), self.radius)

        arc = OCC.Core.GC.GC_MakeArcOfCircle(
            circ,
            gp_Pnt(self.p1.x.value, self.p1.y.value, 0),
            gp_Pnt(self.p0.x.value, self.p0.y.value, 0),
            True
        )

        edge = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(arc.Value()).Edge()

        return InterrogateUtils.length(edge)

    @staticmethod
    def create(system: System, center: PointEntity, p0: PointEntity, p1: PointEntity) -> CircleArcEntity:

        result = CircleArcEntity(center, p0, p1)

        #DistanceConstraint.create(system, center, p0, pr)
        #DistanceConstraint.create(system, center, p1, pr)
        #system.add_constraint(GtThanConstraint(pr, system.add_parameter(0, fixed=True)))

        system.add_constraint(CircleArcEntity.PointConstraints(center, p0, p1))

        system.add_entity(result)
        return result
