import typing

import OCC.Core.TopAbs
from OCC.Core import Precision

from ezocc.alg.geometry_exploration.edge_network.is_definite_outer_edge import is_definite_outer_edge
from ezocc.occutils_python import SetPlaceablePart, SetPlaceableShape, InterrogateUtils
from ezocc.part_manager import Part

TEdgesToVerts = typing.Dict[SetPlaceablePart, typing.Tuple[SetPlaceablePart, SetPlaceablePart]]
TVertsToEdges = typing.Dict[SetPlaceablePart, typing.Set[SetPlaceablePart]]
TEdgesToEdges = typing.Dict[SetPlaceablePart, typing.Set[SetPlaceablePart]]
TIsDefiniteOuter = typing.Set[SetPlaceablePart]


def _edge_is_singly_connected_to_vert(edge: SetPlaceablePart, vert: SetPlaceablePart, edges_to_verts: TEdgesToVerts):
    v0, v1 = edges_to_verts[edge]

    return bool(v0 == vert) != bool(v1 == vert)


def _get_singly_connected_edge_complimentary_vert(edge: SetPlaceablePart, vert: SetPlaceablePart, edges_to_verts: TEdgesToVerts):
    if not _edge_is_singly_connected_to_vert(edge, vert, edges_to_verts):
        raise ValueError("Edge is not singly connected to vertex")

    v0, v1 = edges_to_verts[edge]

    if v0 == vert:
        return v1
    else:
        return v0


def _build_edge_verts_maps(network: Part) -> typing.Tuple[
    TEdgesToVerts,
    TVertsToEdges,
    TEdgesToEdges,
    TIsDefiniteOuter]:

    edges_to_verts: TEdgesToVerts = dict()
    verts_to_edges: TVertsToEdges = dict()

    definite_outer_edges = {e.set_placeable for e in network.explore.edge.get() if is_definite_outer_edge(e, network)}

    total_edge_set: typing.Set[SetPlaceablePart] = {e.set_placeable for e in network.explore.edge.get()}

    if len(total_edge_set) == 1:
        return next(e for e in total_edge_set).part.make.wire()

    total_vert_set: typing.Set[SetPlaceablePart] = set()
    for e in total_edge_set:
        v0, v1 = e.part.explore.vertex.get()
        total_vert_set.add(v0.set_placeable)
        total_vert_set.add(v1.set_placeable)

    for sedge in total_edge_set:

        v0, v1 = sedge.part.explore.vertex.get()

        sv0 = v0.set_placeable
        sv1 = v1.set_placeable

        edges_to_verts[sedge] = sv0, sv1

        if sv0 not in verts_to_edges:
            verts_to_edges[sv0] = set()

        if sv1 not in verts_to_edges:
            verts_to_edges[sv1] = set()

        verts_to_edges[sv0].add(sedge)
        verts_to_edges[sv1].add(sedge)

    edges_to_edges: TEdgesToEdges = dict()

    for edge, verts in edges_to_verts.items():
        v0, v1 = verts

        connected_edges = set()
        for e in verts_to_edges[v0]:
            connected_edges.add(e)

        for e in verts_to_edges[v1]:
            connected_edges.add(e)

        # do not connect an edge to itself
        connected_edges.remove(edge)

        edges_to_edges[edge] = connected_edges

    edges_to_verts__verts = set()
    for verts in edges_to_verts.values():
        for v in verts:
            edges_to_verts__verts.add(v)
    edges_to_verts__edges = {e for e in edges_to_verts.keys()}

    verts_to_edges__verts = {v for v in verts_to_edges.keys()}
    verts_to_edges__edges = set()
    for edges in verts_to_edges.values():
        for e in edges:
            verts_to_edges__edges.add(e)

    if edges_to_verts__edges != total_edge_set:
        raise ValueError(f"edges_to_verts does not have all edges {len(edges_to_verts__edges)} vs {len(total_edge_set)}")

    if edges_to_verts__verts != total_vert_set:
        raise ValueError(f"edges_to_verts does not have all verts {len(edges_to_verts__verts)} vs {len(total_vert_set)}")

    if edges_to_edges.keys() != total_edge_set:
        raise ValueError(f"edges_to_edges does not have a key for every edge {len(edges_to_edges.keys())} vs {len(total_edge_set)}")

    if any(len(edges) == 0 for edges in edges_to_edges.values()):
        raise ValueError("Edge collection contains orphaned edges")

    return edges_to_verts, verts_to_edges, edges_to_edges, definite_outer_edges


