import typing

from ezocc.alg.joinery.pipe_segment_joiner import PipeSegmentJoiner, LoftProperties
from ezocc.part_manager import PartCache, Part, PartFactory


class BoxSegmentJoiner(PipeSegmentJoiner):

    def _construct_face(self, edge_a: Part, edge_b: Part, shared_vertex: Part) -> Part:
        v_a = edge_a.inspect.edge.complementary_vertex(shared_vertex)
        v_b = edge_b.inspect.edge.complementary_vertex(shared_vertex)

        edge_a_opposite = edge_a.tr.mv(
            v_b.xts.x_mid - shared_vertex.xts.x_mid,
            v_b.xts.y_mid - shared_vertex.xts.y_mid,
            v_b.xts.z_mid - shared_vertex.xts.z_mid)

        edge_b_opposite = edge_b.tr.mv(
            v_a.xts.x_mid - shared_vertex.xts.x_mid,
            v_a.xts.y_mid - shared_vertex.xts.y_mid,
            v_a.xts.z_mid - shared_vertex.xts.z_mid)

        return PartFactory(edge_a.cache_token.get_cache()).compound(
            edge_a, edge_b, edge_a_opposite, edge_b_opposite)\
            .make.wire()

    def _get_profiles(self, loft_properties: LoftProperties) -> typing.List[Part]:
        return [
            self._construct_face(loft_properties.edge_a_start, loft_properties.edge_b_start, loft_properties.v0),
            self._construct_face(loft_properties.edge_a_end, loft_properties.edge_b_end, loft_properties.v1)
        ]
