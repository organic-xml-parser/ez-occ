import math
import typing

from OCC.Core import Precision

from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import Part, PartFactory


def _pick_edge(network: Part, xyz: typing.Tuple[float, float, float], dxyz: typing.Tuple[float, float, float]):
    pick = network.pick.dir(xyz, dxyz)
    if len(pick.as_list()) == 0:
        return None

    return pick.first_edge().set_placeable_shape


def is_definite_outer_edge(edge: Part, network: Part):

    if edge.xts.x_span > 0:
        x0 = _pick_edge(network, (network.xts.x_min - 1, edge.xts.y_mid, edge.xts.z_mid), (0, 1, 0))
        if x0 is not None and edge.set_placeable_shape == x0:
            return True

        x1 = _pick_edge(network, (network.xts.x_max + 1, edge.xts.y_mid, edge.xts.z_mid), (0, -1, 0))
        if x1 is not None and edge.set_placeable_shape == x1:
            return True

    if edge.xts.y_span > 0:
        y0 = _pick_edge(network, (edge.xts.x_mid, network.xts.y_min - 1, edge.xts.z_mid), (1, 0, 0))
        if y0 is not None and edge.set_placeable_shape == y0:
            return True

        y1 = _pick_edge(network, (edge.xts.x_mid, network.xts.y_max + 1, edge.xts.z_mid), (-1, 0, 0))
        if y1 is not None and edge.set_placeable_shape == y1:
            return True

    return False


def main():
    cache = InMemoryPartCache()
    factory = PartFactory(cache)

    shape = (factory.polygon(3, 6).sp("body").make.face()
        .do(lambda p: p.bool.cut(factory.box_surrounding(p, z_clearance=1, y_length=0.4)
                                 .align().by("xminmidyminmidzmid", p))))

    def_outer_edges = [
        e for e in shape.explore.edge.get() if is_definite_outer_edge(e, shape)
    ]

    shape.preview(*[e.tr.mv(dz=1) for e in def_outer_edges])


if __name__ == '__main__':
    main()