class SinglyConnectedEdge:

    def __init__(self, edge_from: SetPlaceablePart, edge_to: SetPlaceablePart, shared_vertex: SetPlaceablePart):
        self.edge_from = edge_from
        self.edge_to = edge_to
        self.shared_vertex = shared_vertex

        # verify that the two edges share only a single vertex
        unique_verts = {*[v.set_placeable_shape for v in edge_from.part.explore.vertex.get()], *[v.set_placeable_shape for v in edge_to.part.explore.vertex.get()]}
        unique_vert_count = len(unique_verts)

        if unique_vert_count != 3:
            raise ValueError(f"Expected exactly 3 unique vertices among the two edges. "
                             f"Instead there were: {unique_vert_count}")

class EdgeNetwork:

    def __init__(self, part: Part):
        if not part.inspect.is_compound_of(OCC.Core.TopAbs.TopAbs_EDGE):
            raise ValueError("Expected edge network to consist of a compound of edges")

        for e in part.explore.edge.get():
            if e.inspect.edge.is_degenerated:
                raise ValueError("Edge network cannot contain degenerated edges")

        self._part = part

        self._edges_to_verts, self._verts_to_edges, self._edges_to_edges, self._definite_outer_edges = (
            _build_edge_verts_maps(part))

        self._verts_to_coordinates: typing.Dict[SetPlaceableShape, typing.Tuple[float, float, float]] = {}
        self._coordinates_to_verts: typing.Dict[typing.Tuple[float, float, float], SetPlaceableShape] = {}
        for v in part.explore.vertex.get():
            coordinate = InterrogateUtils.vertex_to_xyz(v.shape)

            if coordinate in self._coordinates_to_verts:
                raise ValueError("Multiple vertices found with same coordinate. "
                                 "All connected edge endpoints should share vertices.")

            self._verts_to_coordinates[v.set_placeable_shape] = coordinate

    def get_edge_verts(self, edge: SetPlaceablePart) -> typing.Tuple[SetPlaceablePart, SetPlaceablePart]:
        return self.edges_to_verts[edge]

    def edge_is_singly_connected_to_vert(self, edge: SetPlaceablePart, vert: SetPlaceablePart) -> bool:
        return _edge_is_singly_connected_to_vert(edge, vert, self._edges_to_verts)

    def get_singly_connected_edge_complimentary_vert(self, edge: SetPlaceablePart, vert: SetPlaceablePart) -> (
            SetPlaceablePart):
        return _get_singly_connected_edge_complimentary_vert(edge, vert, self._edges_to_verts)

    def is_definite_outer_edge(self, edge: SetPlaceablePart) -> bool:
        return edge in self._definite_outer_edges

    @property
    def part(self) -> Part:
        return self._part

    @property
    def edges(self) -> typing.Generator[SetPlaceablePart, None, None]:
        for e in self._part.explore.edge.get():
            yield e.set_placeable

    @property
    def vertices(self) -> typing.Generator[SetPlaceablePart, None, None]:
        for v in self._part.explore.vertex.get():
            yield v.set_placeable

    @property
    def edges_to_verts(self) -> TEdgesToVerts:
        return self._edges_to_verts.copy()

    @property
    def verts_to_edges(self) -> TVertsToEdges:
        return self._verts_to_edges.copy()

    @property
    def edges_to_edges(self) -> TEdgesToEdges:
        return self._edges_to_edges.copy()

    @property
    def definite_outer_edges(self) -> TIsDefiniteOuter:
        return self._definite_outer_edges.copy()

    def get_singly_connected_edges(self, edge_from: Part) -> typing.Generator[SinglyConnectedEdge, None, None]:
        neighboring_edges = self._edges_to_edges[edge_from.set_placeable]

        from_verts = {*self._edges_to_verts[edge_from.set_placeable]}

        # edges are singly connected if they share exactly one vert
        for edge_to in neighboring_edges:
            to_verts = {*self._edges_to_verts[edge_to]}

            common_verts = from_verts.intersection(to_verts)

            if len(common_verts) == 1:
                yield SinglyConnectedEdge(edge_from.set_placeable, edge_to, next(v for v in common_verts))

