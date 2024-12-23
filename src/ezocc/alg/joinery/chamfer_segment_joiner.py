import typing

from ezocc.alg.joinery.pipe_segment_joiner import PipeSegmentJoiner, LoftProperties
from ezocc.occutils_python import WireSketcher
from ezocc.part_manager import PartCache, PartFactory, Part


class ChamferSegmentJoiner(PipeSegmentJoiner):
    """
    @deprecated I think this is no longer needed due to LoftingSegmentJoiner, try to use that instead. If a use case is
    found for this one, remove the deprecation and explain it here.
    """

    def _get_profiles(self, loft_properties: LoftProperties) -> typing.List[Part]:
        cache = loft_properties.v0.cache_token.get_cache()
        factory = PartFactory(cache)

        start = factory.compound(
            loft_properties.edge_a_start,
            loft_properties.edge_b_start,
            WireSketcher(
                *loft_properties.edge_a_start.inspect.edge.complementary_vertex(loft_properties.v0).xts.xyz_mid)
            .line_to(*loft_properties.edge_b_start.inspect.edge.complementary_vertex(loft_properties.v0).xts.xyz_mid)
            .get_wire_part(cache)
            .explore.edge.get_single()
        ).make.wire()

        end = factory.compound(
            loft_properties.edge_a_end,
            loft_properties.edge_b_end,
            WireSketcher(*loft_properties.edge_a_end.inspect.edge.complementary_vertex(loft_properties.v1).xts.xyz_mid)
            .line_to(*loft_properties.edge_b_end.inspect.edge.complementary_vertex(loft_properties.v1).xts.xyz_mid)
            .get_wire_part(cache)
            .explore.edge.get_single()).make.wire()

        return [start, end]
