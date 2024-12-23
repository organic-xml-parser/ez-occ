import random
import typing

import OCC.Core.TopAbs

from ezocc.alg.geometry_exploration.edge_network.edge_network import EdgeNetwork
from ezocc.alg.trace.halt_exception import HaltException
from ezocc.occutils_python import SetPlaceablePart
from ezocc.part_manager import Part, PartFactory


# start by building adjacency list of edges
# this can be done by checking for shared vertices


class LoopSequence:

    def __init__(self,
                 init_reason: str,
                 input_network: Part,
                 sequence_limit: typing.Optional[int] = None):
        self.init_reason = init_reason
        self.input_network = input_network
        self.edge_list: typing.List[SetPlaceablePart] = []
        self.loop_face: typing.Optional[SetPlaceablePart] = None
        self.cut_face: typing.Optional[SetPlaceablePart] = None
        self._sequence_limit = sequence_limit
        self._iteration = 0

    def push_edge(self, part: SetPlaceablePart):
        if self._sequence_limit is not None and self._iteration >= self._sequence_limit:
            raise HaltException(f"Loop sequence limit reached ({self._sequence_limit})")

        self.edge_list.append(part)
        self._iteration += 1


class OuterWireProgress:

    def __init__(self,
                 iteration_limit: typing.Optional[int] = None,
                 loop_sequence_iteration_limit: typing.Optional[int] = None):
        self.iteration_limit = iteration_limit
        self.loop_sequence_iteration_limit = loop_sequence_iteration_limit
        self.iteration = 0
        self.loop_sequences: typing.List[LoopSequence] = []

    def append_loop_sequence(self, loop_sequence: LoopSequence):
        if self.iteration_limit is not None and self.iteration >= self.iteration_limit:
            raise HaltException(f"Iteration limit reached ({self.iteration_limit})")

        self.loop_sequences.append(loop_sequence)
        self.iteration += 1


def get_edge_loop(start_edge: SetPlaceablePart,
                  edge_network: EdgeNetwork,
                  loop_sequence: LoopSequence):
    factory = PartFactory(start_edge.part.cache_token.get_cache())

    # set of edges which have been visited, needed to prevent re-tracking
    visited_edges: typing.Set[SetPlaceablePart] = set()
    visited_edges.add(start_edge)

    v_start, v_end = edge_network.get_edge_verts(start_edge)
    edge_stack = [start_edge]

    def get_edge_stack_verts() -> typing.Set[SetPlaceablePart]:
        return {v for e in edge_stack for v in edge_network.get_edge_verts(e) if v != v_start and v != v_end}

    def get_next_edges() -> typing.List[SetPlaceablePart]:
        candidates = [e for e in edge_network.edges if e not in visited_edges and edge_network.edge_is_singly_connected_to_vert(e, v_end)]

        edge_stack_verts = get_edge_stack_verts()

        # prevent crossing
        candidates = [e for e in candidates if edge_network.get_singly_connected_edge_complimentary_vert(e, v_end) not in edge_stack_verts]

        # shuffle helps prevent getting stuck running the same loop repeatedly... I think...
        random.shuffle(candidates)

        # 2x more likely to prefer a definite outer edge...
        result: typing.List[SetPlaceablePart] = []
        for e in candidates:
            if edge_network.is_definite_outer_edge(e) and random.choice([True, False]):
                result.insert(0, e)
            else:
                result.append(e)

        return result

    sphere = factory.sphere(0.1)
    while len(visited_edges) != len(edge_network.edges_to_edges.keys()):
        next_edges = get_next_edges()

        if len(next_edges) == 0:
            # check to see if a self-closing edge loop exists, e.g. two edges forming halves of a circle
            if len(edge_stack) == 1:
                self_closing_edge = [e for e in edge_network.edges_to_edges[edge_stack[0]]
                                     if e not in visited_edges and v_start in edge_network.edges_to_verts[e] and
                                     v_end in edge_network.edges_to_verts[e]]
                if len(self_closing_edge) != 0:
                    return factory.compound(edge_stack[0].part, self_closing_edge[0].part).preview().make.wire()

            if len(edge_stack) < 2:
                factory.arrange(
                    factory.compound(*[e.part for e in edge_stack]).add(
                        *[sphere.tr.mv(*v.part.xts.xyz_mid) for v in get_edge_stack_verts()],
                        sphere.name("start").tr.mv(*v_start.part.xts.xyz_mid),
                        sphere.name("end").tr.mv(*v_end.part.xts.xyz_mid)
                    ),
                    factory.compound(*[e.part.tr.mv(dz=-10) for e in visited_edges]),
                    factory.compound(*[e.part for e in edge_network.edges_to_edges]),
                    spacing=20
                ).preview()

                raise ValueError("Could not form an edge loop")

            v_end = edge_network.get_singly_connected_edge_complimentary_vert(edge_stack[-1], v_end)
            edge_stack.pop()
        else:
            next_edge = next_edges[0]
            v_end = edge_network.get_singly_connected_edge_complimentary_vert(next_edge, v_end)

            visited_edges.add(next_edge)
            edge_stack.append(next_edge)
            loop_sequence.push_edge(next_edge)

            if v_end == v_start:
                return edge_stack

    raise ValueError("Loop could not be found")


