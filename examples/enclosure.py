import math

import OCC
from OCC.Core import BRepBuilderAPI

from ezocc.constants import Constants
from ezocc.occutils_python import WireSketcher, MathUtils, InterrogateUtils
from ezocc.part_manager import PartCache, PartFactory

from . import bolt as mkbolt


TITLE = "Enclosure"
DESCRIPTION = "Creating an Enclosure w. shadow line"
FILENAME = "enclosure"

def build(cache: PartCache):
    factory = PartFactory(cache)

    bolt = mkbolt.build(cache).tr.ry(math.radians(90)).incremental_pattern(
        range(0, 4), lambda p: p.tr.mv(dy=p.xts.y_span + 2))

    result = factory.box_surrounding(bolt, 3, 3, 3)\
        .do(lambda p: p.extrude.make_thick_solid(3).bool.cut(p))

    v0, v1 = result.pick.from_dir(1, 0, 0).as_list()[0:2]
    interface_cut = WireSketcher(*v0.xts.xyz_mid)\
        .line_to(x=MathUtils.lerp(x0=v0.xts.x_mid, x1=v1.xts.x_mid, coordinate_proportional=0.5)[0])\
        .line_to(z=2, is_relative=True)\
        .line_to(x=v1.xts.x_mid)\
        .get_wire_part(cache)\
        .extrude.offset(Constants.clearance_mm())

    spine = result.bool.common(
        factory.square_centered(result.xts.x_span, result.xts.y_span)
        .align().by("xmidymidzmid", result)).explore.wire.get_min(lambda w: InterrogateUtils.length(w.shape))

    result = result.bool.cut(
        interface_cut.loft.pipe(
            spine,
            transition_mode=BRepBuilderAPI.BRepBuilderAPI_TransitionMode.BRepBuilderAPI_RoundCorner))\
        .cleanup()

    bottom, top = result.explore.solid.order_by(lambda s: s.xts.z_max).get()

    return factory.arrange(bottom.add(bolt), top.tr.ry(math.radians(180)), spacing=3)