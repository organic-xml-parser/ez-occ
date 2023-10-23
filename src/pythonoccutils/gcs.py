"""
Contains geometric constraint solving utilities.
While a suitable free general-purpose gcs library is likely a long way off, certain specific tasks can be automated
to avoid duplication.
"""
import math
import pdb
import typing

from OCC.Core import GccEnt, Precision
from OCC.Core.GccAna import GccAna_Circ2d2TanRad, GccAna_Circ2d3Tan
from OCC.Core.GccEnt import GccEnt_QualifiedLin
from OCC.Core.gp import gp_Pnt2d, gp_Lin2d, gp_Circ2d, gp_Vec2d, gp_XOY, gp_Ax2d, gp_XY, gp_Dir2d
import OCC.Core.gp as gp

from pythonoccutils.occutils_python import WireSketcher
from pythonoccutils.part_manager import PartFactory
from pythonoccutils.precision import Compare


class RightAngleTriangle:

    def get_last_side_length(self, hypotenuse: float, other_side: float) -> float:
        return math.sqrt(hypotenuse * hypotenuse - other_side * other_side)


class GCS_2d:

    PNT2D_ARG = typing.Union[typing.Tuple[float, float], gp_Pnt2d]
    DIR2D_ARG = typing.Union[typing.Tuple[float, float], gp_Dir2d]

    @staticmethod
    def right_angle_triangle() -> RightAngleTriangle:
        return RightAngleTriangle()

    @staticmethod
    def pnt2d_arg(arg: PNT2D_ARG) -> gp_Pnt2d:
        if isinstance(arg, gp_Pnt2d):
            return arg

        return gp_Pnt2d(arg[0], arg[1])

    @staticmethod
    def dir2d_arg(arg: DIR2D_ARG) -> gp_Dir2d:
        if isinstance(arg, gp_Dir2d):
            return arg

        return gp_Dir2d(arg[0], arg[1])

    @staticmethod
    def circ_2d(cx: float, cy: float, cr: float) -> gp_Circ2d:
        if cr <= 0:
            raise ValueError("Must have a radius > 0")

        circ = gp_Circ2d(gp.gp_OX2d(), cr, True)
        circ = circ.Translated(gp_Vec2d(cx, cy))

        return circ

    @staticmethod
    def lin_2d(p0: PNT2D_ARG, p1: PNT2D_ARG) -> gp_Lin2d:
        p0 = GCS_2d.pnt2d_arg(p0)
        p1 = GCS_2d.pnt2d_arg(p1)

        vec = gp_Vec2d(p0, p1)
        return gp_Lin2d(p0, gp_Dir2d(vec.Normalized()))

    @staticmethod
    def get_lin_y(lin: gp_Lin2d, x: float) -> float:
        # ax + by + c = 0
        a, b, c = lin.Coefficients()

        if b == 0:
            raise ValueError("Line is vertical. No single value of y for x")

        return -c / b - a * x / b

    @staticmethod
    def get_lin_x(lin: gp_Lin2d, y: float) -> float:
        # ax + by + c = 0
        a, b, c = lin.Coefficients()

        if a == 0:
            raise ValueError("Line is horizontal. No single value of x for y")

        return -c / a - b * y / a

    @staticmethod
    def get_circle_intersection_points(circ_1: gp_Circ2d, circ_2: gp_Circ2d) -> typing.Tuple[gp_Pnt2d, gp_Pnt2d]:
        circle_distance = circ_1.Location().Distance(circ_2.Location())

        if circle_distance > circ_1.Radius() + circ_2.Radius():
            raise ValueError("Circles do not intersect")

        # if we treat r1 as origin, and r1 -> r2 as parallel to y axis, we can use simplified formula:
        # y = r1 ^ 2 / (2 * distance(c1, c2))

        # todo: my math is off somewhere.. (surprise) for some reason the 1/2 factor is not needed...

        v = circ_1.Radius() * circ_1.Radius() / ( circle_distance)
        u = math.sqrt(circ_1.Radius() * circ_1.Radius() - v * v)

        # now project these along the c1 -> c2 and normal vectors
        c1_c2_v = gp_Vec2d(circ_1.Location(), circ_2.Location())\
            .Normalized()\
            .Scaled(v)

        c1_c2_u = c1_c2_v.GetNormal()\
            .Normalized()\
            .Scaled(u)

        if not c1_c2_u.IsNormal(c1_c2_v, 0.01):
            raise ValueError()

        result = circ_1.Location().Translated(c1_c2_v)

        return result.Translated(c1_c2_u), result.Translated(c1_c2_u.Scaled(-1))

    @staticmethod
    def get_tangent_points(circle: gp_Circ2d, pnt: PNT2D_ARG) -> typing.Tuple[gp_Pnt2d, gp_Pnt2d]:
        """
        @return: a point on the circle from which the tangent line will intersect the specified point
        @raise
            ValueError if the point is inside, or on the boundary of, the circle.
        """
        pnt = GCS_2d.pnt2d_arg(pnt)

        circ_to_pnt = gp_Vec2d(circle.Location(), pnt)

        if circ_to_pnt.SquareMagnitude() <= circle.Radius() * circle.Radius():
            raise ValueError("Specified point is inside the circle")

        v2 = math.sqrt(circ_to_pnt.SquareMagnitude() - circle.Radius() * circle.Radius())

        result = GCS_2d.get_circle_intersection_points(circle, GCS_2d.circ_2d(pnt.X(), pnt.Y(), v2))

        circ_to_r0 = gp_Vec2d(circle.Location(), result[0])
        r0_to_pnt = gp_Vec2d(result[0], pnt)

        circ_to_r1 = gp_Vec2d(circle.Location(), result[1])
        r1_to_pnt = gp_Vec2d(result[1], pnt)

        sph = PartFactory.sphere(circle.Radius() / 5)

        if not circ_to_r0.IsNormal(r0_to_pnt, 0.01):
            PartFactory.circle(circle.Radius()).tr.mv(circle.Location().X(), circle.Location().Y())\
                .preview(
                sph.tr.mv(pnt.X(), pnt.Y()),
                sph.tr.mv(result[0].X(), result[0].Y()),
                WireSketcher(result[0].X(), result[0].Y(), 0).line_to(pnt.X(), pnt.Y()).get_wire_part(),
                WireSketcher(result[0].X(), result[0].Y(), 0).line_to(circle.Location().X(), circle.Location().Y())
                .get_wire_part())
            raise ValueError(f"Circ tangent is not normal to radius, angle is: {math.degrees(circ_to_r0.Angle(r0_to_pnt))} deg")

        if not circ_to_r1.IsNormal(r1_to_pnt, 0.01):
            PartFactory.circle(circle.Radius()).tr.mv(circle.Location().X(), circle.Location().Y())\
                .preview(
                sph.tr.mv(pnt.X(), pnt.Y()),
                sph.tr.mv(result[1].X(), result[1].Y()),
                WireSketcher(result[1].X(), result[1].Y(), 0).line_to(pnt.X(), pnt.Y()).get_wire_part(),
                WireSketcher(result[1].X(), result[1].Y(), 0).line_to(circle.Location().X(), circle.Location().Y())
                .get_wire_part())
            raise ValueError(f"Circ tangent is not normal to radius, angle is: {math.degrees(circ_to_r1.Angle(r1_to_pnt))} deg")

        return result

    @staticmethod
    def circle_by_tangent_and_point(p0: PNT2D_ARG, d0: gp.gp_Dir2d, p1: PNT2D_ARG) -> gp_Circ2d:
        # constraints:
        # circle intersects p0 and p1

        qualified_lin = GccEnt_QualifiedLin(gp_Lin2d(p0, d0), GccEnt.GccEnt_Position.GccEnt_outside)
        result = GccAna_Circ2d3Tan(qualified_lin, p0, p1, Precision.precision_Confusion())
        return result.ThisSolution(1)

