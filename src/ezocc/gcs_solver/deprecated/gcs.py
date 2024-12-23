"""
Contains geometric constraint solving utilities.
While a suitable free general-purpose gcs library is likely a long way off, certain specific tasks can be automated
to avoid duplication.
"""
import math
import pdb
import typing

from OCC.Core import GccEnt, Precision, ProjLib
from OCC.Core.GccAna import GccAna_Circ2d2TanRad, GccAna_Circ2d3Tan, GccAna_Circ2dBisec
from OCC.Core.GccEnt import GccEnt_QualifiedLin
from OCC.Core.gp import gp_Pnt2d, gp_Lin2d, gp_Circ2d, gp_Vec2d, gp_XOY, gp_Ax2d, gp_XY, gp_Dir2d
import OCC.Core.gp as gp

from ezocc.occutils_python import WireSketcher
from ezocc.part_manager import PartFactory, PartCache


class RightAngleTriangle:

    def get_last_side_length(self, hypotenuse: float, other_side: float) -> float:
        return math.sqrt(hypotenuse * hypotenuse - other_side * other_side)


class GCS_2d:

    PNT2D_ARG = typing.Union[typing.Tuple[float, float], gp_Pnt2d]
    DIR2D_ARG = typing.Union[typing.Tuple[float, float], gp_Dir2d]

    def __init__(self, cache: PartCache):
        self._cache = cache
        self._factory = PartFactory(cache)

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

        circ = gp_Circ2d(gp.gp.OX2d(), cr, True)
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

    def get_circle_intersection_points(self, circ_1: gp_Circ2d, circ_2: gp_Circ2d) -> typing.Tuple[gp_Pnt2d, gp_Pnt2d]:
        circle_distance = circ_1.Location().Distance(circ_2.Location())

        if circle_distance == 0:
            raise ValueError("Circles overlap")

        if abs(circle_distance) > circ_1.Radius() + circ_2.Radius():
            raise ValueError("Circles do not intersect")

        # if c1 is at origin, c2 at y == 0 then:
        # (r1**2 - r2**2 - x2**2) / 2x2 == x
        # where x2 == circ distance
        x2 = circle_distance
        r1 = circ_1.Radius()
        r2 = circ_2.Radius()
        x = (r1 * r1 + x2 * x2 - r2 * r2)
        x = x / (2 * x2)

        #print(f"circle dist: {circle_distance}, r1 = {circ_1.Radius()}, r2 = {circ_2.Radius()}")
        #print(f"x = {x}")

        y = math.sqrt(r1 * r1 - x * x)

        # now convert these coordinates into the source coordinate system
        dx = gp_Vec2d(circ_1.Location(), circ_2.Location()).Normalized()
        dy = dx.Rotated(math.radians(90))

        p0 = circ_1.Location().Translated(dx.Scaled(x)).Translated(dy.Scaled(y))
        p1 = circ_1.Location().Translated(dx.Scaled(x)).Translated(dy.Scaled(-y))

        return p0, p1

    def get_tangent_points_circ_circ(self, circle_a: gp_Circ2d, circle_b: gp_Circ2d) -> \
        typing.Tuple[typing.Tuple[gp_Pnt2d, gp_Pnt2d], typing.Tuple[gp_Pnt2d, gp_Pnt2d]]:

        # assume in plane
        r0 = circle_a.Radius()
        r1 = circle_b.Radius()

        cen_cen_vector = gp_Vec2d(circle_a.Location(), circle_b.Location())

        cen_cen_dist = cen_cen_vector.Magnitude()

        cen_cen_angle = (0.5 * math.pi) + math.atan2(circle_a.Location().X() - circle_b.Location().X(),
                                          circle_a.Location().Y() - circle_b.Location().Y())

        angle = math.atan2(cen_cen_dist, r0 - r1)

        p0 = gp_Pnt2d(
            circle_a.Location().X() + r0 * math.sin(angle + math.pi / 2),
            circle_a.Location().Y() - r0 * math.cos(angle + math.pi / 2))

        p1 = gp_Pnt2d(
            circle_a.Location().X() + cen_cen_dist + r1 * math.sin(angle + math.pi / 2),
            circle_a.Location().Y() - r1 * math.cos(angle + math.pi / 2))

        p0.Rotate(circle_a.Location(), -cen_cen_angle)
        p1.Rotate(circle_a.Location(), -cen_cen_angle)

        p00 = p0.Mirrored(gp_Ax2d(circle_a.Location(), gp_Dir2d(cen_cen_vector)))
        p11 = p1.Mirrored(gp_Ax2d(circle_a.Location(), gp_Dir2d(cen_cen_vector)))

        #self._factory.compound(
        #    self._factory.circle(r0).tr.mv(circle_a.Location().X(), circle_a.Location().Y()),
        #    self._factory.circle(r1).tr.mv(circle_b.Location().X(), circle_b.Location().Y()),
        #    self._factory.sphere(1).tr.mv(p0.X(), p0.Y()),
        #    self._factory.sphere(1).tr.mv(p1.X(), p1.Y()),
        #    WireSketcher(p0.X(), p0.Y(), 0).line_to(p1.X(), p1.Y()).get_wire_part(self._cache),
        #    self._factory.sphere(1).tr.mv(p00.X(), p00.Y()),
        #    self._factory.sphere(1).tr.mv(p11.X(), p11.Y()),
        #    WireSketcher(p00.X(), p00.Y(), 0).line_to(p11.X(), p11.Y()).get_wire_part(self._cache)).preview().raise_exception()

        return (
            (p0, p00),
            (p11, p1))

    def get_tangent_points(self, circle: gp_Circ2d, pnt: PNT2D_ARG) -> typing.Tuple[gp_Pnt2d, gp_Pnt2d]:
        """
        @return: a point on the circle from which the tangent line will intersect the specified point
        @raise
            ValueError if the point is inside, or on the boundary of, the circle.
        """
        pnt = GCS_2d.pnt2d_arg(pnt)

        circ_to_pnt = gp_Vec2d(circle.Location(), pnt)

        if circ_to_pnt.SquareMagnitude() <= circle.Radius() * circle.Radius():
            raise ValueError("Specified point is inside the circle")

        # since tangent is normal to dr, the radius of the circle, point to center dist, and the radius of the second
        # imaginary circle form a right-angle triangle
        v2 = math.sqrt(circ_to_pnt.SquareMagnitude() - circle.Radius() * circle.Radius())

        #print(f"Checking circle to circle intersection "
        #      f"({circle.Location().X()}, {circle.Location().Y()}, {circle.Radius()}) to ({pnt.X(), pnt.Y(), v2})")


        result = self.get_circle_intersection_points(circle, GCS_2d.circ_2d(pnt.X(), pnt.Y(), v2))


        #self._factory.circle(v2).tr.mv(pnt.X(), pnt.Y())\
        #    .preview(self._factory.circle(circle.Radius()).tr.mv(circle.Location().X(), circle.Location().Y()),
        #             self._factory.sphere(1).tr.mv(pnt.X(), pnt.Y()),
        #             self._factory.sphere(1).tr.mv(result[0].X(), result[0].Y()),
        #             self._factory.sphere(1).tr.mv(result[1].X(), result[1].Y()))

        circ_to_r0 = gp_Vec2d(circle.Location(), result[0])
        r0_to_pnt = gp_Vec2d(result[0], pnt)

        circ_to_r1 = gp_Vec2d(circle.Location(), result[1])
        r1_to_pnt = gp_Vec2d(result[1], pnt)

        sph = self._factory.sphere(circle.Radius() / 5)

        if not circ_to_r0.IsNormal(r0_to_pnt, 0.01):
            self._factory.circle(circle.Radius()).tr.mv(circle.Location().X(), circle.Location().Y())\
                .preview(
                sph.tr.mv(pnt.X(), pnt.Y()),
                sph.tr.mv(result[0].X(), result[0].Y()),
                WireSketcher(result[0].X(), result[0].Y(), 0).line_to(pnt.X(), pnt.Y()).get_wire_part(),
                WireSketcher(result[0].X(), result[0].Y(), 0).line_to(circle.Location().X(), circle.Location().Y())
                .get_wire_part())
            raise ValueError(f"Circ tangent is not normal to radius, angle is: {math.degrees(circ_to_r0.Angle(r0_to_pnt))} deg")

        if not circ_to_r1.IsNormal(r1_to_pnt, 0.01):
            self._factory.circle(circle.Radius()).tr.mv(circle.Location().X(), circle.Location().Y())\
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
        p0 = GCS_2d.pnt2d_arg(p0)
        p1 = GCS_2d.pnt2d_arg(p1)
        qualified_lin = GccEnt_QualifiedLin(gp_Lin2d(p0, d0), GccEnt.GccEnt_Position.GccEnt_outside)
        result = GccAna_Circ2d3Tan(qualified_lin, p0, p1, Precision.precision_Confusion())
        return result.ThisSolution(1)

    def circle_by_points_and_radius(self, p0: PNT2D_ARG, p1: PNT2D_ARG, radius: float) -> \
            typing.Tuple[gp_Circ2d, gp_Circ2d]:
        """
        Compute a circle by intersection of two points and a specified radius. Note that the circle with center closest
        to p0 is always the first element returned.
        """

        p0 = GCS_2d.pnt2d_arg(p0)
        p1 = GCS_2d.pnt2d_arg(p1)

        if p0.Distance(p1) > 2 * radius:
            raise ValueError("No solution exists")

        c0 = gp_Circ2d(gp.gp_Ax2d(p0, gp.gp.DX2d()), radius)
        c1 = gp_Circ2d(gp.gp_Ax2d(p1, gp.gp.DX2d()), radius)

        c0, c1 = self.get_circle_intersection_points(c0, c1)

        c0 = gp_Circ2d(gp.gp_Ax2d(c0, gp.gp.DX2d()), radius)
        c1 = gp_Circ2d(gp.gp_Ax2d(c1, gp.gp.DX2d()), radius)

        if c0.Location().Distance(p0) > c1.Location().Distance(p1):
            tmp = c0
            c0 = c1
            c1 = tmp

        return c1, c0


