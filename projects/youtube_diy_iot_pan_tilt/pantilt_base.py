import inspect
import logging
import math
import random

import OCC
from OCC.Core import Precision
import OCC.Core.GeomAbs
from OCC.Core.gp import gp_ZOX, gp_XOY

from ezocc.constants import Constants
from ezocc.gears.gear_generator import GearSpec, GearPairSpec, InvoluteGearFactory
from ezocc.occutils_python import WireSketcher, InterrogateUtils
from ezocc.part_cache import PartCache, CacheToken, FileBasedPartCache, InMemoryPartCache
from ezocc.part_manager import PartFactory, Part, NoOpPartCache
from ezocc.stock_parts import StockParts

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    cache = FileBasedPartCache("/wsp/cache")
    stock_parts = StockParts(cache)
    part_factory = PartFactory(cache)

    servo = stock_parts.mg90s_servo()
    stepper = stock_parts.nema_17_stepper().tr.ry(math.radians(90))

    logger.info("Generating bevel gears")

    bevel_gears = InvoluteGearFactory(cache).create_bevel_gear_pair(GearPairSpec.matched_pair(3, 20, 20, clearance=Constants.clearance_mm()), 10, math.radians(45)) \
            .tr.rx(math.radians(180))\
            .align("pinion", "center").by("ymidzmid", stepper.single_subpart("shaft"))\
            .align("pinion").by("xmax", stepper.single_subpart("shaft"))

    bull_common = part_factory.cylinder(
                    abs(bevel_gears.sp("bull", "clearance").xts.x_mid - bevel_gears.sp("pinion", "clearance").xts.x_max),
                    bevel_gears.sp("bull", "clearance").xts.z_span)\
        .align().by("xmidymidzmid", bevel_gears.sp("bull", "clearance"))

    pinion_common = part_factory.cylinder(
        abs(bevel_gears.sp("pinion", "clearance").xts.z_mid - bevel_gears.sp("bull", "clearance").xts.z_max),
        bevel_gears.sp("pinion", "clearance").xts.x_span)\
        .tr.ry(math.radians(90))\
        .align().by("xmidymidzmid", bevel_gears.sp("pinion", "clearance"))

    bevel_gears = bevel_gears.do_on("bull", consumer=lambda bull:
        bull
            .do_on("body", consumer=lambda p: p.bool.common(bull_common))
            .do_on("clearance", consumer=lambda p: p.bool.common(bull_common)))

    bevel_gears = bevel_gears.do_on("pinion", consumer=lambda pinion:
        pinion
            .do_on("body", consumer=lambda p: p.bool.common(pinion_common))
            .do_on("clearance", consumer=lambda p: p.bool.common(pinion_common)))

    logger.info("Generating idler gears")

    idler_gears = InvoluteGearFactory(cache).create_involute_gear_pair(GearPairSpec.matched_pair(2, 16, 8), 8)\
            .tr.ry(math.radians(90))\
            .align("bull", "center").by("xmidymidzmid", bevel_gears.sp("pinion", "center"))\
            .align().stack_x0(bevel_gears.single_subpart("pinion"))

    logger.info("Creating stepper and positioning idler gears")

    stepper = stepper.align("shaft")\
        .by("ymidzmid", idler_gears.sp("pinion", "center"))\
        .align().by("xmax", idler_gears.sp("pinion"))

    idler_gears = idler_gears.do_on("bull",
                                    consumer=lambda p: p.tr.mv(dx=Constants.clearance_mm()))

    bevel_gears = bevel_gears.tr.mv(dx=Constants.clearance_mm())

    logger.info("Creating slip ring")

    slip_ring = part_factory.cylinder(12 / 2, 20).name_recurse("body")\
        .do(lambda p: p.bool.union(part_factory.cylinder(2, 3).align().by("xmidymidzminmax", p)))\
        .cleanup()\
        .align().by("xmidymid", bevel_gears.sp("bull", "center"))\
        .align("body").by("zmax", bevel_gears.sp("bull"))

    logger.info("Attaching top to bevel gears")

    top_interface = part_factory.cylinder(20, 20).do(lambda p: p.bool.cut(
        part_factory.cylinder(2.8 / 2, 15)
            .do_and_add(lambda pp: pp.tr.mv(dx=20))
            .do_and_add(lambda pp: pp.tr.mv(dy=20))
            .align().by("xmidymidzmax", p)
    ))\
        .name("body")\
        .add(part_factory.vertex(0, 0, 0, "center"))\
        .align("body").by("xmidymid", bevel_gears.sp("bull", "center"))\
        .align("body").stack_z1(bevel_gears.sp("bull"))

    def cut_interface_screw_mounts():
        screw = part_factory.cylinder(
            2.8 / 2,
            bevel_gears.sp("bull", "body").xts.z_span)

        screw = screw.bool.union(part_factory.cylinder(3.1 / 2, 5).align().stack_z1(screw))
        screw = screw.bool.union(part_factory.cylinder(6 / 2, 100).align().stack_z1(screw))

        screws = screw.do_and_add(lambda p: p.tr.mv(dx=20)).do_and_add(lambda p: p.tr.mv(dy=20))\
            .align().by("zmin", bevel_gears.sp("bull", "body"))\
            .align().by("xmidymid", bevel_gears.sp("bull", "center"))\
            .tr.rz(math.radians(45), offset=bevel_gears.sp("bull", "center").xts.xyz_mid)

        top_interface_cable_channel = part_factory.box_surrounding(top_interface)\
            .tr.scale_to_x_span(slip_ring.xts.x_span)\
            .align().by("xmidyminmid", slip_ring)\
            .align().stack_z1(top_interface).tr.mv(dz=-8)

        return top_interface.do_on(
                "body",
                consumer=lambda p: p.bool.cut(*screws.explore.solid.get(), top_interface_cable_channel)), \
            bevel_gears.do_on("bull", "body", consumer=lambda p: p.bool.cut(*screws.explore.solid.get()))

    top_interface, bevel_gears = cut_interface_screw_mounts()

    #bevel_gears = bevel_gears.do_on(
    #    "bull", "body", consumer=lambda p: p.bool.union(top_interface).cleanup())

    #def _export_top_interface():


    logger.info("Cutting idler shaft")

    idler = bevel_gears.single_subpart("pinion").add(idler_gears.single_subpart("bull"))

    logger.info("Cutting idler shaft")

    idler_shaft = part_factory.cylinder(4, idler.xts.x_span + 20)\
        .tr.ry(math.radians(90))\
        .align().by("xmidymidzmid", idler)\
        .extrude.make_thick_solid(Constants.clearance_mm()).make.solid()

    logger.info("Cutting idler shaft")

    bevel_gears = bevel_gears.do_on("bull", "body", consumer=lambda p: p.bool.cut(idler_shaft))
    logger.info("Cutting idler shaft")

    idler_gears = idler_gears.do_on("bull", "body", consumer=lambda p: p.bool.cut(idler_shaft))
    logger.info("Creating gearbox")

    gearbox_bounds = part_factory.box_surrounding(stepper.add(idler_gears, bevel_gears, slip_ring))

    gearbox = gearbox_bounds\
        .do(lambda p: p.bool.union(
            part_factory.box(abs(p.xts.x_mid - idler_shaft.xts.x_max), p.xts.y_span, p.xts.z_span)
            .align().by("xminmidyminzmin", p)))\
        .do(lambda p: p.bool.cut(part_factory.box_surrounding(p).align().by("xmaxmin", stepper).tr.mv(dx=15)))\
        .do(lambda p: p.bool.cut(part_factory.box_surrounding(p).align().by("zmin", top_interface).tr.mv(dz=2)))\
        .cleanup()\
        .do(lambda p: p.extrude.make_thick_solid(5, join_type=OCC.Core.GeomAbs.GeomAbs_JoinType.GeomAbs_Intersection))\
        .make.solid().cleanup()

    gearbox = gearbox\
        .fillet.chamfer_edges(4, lambda f: Part.of_shape(f).xts.x_mid < gearbox.xts.x_max)\
        .cleanup().make.solid().cleanup()

    gearbox_shadow_line: Part = gearbox.bool.common(
        part_factory.square_centered(gearbox.xts.x_span + 1, gearbox.xts.z_span + 1)
        .tr.rx(math.radians(90))
        .align().com(gearbox).explore.face.get()[0]).explore.face.get()[0].inspect.outer_wire()
    gearbox_shadow_line_inner = gearbox_shadow_line.extrude.offset(-10)

    gearbox_cut = WireSketcher(
            gearbox_shadow_line.xts.x_min - 50,
            gearbox_shadow_line.xts.y_mid,
            gearbox_shadow_line.xts.z_mid - 3)\
        .line_to(x=gearbox_shadow_line.xts.x_min)\
        .line_to(x=3, is_relative=True)\
        .line_to(y=6, is_relative=True)\
        .line_to(x=gearbox_shadow_line_inner.xts.x_min)\
        .get_wire_part(cache)\
        .extrude.offset(Constants.clearance_mm() / 2).make.face()\
        .cleanup.build_curves_3d()\
        .loft.pipe(gearbox_shadow_line_inner.cleanup.build_curves_3d()).make.solid()

    gearbox_cut = gearbox_shadow_line_inner\
        .make.face()\
        .extrude.prism(dy=Constants.clearance_mm())\
        .align().by("ymax", gearbox_cut)\
        .bool.union(gearbox_cut)\
        .cleanup()\
        .align().by("ymaxmid", gearbox)

    stepper_screws = part_factory.cylinder(3.1 / 2, 5)\
        .do(lambda p: p.add(part_factory.cylinder(6.5/2, 100).align().stack_z1(p)))\
        .tr.ry(math.radians(90))\
        .align().by("xminmax", stepper.compound_subpart("screw_hole"))\
        .do(lambda p: part_factory.compound(*
            [p.align().by("ymidzmid", f) for f in stepper.list_subpart("screw_hole")]))

    logger.info("Cutting gearbox cavities")
    gearbox = gearbox.bool.cut(*[s.extrude.make_thick_solid(Constants.clearance_mm()).make.solid() for s in [
            idler_shaft,
            *stepper_screws.explore.solid.get(),
            stepper.single_subpart("body_clearance"),
            stepper.single_subpart("shaft_clearance"),
            stepper.single_subpart("top_ring_clearance"),
            slip_ring.cleanup().make.solid(),
            idler_gears.sp("pinion", "clearance"),
            idler_gears.sp("bull", "clearance"),
            bevel_gears.sp("pinion", "clearance"),
            bevel_gears.sp("bull", "clearance"),
            part_factory.cylinder(top_interface.xts.x_span / 2, top_interface.xts.z_span)
                               .align().by("xmidymidzmid", top_interface.sp("center")),
            *part_factory.cylinder(2.8 / 2, 20).array.on_verts_of(part_factory.square_centered(50, 50))
                               .align().by("xmidymidzmin", gearbox).explore.solid.get()
        ]])

    logger.info("Cutting cable passthrough")
    gearbox = gearbox.bool.cut(
        part_factory.capsule(gearbox.xts.x_span, slip_ring.xts.y_span)
            .extrude.prism(dz=4)
            .make.solid()
            .align().by("xmaxymidzmaxmin", slip_ring)
            .extrude.make_thick_solid(Constants.clearance_mm()))

    hex = part_factory.polygon(1, 6)\
            .tr.scale_to_x_span(17, scale_other_axes=True)\
            .sp("body")\
            .make.face()\
            .extrude.prism(dz=6.5)

    bolt = part_factory.cylinder(5, 75).name_recurse("thread")\
        .do(lambda p: p.bool.union(hex
            .name_recurse("head")
            .align().by("xmidymidzminmax", p)))\
        .tr.rx(math.radians(90))\
        .align("head").by("ymaxmin", gearbox)\
        .do(lambda p: p.bool.union(hex
            .tr.rz(math.radians(90))
            .tr.rx(math.radians(90))
            .align().by("xmidzmid", p)
            .align().by("ymax", gearbox)
            .extrude.make_thick_solid(Constants.clearance_mm())))

    gearbox = gearbox.bool.cut(
        bolt.align("thread").by("zmaxmin", bevel_gears.single_subpart("bull"))
            .align().by('xmin', gearbox).tr.mv(dx=4, dz=-1),
        bolt.align("thread").by("zmaxmin", bevel_gears.single_subpart("bull"))
            .align().by('xmax', gearbox).tr.mv(dx=-0.5, dz=5),
        bolt.align("thread").by("zmid", stepper.single_subpart("body"))
            .align().by('xmax', gearbox).tr.mv(dx=-0.5, dz=1))

    gearbox = gearbox.bool.cut(gearbox_cut)

    gearbox_ymin = gearbox.explore.solid.get_min(lambda s: s.xts.y_mid)
    gearbox_ymax = gearbox.explore.solid.get_max(lambda s: s.xts.y_mid)\
        .bool.cut(part_factory.box_surrounding(top_interface).align().by("ymaxmid", top_interface))

    gearbox_ymin.save.single_stl("/wsp/output/GEARBOX_YMIN")
    gearbox_ymax.save.single_stl("/wsp/output/GEARBOX_YMAX")

    gear_stepper = idler_gears.single_subpart("pinion").single_subpart("body").bool.cut(stepper.single_subpart("shaft"))
    gear_idler = idler_gears.sp("bull", "body")\
        .bool.union(bevel_gears.sp("pinion", "body"))\
        .bool.cut(idler_shaft)

    slip_ring_clearance = part_factory.cylinder(slip_ring.xts.x_span / 2, gearbox.xts.z_span)\
        .align().by("xmidymidzmid", slip_ring)
    gear_top = bevel_gears.single_subpart("bull", "body").bool.cut(slip_ring_clearance)
    top_interface = top_interface.do_on("body", consumer=lambda p: p.bool.cut(slip_ring_clearance))

    gear_top.save.single_stl("/wsp/output/GEAR_TOP")
    top_interface.save.single_stl("/wsp/output/TOP_INTERFACE")

    gear_idler.save.single_stl("/wsp/output/GEAR_IDLER")
    gear_stepper.save.single_stl("/wsp/output/GEAR_STEPPER")

    logger.info("Starting visualization")
    stepper.remove(
        stepper.single_subpart("shaft_clearance"),
        stepper.single_subpart("top_ring_clearance"))\
        .add(
            gear_top,
            top_interface,
            gear_stepper,
            gear_idler,
            gearbox_ymin,
            gearbox_ymax
    ).preview()
