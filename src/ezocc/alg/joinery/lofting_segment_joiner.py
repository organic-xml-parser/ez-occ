import math

import OCC.Core.ShapeAnalysis
import OCC.Core.BRepCheck

from ezocc.alg.joinery.segment_joiner import SegmentJoiner
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import Part, PartFactory


class LoftingSegmentJoiner(SegmentJoiner):

    def __init__(self, is_ruled: bool = True):
        self._is_ruled = is_ruled

    def _get_joint(self, face_a: Part, face_b: Part, shared_edge: Part) -> Part:
        factory = PartFactory(face_a.cache_token.get_cache())

        # get terminating edges
        v0, v1 = shared_edge.explore.vertex.get()

        face_a_exterior_edges = face_a.explore.edge\
            .filter_by(lambda e: not e.bool.intersects(v0) and not e.bool.intersects(v1))\
            .get_compound()\
            .make.wire()

        face_b_exterior_edges = face_b.explore.edge\
            .filter_by(lambda e: not e.bool.intersects(v0) and not e.bool.intersects(v1))\
            .get_compound()\
            .make.wire()

        bridge = factory\
            .loft([face_a_exterior_edges, face_b_exterior_edges], is_solid=False, is_ruled=self._is_ruled)

        result = factory.union(face_a, face_b, *bridge.explore.face.get())\
            .make.shell()

        sa = OCC.Core.ShapeAnalysis.ShapeAnalysis_FreeBounds(result.shape)

        open_wires = [w for w in Part.of_shape(sa.GetOpenWires(), cache=face_a.cache_token.get_cache()).explore.wire.get()]
        closing_faces = Part.of_shape(sa.GetClosedWires(), cache=face_a.cache_token.get_cache()).explore.wire.get()
        closing_faces = [w.make.face() for w in closing_faces]

        print(f"Open wires: {open_wires}")
        print(f"Closing faces: {closing_faces}")

        result = factory.compound(
            *result.explore.face.get(),
            *closing_faces).make.shell().make.solid()

        return result



def main():
    cache = InMemoryPartCache()
    factory = PartFactory(cache)

    face_a = factory.square_centered(10, 10)

    face_b = factory.square_centered(10, 10).tr.ry(math.radians(90))\
        .align().by("xmaxymidzmin", face_a)

    LoftingSegmentJoiner().get_joint(face_a, face_b).print_recursive().preview()


if __name__ == '__main__':
    main()