if __name__ == '__main__':

    def test(circ_x: float, circ_y: float, circ_rad: float,
             px: float, py: float):

        circ = gp_Circ2d(gp.gp_OX2d(), circ_rad, True)
        circ = circ.Translated(gp_Vec2d(circ_x, circ_y))
        pnt = gp_Pnt2d(px, py)

        t0, t1 = GCS_2d.get_tangent_points(circ, pnt)

        return PartFactory.circle(circ.Radius()).tr.mv(circ.Position().Location().X(), circ.Position().Location().Y())\
            .add(
                PartFactory.sphere(circ_rad / 5).tr.mv(t0.X(), t0.Y()),
                PartFactory.sphere(circ_rad / 5).tr.mv(t1.X(), t1.Y()),
                PartFactory.sphere(circ_rad / 5).tr.mv(pnt.X(), pnt.Y()))

    result = []
    for i in range(0, 10):
        theta_0 = i * math.pi * 2 / 10
        theta_1 = theta_0 * 0.75
        theta_2 = theta_0 * 1.75

        cx = 40 * math.cos(theta_1)
        cy = 40 * math.sin(theta_1)

        cr = 20 + 5 * math.sin(theta_2)

        px = 40 * math.sin(theta_1) * math.cos(theta_0 + math.pi)
        py = 40 * math.sin(theta_1) * math.sin(theta_0 + math.pi)

        result.append(test(cx, cy, cr, px, py).tr.ry(math.radians(90)))

    for r in result:
        r.preview()

    PartFactory.arrange(*result, spacing=30).preview()

