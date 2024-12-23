import typing

from ezocc.alg.joinery.segment_joiner import SegmentJoiner
from ezocc.part_manager import Part


class LoftProperties:
    def __init__(self,
                 face_a: Part,
                 face_b: Part,
                 v0: Part,
                 v1: Part,
                 edge_a_start: Part,
                 edge_b_start: Part,
                 edge_a_end: Part,
                 edge_b_end: Part):
        self.face_a = face_a
        self.face_b = face_b
        self.v0 = v0
        self.v1 = v1
        self.edge_a_start = edge_a_start
        self.edge_b_start = edge_b_start
        self.edge_a_end = edge_a_end
        self.edge_b_end = edge_b_end


class PipeSegmentJoiner(SegmentJoiner):

    def _get_joint(self, face_a: Part, face_b: Part, shared_edge: Part) -> Part:
        # get terminating edges
        v0, v1 = shared_edge.explore.vertex.get()

        edge_a_start = face_a.explore.wire.get_single() \
            .bool.cut(shared_edge) \
            .explore.edge.filter_by(lambda e: e.bool.intersects(v0)) \
            .get_single()

        edge_b_start = face_b.explore.wire.get_single() \
            .bool.cut(shared_edge) \
            .explore.edge.filter_by(lambda e: e.bool.intersects(v0)) \
            .get_single()

        edge_a_end = face_a.explore.wire.get_single() \
            .bool.cut(shared_edge) \
            .explore.edge.filter_by(lambda e: e.bool.intersects(v1)) \
            .get_single()

        edge_b_end = face_b.explore.wire.get_single() \
            .bool.cut(shared_edge) \
            .explore.edge.filter_by(lambda e: e.bool.intersects(v1)) \
            .get_single()

        loft_properties = LoftProperties(
            face_a, face_b, v0, v1, edge_a_start, edge_b_start, edge_a_end, edge_b_end)

        return shared_edge.loft.pipe_through_profiles(self._get_profiles(loft_properties))

    def _get_profiles(self, loft_properties: LoftProperties) -> typing.List[Part]:
        raise NotImplementedError()
