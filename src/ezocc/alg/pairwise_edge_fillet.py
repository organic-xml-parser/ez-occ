import typing

from ezocc.occutils_python import SetPlaceablePart
from ezocc.part_manager import Part, PartFactory


def pairwise_edge_fillet(radius: float, wire: Part) -> Part:
    """
    Perform a fillet operation on each pair of vertices. E.g. for a wire consisting of edges:
    [e0, e1, e2, e3]
    the following fillets will be computed:
    {e0, e1}
    {e1, e2}
    {e2, e3}
    and the result merged
    """
    if not wire.inspect.is_wire():
        raise ValueError("Expect wire as input")

    cache = wire.cache_token.get_cache()
    factory = PartFactory(cache)

    edges: typing.List[Part] = [e for e in wire.explore.explore_wire_edges_ordered().get()]
    edge_pairs: typing.List[typing.Tuple[Part, Part]] = []

    # resulting wire + vertex that was filleted
    fillet_results: typing.List[typing.Tuple[Part, Part]] = []

    for i in range(0, len(edges) - 1):
        edge_pairs.append((edges[i], edges[i + 1]))

    for edge_pair in edge_pairs:
        midpoint_vertex = edge_pair[0].bool.section(edge_pair[1]).print("MIDPOINT VERTEX")
        w = (factory.union(*[e for e in edge_pair])
             .make.wire()
             .cleanup(concat_b_splines=True, fix_small_face=True)
             .cleanup.build_curves_3d()
             .print())
        w = w.fillet.fillet2d_verts(radius, w.explore.vertex.get_min(lambda v: v.cast.get_distance_to(midpoint_vertex)))
        fillet_results.append((w, midpoint_vertex))

    # to construct the result, cut the edge by its neighbors and choose the remaining wire that is closest to the
    # midpoint vertex
    cut_fillet_results = []
    for i in range(0, len(fillet_results)):
        result = fillet_results[i][0]

        if i > 0:
            result = result.bool.cut(fillet_results[i - 1][0])

        if i < len(fillet_results) - 1:
            result = result.bool.cut(fillet_results[i + 1][0])

        result = result.explore.wire.get_min(lambda w: w.cast.get_distance_to(fillet_results[i][1]))

        cut_fillet_results.append(result)

    common_fillet_results = []
    for i in range(0, len(fillet_results)):
        result = fillet_results[i][0]

        if i > 0:
            result = result.bool.common(fillet_results[i - 1][0])

        if i < len(fillet_results) - 1:
            result = result.bool.common(fillet_results[i + 1][0])

        if not result.inspect.is_empty_compound():
            result = result.explore.wire.get_min(lambda w: w.cast.get_distance_to(fillet_results[i][1]))

            common_fillet_results.append(result)

    return (factory.union(*cut_fillet_results, *common_fillet_results)
            .cleanup(concat_b_splines=True, fix_small_face=True).cleanup.fuse_wires()
            .make.wire())
