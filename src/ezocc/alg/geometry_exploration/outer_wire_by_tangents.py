import typing

from OCC.Core.gp import gp_Dir, gp_Pnt

from ezocc.alg.adjacent_edges_to_wire import merge_adjacent_edges
from ezocc.alg.geometry_exploration.edge_network.edge_network import EdgeNetwork
from ezocc.alg.geometry_exploration.edge_network.transform_to_xy_plane import get_transform_to_xy_plane
from ezocc.alg.geometry_exploration.edges.intersection_angle import select_perimeter_edge
from ezocc.decorators import unstable
from ezocc.occutils_python import SetPlaceablePart, InterrogateUtils
from ezocc.part_manager import Part, PartFactory


@unstable
def get_outer_wire(network: Part) -> Part:

    trsf = get_transform_to_xy_plane(network)

    network = network.transform(trsf)

    network = EdgeNetwork(network)

    starting_edge = (network.part.explore.edge.filter_by(lambda e: e.set_placeable not in network.definite_outer_edges)
                     .get_max(lambda e: e.xts.y_mid)
                     .set_placeable)

    edge_list: typing.List[SetPlaceablePart] = [starting_edge]
    terminating_vertex, current_vertex = (v.set_placeable for v in starting_edge.part.explore.vertex.get())

    if terminating_vertex.part.inspect.vertex.xyz[0] > current_vertex.part.inspect.vertex.xyz[0]:
        # angle should be measured clockwise
        normal = gp_Dir(0, 0, 1)
    else:
        # ccw
        normal = gp_Dir(0, 0, -1)

    PartFactory(network.part.cache_token.get_cache()).compound(
        network.part,
        starting_edge.part.tr.mv(dz=10)
    ) #.preview()

    while current_vertex != terminating_vertex:
        singly_connected_edges = \
            [s for s in network.get_singly_connected_edges(edge_list[-1].part) if s.shared_vertex == current_vertex]

        next_edge: SetPlaceablePart = select_perimeter_edge(
            edge_from=edge_list[-1].part,
            edge_to_candidates={s.edge_to.part for s in singly_connected_edges},
            intersection_point=gp_Pnt(*InterrogateUtils.vertex_to_xyz(current_vertex.part.shape)),
            intersection_normal=normal).set_placeable

        next_vertex = next_edge.part.inspect.edge.complementary_vertex(current_vertex.part).set_placeable

        edge_list.append(next_edge)
        current_vertex = next_vertex

    factory = PartFactory(network.part.cache_token.get_cache())

    factory.compound(
        network.part,
        *[e.part.tr.mv(dz=i + 1) for i, e in enumerate(edge_list)]
    ) #.preview()

    result = merge_adjacent_edges(factory.compound(*[e.part for e in edge_list]))

    return result.transform(trsf.Inverted())
