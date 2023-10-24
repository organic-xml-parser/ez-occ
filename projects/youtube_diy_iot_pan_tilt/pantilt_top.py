import inspect
import logging
import math

from OCC.Core import Precision
from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
from OCC.Core.gp import gp
import OCC.Core.BRepBuilderAPI
import OCC.Core.GeomAbs
import OCC.Core.BOPAlgo

from ezocc.constants import Constants
from ezocc.gcs import GCS_2d
from ezocc.gears.gear_generator import InvoluteGearFactory, GearSpec, PlanetaryGearSpec
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

    def _make_gearbox_and_stepper() -> Part:
        num_planets = 4
        gearbox_thickness = 16

        stepper = StockParts(cache).nema_17_stepper()
        hole_spacing = stepper.compound_subpart("screw_hole").xts.x_span - stepper.list_subpart("screw_hole")[0].xts.x_span

        sun_pitch_dia = math.sqrt(2) * hole_spacing / 2
        planet_pitch_dia = math.sqrt(2) * hole_spacing / 2

        sun_num_teeth = 8
        planet_num_teeth = 8

        module = sun_pitch_dia / sun_num_teeth

        reduction = 0.5

        num_teeth_ring: int = int(sun_num_teeth / reduction + sun_num_teeth)

        gear_spec = PlanetaryGearSpec(
            num_planets=4,
            sun=GearSpec(module, sun_num_teeth),
            planets=GearSpec(module, planet_num_teeth),
            ring=GearSpec(module, num_teeth_ring), clearance=Constants.clearance_mm())

        ring = InvoluteGearFactory(cache).create_planetary_gear_set(gear_spec)\
            .tr.rz(math.radians(45))\
            .align("ring", "center").by("xmidymidzmax", stepper.sp("shaft_clearance"))

        def extrude_gear(gear: Part, sense: bool) -> Part:
            gear = gear.do_on("body",
                              consumer=lambda p: p.make.face())

            center = gear.sp("center")
            pitch_dia = float(gear.annotation("gear_spec/pitch_diameter")) / 2

            helix = factory.helix_by_angle(gearbox_thickness / 2, pitch_dia, helix_angle=math.radians(45 if sense else -45))

            helix = helix.add(helix.mirror.z().align().stack_z0(helix))\
                .bool.union()\
                .make.wire()\
                .align().stack_z1(gear)\
                .tr.mv(dx=center.xts.x_mid, dy=center.xts.y_mid).cleanup.build_curves_3d()

            spine = WireSketcher(*center.xts.xyz_mid).line_to(z=gearbox_thickness, is_relative=True).get_wire_part(cache)

            gear = gear.cleanup.build_curves_3d()
            gear = gear.do_on("body",
                              consumer=lambda p:
                                p.loft.pipe(spine_part=spine, aux_spine=helix),
                              part_filter=lambda p: p.inspect.is_face())

            return gear

        ring = ring.do_on("sun", consumer=lambda p: extrude_gear(p, False))

        stepper = stepper\
            .align("shaft").by("zmax", ring.sp("sun", "body"))\
            .align("shaft").by("xmidymid", ring.sp("sun", "center"))

        def cut_ring(ring: Part):
            ring_outside_diameter = float(ring.annotation("gear_spec/outside_diameter"))

            exterior = factory.cylinder(8 + ring_outside_diameter / 2, ring.xts.z_span - Precision.precision.Confusion())\
                .align().by("xmidymid", ring.sp("center"))\
                .align().by("zmid", ring)

            bolts = factory.cylinder(2.8 / 2, exterior.xts.z_span).bool.union(factory.cylinder(3, 3))\
                .align().by("xmidymid", exterior)\
                .align().by("zmid", exterior)\
                .do(lambda p: p.tr.mv(dx=ring_outside_diameter / 2 + 4))\
                .pattern(range(0, 8), lambda i, p: p.tr.rz(math.radians(i * 360 / 8), offset=exterior.xts.xyz_mid))

            exterior = exterior.bool.cut(bolts)

            return ring.do_on("body", consumer=lambda p: exterior.bool.cut(p)).insert(exterior.name("ring_extents"))

        ring = ring.do_on("ring", consumer=lambda p: extrude_gear(p, True))
        ring = ring.do_on("ring", consumer=cut_ring)

        def make_planet_faces(planets):
            for i in range(0, num_planets):
                planets = planets.do_on(
                    str(i),
                    consumer=lambda p: extrude_gear(p, True))

                planets = planets.do_on(
                    str(i),
                    consumer=lambda p: p.bool.cut(factory.cylinder(3.3 / 2, p.xts.z_span + 2)
                                                  .do(lambda p: p.bool.union(factory.cylinder(3.5, 4).align().by("zmax", p)))
                                                  .cleanup()
                                                  .align().by("xmidymidzmin", p.sp("center")).tr.mv(dz=-1))).cleanup()

            return planets

        ring = ring.do_on("planets", consumer=make_planet_faces)

        ring = ring.do_on("sun", "body", consumer=lambda p: p.bool.cut(stepper.sp("shaft")))

        # todo: remove this simplification when ready to create full model
        ring = factory.compound(ring.sp("ring_extents").name("ring_extents"), factory.vertex(0, 0, 0)).print()

        return factory.compound(
            ring.name("gearbox"),
            stepper.name("stepper")
        )

    logger.info("Fetching gearbox and stepper")

    token = cache.create_token("make_gearbox_and_stepper", inspect.getsource(_make_gearbox_and_stepper))
    gearbox_and_stepper = cache.ensure_exists(token, lambda: _make_gearbox_and_stepper().with_cache_token(token))

    def _make_extrusions_and_stepper_mount() -> Part:
        gearbox = gearbox_and_stepper.sp("gearbox")
        stepper = gearbox_and_stepper.sp("stepper")

        extrusion = factory.box(10, 10, gearbox_and_stepper.xts.z_span * 2) \
            .do_and_add(lambda p: p.tr.mv(dx=stepper.xts.x_span + p.xts.x_span)) \
            .align().by("xmidymaxminzmid", stepper)

        intersection = extrusion.bool.common(gearbox.sp("ring_extents"))
        while len(intersection.explore.solid.get()) > 0:
            extrusion = extrusion.align().stack_y0(intersection)
            intersection = extrusion.bool.common(gearbox.sp("ring_extents"))

        extrusion = extrusion.tr.mv(dy=-3)

        phone = factory.box(10.6, 139, 70) \
            .fillet.fillet_edges(10, lambda e: InterrogateUtils.is_dx_line(e))\
            .fillet.fillet_edges(2, lambda e: not InterrogateUtils.is_dx_line(e))\
            .align().stack_y1(gearbox).tr.mv(dy=20)\
            .align().by("xmid", stepper.sp("body"))\
            .align().by("zmid", stepper.sp("body")).preview(stepper)

        stepper_mount = WireSketcher(
            stepper.xts.x_min, extrusion.xts.y_min, gearbox.sp("ring_extents").xts.z_min)\
            .line_to(x=extrusion.xts.x_max)\
            .line_to(y=extrusion.xts.y_max)\
            .line_to(x=stepper.xts.x_max, y=stepper.xts.y_min)\
            .line_to(y=stepper.compound_subpart("screw_hole").xts.y_max + 3) \
            .line_to(x=stepper.sp("cap_top").xts.x_min) \
            .line_to(y=stepper.xts.y_min)\
            .line_to(x=extrusion.xts.x_min, y=extrusion.xts.y_max)\
            .line_to(y=extrusion.xts.y_min)\
            .close()\
            .get_face_part(cache)\
            .extrude.offset(5, join_type=OCC.Core.GeomAbs.GeomAbs_JoinType.GeomAbs_Intersection)\
            .make.face().tr.mv(dz=-Constants.clearance_mm())\
            .do(lambda p: p.extrude.prism(dz=-abs(p.xts.z_mid - stepper.xts.z_min) - 6))\
            .cleanup()\
            .fillet.chamfer_edges(2, lambda e: InterrogateUtils.is_dz_line(e) or True)

        cutout = stepper.sp("body_clearance")\
            .bool.union(stepper.sp("top_ring_clearance"), factory.box_surrounding(stepper_mount)
                        .tr.scale_to_z_span(stepper.sp("body").xts.z_span - stepper.sp("top_ring_clearance").xts.z_span)
                        .tr.scale_to_x_span(stepper.sp("body_clearance").xts.x_span)
                        .align().by("zmin", stepper.sp("cap_bottom"))\
                        .align().by("xmidyminmid", stepper.sp("body_clearance")))\
            .cleanup()\
            .extrude.make_thick_solid(Constants.clearance_mm())

        stepper_mount = stepper_mount.bool.cut(cutout)

        shaft_cut = stepper.sp("shaft_clearance")\
            .do(lambda p: p.bool.union(factory.box_surrounding(p).tr.scale_to_y_span(stepper_mount).align().by("yminmid", p)))\
            .cleanup()\
            .extrude.make_thick_solid(Constants.clearance_mm()).cleanup()

        top_ring_cut = stepper.sp("top_ring_clearance") \
            .do(lambda p: p.bool.union(
            factory.box_surrounding(p).tr.scale_to_y_span(stepper_mount).align().by("yminmid", p))) \
            .cleanup() \
            .extrude.make_thick_solid(Constants.clearance_mm()).cleanup()

        stepper.print()

        bolt_cuts = factory.cylinder(3.2 / 2, stepper_mount.xts.z_span)\
            .array.on_faces_of(stepper.compound_subpart("screw_hole"))\
            .align().stack_z1(stepper.compound_subpart("screw_hole"))

        stepper_mount = stepper_mount.bool.cut(shaft_cut, top_ring_cut, bolt_cuts)

        stepper_mount = stepper_mount.bool.cut(
            factory.cylinder(3.3 / 2, stepper_mount.xts.z_span)
            .align().by("xmidymid", stepper.sp("shaft_clearance"))
            .align().by("zmid", stepper_mount))

        stepper_mount = stepper_mount.bool.cut(
            *[s.extrude.make_thick_solid(Constants.clearance_mm()) for s in extrusion.explore.solid.get()])

        pan_module_screw_mounts = factory.cylinder(2.8 / 2, stepper_mount.xts.y_span)\
            .bool.union(factory.cylinder(3, stepper_mount.xts.y_span).tr.mv(dz=15))\
            .cleanup()\
            .tr.rx(math.radians(-90))\
            .do_and_add(lambda p: p.tr.mv(dx=20))\
            .do_and_add(lambda p: p.tr.mv(dz=20))\
            .align().by("xmid", extrusion)\
            .align().by("zmid", stepper.sp("body"))\
            .align().by("ymin", stepper_mount)

        stepper_mount = stepper_mount.bool.cut(pan_module_screw_mounts)

        breather_holes = factory.hex_lattice(9, 3, hex_radius=4, grid_radius=5, truncate_odd_rows=True)\
            .tr.rz(math.radians(90))\
            .tr.ry(math.radians(90))\
            .align().by("ymidzmid", stepper.sp("body"))\
            .align().by("xmin", stepper_mount)\
            .extrude.prism(dx=stepper_mount.xts.x_span + 1)

        stepper_mount = stepper_mount.bool.cut(breather_holes)

        back_mount_hole = factory.cylinder(2.8 / 2, stepper_mount.xts.x_span).tr.ry(math.radians(90))

        # cut some more mount holes
        #stepper_mount = stepper_mount.bool.cut(
        #    back_mount_hole.do_and_add(lambda p: p.tr.mv(dz=30)).do_and_add(lambda p: p.tr.mv(dy=-10))
        #    .align().by("xmaxminzmid", stepper.sp("body")).tr.mv(dx=25)
        #    .align().stack_y1(extrusion).tr.mv(dy=5))


        back_mount_hole = back_mount_hole.align().by("ymid", extrusion).align().by("xmaxmin", extrusion)
        stepper_mount = stepper_mount.bool.cut(back_mount_hole.align().by("zmax", stepper_mount).tr.mv(dz=-6))
        stepper_mount = stepper_mount.bool.cut(back_mount_hole.align().by("zmin", stepper_mount).tr.mv(dz=6))

        back_mount_hole = back_mount_hole.align().by("xminmax", extrusion)
        stepper_mount = stepper_mount.bool.cut(back_mount_hole.align().by("zmax", stepper_mount).tr.mv(dz=-6))
        stepper_mount = stepper_mount.bool.cut(back_mount_hole.align().by("zmin", stepper_mount).tr.mv(dz=6))

        return factory.compound(
            extrusion.name("extrusion"),
            phone.name("phone"),
            stepper_mount.name("stepper_mount"))

    logger.info("Fetching extrusions and stepper mount")

    token = cache.create_token("extrusions_and_stepper_mount", gearbox_and_stepper, inspect.getsource(_make_extrusions_and_stepper_mount))
    extrusions_and_stepper_mount = cache.ensure_exists(token, lambda: _make_extrusions_and_stepper_mount().with_cache_token(token))

    def _make_phone_cradle() -> Part:
        phone = extrusions_and_stepper_mount.sp("phone")

        cradle = phone.make.solid()\
            .extrude.make_thick_solid(5).make.solid()

        cradle = cradle.bool.union(cradle.bool.common(factory.square_centered(cradle.xts.z_span, cradle.xts.y_span)
                           .tr.ry(math.radians(90))
                           .align().by("xmidymidzmid", cradle))\
            .extrude.prism(dx=-cradle.xts.x_span / 2 - 2)).cleanup()

        cradle = cradle.fillet.chamfer_faces(1, {cradle.pick.from_dir(1, 0, 0).first_face()})

        cradle = cradle.bool.cut(
            phone.extrude.make_thick_solid(Constants.clearance_mm() / 2).make.solid(),
            phone.pick.from_dir(-1, 0, 0).first_face()
                                 .extrude.offset(-1).make.face()
                                 .extrude.prism(dx=100),
            factory.box_surrounding(cradle).align().stack_x1(cradle, offset=-2))

        cradle = cradle.bool.cut(factory.box_surrounding(cradle, x_clearance=10, y_clearance=10, z_clearance=-10)
                                 .align().by("xmin", phone).tr.mv(dx=2)
                                 .do(lambda p: p.fillet.chamfer_faces(6, {p.pick.from_dir(1, 0, 0).first_face()})))

        cradle = cradle.bool.cut(factory.box_surrounding(cradle, x_clearance=10, y_clearance=-10, z_clearance=10)
                                 .align().by("xmin", phone).tr.mv(dx=2)
                                 .do(lambda p: p.fillet.chamfer_faces(6, {p.pick.from_dir(1, 0, 0).first_face()})))

        lattice = factory.hex_lattice(19, 3, hex_radius=6, grid_radius=7.5, truncate_odd_rows=True, cube_hex_line_thickness=3)\
            .tr.ry(math.radians(90))\
            .align().by("ymidzmid", phone)\
            .align().by("xmin", cradle)\
            .extrude.prism(dx=cradle.xts.x_span)

        cradle = cradle.bool.cut(*[s for s in lattice.explore.solid.get()])

        cradle_screws = factory.cylinder(2.8 / 2, abs(cradle.xts.z_span - lattice.xts.z_span) * 0.5 - 1, bottom_wire_name="cradle_screws")\
            .incremental_pattern(range(0, 6), lambda p: p.tr.mv(dy=20))\
            .align().by("xminymidzmax", cradle)\
            .align().x_mid_to(x=cradle.xts.x_min + 0.5 * abs(cradle.xts.x_min - phone.xts.x_min))

        cradle = cradle.bool.cut(cradle_screws, cradle_screws.align().by("zmin", cradle))

        cradle = cradle.mirror.x(center_x=phone.xts.x_mid)

        return cradle.name("cradle")

    token = cache.create_token("phone_cradle",
                               gearbox_and_stepper,
                               extrusions_and_stepper_mount,
                               inspect.getsource(_make_phone_cradle))

    phone_cradle = cache.ensure_exists(token, lambda: _make_phone_cradle().with_cache_token(token))

    def _cradle_connectors() -> Part:
        gearbox_extents = gearbox_and_stepper.sp("gearbox", "ring_extents")
        gearbox_ring_rad = gearbox_extents.xts.x_span / 2
        ring_inner_rad = gearbox_ring_rad - 12

        result = factory.cylinder(radius=gearbox_ring_rad,
                     height=gearbox_extents.xts.z_span / 2)\
            .align().by("xmidymidzmid", gearbox_extents)\
            .align().stack_z1(phone_cradle)

        cradle_screws = phone_cradle.compound_subpart("cradle_screws").explore.wire.order_by(lambda w: w.xts.y_mid).get()
        tp = GCS_2d(cache).get_tangent_points(GCS_2d.circ_2d(gearbox_extents.xts.x_mid, gearbox_extents.xts.y_mid, ring_inner_rad), cradle_screws[1].xts.xy_mid)

        arm = WireSketcher(tp[0].X(), tp[0].Y(), gearbox_extents.xts.z_max)\
            .line_to(x=tp[1].X(), y=tp[1].Y())\
            .line_to(x=cradle_screws[2].xts.x_mid, y=cradle_screws[2].xts.y_mid)\
            .close().get_face_part(cache)\
            .extrude.offset(8)\
            .make.face().extrude.prism(dz=-result.xts.z_span)\
            .align().by("zmax", result)\
            .make.solid()

        result = result.bool.union(arm).cleanup()

        result = result.bool.cut(factory.box_surrounding(result, 10, 10, 10).align().by("ymaxmid", gearbox_extents))

        result = result\
            .extrude.make_thick_solid(3, join_type=OCC.Core.GeomAbs.GeomAbs_JoinType.GeomAbs_Intersection)\
            .align().by("zmin", result)

        result = result.bool.cut(factory.box_surrounding(result).align().by("xminmax", gearbox_extents))
        result = result.bool.cut(factory.box_surrounding(result).align().by("xmaxmin", gearbox_extents))

        result = result.fillet.chamfer_edges(1)

        result = result.bool.cut(factory.cylinder(ring_inner_rad, result.xts.z_span)
                                 .align().by("xmidymid", gearbox_extents)
                                 .align().by("zmax", result))

        result = result.bool.cut(factory.cylinder(gearbox_ring_rad, gearbox_extents.xts.z_span)
                                 .extrude.make_thick_solid(Constants.clearance_mm())
                                 .align().by("xmidymidzmid", gearbox_extents))

        screw_faces = gearbox_extents.explore.face.filter_by(lambda f: gearbox_extents.xts.z_max - 0.1 > f.xts.z_max and f.xts.z_min > gearbox_extents.xts.z_min + 0.1).get()

        screw_cut = factory.cylinder(2.8 / 2, result.xts.z_span + 2)

        result = result.bool.cut(screw_cut.array.on_faces_of(factory.compound(*screw_faces)).align().by("zmid", result))

        result = result.bool.cut(
            screw_cut.array.on_faces_of(factory.compound(*[w.make.face() for w in cradle_screws]))\
                .align().by("zmid", result))

        arm_c1: Part = factory.cylinder(gearbox_ring_rad - 25,
                                    4 + abs(phone_cradle.xts.z_min - extrusions_and_stepper_mount.sp("stepper_mount").xts.z_min))\
            .align().by("xmidymid", gearbox_and_stepper.sp("stepper", "shaft_clearance"))\
            .align().stack_z0(extrusions_and_stepper_mount.sp("stepper_mount"), offset=-Constants.clearance_mm())

        arm_c2: Part = factory.cylinder(10, arm_c1.xts.z_span)\
            .align().by("xmidymid", cradle_screws[2]).preview(cradle_screws[2], phone_cradle.tr.mv(dz=10))\
            .align().by("zmin", arm_c1)

        tangent_points = GCS_2d(cache).get_tangent_points_circ_circ(
            GCS_2d.circ_2d(*arm_c1.xts.xy_mid, arm_c1.xts.x_span / 2),
            GCS_2d.circ_2d(*arm_c2.xts.xy_mid, arm_c2.xts.x_span / 2))

        arm_main = WireSketcher(tangent_points[0][0].X(), tangent_points[0][0].Y(), 0)\
            .line_to(x=tangent_points[0][1].X(), y=tangent_points[0][1].Y())\
            .line_to(x=tangent_points[1][0].X(), y=tangent_points[1][0].Y())\
            .line_to(x=tangent_points[1][1].X(), y=tangent_points[1][1].Y())\
            .close()\
            .get_face_part(cache)\
            .extrude.prism(dz=arm_c2.xts.z_span)\
            .align().by("zmin", arm_c1)

        arm_main = arm_main.bool.union(arm_c2, arm_c1).cleanup()

        arm_main = arm_main.fillet.chamfer_edges(1)

        arm_main = arm_main.bool.cut(
            factory.box_surrounding(phone_cradle).extrude.make_thick_solid(Constants.clearance_mm()))

        arm_main = arm_main.bool.cut(
            screw_cut.array.on_faces_of(factory.compound(*[w.make.face() for w in cradle_screws]))\
                .align().by("zmid", arm_main))
        arm_main = arm_main.bool.cut(screw_cut
                                     .align().by("xmidymid", gearbox_and_stepper.sp("stepper", "shaft_clearance"))
                                     .align().by("zmin", arm_main))

        return result.add(arm_main)

    token = cache.create_token("cradle_connectors",
                               gearbox_and_stepper,
                               extrusions_and_stepper_mount,
                               phone_cradle,
                               inspect.getsource(_cradle_connectors))

    cradle_connectors = cache.ensure_exists(token, lambda: _cradle_connectors().with_cache_token(token))

    def _stepper_enclosure() -> Part:
        extrusion = extrusions_and_stepper_mount.sp("extrusion")
        board = factory.box(40, 1.5, 60)\
            .align().by("xmid", extrusion)\
            .align().stack_y1(extrusion)\
            .align().by("zmid", extrusion)

        terminals = factory.box(8, 10, 40)\
            .align().by("xminyminmaxzmid", board)

        stepper_driver = factory.box(21, 25, 15)\
            .align().by("xmax", board).tr.mv(dx=-11)\
            .align().stack_y1(board)\
            .align().by("zmax", board).tr.mv(dz=-15)

        stepper_plug = factory.box(10.5, 8, 2.2)\
            .align().by("xmid", board)\
            .align().by("zmax", board).tr.mv(dz=-7)\
            .align().stack_y1(board)

        solder_clearance = factory.box(3, 3, 3)\
            .align().by("xmidymaxminzmid", board)

        board = factory.compound(
            board.name("board"),
            terminals.name("terminals"),
            stepper_driver,
            stepper_plug.name("stepper_plug"),
            solder_clearance)

        board = board.align().stack_y1(extrusion).tr.mv(dy=5)

        enclosure = factory.box_surrounding(board.add(extrusion), 1, 1, 1)\
            .tr.scale_to_z_span(board.xts.z_span).align().by("zmid", board)

        enclosure_outer = factory.box_surrounding(enclosure, 3, 3, 6).fillet.fillet_edges(2) # enclosure.extrude.make_thick_solid(3)

        enclosure_shadow_line_spine = \
            factory.square_centered(
                enclosure_outer.xts.x_span + 1,
                enclosure_outer.xts.z_span + 1)\
            .tr.rx(math.radians(90))\
            .align().by("xmidymidzmid", enclosure_outer)\
                .align().by("ymid", board.sp("board"))\
                .bool.section(enclosure_outer)\
                .make.wire().extrude.offset(-10)

        shadow_line = WireSketcher(
                enclosure_outer.xts.x_min,
                board.sp("board").xts.y_max + 3, enclosure_outer.xts.z_mid)\
            .line_to(x=enclosure.xts.x_min, fraction=0.5)\
            .line_to(y=-3, is_relative=True)\
            .line_to(x=enclosure.xts.x_min+10)\
            .get_wire_part(cache)\
            .extrude.offset(Constants.clearance_mm()).loft.pipe(spine_part=enclosure_shadow_line_spine)

        enclosure_outer = enclosure_outer\
            .bool.cut(enclosure.bool.cut(*[e.extrude.make_thick_solid(3) for e in extrusion.explore.solid.get()]))

        standoff = factory.box(enclosure.xts.x_span, enclosure.xts.y_span, 4)\
            .align().by("xmaxyminzmin", enclosure)\
                .bool.cut(board.sp("board")
                          .extrude.make_thick_solid(Constants.clearance_mm()))\
            .do_and_add(lambda p: p.mirror.z().align().by("zmax", enclosure))

        enclosure_outer = enclosure_outer.bool.union(*[s for s in standoff.explore.solid.get()])

        enclosure_outer = enclosure_outer.bool.cut(
            factory.box(enclosure_outer.xts.x_span, terminals.xts.y_span, terminals.xts.z_span)
            .align().by("xmaxminymaxzmin", board.sp("terminals")).extrude.make_thick_solid(1))

        enclosure_outer = enclosure_outer.bool.cut(shadow_line)

        posts = factory.cylinder(3, 15)\
            .do(lambda p: p.bool.union(
                factory.cylinder(2.8 / 2, enclosure_outer.xts.y_span)
                    .align().by("zmin", p)).cleanup()).tr.rx(math.radians(90))\
            .align().by("ymaxzmin", enclosure_outer)\
            .align().by("xmid", extrusion.explore.solid.order_by(lambda p: p.xts.x_mid).get()[0])\
            .tr.mv(dz=3)\
            .do_and_add(lambda p: p.tr.mv(dz=2 * abs(enclosure_outer.xts.z_mid - p.xts.z_mid)))\
            .do_and_add(lambda p: p.tr.mv(dx=2 * abs(enclosure_outer.xts.x_mid - p.xts.x_mid)))

        enclosure_outer = enclosure_outer.bool.cut(posts)

        enclosure_outer = enclosure_outer.bool.cut(
            factory.box_surrounding(board.sp("terminals"))
            .tr.scale_to_y_span(enclosure_outer.xts.y_span)
            .align().by("ymin", board.sp("terminals")).extrude.make_thick_solid(1))

        enclosure_outer = enclosure_outer.bool.cut(
            *[s.extrude.make_thick_solid(Constants.clearance_mm()) for s in extrusion.explore.solid.get()])

        enclosure_bottom, enclosure_top = enclosure_outer.explore.solid.order_by(lambda s: s.xts.y_mid).get()

        bottom_vent_face = enclosure_bottom.pick.from_dir(0, -1, 0).first_face().extrude.offset(-2).make.face()

        vents = factory.hex_lattice(12, 3,
                            hex_radius=5,
                            grid_radius=5.5,
                            truncate_odd_rows=True,
                            cube_hex_line_thickness=1,
                            cube_hex_effect_a=True, cube_hex_effect_b=True).tr.rx(math.radians(90))\
            .align().by("xmidymaxzmid", bottom_vent_face).bool.common(bottom_vent_face).extrude.prism(dy=-10)

        enclosure_bottom = enclosure_bottom.bool.cut(vents)

        enclosure_top = enclosure_top.bool.cut(board.sp("stepper_plug")
                                               .tr.scale_to_y_span(enclosure_top.xts.y_span)
                                               .extrude.make_thick_solid(3).align().by("ymid", enclosure_top))

        top_face: Part = enclosure_top.pick.from_dir(0, -1, 0).first_face()
        top_face_wires = top_face.explore.wire.get()

        print("Called")
        offsets = [
            f.extrude.offset(2).make.face().cleanup() for f in top_face_wires[1:]]

        top_vent_face = top_face_wires[0].extrude.offset(-3)\
            .make.face()\
            .cleanup().do(lambda p: p.bool.common(
                factory.box_surrounding(p, 1, 1, 1)
                    .tr.scale_to_z_span(p.xts.z_span - 10).align().by("zmid", p))).bool.cut(*offsets)

        vents = factory.hex_lattice(14, 5,
                                    hex_radius=5,
                                    grid_radius=5.5,
                                    truncate_odd_rows=True,
                                    cube_hex_line_thickness=1,
                                    cube_hex_effect_a=True,
                                    cube_hex_effect_b=True).tr.rx(math.radians(90)) \
            .align().by("xmidymaxzmid", top_vent_face).bool.common(top_vent_face).extrude.prism(dy=-10)

        enclosure_top = enclosure_top.bool.cut(vents)

        return factory.compound(
            board.name("board"),
            enclosure_top.name("enclosure_top"),
            enclosure_bottom.name("enclosure_bottom")).align().stack_z0(cradle_connectors, offset=-10)

    token = token.mutated(inspect.getsource(_stepper_enclosure))

    stepper_enclosure = cache.ensure_exists(token, lambda: _stepper_enclosure().with_cache_token(token))

    stepper_enclosure.save.stl_solids("/wsp/output/stepper_enclosure")
    #extrusions_and_stepper_mount.sp("stepper_mount").save.single_stl("/wsp/output/stepper_mount")

    #phone_cradle.sp("cradle").save.single_stl("/wsp/output/phone_cradle")

    gearbox_and_stepper.sp("gearbox", "ring_extents")\
        .preview(phone_cradle,
                 gearbox_and_stepper.sp("stepper"),
                 extrusions_and_stepper_mount,
                 cradle_connectors,
                 stepper_enclosure)

    #ring.sp("ring_extents").preview(stepper)

    #ring.save.single_stl("/wsp/output/planetary_gearset").preview()

    #phone_mount = WireSketcher()

    #motor.preview(phone, ring)