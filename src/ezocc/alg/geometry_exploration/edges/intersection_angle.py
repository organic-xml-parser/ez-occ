from __future__ import annotations

import math
import typing

from OCC.Core import Precision
from OCC.Core.gp import gp_Pnt, gp_Dir, gp, gp_Vec
from OCC.Core.BRepAdaptor import BRepAdaptor_Curve

from ezocc.cad.visualization_widgets.visualization_widgets import EdgeWidgets
from ezocc.occutils_python import InterrogateUtils, WireSketcher, SetPlaceablePart
from ezocc.part_manager import Part, PartFactory

def _edge_u0_is_point(edge: Part, location: gp_Pnt, precision: float) -> bool:
    p0, p1 = InterrogateUtils.line_points(edge.shape)

    # sanity check the distance of the result
    if (p0.Distance(location) > precision and
            p1.Distance(location) > precision):
        raise ValueError("Neither end point of the specified curve is close to the specified location")

    return p0.Distance(location) < precision


def get_edge_intersection_angle(edge_from: Part,
                                reference: gp_Dir,
                                edge_to: Part,
                                common_vertex: gp_Pnt,
                                precision: float = 10e-6,
                                reference_is_in_plane: bool = False) -> float:
    """
    All edges and edge_from_normal are assumed to lie in a shared plane. This is not verified by the algorithm.

    @param edge_from: edge consisting of points u0 -> u1
    @param edge_from_normal: defines the side of edge_from to sweep from to establish the angle to edge_to. For example
    a line segment (0, 0) -> (1, 0) intersecting with (1, 0) -> (1, 1) will have angle 90 degrees if edge_from_normal
    is (0, 1, 0), since the positive y half plane is intersected with edge_to. If edge_from_normal is (0, -1, 0), the
    opposite sweep direction will be used and the resulting angle will be 270 degrees.
    @param edge_to: edge consisting of points u1 -> u2
    @param common_vertex: point of u1
    @param precision
    @param reference_is_in_plane if True, the reference is associated with the sweep "direction" of the angle,
    e.g. line (0, 0) -> (1, 0) and line (1, 0) -> (0, 1) (i.e. a 45 degree acute angle with horizontal x base)
    can have 45 degrees with an "in plane" reference of (0, 1), this defines the side of the line to sweep from.
    If False, reference is the standard angular normal reference when measuring the angle between segments.
    @return:
    """

    # construct the edge tangents
    from_tan = _get_edge_tangent_at_3d_point(edge_from, common_vertex, precision)
    to_tan = _get_edge_tangent_at_3d_point(edge_to, common_vertex, precision)

    # orient the edges such that the first point is the U0 parameter, so that the tan result can be consistent
    if _edge_u0_is_point(edge_from, common_vertex, precision):
        from_tan = from_tan.Reversed()

    if _edge_u0_is_point(edge_to, common_vertex, precision):
        to_tan = to_tan.Reversed()

    if reference_is_in_plane:
        reference = reference.Crossed(from_tan)

    # measure the distance between the tangent vectors using the reference direction
    result = from_tan.AngleWithRef(to_tan, reference)
    if result < 0:
        result = math.radians(360) + result

    if result == 0:
        result = math.radians(360)

    # debug the intersection
    cache = edge_from.cache_token.get_cache()
    factory = PartFactory(cache)

    (factory.compound(
        edge_from.name("EDGE FROM"),
        edge_to,
        factory.conical_arrow(
            (common_vertex.X(), common_vertex.Y(), common_vertex.Z()),
            (common_vertex.X() + to_tan.X(), common_vertex.Y() + to_tan.Y(), common_vertex.Z() + to_tan.Z())),
        factory.conical_arrow(
            (common_vertex.X(), common_vertex.Y(), common_vertex.Z()),
            (common_vertex.X() + reference.X(), common_vertex.Y() + reference.Y(), common_vertex.Z() + reference.Z())),
        factory.conical_arrow(
            (common_vertex.X(), common_vertex.Y(), common_vertex.Z()),
            (common_vertex.X() + from_tan.X(), common_vertex.Y() + from_tan.Y(), common_vertex.Z() + from_tan.Z())).name("from_tan")
    ).do_and_add(
        lambda p: factory.text(str(math.degrees(result)), "serif", 1).align().by("xmidymidzmaxmin", p).tr.mv(dz=-5))
     #.preview()
     )

    return result


def _get_edge_tangent_at_3d_point(edge: Part, location: gp_Pnt, precision: float) -> gp_Dir:

    start_pnt, end_pnt = InterrogateUtils.line_points(edge.shape)
    start_tan, end_tan = InterrogateUtils.line_tangent_points(edge.shape)

    # sanity check the distance of the result
    if (start_pnt.Distance(location) > precision and
            end_pnt.Distance(location) > precision):
        raise ValueError("Neither end point of the specified curve is close to the specified location")

    is_first_point = start_pnt.Distance(location) < end_pnt.Distance(location)

    if is_first_point:
        return gp_Dir(start_tan.Normalized())
    else:
        return gp_Dir(end_tan.Normalized())