def get_outer_wire(network: Part, progress: OuterWireProgress = None) -> Part:
    if not network.inspect.is_compound_of(OCC.Core.TopAbs.TopAbs_EDGE):
        raise ValueError("Expected a part which is a compound of edges")

    if progress is None:
        progress = OuterWireProgress()

    factory = PartFactory(network.cache_token.get_cache())

    if network.inspect.is_edge():
        return network.make.wire()
    elif network.inspect.is_compound_of(OCC.Core.TopAbs.TopAbs_EDGE) and len(network.explore.edge.get()) == 1:
        return network.explore.edge.get_single().make.wire()

    network = factory.compound(*[e.oriented.forward() for e in network.bool.union().explore.edge.get()])

    edge_network = EdgeNetwork(network)

    total_loop_faces: typing.List[Part] = []

    def pick_start_edge():
        # shuffling introduced to try and prevent infinite loops, e.g. picking the same start edge
        # and experiencing a failure each time

        # always prefer definite outer edges
        outer_edge_choice = [e for e in edge_network.definite_outer_edges]
        random.shuffle(outer_edge_choice)
        for e in outer_edge_choice:
            if len(edge_network.edges_to_edges[e]) > 1:
                return e

        # require an edge that is adjacent to other edges
        all_edge_choice = [e for e in edge_network.edges_to_edges.keys()]
        random.shuffle(all_edge_choice)
        for e in all_edge_choice:
            if len(edge_network.edges_to_edges[e]) > 1:
                return e

    iteration_count: int = 0

    while any(len(ee) > 2 for v, ee in edge_network.verts_to_edges.items()):
        iteration_count += 1
        sequence = LoopSequence("More than two edges connected at a single vertex", network, progress.loop_sequence_iteration_limit)

        start_edge = pick_start_edge()
        sequence.push_edge(start_edge)

        edge_loop = get_edge_loop(start_edge, edge_network, sequence)

        # eliminate all edges within the loop
        loop_face = factory\
            .compound(*[e.part for e in edge_loop]).make.wire().make.face()

        sequence.loop_face = loop_face

        progress.append_loop_sequence(sequence)

        if len(total_loop_faces) == 0:
            total_loop_faces = [loop_face]
        else:
            total_loop_faces.append(loop_face)

        cut_face = factory.union(*total_loop_faces).sew.faces().cleanup()
        cut_face = factory.compound(*[f.inspect.outer_wire().make.face().cleanup() for f in cut_face.explore.face.get()])

        sequence.cut_face = cut_face

        network = network.bool.cut(*[f for f in cut_face.explore.face.get()])
        network = factory.compound(*[e.oriented.forward() for e in network.explore.edge.get()],
                                   *[e.oriented.forward() for f in cut_face.explore.face.get() for e in f.inspect.outer_wire().explore.edge.get()])\
            .bool.union()

        edge_network = EdgeNetwork(network)

    return (edge_network.part.cleanup.build_curves_3d()
            .make.wire()
            .annotate("outer-wire-iteration-count", str(iteration_count)))