class GCS_3d:

    PNT3D_ARG = typing.Union[typing.Tuple[float, float, float], gp.gp_Pnt]

    @staticmethod
    def pnt3d_arg(arg: PNT3D_ARG) -> gp.gp_Pnt:
        if isinstance(arg, gp.gp_Pnt):
            return arg

        return gp.gp_Pnt(arg[0], arg[1], arg[2])

    def __init__(self, cache: PartCache):
        self._cache = cache

    def circle_tangent_points_to(self, circ: gp.gp_Circ, point: PNT3D_ARG) -> \
            typing.Tuple[typing.Tuple[float, float, float], typing.Tuple[float, float, float]]:

        pnt = GCS_3d.pnt3d_arg(point)

        trsf = gp.gp_Trsf()
        trsf.SetTransformation(
            gp.gp_Ax3(gp.gp_Pnt(0, 0, 0), gp.gp_Dir(0, 0, 1)),
            gp.gp_Ax3(gp.gp_Ax2(circ.Axis().Location(), circ.Axis().Direction())))

        trsf_inv = trsf.Inverted()

        circ_in_plane = circ.Transformed(trsf)
        pnt_in_plane = pnt.Transformed(trsf)

        circ_2d = gp.gp_Circ2d(gp.gp_Ax2d(gp.gp_Pnt2d(0, 0), gp.gp.DX2d()), circ_in_plane.Radius())
        pnt_2d = gp.gp_Pnt2d(pnt_in_plane.X(), pnt_in_plane.Y())

        print(f"intersection point({pnt_2d.X()}, {pnt_2d.Y()}) -> "
              f"circ ({circ_2d.Location().X()}, {circ_2d.Location().Y()}, r={circ_2d.Radius()})")

        tangent_pnt_2d_0, tangent_pnt_2d_1 = GCS_2d(self._cache).get_tangent_points(circ_2d, pnt_2d)

        tangent_pnt_0 = gp.gp_Pnt(tangent_pnt_2d_0.X(), tangent_pnt_2d_0.Y(), 0)\
            .Transformed(trsf_inv)

        tangent_pnt_1 = gp.gp_Pnt(tangent_pnt_2d_1.X(), tangent_pnt_2d_1.Y(), 0)\
            .Transformed(trsf_inv)

        return (tangent_pnt_0.X(), tangent_pnt_0.Y(), tangent_pnt_0.Z()), \
               (tangent_pnt_1.X(), tangent_pnt_1.Y(), tangent_pnt_1.Z())