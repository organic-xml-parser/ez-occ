import typing

import OCC.Core.BRepBuilderAPI
import OCC.Core.TopAbs

from ezocc.alg.geometry_exploration.edge_network.edge_network import EdgeNetwork
from ezocc.occutils_python import SetPlaceablePart
from ezocc.part_manager import Part


def merge_adjacent_edges(edges: Part) -> Part:
    if not edges.inspect.is_compound_of(OCC.Core.TopAbs.TopAbs_EDGE):
        raise ValueError("Input is not a compound of edges")

    edge_network = EdgeNetwork(edges)

    # in order to build a wire, each vertex must connect to at most two edges
    if any(len(e) > 2 for v, e in edge_network.verts_to_edges.items()):
        edge_network.part.preview()
        raise ValueError("Edge network cannot be reduced to a single wire")

    # edge network should not be a tree. i.e. there should be exactly two edges which are connected to 1 edge
    terminating_verts = [v for v, e in edge_network.verts_to_edges.items() if len(e) == 1]
    if len(terminating_verts) != 2 and len(terminating_verts) != 0:
        edges.preview(*[v.part.tr.mv(dz=1) for v in terminating_verts])
        raise ValueError(f"Expected exactly 2 verts with a single edge connection. Instead there were: {terminating_verts}")

    start_edges: typing.List[typing.Set[SetPlaceablePart]] = [e for v, e in edge_network.verts_to_edges.items() if len(e) == 1]
    if len(start_edges) == 0:
        start_edges = [e for e in edge_network.verts_to_edges.values()]

    start_edge: SetPlaceablePart = next(next(ee for ee in e) for e in start_edges)

    if start_edge not in edge_network.edges_to_verts.keys():
        raise ValueError()

    visited_edges = {start_edge}
    edge_sequence = [start_edge]

    while len(visited_edges) != len(edge_network.edges_to_edges.keys()):
        previous_edge = edge_sequence[-1]
        next_edges = edge_network.edges_to_edges[previous_edge]
        next_edges = [e for e in next_edges if e not in visited_edges]

        next_edge = next_edges[0]

        visited_edges.add(next_edge)
        edge_sequence.append(next_edge)

    makewire = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeWire()
    for edge in edge_sequence:
        makewire.Add(edge.part.shape)

    wire = makewire.Wire()

    return Part(edges.cache_token.mutated("connect_adjacent_edges"),
                edges.subshapes.with_updated_root_shape(wire))
