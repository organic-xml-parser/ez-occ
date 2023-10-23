import math
import typing
from collections import OrderedDict

from OCC.Core.gp import gp_Pnt

from pythonoccutils.occutils_python import InterrogateUtils, SetPlaceableShape, SetPlaceablePart
from pythonoccutils.part_manager import Part, PartFactory
from pythonoccutils.precision import Compare

def points_eq(pA: gp_Pnt, pB: gp_Pnt) -> bool:
    return Compare.lin_eq(
        pA.X(), pA.Y(), pA.Z(),
        pB.X(), pB.Y(), pB.Z())


class PathTracker:

    def __init__(self, start: SetPlaceablePart):
        self._edges : typing.OrderedDict[SetPlaceablePart, typing.Tuple[gp_Pnt, gp_Pnt]] = OrderedDict()
        self._edges[start] = InterrogateUtils.line_points(start.part.shape)

    def pop(self):
        self._edges.popitem()

    def add_connection(self, e_to: SetPlaceablePart) -> bool:
        """
        Record the point orientation of the edges, implying that e_from leads to e_to
        """
        if e_to in self._edges:
            # edge has already been added to the sequence
            return False

        # check that the edge does not cross an existing one in the sequence
        for e in self._edges.keys():
            common = e.part.bool.common(e_to.part)
            if len(common.explore.edge.get()) != 0 or len(common.explore.vertex.get()) != 0:
                return False

        from_edge = next(reversed(self._edges))
        from_b =  self._edges[from_edge][1]

        next_a, next_b = InterrogateUtils.line_points(e_to.part.shape)

        if points_eq(from_b, next_a):
            self._edges[e_to] = (next_a, next_b)
            return True
        elif points_eq(from_b, next_b):
            self._edges[e_to] = (next_b, next_a)
            return True
        else:
            return False

    def is_closed(self):
        first_edge = next(iter(self._edges))
        last_edge = next(iter(reversed(self._edges)))

        first_point = self._edges[first_edge][0]
        last_point = self._edges[last_edge][1]

        return points_eq(first_point, last_point)

    @property
    def edges(self):
        return self._edges

    def preview(self):
        self.get_compound().preview()

    def get_compound(self) -> Part:
        return PartFactory.compound(*[p.part for p in self._edges.keys()])

def is_edge_connected_to_vertex(e0: Part, vert: gp_Pnt):
    p0, p1 = InterrogateUtils.line_points(e0.shape)

    return \
        Compare.lin_eq(
            p0.X(), p0.Y(), p0.Z(),
            vert.X(), vert.Y(), vert.Z()) or \
        Compare.lin_eq(
            p1.X(), p1.Y(), p1.Z(),
            vert.X(), vert.Y(), vert.Z())



def are_edges_connected(e0: Part, e1: Part) -> bool:
    e0t0, e0t1 = InterrogateUtils.line_points(e0.shape)
    e1t0, e1t1 = InterrogateUtils.line_points(e1.shape)

    return \
        Compare.lin_eq(
            e0t0.X(), e0t0.Y(), e0t0.Z(),
            e1t0.X(), e1t0.Y(), e1t0.Z()) or \
        Compare.lin_eq(
            e0t0.X(), e0t0.Y(), e0t0.Z(),
            e1t1.X(), e1t1.Y(), e1t1.Z()) or \
        Compare.lin_eq(
            e0t1.X(), e0t1.Y(), e0t1.Z(),
            e1t0.X(), e1t0.Y(), e1t0.Z()) or \
        Compare.lin_eq(
            e0t1.X(), e0t1.Y(), e0t1.Z(),
            e1t1.X(), e1t1.Y(), e1t1.Z())


def does_edge_overlap(e: Part, others: Part):

    sec = e.bool.section(others)

    has_overlap = len(sec.explore.vertex.get()) > 1

    return has_overlap


def face_isolated_from_edge(face: Part, edge: Part):
    common = face.bool.common(edge)
    return len(common.explore.vertex.get()) == 0 and len(common.explore.edge.get()) == 0


def find_loop(wires_comp: Part, existing_faces: typing.List[Part]) -> typing.Tuple[Part, Part]:
    """
    identifies and extracts a single loop from the supplied wires
    @return: the identified loop, and a compound of the remaining edges
    """

    edges: typing.List[SetPlaceablePart] = [SetPlaceablePart(s) for s in wires_comp.explore.edge.get()]
    non_face_edges = [e for e in edges if all(face_isolated_from_edge(f, e.part) for f in existing_faces)]

    if len(non_face_edges) == 0:
        return None

    visited_edges: typing.Set[SetPlaceablePart] = set()

    visited_edges.add(non_face_edges[0])

    path_tracker = PathTracker(non_face_edges[0])

    def increment_path():
        for e in edges:
            if e in visited_edges:
                continue

            if path_tracker.add_connection(e):
                visited_edges.add(e)
                return True

        return False

    while not path_tracker.is_closed() and len(visited_edges) < len(edges):
        if not increment_path():
            path_tracker.pop()

        #path_tracker.preview()

    return path_tracker.get_compound(), PartFactory.compound(*[e.part for e in edges if e not in path_tracker.edges])


def to_outer_wire(edges_comp: Part) -> Part:
    original_edges = edges_comp

    edges_comp = edges_comp.bool.union()

    #PartFactory.arrange(*edges_comp.tr.ry(math.radians(90)).explore.edge.get(), spacing=0.1).preview()

    faces = []
    while True:
        loop_result = find_loop(edges_comp, faces)
        if loop_result is None:
            break

        loop, edges_comp = loop_result

        faces.append(loop.make.wire().make.face().cleanup())
        #faces = [PartFactory.union(*faces).cleanup()]

        edges_comp = PartFactory.compound(*edges_comp.bool.cut(*faces).add(*faces).explore.edge.get()).bool.union()

        #edges_comp = edges_comp.bool.cut(*faces)
        edges_comp = PartFactory.compound(*edges_comp.explore.edge.get(), *faces[-1].explore.edge.get())

    PartFactory.arrange(*faces, spacing=1).preview()

    return PartFactory.union(*faces).sew.faces().cleanup().preview(original_edges)


def to_outer_wire_via_lefthand_follower(edges: Part):
    edges = edges.bool.union()

    # store the intere

    edge_map : typing.Dict[SetPlaceablePart, typing.Set[SetPlaceablePart]]