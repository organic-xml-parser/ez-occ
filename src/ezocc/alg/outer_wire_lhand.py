import math
import pdb
import typing

import OCC.Core.BRepAdaptor
from OCC.Core.gp import gp_Vec

from ezocc.alg.set_placeable_pnt import SetPlaceablePnt
from ezocc.occutils_python import SetPlaceablePart, InterrogateUtils
from ezocc.part_manager import Part, PartFactory


def get_endpoint_vector(edge: SetPlaceablePart, vertex: SetPlaceablePnt, degree: int) -> typing.Optional[gp_Vec]:
    p0, p1 = InterrogateUtils.line_points(edge.part.shape)

    p0 = SetPlaceablePnt.get(p0)
    p1 = SetPlaceablePnt.get(p1)

    if p0 == vertex:
        is_first_param = True
    elif p1 == vertex:
        is_first_param = False
    else:
        raise ValueError("vertex did not correspond to first or last parameter")

    adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(edge.part.shape)

    param = adaptor.FirstParameter() if is_first_param else adaptor.LastParameter()

    if adaptor.Degree() < degree:
        return None
    else:
        return adaptor.DN(param, degree)


def get_angle(from_edge: SetPlaceablePart, vertex: SetPlaceablePnt, to_edge: SetPlaceablePart, degree: int) -> float:
    print(f"Finding angle between: {from_edge} {to_edge}")
    print(f"From shape: {from_edge.part.shape}")

    from_adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(from_edge.part.shape)

    pdb.set_trace()
    from_degree = min(degree, from_adaptor.Degree())

    from_vec = get_endpoint_vector(from_edge, vertex, from_degree)
    to_vec = get_endpoint_vector(to_edge, vertex, degree)

    if to_vec is None:
        return 2 * math.pi
    else:
        return math.atan2(from_vec.X() - to_vec.X(), from_vec.Y() - to_vec.Y())


def select_next_edge(current_edge: SetPlaceablePart,
                     current_vertex: SetPlaceablePnt,
                     candidate_edges: typing.List[SetPlaceablePart]):

    angles: typing.Dict[SetPlaceablePart, typing.List[float]] = {}

    for e in candidate_edges:
        angles[e] = []
        for d in range(1, 4):
            angles[e].append(get_angle(current_edge, current_vertex, e, d))

    # for degree 1, if there is a single min angle, pick that
    # otherwise repeat for degree 2, 3 etc.

    for degree in range(1, 4):
        dn_angles = {e : angles[e][degree - 1] for e in candidate_edges}
        min_angle = min(dn_angles.values())
        min_edges = [e for e in candidate_edges if dn_angles[e] == min_angle]
        if len(min_edges) == 1:
            return min_edges[0]

    raise ValueError()


def get_outer_wire(edges_comp: Part):

    # split the intersections
    edges_comp = edges_comp.bool.union().cleanup.build_curves_3d()

    # sort the edges by their incidence to the given vertices
    intersection_points: typing.Dict[SetPlaceablePnt, typing.Set[SetPlaceablePart]] = {}

    for edge in edges_comp.explore.edge.get():
        v0, v1 = InterrogateUtils.line_points(edge.shape)
        v0 = SetPlaceablePnt.get(v0)
        v1 = SetPlaceablePnt.get(v1)

        if v0 not in intersection_points:
            intersection_points[v0] = set()

        if v1 not in intersection_points:
            intersection_points[v1] = set()

        edge = SetPlaceablePart(edge)

        intersection_points[v0].add(edge)
        intersection_points[v1].add(edge)

    # determine an outside edge via a line cast
    visited_edges: typing.Set[SetPlaceablePart] = set()
    current_edge = SetPlaceablePart(edges_comp.pick.from_dir(1, 0, 0).first_edge())
    current_vertex = SetPlaceablePnt.get(InterrogateUtils.line_points(current_edge.part.shape)[1])

    while current_edge not in visited_edges:
        print("selecting edge...")
        candidate_edges = [e for e in intersection_points[current_vertex]]

        if len(candidate_edges) == 0:
            break

        next_edge = select_next_edge(current_edge, current_vertex, candidate_edges)

        next_v0, next_v1 = InterrogateUtils.line_points(next_edge.part.shape)
        next_v0 = SetPlaceablePnt.get(next_v0)
        next_v1 = SetPlaceablePnt.get(next_v1)

        next_vertex = next_v1 if next_v0 == current_vertex else next_v0

        current_edge = next_edge
        current_vertex = next_vertex

    return PartFactory.compound(*[e.part for e in visited_edges])
