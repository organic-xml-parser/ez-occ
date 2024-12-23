import pdb
import typing


class ConstraintCheckResult:

    def __init__(self,
                 system_dof: int,
                 nodes: typing.Set[typing.Any],
                 internal_edges: typing.Set[typing.Any],
                 incident_edges: typing.Set[typing.Any]):
        self.system_dof = system_dof
        self.nodes = nodes.copy()
        self.internal_edges = internal_edges.copy()
        self.incident_edges = incident_edges.copy()


class Node:

    def __init__(self, dof: int):
        self.dof = dof


class Edge:

    def __init__(self, dof_restricted: int):
        self.dof_restricted = dof_restricted


class ConstraintGraph:
    """
    System of constraints can be represented as a hypergraph where nodes are entities (points/lines/coordinates etc.)
    and constraints are hyperedges linking them.
    """
    def __init__(self):
        self._nodes: typing.Dict[typing.Any, Node] = {}
        self._edges: typing.Dict[typing.Any, Edge] = {}

        self._edges_to_nodes: typing.Dict[Edge, typing.Set[Node]] = {}
        self._nodes_to_edges: typing.Dict[Node, typing.Set[Edge]] = {}

    def check_fully_constrained(self, node_lookups: typing.Set[typing.Any]):
        nodes = {self._get_node(l) for l in node_lookups}
        total_dof = sum(n.dof for n in nodes)

        incident_hyperedges = [e for n in nodes for e in self._nodes_to_edges[n]]

        # hyperedges contained only to the node collection, and not linked to external entities
        hyperedges = [e for e in incident_hyperedges if all(n in nodes for n in self._edges_to_nodes[e])]

        total_dof_restricted = sum(h.dof_restricted for h in hyperedges)

        net_dof = total_dof - total_dof_restricted

        print(f"    {total_dof} - {total_dof_restricted} = {net_dof}")
        for e in hyperedges:
            lookup = [k for k, v in self._edges.items() if v == e]
            print(f"        {lookup}")


    def add_node(self, lookup: typing.Any, node: Node):
        if lookup in self._nodes:
            raise ValueError("Lookup already registered")

        self._nodes[lookup] = node
        self._nodes_to_edges[node] = set()

    def _get_node(self, lookup: typing.Any) -> Node:
        if lookup not in self._nodes:
            raise ValueError("No node associated with lookup")

        return self._nodes[lookup]

    def add_hyperedge(self, lookup: typing.Any, edge: Edge, node_lookups: typing.Set[typing.Any]):
        if lookup in self._edges:
            raise ValueError("Lookup already registered for edge")

        nodes = {self._get_node(l) for l in node_lookups}
        self._edges[lookup] = edge
        self._edges_to_nodes[edge] = nodes.copy()

        for n in nodes:
            self._nodes_to_edges[n].add(edge)
