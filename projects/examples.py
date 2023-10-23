import math

import OCC.Core.BRepBuilderAPI

from pythonoccutils.constants import Constants
from pythonoccutils.occutils_python import WireSketcher, MathUtils, InterrogateUtils
from pythonoccutils.part_cache import FileBasedPartCache
from pythonoccutils.part_manager import PartCache, PartFactory, ThreadSpec, Part
from pythonoccutils.svg_parser import SVGParser


def bolt_m4(cache: PartCache):
    factory = PartFactory(cache)

    thread_spec = ThreadSpec.metric("m4")

    body = factory.cylinder(thread_spec.d1_basic_minor_diameter / 2, 10)

    thread = factory.thread(thread_spec, True, 10, separate_sections=False)
    thread_chamfer_cylinder = factory.cylinder(thread.xts.x_span / 2 + 1, thread.xts.z_span) \
        .fillet.chamfer_edges(1.5, lambda e: Part.of_shape(e).xts.z_mid < thread.xts.z_mid)

    thread = thread.bool.common(thread_chamfer_cylinder)
    body = body.bool.common(thread_chamfer_cylinder)

    head = factory.polygon(1, 6) \
        .driver(PartFactory.PolygonDriver).set_flat_to_flat_dist(6) \
        .do_on("body", consumer=lambda p: p.make.face()) \
        .do_on("bounding_circle", consumer=lambda p: p.make.face()) \
        .extrude.prism(dz=3) \
        .do(lambda p: p.sp("body").bool.common(p.sp("bounding_circle").fillet.fillet_edges(0.5))) \
        .align().stack_z1(body)

    head = head.bool.cut(
        factory.text("M4", "arial", 10) \
            .tr.scale_to_y_span(2, scale_other_axes=True) \
            .align().by("xmidymidzmid", head) \
            .align().stack_z1(head) \
            .extrude.prism(dz=-0.2))

    return factory.compound(head, body, thread)


def enclosure(cache: PartCache):
    factory = PartFactory(cache)

    bolt = bolt_m4(cache).preview().tr.ry(math.radians(90)).incremental_pattern(
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
            transition_mode=OCC.Core.BRepBuilderAPI.BRepBuilderAPI_TransitionMode.BRepBuilderAPI_RoundCorner))\
        .cleanup()

    bottom, top = result.explore.solid.order_by(lambda s: s.xts.z_max).get()

    return factory.arrange(bottom.add(bolt), top.tr.ry(math.radians(180)), spacing=3)


def svg(cache):
    output = SVGParser().parse_file("/wsp/resources/example.svg")
    return PartFactory(cache).compound(*[Part.of_shape(s) for s in output.shapes])

if __name__ == '__main__':
    cache = FileBasedPartCache("/wsp/cache")
    enclosure(cache).preview()
