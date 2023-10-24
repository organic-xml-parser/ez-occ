import logging
import math

import OCC.Core.GeomAbs
from OCC.Core import Precision

from ezocc.alg.math import snap
from ezocc.alg.offset_face_with_holes import offset_face_with_holes, offset_holes_in_face
from ezocc.constants import Constants
from ezocc.occutils_python import WireSketcher, InterrogateUtils
from ezocc.part_cache import FileBasedPartCache
from ezocc.part_manager import PartFactory, Part
from ezocc.stock_parts import StockParts

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    cache = FileBasedPartCache("/wsp/cache")
    factory = PartFactory(cache)
    stock_parts = StockParts(cache)

    wall_thickness = 0.4 * 3

    board = factory.box(70, 50, 1.5)
    board = factory.compound(
        board.name("body"),
        factory.box_surrounding(board, -3, -3, -3)
            .tr.scale_to_z_span(board.xts.z_span + 38).align().by("zmin", board).tr.mv(dz=-13).name("clearance")
        )

    holes = factory.cylinder(1, board.xts.z_span)\
        .do_and_add(lambda p: p.tr.mv(dy=46))\
        .do_and_add(lambda p: p.tr.mv(dx=65))\
        .align().by("xmidymidzmid", board)

    boards = board.incremental_pattern(range(0, 3), lambda p: p.align().stack_z1(p))

    margin = 4
    pad = 10
    standoff = WireSketcher(board.xts.x_min + pad, board.xts.y_min - margin, board.xts.z_mid)\
        .line_to(x=board.xts.x_min - margin)\
        .line_to(y=board.xts.y_min + pad)\
        .close()\
        .get_face_part(cache)\
        .make.face()\
        .extrude.prism(dz=boards.xts.z_span)\
        .align().by("zmax", boards)\
        .do(lambda p: p.bool.cut(factory.box_surrounding(p).align().stack_x1(factory.box_surrounding(boards).bool.common(p))))\
        .bool.cut(*[s.extrude.make_thick_solid(Constants.clearance_mm()) for s in boards.compound_subpart("body").explore.solid.get()])

    standoffs = standoff.do_and_add(lambda p: p.mirror.x(center_x=board.xts.x_mid))\
        .do_and_add(lambda p: p.mirror.y(center_y=board.xts.y_mid))

    interior = factory.box_surrounding(standoffs)

    exterior = interior.extrude\
        .make_thick_solid(wall_thickness, join_type=OCC.Core.GeomAbs.GeomAbs_JoinType.GeomAbs_Intersection)\
        .bool.cut(interior)

    seam = factory.box_surrounding(standoffs).pick.from_dir(0, 1, 0)\
        .first_face()\
        .do(lambda f: f.bool.cut(f.extrude.offset(-Constants.clearance_mm()).make.face()))\
        .align().by("ymin", exterior)\
        .do(lambda f: f.extrude.prism(dy=abs(f.xts.y_min - standoffs.explore.solid.get_min(lambda s: s.xts.y_mid).xts.y_max)))

    exterior = exterior.bool.union(standoffs).cleanup()
    exterior = exterior.bool.cut(seam).cleanup()

    screw_cuts = factory.cylinder(2.8 / 2, standoff.xts.x_span)\
        .tr.ry(math.radians(90))\
        .pattern(range(0, 3), lambda i, p: p.tr.mv(dz=board.xts.z_span * i))\
        .align().by("xminymidminzmid", exterior).tr.mv(dy=4)

    exterior = exterior.bool.cut(*screw_cuts.explore.solid.get(), *screw_cuts.mirror.x(center_x=exterior.xts.x_mid).explore.solid.get())

    screw_spacing = snap(exterior.xts.x_span - 10, 2)

    screw_cuts = factory.cylinder(2.8 / 2, 10)\
        .do_and_add(lambda p: p.tr.mv(dx=screw_spacing))\
        .align().by("xmidymidminzmin", exterior).tr.mv(dy=4)

    exterior = exterior.bool.cut(
        *screw_cuts.explore.solid.get(),
        *screw_cuts.mirror.z(center_z=exterior.xts.z_mid).explore.solid.get())

    screen = stock_parts.i2c_oled_with_mount()\
        .tr.rx(math.radians(-90))\
        .align("screen_top").by("ymax", interior)\
        .align().by("zmid", factory.compound(*boards.compound_subpart("body").explore.solid.order_by(lambda s: s.xts.z_mid).get()[0:2]))\
        .align().by("xmid", exterior)

    screen.sp("clamp").save.single_stl("/wsp/output/SCREEN_CLAMP")

    ext_bottom, ext_top = exterior.explore.solid.order_by(lambda p: p.xts.y_mid).get()

    ext_top = ext_top.bool.cut(screen.sp("screen_top").extrude.prism(dy=10))\
        .bool.union(*screen.compound_subpart("mount").explore.solid.get())

    cable_passthrough = stock_parts.cable_passthrough(6)\
        .tr.rx(math.radians(-90))\
        .align().by("xmid", ext_top)\
        .align("clamp").by("zmax", ext_bottom).tr.mv(dz=-Constants.clearance_mm())\
        .align("mount").by("ymin", ext_bottom.pick.from_dir(0, -1, 1).first_face())

    cable_passthrough.sp("clamp").save.single_stl("/wsp/output/CABLE_PASSTHROUGH_CLAMP")

    ext_bottom = ext_bottom.bool.union(cable_passthrough.sp("mount"))
    ext_top = ext_top.bool.cut(cable_passthrough.sp("cable_cut_down_clearance"))
    ext_top = ext_top.bool.common(factory.box_surrounding(ext_top).fillet.chamfer_edges(2, lambda e: Part.of_shape(e).xts.y_mid > ext_top.xts.y_mid and InterrogateUtils.is_dz_line(e)))

    logger.info("Saving...")

    #ext_top.save.single_stl("/wsp/output/pantilt_enclosure_top")
    #ext_bottom.save.single_stl("/wsp/output/pantilt_enclosure_bottom")

    ymax_vent_face = ext_top.pick.from_dir(0, -1, 0).first_face()
    ymax_vent_face = ymax_vent_face.bool.cut(*[factory.box_surrounding(s, 0, 100, 100) for s in standoffs.explore.solid.get()])
    ymax_vent_face = ymax_vent_face.bool.cut(*[factory.cylinder(s.xts.x_span / 2, 1).align().by("xmidzmid", s).align().by("ymid", ymax_vent_face) for s in screen.compound_subpart("mount").explore.solid.get()])
    ymax_vent_face = offset_holes_in_face(ymax_vent_face, 3)
    ymax_vent_face = ymax_vent_face.bool.common(factory.box_surrounding(ymax_vent_face, 1, 1, -wall_thickness))

    ymin_vent_face = ext_bottom.pick.from_dir(0, -1, 0).first_face().align().by("ymin", ext_bottom)
    ymin_vent_face = ymin_vent_face.bool.cut(*[factory.box_surrounding(s, 0, 100, 100) for s in standoffs.explore.solid.get()])
    ymin_vent_face = offset_holes_in_face(ymin_vent_face, 3)
    ymin_vent_face = ymin_vent_face.bool.common(factory.box_surrounding(ymin_vent_face, 1, 1, -wall_thickness))

    x_vent_face = ext_top.pick.from_dir(1, 0, 0).first_face()
    x_vent_face = x_vent_face.bool.cut(*[factory.box_surrounding(s, 100, 0, 100) for s in standoffs.explore.solid.get()])\
        .explore.face.get_max(lambda f: f.xts.y_mid)
    x_vent_face = x_vent_face.bool.common(factory.box_surrounding(x_vent_face, 1, 1, -wall_thickness))

    z_min_face = ext_top.pick.from_dir(0, 0, 1).first_face()
    z_min_face = z_min_face.bool.cut(*standoffs.align().by("zmax", z_min_face).explore.solid.get()).bool.common(factory.box_surrounding(standoffs).align().by("zmidmax", z_min_face))
    z_min_face = offset_face_with_holes(z_min_face, -wall_thickness)

    #z_max_face = ext_top.pick.from_dir(0, 0, -1).first_face()
    #z_max_face = offset_face_with_holes(z_max_face, -2 * wall_thickness)

    #ext_top.preview(x_vent_face, ymin_vent_face, ymax_vent_face, z_min_face).raise_exception()

    vents = factory.hex_lattice(20, 20, 8, 8 + 0.2 * 4,
                                truncate_odd_rows=True,
                                cube_hex_effect_a=True,
                                cube_hex_effect_b=True)\
        .tr.rx(math.radians(90))\
        .align().by("xmidymaxzmid", exterior)

    base_vent_area = InterrogateUtils.surface_properties(vents.explore.face.get()[0].shape).Mass()

    ymax_vents = vents.align().by("ymid", ymax_vent_face).bool.common(ymax_vent_face)
    ymin_vents = vents.align().by("ymid", ymin_vent_face).bool.common(ymin_vent_face)

    x_vents = vents.tr.rz(math.radians(90))\
        .tr.rx(math.radians(90)).align().by("xmidymidzmid", x_vent_face).bool.common(x_vent_face)

    z_min_vents = vents.tr.rx(math.radians(90)).align().by("xmidymidzmid", z_min_face).bool.common(z_min_face)
    #z_max_vents = vents.tr.rx(math.radians(90)).align().by("xmidymidzmid", z_max_face)#.bool.common(z_max_face)
    #z_max_vents = factory.compound(*[v.bool.common(z_max_face) for v in z_max_vents.explore.face.get()]).preview()

    def filter_small_vents(part):
        return factory.compound(*[
            f for f in part.explore.face.get() if
            InterrogateUtils.surface_properties(f.shape).Mass() > base_vent_area / 2
         ])

    ymax_vents = filter_small_vents(ymax_vents)
    ymin_vents = filter_small_vents(ymin_vents)
    z_min_vents = filter_small_vents(z_min_vents)
    #z_max_vents = filter_small_vents(z_max_vents)
    x_vents = filter_small_vents(x_vents)

    ext_top = ext_top.bool.cut(z_min_vents.extrude.prism(dz=wall_thickness))
    ext_top = ext_top.bool.cut(ymax_vents.extrude.prism(dy=-wall_thickness))
    ext_bottom = ext_bottom.bool.cut(ymin_vents.extrude.prism(dy=wall_thickness))
    ext_top = ext_top.bool.cut(x_vents.extrude.prism(dx=wall_thickness))
    ext_top = ext_top.bool.cut(x_vents.extrude.prism(dx=wall_thickness).align().by("xmax", ext_top))

    ext_bottom.save.single_stl("/wsp/output/ENCLOSURE_BOTTOM")
    ext_top.save.single_stl("/wsp/output/ENCLOSURE_TOP")

    logger.info("Previewing...")

    factory.arrange(ext_bottom.add(boards),
                    ext_top.add(boards.compound_subpart("body")), spacing=10).preview()

