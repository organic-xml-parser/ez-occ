import typing

from ezocc.occutils_python import SetPlaceablePart, InterrogateUtils
from ezocc.part_manager import Part, PartCache, PartFactory
from ezocc.precision import Compare


class WiresFromEdges:

    def __init__(self, cache: PartCache):
        self._cache = cache

    def get_wires(self, *edges: Part) -> Part:
        edges = {e.set_placeable for e in edges}

        # for each edge:
        # check to see if another edge connects with it
        # store the adjacency list
        # check for loops...?

        adjacency_list: typing.Dict[SetPlaceablePart, typing.Set[SetPlaceablePart]] = dict()

        for e0 in edges:
            adjacency_list[e0] = set()
            for e1 in edges:
                if e0 == e1:
                    continue

                if WiresFromEdges._are_endpoints_connected(e0.part, e1.part):
                    adjacency_list[e0].add(e1)

        # start from random element,
        # depth first traverse adjacency list
        # build wire
        processed_edges: typing.Set[SetPlaceablePart] = set()
        remaining_edges = {e for e in edges}
        result = []

        while len(remaining_edges) > 0:
            next_edge = remaining_edges.pop()
            if next_edge not in processed_edges:
                next_edge_connections = self._get_all_connected_edges(next_edge, adjacency_list, processed_edges)

                next_wire_set = {next_edge}.union(next_edge_connections)

                result.append(next_wire_set)
                processed_edges = processed_edges.union(next_wire_set)

        factory = PartFactory(self._cache)
        return factory.compound(*[factory.compound(*[e.part for e in edges]).make.wire() for edges in result])

    def _get_all_connected_edges(self,
                                 edge: SetPlaceablePart,
                                 adjacency_list: typing.Dict[SetPlaceablePart, typing.Set[SetPlaceablePart]],
                                 processed_edges: typing.Set[SetPlaceablePart]):
        result = set()

        stack = {edge}
        while len(stack) > 0:
            e = stack.pop()
            result.add(e)

            for ee in adjacency_list[e]:
                if ee not in result and ee not in processed_edges:
                    stack.add(ee)
                    result.add(ee)

        return result

    @staticmethod
    def _are_endpoints_connected(e0, e1):
        v0, v1 = e0.explore.vertex.get()
        v2, v3 = e1.explore.vertex.get()

        return Compare.lin_eq(*v0.xts.xyz_mid, *v2.xts.xyz_mid) or \
               Compare.lin_eq(*v0.xts.xyz_mid, *v3.xts.xyz_mid) or \
               Compare.lin_eq(*v1.xts.xyz_mid, *v2.xts.xyz_mid) or \
               Compare.lin_eq(*v1.xts.xyz_mid, *v3.xts.xyz_mid)