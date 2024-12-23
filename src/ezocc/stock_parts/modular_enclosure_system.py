import inspect
import logging
import math

import OCC.Core.GeomAbs
from OCC.Core.gp import gp_Dir

from ezocc.alg.math import lerp
from ezocc.alg.offset_face_with_holes import offset_face_with_holes
from ezocc.constants import Constants
from ezocc.occutils_python import WireSketcher, InterrogateUtils, MathUtils
from ezocc.part_cache import FileBasedPartCache, InMemoryPartCache
from ezocc.part_manager import PartCache, Part, PartFactory
from ezocc.precision import Compare
from ezocc.stock_parts.misc import StockParts


class ModularEnclosureFactory:

    # gap between two neighboring units, sitting "flush"
    ADJACENT_UNIT_GAP = Constants.clearance_mm() / 2

    # todo: Parameterize
    WALL_THICKNESS = 0.4 * 5

    def __init__(self, cache: PartCache):
        self._cache = cache

    def _make_base_dovetail_unit(self,
                                 x_unit_length: float,
                                 y_unit_length: float,
                                 z_unit_length: float, z_units: int) -> Part:

        token = self._cache.create_token(
            z_units,
            x_unit_length,
            y_unit_length,
            z_unit_length,
            inspect.getsource(ModularEnclosureFactory))

        z_length = z_units * z_unit_length

        def _do():
            factory = PartFactory(self._cache)

            dovetail = factory.box(25, 25, z_length - 10).fillet.chamfer_edges(7, lambda e: InterrogateUtils.is_dz_line(e))
            dovetail = ((dovetail.bool.cut(*factory.cylinder(4, dovetail.xts.z_span + 1)
                                         .array.on_verts_of(
                                                factory.box_surrounding(dovetail).pick.from_dir(0, 0, -1).first_face().extrude.offset(-5))
                                         .align().by("zmid", dovetail)
                                         .explore.solid.get())
                        .cleanup()
                        .explore.solid.get_max(lambda s: InterrogateUtils.volume_properties(s.shape).Mass())))

            dovetail = dovetail.fillet.fillet_edges(0.25, {
                *dovetail.explore.edge.filter_by(lambda e: InterrogateUtils.is_dz_line(e.shape)).get()
            }).cleanup()

            dovetail = factory.compound(
                dovetail.name("dovetail"),
                factory.cylinder(2.8 / 2, z_length)
                    .do(lambda p: p.name_recurse("mount_point"))
                    .do(lambda p: p.bool.union(
                        factory.cylinder(3, 3).align().by("zmax", p).do(lambda pp: pp.bool.cut(
                        factory.box_surrounding(pp).align().stack_z0(pp).tr.mv(dz=0.4).align().by("xminmid", pp).tr.mv(
                            dx=p.xts.x_span / 2).do_and_add(lambda ppp: ppp.mirror.x(center_x=pp.xts.x_mid))))
                    ))
                    .align().by("xminymidzmin", dovetail).tr.mv(dx=1).pattern(range(0, 4), lambda i, p: p.tr.rz(math.radians(90 * i), offset=dovetail.xts.xyz_mid))
                    .name("mounts")
            ).tr.rz(math.radians(45))

            dovetail = dovetail.tr.rz(math.radians(45))
            dovetail = (dovetail.do_on(
                "dovetail",
                consumer=lambda p: p.bool.cut(
                    factory.box_surrounding(p, z_length=0.4).align().by("zmax", p).bool.cut(*
                        factory.box(dovetail.xts.y_span, 2.8, 0.4)
                        .align().by("xmidymid", dovetail.compound_subpart("mounts").explore.solid.get_min(lambda s: s.xts.y_mid))
                        .align().by("zminmax", p).tr.mv(dz=-0.4)
                        .pattern(range(0, 4), lambda i, pp: pp.tr.rz(math.radians(90 * i), offset=p.xts.xyz_mid))
                        .explore.solid.get()
                    )))
                .tr.rz(math.radians(45)))

            nuts = (factory.polygon(1, 6)
                   .driver(PartFactory.PolygonDriver).set_flat_to_flat_dist(5.5)
                   .do_on("body", consumer=lambda p: p.make.face().extrude.prism(dz=2.5))
                   .do(lambda p: factory.compound(*[p.tr.rz(math.atan2(s.xts.x_mid - dovetail.xts.x_mid, s.xts.y_mid - dovetail.xts.y_mid))
                                                  .align("center").by("xmidymidzmin", s)
                                                    for s in dovetail.compound_subpart("mounts").explore.solid.get()]))
                    .align().by("zmidmax", dovetail.sp("dovetail")).tr.mv(dz=-dovetail.sp("dovetail").xts.z_span / 4))

            dovetail_inner = (dovetail.sp("dovetail").alg.project_z().alg.edge_network_to_outer_wire()
                              .align().by("zmax", dovetail).make.face()
                              .extrude.offset(-Constants.clearance_mm() / 2)
                              .make.face()
                              .align().by("zmin", dovetail.sp("dovetail"))
                              .extrude.prism(dz=dovetail.sp("dovetail").xts.z_span)
                              .bool.cut(*dovetail.compound_subpart("mounts").explore.solid.get(), *nuts.explore.solid.get()))

            # provide some clearance so the dovetail does not stick out of the bottom
            dovetail_inner = dovetail_inner.bool.common(
                factory.box_surrounding(dovetail_inner, z_length=dovetail_inner.xts.z_span - 2).align().by("zmax", dovetail_inner))

            dovetail_inner_half = (dovetail_inner.bool.cut(factory.box_surrounding(dovetail_inner, z_clearance=1).align().by("ymaxmid", dovetail_inner)))
            dovetail_inner_quarter = dovetail_inner_half.bool.cut(factory.box_surrounding(dovetail_inner_half, z_clearance=1).align().by("xmaxmid", dovetail_inner_half))

            vertical_dovetail = (dovetail_inner_quarter.tr.rz(math.radians(45))
                                 .do(lambda p: p.bool.cut(WireSketcher(p.xts.x_min, p.xts.y_max + Constants.clearance_mm() / 2, p.xts.z_min - Constants.clearance_mm() / 2)
                                                          #.line_to(y=lerp(p.xts.y_min, p.xts.y_max, 2.5/3))
                                                          .line_to(z=lerp(p.xts.z_min, p.xts.z_max, 1.0/4))
                                                          .line_to(y=lerp(p.xts.y_min, p.xts.y_max, 1.2/3))
                                                          .line_to(z=p.xts.z_max + Constants.clearance_mm() / 2)
                                                          .line_to(y=p.xts.y_min)
                                                          .get_wire_part(self._cache)
                                                          .extrude.offset(Constants.clearance_mm() / 2)
                                                          .make.face()
                                                          .extrude.prism(dx=p.xts.x_span)))
                                 .do(lambda p: p.bool.cut(
                                    factory.cylinder(3, 3)
                                    .align().by("xmidymid", p.compound_subpart("mount_point"))
                                    .align().by("zmin", p)
                                    .tr.mv(dz=p.xts.z_span / 4)))
                                 .do(lambda p: p.bool.cut(
                                    factory.cylinder(2.8 / 2, p.xts.y_span)
                                    .tr.rx(math.radians(-90))
                                    .align().by("xmidyminzmid", p).tr.mv(dz=p.xts.z_span / 4))))

            return factory.compound(
                dovetail.name("dovetail_clearance"),
                dovetail_inner.name("dovetail_1"),
                dovetail_inner_half.name("dovetail_0.5"),
                dovetail_inner_quarter.name("dovetail_0.25"),
                vertical_dovetail.name("dovetail_0.25_two_part")
            ).with_cache_token(token)

        return self._cache.ensure_exists(token, _do)

    def _make_dovetail_clearance_cuts(self,
                                        x_units: int,
                                        y_units: int,
                                        z_units: int,
                                        dovetail_alignment_face: Part,
                                        dovetail: Part):

        token = self._cache.create_token(
            inspect.getsource(ModularEnclosureFactory._make_dovetail_clearance_cuts),
            x_units,
            y_units,
            z_units,
            dovetail_alignment_face,
            dovetail)

        def _do():
            clearance = dovetail.sp("dovetail_clearance")

            corner_dovetails = (clearance.array.on_verts_of(dovetail_alignment_face)
                                .align().by("xmidymid", dovetail_alignment_face)
                                .align().by("zmin", clearance))
            if x_units > 1:
                x_dovetails = [(clearance.pattern(range(0, x_units - 1), lambda i, p: p.tr.mv(
                    dx=i * (dovetail_alignment_face.xts.x_span / (x_units))))
                                .align().by("xmidyminzmin", corner_dovetails)
                                .do_and_add(lambda p: p.mirror.y(center_y=dovetail_alignment_face.xts.y_mid)))]
            else:
                x_dovetails = []

            if y_units > 1:
                y_dovetails = [(clearance.pattern(range(0, y_units - 1), lambda i, p: p.tr.mv(
                    dy=i * (dovetail_alignment_face.xts.y_span / (y_units))))
                                .align().by("xminymidzmin", corner_dovetails)
                                .do_and_add(lambda p: p.mirror.x(center_x=dovetail_alignment_face.xts.x_mid)))]
            else:
                y_dovetails = []

            return PartFactory(self._cache).compound(
                corner_dovetails,
                *x_dovetails,
                *y_dovetails).with_cache_token(token)

        return self._cache.ensure_exists(token, _do)

    def _make_shadow_line(self, box: Part, clearance_cuts: Part) -> Part:
        token = self._cache.create_token(inspect.getsource(ModularEnclosureFactory), box, clearance_cuts)

        def _do():
            lid_profile = (box.explore.face.get_max(lambda f: f.xts.z_mid)
                           .extrude.offset(-ModularEnclosureFactory.WALL_THICKNESS).make.face()
                           .align().stack_z1(clearance_cuts.compound_subpart("dovetail"))
                           .tr.mv(dz=ModularEnclosureFactory.WALL_THICKNESS))

            lid_shadow_line = (WireSketcher()
                               .line_to(x=ModularEnclosureFactory.WALL_THICKNESS / 2, is_relative=True)
                               .line_to(z=ModularEnclosureFactory.WALL_THICKNESS, is_relative=True)
                               .line_to(x=ModularEnclosureFactory.WALL_THICKNESS / 2, is_relative=True)
                               .get_wire_part(self._cache)
                               .align().by("xmaxminymidzmax", lid_profile)
                               .extrude.offset(Constants.clearance_mm() / 2)
                               .loft.pipe(lid_profile.explore.wire.get_single())
                               .tr.mv(dz=Constants.clearance_mm() / 2))

            lid_profile = (lid_profile.extrude.prism(dz=Constants.clearance_mm())
                           .bool.union(lid_shadow_line).cleanup())

            return lid_profile.with_cache_token(token)

        return self._cache.ensure_exists(token, _do)


    def _cut_slots(self,
                   result_top: Part,
                   result_bottom: Part,
                   dovetail_alignment_face: Part,
                   x_slot_unit_length: int,
                   y_slot_unit_length: int) -> Part:

        token = self._cache.create_token(
            inspect.getsource(ModularEnclosureFactory),
            result_top, result_bottom,
            dovetail_alignment_face,
            x_slot_unit_length,
            y_slot_unit_length)

        def _do():
            slots = (PartFactory(self._cache).box(
                2 * (ModularEnclosureFactory.WALL_THICKNESS + Constants.clearance_mm()),
                2 * (ModularEnclosureFactory.WALL_THICKNESS + Constants.clearance_mm()),
                result_top.xts.z_span)
                     .align().by("xmidminymidmin", dovetail_alignment_face)
                     .align().by("zmax", result_bottom).tr.mv(dz=Constants.clearance_mm())
                     .pattern(range(0, 2 + int(float(result_top.xts.x_span) / x_slot_unit_length)),
                              lambda i, p: p.tr.mv(dx=i * x_slot_unit_length))
                     .pattern(range(0, 2 + int(float(result_top.xts.y_span) / y_slot_unit_length)),
                              lambda i, p: p.tr.mv(dy=i * y_slot_unit_length)))

            _result = result_top.bool.cut(*slots.explore.solid.get())
            _result = _result.bool.cut(*slots.mirror.x(center_x=result_top.xts.x_mid).explore.solid.get())
            _result = _result.bool.cut(*slots.mirror.y(center_y=result_top.xts.y_mid).explore.solid.get())

            return _result.with_cache_token(token)

        return self._cache.ensure_exists(token, _do)

    def _make_cap_bridge(self, clearance_cuts: Part, result_top: Part, result_bottom: Part, dovetail_alignment_face: Part):
        factory = PartFactory(self._cache)

        token = self._cache.create_token(inspect.getsource(ModularEnclosureFactory._make_cap_bridge),
                                         clearance_cuts,
                                         result_top,
                                         result_bottom,
                                         dovetail_alignment_face)

        def _do():
            cap_mount_point = (clearance_cuts.compound_subpart("mounts")
                               .explore.solid
                               .filter_by(lambda s: result_top.xts.x_min < s.xts.x_mid < result_top.xts.x_max and
                                                    result_top.xts.y_min < s.xts.y_mid < result_top.xts.y_max)
                               .get_max(lambda s: s.xts.x_mid + s.xts.y_mid))

            return (factory.cylinder(4, abs(result_top.xts.z_min - result_bottom.xts.z_max))
                          .align().by("xmidymid", cap_mount_point)
                          .align().by("zmin", result_top)
                          .do(lambda p: p.bool.cut(factory.box_surrounding(p).align().by("yminmid", p)))
                          .do(lambda p: p.bool.union(p.pick.from_dir(0, -1, 0).first_face().extrude.prism(
                dy=abs(p.xts.y_max - dovetail_alignment_face.xts.y_max))))
                          .cleanup()
                          .do(lambda p: p.bool.union(p.pick.from_dir(0, 0, 1).first_face().extrude.prism(dz=-5)))
                          .do(lambda p: p.bool.cut(factory.box_surrounding(p, 1, 1, 0).bool.common(result_top)
                                                   .extrude.make_thick_solid(Constants.clearance_mm() / 2)))
                          .bool.cut(cap_mount_point)
                          .do(lambda p: p.bool.union(p.mirror.y(center_y=p.xts.y_max)))
                    .with_cache_token(token))

        return self._cache.ensure_exists(token, _do)

    def make_unit(self,
                  x_units: int,
                  y_units: int,
                  z_units: int,
                  x_unit_length: float = 32,
                  y_unit_length: float = 32,
                  z_unit_length: float = 32,
                  x_slot_unit_length=32,
                  y_slot_unit_length=32) -> Part:

        dovetail = self._make_base_dovetail_unit(x_unit_length, y_unit_length, z_unit_length, z_units)

        token = self._cache.create_token(
            x_units,
            y_units,
            z_units,
            x_unit_length,
            y_unit_length,
            z_unit_length,
            x_slot_unit_length,
            y_slot_unit_length,
            inspect.getsource(ModularEnclosureFactory.make_unit))

        def _do():
            factory = PartFactory(self._cache)

            result = factory.box(dx=x_unit_length * x_units - 2 * ModularEnclosureFactory.ADJACENT_UNIT_GAP,
                                 dy=y_unit_length * y_units - 2 * ModularEnclosureFactory.ADJACENT_UNIT_GAP,
                                 dz=z_unit_length * z_units - 2 * ModularEnclosureFactory.ADJACENT_UNIT_GAP)


            # create a face for the purposes of aligning the dovetails, with the necessary
            dovetail_alignment_face = (factory.square_centered(
                result.xts.x_span + ModularEnclosureFactory.ADJACENT_UNIT_GAP,
                result.xts.y_span + ModularEnclosureFactory.ADJACENT_UNIT_GAP)
                                       .align().by("xmidymidzmin", result))


            clearance_cuts = self._make_dovetail_clearance_cuts(x_units, y_units, z_units, dovetail_alignment_face, dovetail)

            #result.preview(clearance_cuts)

            result = result.bool.cut(
                *clearance_cuts.compound_subpart("dovetail").explore.solid.get())

            #result.preview()

            interior = (result.explore.face.get_min(lambda f: f.xts.z_mid).extrude.offset(-ModularEnclosureFactory.WALL_THICKNESS)
                        .explore.wire.get_min(lambda w: math.hypot(w.xts.x_mid - result.xts.x_mid, w.xts.y_mid - result.xts.y_mid))
                        .make.face().extrude.offset(-ModularEnclosureFactory.WALL_THICKNESS)
                        .explore.wire.get_min(lambda w: math.hypot(w.xts.x_mid - result.xts.x_mid, w.xts.y_mid - result.xts.y_mid))
                        .extrude.offset(ModularEnclosureFactory.WALL_THICKNESS).make.face())

            result = result.bool.cut(
                interior.tr.mv(dz=ModularEnclosureFactory.WALL_THICKNESS)
                .do(lambda p: p.extrude.prism(dz=abs(p.xts.z_min - result.xts.z_max) - ModularEnclosureFactory.WALL_THICKNESS)))

            #result.preview()

            interior = (result.explore.face.get_max(lambda f: f.xts.z_mid)
                        .tr.mv(dz=-ModularEnclosureFactory.WALL_THICKNESS)
                        .do(lambda p: p.bool.cut(clearance_cuts.compound_subpart("mounts").align().by("zmax", p)))
                        .do(lambda p: offset_face_with_holes(p, -ModularEnclosureFactory.WALL_THICKNESS)
                        .do(lambda p:
                            p.explore.wire.get_min(lambda w: math.hypot(w.xts.x_mid - result.xts.x_mid, w.xts.y_mid - result.xts.y_mid))
                                if not p.inspect.is_face() else p)).make.face())


            result = result.bool.cut(interior.extrude.prism(dz=-abs(dovetail.compound_subpart("dovetail").xts.z_max - interior.xts.z_max) + ModularEnclosureFactory.WALL_THICKNESS))

            #result.preview()

            result = result.cleanup()

            result = result.bool.cut(self._make_shadow_line(result, clearance_cuts)).cleanup()

            result = result.bool.cut(*clearance_cuts.compound_subpart("mounts").explore.solid.get()).cleanup()

            result = result.bool.common(factory.box_surrounding(result).fillet.fillet_edges(0.5))

            result_bottom, result_top = (result.explore.solid.order_by(lambda s: s.xts.z_mid))

            result_bottom = result_bottom.bool.common(factory.box_surrounding(result_bottom)
                                                      .fillet.chamfer_edges(7, lambda e: InterrogateUtils.is_dz_line(e))
                                                      .cleanup())

            cap_bridge = self._make_cap_bridge(clearance_cuts, result_top, result_bottom, dovetail_alignment_face)

            result_top = self._cut_slots(
                result_top, result_bottom, dovetail_alignment_face, x_slot_unit_length, y_slot_unit_length)

            return factory.compound(
                result_top.name("top"),
                result_bottom.name("bottom"),
                dovetail.remove_sp_named("dovetail_clearance").name("dovetail"),
                cap_bridge.name("cap_bridge")
            ).with_cache_token(token)

        return self._cache.ensure_exists(token, _do)