def _has_d1_tangent(part: SetPlaceablePart, point: gp_Pnt, precision: float) -> bool:
    curve_adaptor = BRepAdaptor_Curve(part.part.shape)

    if _edge_u0_is_point(part.part, point, precision):
        param = curve_adaptor.FirstParameter()
    else:
        param = curve_adaptor.LastParameter()

    tangent = gp_Vec()
    curve_adaptor.D1(param, point, tangent)


class ComparisonOrderEdges:

    def __init__(self,
                 edge: Part,
                 point_on_edge: gp_Pnt,
                 precision: float,
                 max_order: int):
        cache = edge.cache_token.get_cache()

        self._edge = edge
        self._point_on_edge = point_on_edge
        self._precision = precision

        # construct fictive linear edges on the intersection point to simulate the vectors of the n'th order tangent
        self._comparison_edges: typing.Dict[int, Part] = {}

        curve_adaptor = BRepAdaptor_Curve(self._edge.shape)

        param = curve_adaptor.FirstParameter() if _edge_u0_is_point(self._edge, point_on_edge,
                                                                    precision) else curve_adaptor.LastParameter()

        for i in range(1, max_order + 1):
            try:
                vec = curve_adaptor.DN(param, i)
                self._comparison_edges[i] = (
                    WireSketcher(point_on_edge).line_to(vec.X(), vec.Y(), vec.Z())
                    .get_wire_part(cache)
                    .explore.edge.get_single())
            except RuntimeError as e:
                break

        self._max_order = max_order

    @property
    def part(self) -> Part:
        return self._edge

    @property
    def max_order(self) -> int:
        return self._max_order

    def get_comparison_edge(self, order: int) -> Part:
        if order - 1 >= max(self._comparison_edges.keys()):
            return self._comparison_edges[max(self._comparison_edges.keys())]

        return self._comparison_edges[order]

    def get_intersection_angles_for_all_orders(self,
                                               other: ComparisonOrderEdges,
                                               up_to_order: int,
                                               reference: gp_Dir) -> typing.Dict[int, float]:
        if self._precision != other._precision or self._point_on_edge.Distance(other._point_on_edge) > self._precision:
            raise ValueError("Incompatible comparison edges")

        return {
            i: get_edge_intersection_angle(
                self.get_comparison_edge(i),
                reference,
                other.get_comparison_edge(i),
                self._point_on_edge,
                self._precision) for i in range(1, up_to_order + 1)
        }


def select_perimeter_edge(edge_from: Part,
                          edge_to_candidates: typing.Set[Part],
                          intersection_point: gp_Pnt,
                          intersection_normal: gp_Dir,
                          precision: float = 10e-6) -> Part:

    """
    All edges are assumed to lie in a plane normal to intersection_normal. This is not verified by the algorithm.

    given edge from with points u0 -> u1
    and the set of input edges u1 -> u2, 3, etc.

    determines the edge which minimizes the angle measured by the reference direction changed when transitioning
    from edge_from to edge_to.

    Edge tangents are first used for comparison, todo: followed by higher order derivatives until a unique edge can be
    found. If no unique edge is found (e.g. edge_to_candidates contains functionally identical edges), an exception is
    thrown.

    @param intersection_point: point in space at which edges intersect
    @param intersection_normal: normal to plane containing the edges
    @return: the input candidate with minimized angle

    """

    print("Selecting perimeter edge...")

    if len(edge_to_candidates) == 0:
        raise ValueError("No edge candidates specified")
    elif len(edge_to_candidates) == 1:
        # only one candidate, no need for angle calculation
        return next(e for e in edge_to_candidates)

    max_order = 6

    edge_from_comp = ComparisonOrderEdges(edge_from, intersection_point, precision, max_order)
    edge_to_candidates_comp = [ComparisonOrderEdges(e, intersection_point, precision, max_order) for e in edge_to_candidates]

    up_to_order = max(
        edge_from_comp.max_order,
        *[e.max_order for e in edge_to_candidates_comp])

    intersection_angles = {e: edge_from_comp.get_intersection_angles_for_all_orders(e, up_to_order, intersection_normal)
                           for e in edge_to_candidates_comp}

    # for first order, check if there are equivalent edges
    for i in range(1, up_to_order + 1):
        print(f"Testing order: {i}")

        comparison_angles: typing.Dict[Part, float] = {e.part: a[i] for e, a in intersection_angles.items()}

        print(f"Comparison angles {comparison_angles.values()}")

        min_comparison_angle = min(comparison_angles.values())

        overlapping_angles = {f for f in comparison_angles.values() if abs(f - min_comparison_angle) < precision}

        print(f"Angles which overlap with the min comparison angle: {overlapping_angles}")

        if len(overlapping_angles) == 1:
            return [p for p, f in comparison_angles.items() if f == min_comparison_angle][0]

    raise ValueError("Unable to determine unique edge")


