import inspect
import logging
import math
import typing

import OCC.Core.TopAbs
import OCC.Core.gp as gp
import OCC.Core.BRepBuilderAPI
import OCC.Core.GeomAbs
from OCC.Core import Precision
from OCC.Core.gp import gp_Vec as vec

import ezocc.occutils_python as op
from ezocc.constants import Constants
from ezocc.part_manager import Part, PartFactory, CacheToken, PartCache, NoOpCacheToken, PartDriver
from ezocc.occutils_python import WireSketcher

logger = logging.getLogger(__name__)


class StepperDriver(PartDriver):

    def __init__(self, part: Part):
        super().__init__(part)

    def get_rendered_part(self) -> Part:
        return self.part.sp("body").add(self.part.sp("shaft"))


class StockParts:

    def __init__(self, part_cache: PartCache):
        self._part_cache = part_cache
        self._factory = PartFactory(self._part_cache)

    def pir_module(self):
        factory = self._factory
        token = self._part_cache.create_token(inspect.getsource(StockParts), "pir_module")

        def _do():
            board = factory.box(32.5, 24, 1.5)

            dome_rad = 22.3 / 2

            dome = factory.sphere(dome_rad).do(lambda p: p.bool.cut(
                factory.box_surrounding(p).align().by("zmaxmid", p)
                ).cleanup(concat_b_splines=True, fix_small_face=True))

            dome = (dome.bool.union(factory.box(dome_rad * 2, dome_rad * 2, 3).align().by("xmidymidzmaxmin", dome))
                    .cleanup(concat_b_splines=True, fix_small_face=True))

            cap = factory.cylinder(2, 9).align().stack_z0(board)

            jumper = factory.box(2.5, 8, 2).align().stack_z0(board)
            jumper = jumper.bool.union(factory.box(0.5, 0.5, 8.5)
                                       .incremental_pattern(range(0, 2), lambda p: p.tr.mv(dy=jumper.xts.y_span / 3))
                                       .align().by("xmidymidzmax", jumper))

            pot = (factory.cylinder(4.5 / 2, 1.5)
                   .do(lambda p: p.bool.cut(*
                        factory.box(1, 3, 1).align().by("xmidymidzmax", p)
                        .do_and_add(lambda p: p.tr.rz(math.radians(90)))
                        .explore.solid.get()))
                   .do(lambda p: p.bool.union(
                        factory.box_surrounding(p, z_length=5 - p.xts.z_span)
                            .align().by("xmidymidzmaxmin", p)))
                   .cleanup())

            pot = pot.tr.rx(math.radians(90)).do_and_add(lambda p: p.align().stack_x1(p).tr.mv(dx=1))

            mount_holes = (factory.cylinder(2.5 / 2, board.xts.z_span)
                           .do_and_add(lambda p: p.tr.mv(dx=29))
                           .align().by("xmidymidzmid", board)
                           .name_recurse("mount", lambda s: Part.of_shape(s).inspect.is_face()))

            board = board.bool.cut(mount_holes).cleanup()

            return factory.compound(
                dome.align().by("xmidymidzminmax", board).name("dome"),
                factory.compound(
                    board,
                    jumper.align().by("xmaxymin", board),
                    jumper.tr.rz(math.radians(90)).align().by("xmidymax", board),
                    cap.align().by("xmaxymax", board),
                    cap.align().by("xminymax", board),
                    cap.align().by("xmaxymin", board).tr.mv(dx=-5),
                    cap.align().by("xminymin", board),
                    pot.align().by("xmidyminzmaxmin", board)
                ).name("board"),
            ).with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def aviation_connector(self):

        token = self._part_cache.create_token(inspect.getsource(StockParts.aviation_connector))

        def _do():

            aviation_connector = (self._factory.cylinder(12 / 2, 9).name("barrel")
                                  .do(lambda p: p.add(
                self._factory.cylinder(15 / 2, 2).name_recurse("connector_flange")
                .align().by("xmidymidzminmax", p)))
                                  .do(lambda p: p.add(
                self._factory.ring(13 / 2, 13 / 2 - 2.5, 5).name_recurse("connector")
                .align().by("xmidymidzminmax", p))))

            aviation_connector = aviation_connector.add(
                self._factory.cylinder(1.5 / 2, 20).array.on_verts_of(self._factory.polygon(2.5, 5))
                .align().by("xmidymidzmax", aviation_connector))

            aviation_connector = aviation_connector.add(self._factory.polygon(1, 6)
                                                        .driver(PartFactory.PolygonDriver)
                                                        .set_flat_to_flat_dist(14)
                                                        .do_on("body",
                                                               consumer=lambda p: p.make.face().extrude.prism(dz=3.5))
                                                        .align("center").by("xmidymid", aviation_connector.compound_subpart(
                                                            "connector_flange"))
                                                        .align("body").by("zmaxmin", aviation_connector.compound_subpart(
                                                            "connector_flange"))
                                                        .tr.mv(dz=-2)
                                                        .sp("body")
                                                        .name("nut"))

            return aviation_connector.with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def led(self):
        token = self._part_cache.create_token(inspect.getsource(StockParts), "led")

        def _do():
            body = self._factory.cylinder(4.64 / 2, 6.2)
            base = self._factory.cylinder(5.5 / 2, 1)

            dome_height = 1
            dome_rad = body.xts.x_span / 2

            sphere_rad = (dome_rad * dome_rad + dome_height * dome_height) / (2 * dome_height)

            angle = math.acos((sphere_rad - dome_height) / sphere_rad)
            arc = (self._factory.circle_arc(sphere_rad, 0, angle)
                   .tr.ry(math.radians(-90))
                   .tr.rz(math.radians(90))
                   .align().by("xmaxmidymidzminmax", body)
                   .revol.about(gp.gp.OZ(), math.radians(360), offset=body.xts.xyz_mid)
                   .cleanup().tr.rz(math.radians(180), offset=body.xts.xyz_mid))

            body = (self._factory.union(
                *[f for f in body.explore.face.order_by(lambda f: -f.xts.z_mid).get()[1:]],
                arc.make.face())
                    .make.shell()
                    .make.solid().cleanup.fix_solid()).cleanup(concat_b_splines=True, fix_small_face=True)

            base = base.align().by("xmidymidzmaxmin", body)

            leg_w = 0.5

            leg_pos = self._factory.box(leg_w, leg_w, 20)
            leg_neg = self._factory.box(leg_w, leg_w, 17)

            legs = (leg_pos.add(leg_neg.align().by("zmax", leg_pos).tr.mv(dx=3))
                    .align().by("xmidymidzmaxmin", base))

            return self._factory.compound(
                body.name("body"),
                base.name("base"),
                legs.name("legs")
            ).with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def knob(self,
             shaft_od: float,
             shaft_height: float,
             knob_od: float,
             knob_height: float,
             knurl_size: float = 1,
             knurl_turns: typing.Optional[float] = None,
             knurl_count: int = 16) -> Part:
        if shaft_od > knob_od:
            raise ValueError("Knob will be inside shaft")

        if knob_height < shaft_height:
            raise ValueError("Shaft will poke through knob")

        knob = self._factory.cylinder(knob_od / 2, knob_height, top_wire_name="top", bottom_wire_name="bottom")\
            .do(lambda p: p.fillet.chamfer_edges(2, p.explore.edge.get_max(lambda e: e.extents.z_mid)))\
            .do(lambda p: p.fillet.chamfer_edges(1, p.explore.edge.get_min(lambda e: e.extents.z_mid)))

        shaft = self._factory.cylinder(shaft_od / 2, shaft_height)\
            .do(lambda p: p.bool.cut(self._factory.box_surrounding(p, 1, 1, 1)
                .align().x_max_to_max(p)
                .transform.translate(dx=-5)))\
            .extrude.make_thick_solid(Constants.clearance_mm(), []).make.solid()

        knurl: Part = self._factory.square_centered(knurl_size, knurl_size).explore.wire.get()[0]\
            .transform.rotate(gp.gp.OY(), math.pi / 2)\
            .transform.rotate(gp.gp.OX(), math.pi / 4)\
            .align().stack_z0(knob)\
            .align().y_mid_to_min(knob)\
            .transform.translate(dy=-0.01)

        if knurl_turns is None:
            knurl_turns = 2 * math.pi / knob_height

        helix_ccw: Part = self._factory.helix(knob_height * 2, knob_od / 2, knurl_turns * 2).transform.rotate(gp.gp.OZ(), -math.pi / 2)

        helix_cw: Part = helix_ccw.mirror.x()

        knurl_cw = knurl.loft.pipe(helix_cw, bi_normal_mode=gp.gp.DZ())
        knurl_ccw = knurl.loft.pipe(helix_ccw, bi_normal_mode=gp.gp.DZ())

        knurls_cw = knurl_cw.pattern(range(0, knurl_count),
                                     lambda i, p: p.transform.rotate(gp.gp.OZ(), i * 2 * math.pi / knurl_count))

        knob = knob.bool.cut(knurls_cw).cleanup()

        knurls_ccw = knurl_ccw.pattern(range(0, knurl_count),
                                       lambda i, p: p.transform.rotate(gp.gp.OZ(), i * 2 * math.pi / knurl_count))

        knob = knob.bool.cut(knurls_ccw).cleanup()

        return knob.bool.cut(shaft).cleanup()

    def switch_momentary(self, button_height: float, body_height=3.5) -> Part:
        result = self._factory.square_centered(dx=6, dy=6)\
            .extrude.prism(dz=body_height, last_shape_name="switch_face")

        pole = self._factory.square_centered(6.5, 1).extrude.prism(dz=1)

        result = result.bool.union(
            pole.align().y_max_to_max(result),
            pole.align().y_min_to_min(result)).cleanup()

        knob = self._factory.loft([
            Part.of_shape(op.GeomUtils.circle_wire(3.5 / 2)),
            Part.of_shape(op.TransformUtils.translate(op.GeomUtils.circle_wire(3 / 2), vec(0, 0, button_height)))
        ], loft_profile_name="knob_surround")

        knob = knob.align()\
            .xy_mid_to_mid(result)\
            .align()\
            .z_min_to_max(result)

        result = result.bool.union(knob).cleanup().fillet.fillet_by_name(0.3, "knob_surround")

        ext = op.Extents(result.shape)
        p = Constants.perfboard_pitch()

        return result\
            .add(self._factory.vertex(-p, -p, ext.z_min, name="P0_0"))\
            .add(self._factory.vertex(p, -p, ext.z_min, name="P1_0"))\
            .add(self._factory.vertex(-p, p, ext.z_min, name="P0_1"))\
            .add(self._factory.vertex(p, p, ext.z_min, name="P1_1"))

    def perfboard_50x70(self, **kwargs) -> Part:
        return self.perfboard(50, 70, 18, 24, **kwargs)

    def arduino_micro(self, add_legs: bool = True) -> Part:
        result = self._factory.square_centered(18, 48).extrude.prism(0, 0, -1.5).name("board")

        pin_template: Part = self._factory.cylinder(0.5, 2 + 1.5, top_wire_name="top_wire") \
            .fillet.fillet_by_name(0.2, "top_wire").align().z_min_to_min(result)

        if add_legs:
            pin_template = pin_template.bool.union(
                self._factory.square_centered(0.6, 0.6)
                    .align().xy_mid_to_mid(pin_template)
                    .align().z_max_to_min(result)
                    .extrude.prism(0, 0, -9.5)).cleanup()

        lpins = pin_template.pattern(
            range(0, 17),
            lambda i, p: p.transform.translate(0, i * Constants.perfboard_pitch(), 0).name(f"pin_{16 - i}"))
        rpins = pin_template.transform.translate(6 * Constants.perfboard_pitch()).pattern(
            range(0, 17),
            lambda i, p: p.transform.translate(0, i * Constants.perfboard_pitch(), 0).name(f"pin_{i + 17}"))

        pins = lpins.add(rpins).align().xy_mid_to_mid(result)

        switch = StockParts.switch_momentary(1, body_height=2).align().y_max_to_max(result)

        chip = self._factory.square_centered(7, 7)\
            .transform.rotate(gp.gp.OZ(), math.pi / 4)\
            .align().x_mid_to_mid(result)\
            .extrude.prism(0, 0, 1)

        usb_connector = self.usb_micro_connector()\
            .align().y_min_to_min(result)\
            .transform.translate(0, 1, 0)

        return result.add(pins, switch, chip, usb_connector)

    def usb_micro_connector(self):
        usb_connector = op.WireSketcher()\
            .line_to(x=6.9 / 2, is_relative=True)\
            .line_to(z=-1.5, is_relative=True)\
            .line_to(x=-1.5, z=-1.5, is_relative=True)\
            .line_to(x=0)\
            .close().get_face_part(self._part_cache)

        usb_connector = usb_connector.bool.union(usb_connector.transform(lambda t: t.SetMirror(gp.gp.YOZ()))) \
            .sew.faces().cleanup()\
            .extrude.prism(0, 5.5, 0) \
            .do(lambda p: p.fillet.fillet_edges(0.5, {e for e in p.pick.from_dir(0, 0, -1).first_face().explore.edge.get() if
                                                      op.InterrogateUtils.is_dy_line(e.shape)}))\
            .cleanup()

        return usb_connector

    def esp32(self):
        token = self._part_cache.create_token("stock_parts" "make_esp32", inspect.getsource(self.esp32))

        def _do():
            factory = PartFactory(self._part_cache)
            stock_parts = StockParts(self._part_cache)

            board = factory.box(28, 55, 1.5)
            board = board.bool.cut(factory.cylinder(2.5 / 2, board.xts.z_span)
                                   .align().by("xminyminzmid", board).tr.mv(dx=0.7, dy=0.7)
                                   .do_and_add(lambda p: p.mirror.x(center_x=board.xts.x_mid))
                                   .do_and_add(lambda p: p.mirror.y(center_y=board.xts.y_mid)))

            leg = factory.box(0.5, 0.5, 8.5)
            leg = leg.bool.union(factory.box(2.5, 2.5, 3).align().by("xmidymidzmax", leg))

            legs = leg.pattern(range(0, 19), lambda i, p: p.tr.mv(dy=i * Constants.perfboard_pitch()))
            legs = legs.align().by("xmaxymidzmaxmin", board) \
                .do_and_add(lambda p: p.align().by("xmin", board))

            can = factory.box(16, 18, 3).align().by("xmidyminzminmax", board).tr.mv(dy=7)

            usb_mini_connector = stock_parts.usb_micro_connector() \
                .align().by("xmidymaxzminmax", board) \
                .tr.mv(dy=0.5)

            antenna = factory.box(18.5, 5.8, 1).align().by("xmidymaxminzmin", can)

            return self._factory.compound(
                board.name("board"),
                legs.name("legs"), can.name("can"), usb_mini_connector, antenna).with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def perfboard(self,
                  dx: float, dy: float, cols: int, rows: int,
                  include_z: bool = True,
                  include_holes: bool = True,
                  include_mount_points: bool = True) -> Part:
        result = Part(op.GeomUtils.square_centered(side_length_0=dx, side_length_1=dy).get_face())
        hole_face = op.GeomUtils.circle_face(0.5)
        hole_part = Part(hole_face, {
            "hole_edge": [op.Explorer.edge_explorer(hole_face).get_single()]
        })

        holes = None

        for col in range(0, cols):
            for row in range(0, rows):
                coord = (col * Constants.perfboard_pitch(), row * Constants.perfboard_pitch(), 0)

                if include_holes:
                    hole = hole_part.rename_subshape("hole_edge", f"{col}_{row}")\
                        .align().xy_min_to_min(result.shape)\
                        .transform.translate(*coord)

                    if holes is None:
                        holes = hole
                    else:
                        holes = holes.add(hole)

        if holes is not None:
            holes = holes.align().xy_mid_to_mid(result)

            result = result.bool.cut(holes)

        if include_z:
            result = result.extrude.prism(0, 0, -1.5)

        if include_mount_points:
            mount_holes = self._factory.circle(2.5 / 2).make.face()\
                .do_and_add(lambda p: p.transform.translate(dx=46))\
                .do_and_add(lambda p: p.transform.translate(dy=66))\
                .align().z_max_to_max(result)\
                .align().y_mid_to_mid(result)\
                .align().x_min_to_min(result).transform.translate(dx=1)

            result = result.add(mount_holes.name("mount_holes"))

        return result

    def sd_card_micro(self) -> Part:
        chamfer_length = 11 - 9.7

        return WireSketcher()\
            .line_to(x=9.7, is_relative=True)\
            .line_to(y=-6.4 + chamfer_length, is_relative=True)\
            .line_to(x=chamfer_length, y=-chamfer_length, is_relative=True)\
            .line_to(y=-15)\
            .line_to(x=0)\
            .close()\
            .get_face_part(self._part_cache)\
            .extrude.prism(dz=1)

    def raspberry_pi_4(self) -> Part:
        board = self._factory.square_centered(85, 56).fillet.fillet2d_verts(3)
        hole = self._factory.cylinder(radius=2.7/2, height=-1.5)\
            .align().xy_mid_to_min(board)\
            .transform.translate(3.5, 3.5)

        hole_cut = hole.name_recurse("hole_bottom_left", lambda s: s.ShapeType() == OCC.Core.TopAbs.TopAbs_EDGE)\
            .add(hole.transform.translate(dy=49).name_recurse("hole_top_left", lambda s: s.ShapeType() == OCC.Core.TopAbs.TopAbs_EDGE))\
            .add(hole.transform.translate(dx=58, dy=49).name_recurse("hole_top_right", lambda s: s.ShapeType() == OCC.Core.TopAbs.TopAbs_EDGE))\
            .add(hole.transform.translate(dx=58).name_recurse("hole_bottom_right", lambda s: s.ShapeType() == OCC.Core.TopAbs.TopAbs_EDGE))

        hole_cut.compound_subpart("hole_bottom_right")

        board = board.bool.cut(hole_cut)\
            .extrude.prism(dz=-1.5).name("board_circumference")

        gpio_slot = self._factory.square_centered(50, 5)\
            .align().x_mid_to_mid(hole_cut)\
            .align().y_mid_to_max(board)\
            .transform.translate(dy=-3.5)\
            .extrude.prism(dz=8.5)\
            .name("gpio_port")

        ethernet_slot = self._factory.square_centered(dx=17.5, dy=16)\
            .extrude.prism(dz=13.5)\
            .align().z_min_to_max(board)\
            .align().y_mid_to_min(board).transform.translate(dy=45.75)\
            .align().x_max_to_max(board).transform.translate(dx=3)\
            .name("ethernet_port")

        usb_slot = self._factory.square_centered(dx=21.5, dy=15)\
            .extrude.prism(dz=16)\
            .align().z_min_to_max(board)\
            .align().y_mid_to_min(board)\
            .align().x_max_to_max(board).transform.translate(dx=3)

        usb_slot_a = usb_slot.transform.translate(dy=9).name("usb_port_a")
        usb_slot_b = usb_slot.transform.translate(dy=27).name("usb_port_b")

        usbc_port = self._factory.square_centered(dx=9, dy=3)\
            .fillet.fillet2d_verts(1)\
            .transform.rotate(gp.gp.OX(), angle=math.pi / 2)\
            .extrude.prism(dy=7.5)\
            .align().z_min_to_max(board)\
            .align().x_mid_to_min(board).transform.translate(dx=3.5+7.7)\
            .align().y_min_to_min(board).transform.translate(dy=-1.5)\
            .name("usbc_port")

        hdmi_micro_port = self._factory.square_centered(dx=7, dy=7)\
            .extrude.prism(dz=3.0)\
            .align().z_min_to_max(board)\
            .align().x_mid_to_min(board)\
            .align().y_min_to_min(board).transform.translate(dy=-1.5)

        hdmi_micro_port_a = hdmi_micro_port\
            .transform.translate(dx=3.5 + 7.7 + 14.8)\
            .name("hdmi_micro_a")

        hdmi_micro_port_b = hdmi_micro_port_a.transform\
            .translate(dx=13.5)\
            .name("hdmi_micro_b")

        sd_card = self.sd_card_micro()\
            .transform.rotate(gp.gp.OZ(), math.pi / 2)\
            .transform.rotate(gp.gp.OY(), math.pi)\
            .align().z_max_to_min(board).transform.translate(dz=-2)\
            .align().y_mid_to_mid(board)\
            .align().x_min_to_min(board).transform.translate(dx=-2.5)\
            .name("sd_card")

        barrel_jack = self._factory.square_centered(dx=7, dy=6)\
            .extrude.prism(dz=12.5)\
            .bool.union(self._factory.cylinder(radius=3, height=15))\
            .cleanup()\
            .transform.rotate(gp.gp.OX(), math.pi/2)\
            .align().z_min_to_max(board)\
            .align().y_min_to_min(board).transform.translate(dy=-2.5)\
            .align().x_mid_to_mid(hdmi_micro_port_b).transform.translate(dx=14.5)\
            .name("audio_jack")

        ribbon_connector = self._factory.square_centered(dx=2.5, dy=22)\
            .extrude.prism(dz=5.5)\
            .align().x_min_to_max(board)

        ribbon_display = ribbon_connector\
            .align().y_mid_to_min(board).transform.translate(dy=3.5+24.5)\
            .align().x_mid_to_min(board).transform.translate(dx=4)\
            .name("ribbon_display")

        ribbon_camera = ribbon_connector\
            .align().x_mid_to_mid(hdmi_micro_port_b).transform.translate(dx=7)\
            .align().y_mid_to_min(board).transform.translate(dy=11.5)\
            .name("ribbon_camera")

        solder_blobs = self._factory.cylinder(1, 2)\
            .align().z_max_to_min(board)\
            .align().xy_mid_to_mid(usb_slot_a).name("solder_blobs")

        usb_c_and_hdmi = usbc_port.add(hdmi_micro_port_a).add(hdmi_micro_port_b).add(barrel_jack).name("usbc_and_hdmi")

        board = board.add(gpio_slot,
                          ethernet_slot,
                          usb_slot_a,
                          usb_slot_b,
                          usb_c_and_hdmi,
                          sd_card,
                          ribbon_display,
                          ribbon_camera,
                          solder_blobs)

        return board

    def x_y_plane(self)-> Part:
        return Part(
            self._part_cache.create_token("xy_plane"),
            OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(gp.gp_Pln(gp.gp.Origin(), gp.gp.DZ())).Shape())

    def y_z_plane(self)-> Part:
        return Part(
            self._part_cache.create_token("xy_plane"),
            OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(gp.gp_Pln(gp.gp.Origin(), gp.gp.DX())).Shape())

    def z_x_plane(self)-> Part:
        return Part(
            self._part_cache.create_token("xy_plane"),
            OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(gp.gp_Pln(gp.gp.Origin(), gp.gp.DZ())).Shape())

    def din_rail_35mm(self, length: float)-> Part:
        return WireSketcher().line_to(z=25/2, is_relative=True)\
            .line_to(y=7.5, is_relative=True)\
            .line_to(z=35/2, is_relative=False)\
            .get_wire_part(self._part_cache).extrude.square_offset(1).make.face()\
            .extrude.prism(dx=length)\
            .mirror.z(True)\
            .cleanup()\
            .fillet.fillet_edges(0.2, lambda e: op.InterrogateUtils.is_dx_line(e))

    def cable_passthrough(self, cable_diam: float) -> Part:
        post_base_diameter = 6
        post_separation = cable_diam + post_base_diameter + 3

        cable = self._factory.cylinder(cable_diam / 2 + Constants.clearance_mm(), 20)\
            .transform.rotate(gp.gp.OX(), math.pi / 2)

        posts = self._factory.cone(post_base_diameter / 2, 2, cable_diam + 2)\
            .do_and_add(lambda p: p.transform.translate(dx=post_separation))

        cable = cable.align().xy_mid_to_mid(posts)\
            .align().z_min_to_min(posts)\
            .transform.translate(dz=0.01)

        cable_cut_up = cable.bool.union(self._factory.box_surrounding(cable, z_clearance=100).align().z_min_to_mid(cable))\
            .cleanup()

        cable_cut_down = cable.bool.union(self._factory.box_surrounding(cable, z_clearance=100).align().z_max_to_mid(cable))\
            .cleanup()

        posts = self._factory.capsule(post_separation, post_base_diameter + 0.01)\
            .make.face()\
            .extrude.prism(dz=cable_diam)\
            .align().xy_mid_to_mid(posts)\
            .align().z_min_to_min(posts)\
            .bool.union(posts)\
            .cleanup()\
            .bool.cut(cable_cut_up)\
            .cleanup()\
            .do(lambda p:
                p.bool.cut(self._factory.box(cable_diam + 3, post_base_diameter / 2, p.extents.z_span)
                           .align().xy_mid_to_mid(posts)
                           .align().z_min_to_min(posts)))\
            .cleanup()

        clamp = self._factory.capsule(post_separation, post_base_diameter)\
            .make.face()\
            .extrude.prism(dz=3)\
            .align().xy_mid_to_mid(posts)\
            .align().stack_z1(posts, offset=3)\
            .do(lambda p: p.bool.union(self._factory.box(
                cable_diam + 3 - Constants.clearance_mm(),
                post_base_diameter / 2 - Constants.clearance_mm(),
                p.extents.z_min - posts.extents.z_mid)
                                       .align().xy_mid_to_mid(p)
                                       .align().stack_z0(p)))\
            .bool.cut(cable_cut_down)\
            .cleanup()

        posts = posts.bool.cut(self._factory.cylinder(2.8/2, posts.extents.z_span)
                               .do_and_add(lambda p: p.transform.translate(dx=post_separation))
                               .align().xy_mid_to_mid(posts)
                               .align().z_min_to_min(posts)).cleanup()

        clamp = clamp.bool.cut(
            self._factory.cylinder(3.2 / 2, posts.add(clamp).extents.z_span)
                .do_and_add(lambda p: p.transform.translate(dx=post_separation))
                .align().xy_mid_to_mid(posts)
                .align().z_mid_to_mid(clamp))

        return self._factory.compound(posts.name("mount"),
                                    clamp.name("clamp"),
                                    cable.name("cable_clearance"),
                                    cable_cut_up.name("cable_cut_up_clearance"),
                                    cable_cut_down.name("cable_cut_down_clearance"))

    def screw_m3(self,
                 length: float,
                 head_diameter: float = 5.5,
                 hex_socket_x_span: float = 3,
                 head_z_span: float = 3)-> Part:

        hex = PartFactory(self._part_cache).polygon(1, 6)\
            .transform.rotate(gp.gp.OZ(), math.pi / 2)\
            .do(lambda p: p.sp("body").make.face())\
            .transform.scale_to_x_span(hex_socket_x_span, scale_other_axes=True)\
            .extrude.prism(dz=head_z_span - 1)

        shaft = self._factory.cylinder(radius=1.5, height=length)

        head = self._factory.cylinder(radius=head_diameter / 2, height=head_z_span)\
            .do(lambda p: p.bool.cut(hex.align().xy_mid_to_mid(p).align().z_max_to_max(p))) \
            .do(lambda p:
                p.fillet.fillet_edges(0.15, lambda f: Part.of_shape(f).extents.z_max > p.extents.z_min))

        return head.bool.union(shaft.align().xy_mid_to_mid(head).align().z_max_to_min(head))\
            .with_cache_token(self._part_cache.create_token("stock_part", "screw_m3", length, head_diameter, hex_socket_x_span, head_z_span))

    def ziptie_cavity(self,
                      ziptie_width: float,
                      ziptie_thickness: float,
                      inner_curvature_radius: float = 5,
                      cavity_depth: float = 4,
                      clearance: float = 0.2) -> Part:
        cylinder_inner = self._factory.cylinder(inner_curvature_radius, height=ziptie_width + 2 * clearance)
        cylinder_outer = self._factory.cylinder(inner_curvature_radius + ziptie_thickness * 2 * clearance, height=ziptie_width + 2 * clearance)

        cylinder = cylinder_outer.bool.cut(cylinder_inner)

        return self._factory.box_surrounding(cylinder)\
            .align().x_min_to_min(cylinder)\
            .transform.translate(dx=cavity_depth)\
            .do(lambda p: cylinder.bool.cut(p))\
            .transform.rotate(gp.gp.OY(), -math.pi / 2)\
            .transform.rotate(gp.gp.OZ(), math.pi / 2)

    def enclosure(
            self,
            enclosed_part: Part,
            lid_offset: float = 0,
            wall_thickness: float = 3)-> Part:

        box = self._factory.box_surrounding(enclosed_part)\
            .do(
                lambda p: self._factory.box_surrounding(p, wall_thickness, wall_thickness, wall_thickness)\
                    .fillet.fillet_edges(radius=wall_thickness)
                    .bool.cut(p))

        if lid_offset == 0:
            return box

        lid_section = self._factory.square_centered(box.extents.x_span + 1, box.extents.y_span + 1, box.extents.z_span + 1)\
            .align().xyz_mid_to_mid(box)\
            .bool.common(box)\
            .explore.wire\
            .order_by(lambda w: op.InterrogateUtils.length(w.shape)).get()[-1]

        lid_section: Part = WireSketcher(0, 0, 0)\
            .line_to(x=wall_thickness / 3)\
            .line_to(z=wall_thickness / 3)\
            .line_to(x=2 * wall_thickness / 3)\
            .line_to(z=0)\
            .line_to(x=wall_thickness)\
            .get_wire_part() \
            .extrude.square_offset(0.15) \
            .align().xz_min_to_min(lid_section)\
            .align().y_mid_to_mid(lid_section)\
            .loft.pipe(lid_section.shape)

        return box.bool.cut(lid_section)

    def standoffs(self,
                  surround_extents: Part,
                  x_hole_spacing: float,
                  y_hole_spacing: float,
                  height: float,
                  fillet_diameter: float,
                  drill_bit: op.Bit)-> Part:

        standoff: Part = self._factory.box(
            (surround_extents.extents.x_span - x_hole_spacing + fillet_diameter) / 2,
            (surround_extents.extents.y_span - y_hole_spacing + fillet_diameter) / 2, height) \
            .do(lambda p: p.fillet.fillet_edges(
                fillet_diameter / 2,
                lambda e: op.InterrogateUtils.is_dz_line(e) and Part(e).extents.xy_mid == [p.extents.x_max, p.extents.y_min]))\
            .align().z_min_to_min(surround_extents)

        sa1 = standoff\
            .align().x_min_to_min(surround_extents).align().y_max_to_max(surround_extents)

        sa2 = standoff\
            .mirror.x()\
            .align().x_max_to_max(surround_extents).align().y_max_to_max(surround_extents)

        sa3 = standoff\
            .mirror.y()\
            .align().x_min_to_min(surround_extents).align().y_min_to_min(surround_extents)

        sa4 = standoff\
            .mirror.y().mirror.x()\
            .align().x_max_to_max(surround_extents).align().y_min_to_min(surround_extents)

        standoffs = self._factory.compound(sa1, sa2, sa3, sa4)

        return standoffs \
            .drill(op.Drill(drill_bit).square_pattern_centered(standoffs.shape,
                                                               *standoffs.extents.xyz_mid,
                                                               du=x_hole_spacing,
                                                               dv=y_hole_spacing))

    def dovetail(self,
                 height: float,
                 h_bottom: float,
                 h_top: float,
                 pln: gp.gp_Ax2 = gp.gp.XOY()) -> Part:

        dx = gp.gp_Vec(pln.XDirection()).Normalized()
        dy = gp.gp_Vec(pln.YDirection()).Normalized()

        def v_to_xyz(vec: gp.gp_Vec):
            return vec.X(), vec.Y(), vec.Z()

        return WireSketcher()\
            .line_to(*v_to_xyz(dx.Scaled(h_bottom)), is_relative=True)\
            .line_to(*v_to_xyz(dx.Scaled(-h_bottom / 2 + h_top / 2).Added(dy.Scaled(height))), is_relative=True)\
            .line_to(*v_to_xyz(dx.Scaled(-h_top)), is_relative=True)\
            .line_to(*v_to_xyz(dx.Scaled(-h_bottom / 2 + h_top / 2).Added(dy.Scaled(-height))), is_relative=True)\
            .get_wire_part()

    def ruler(self, cm: int, is_2d: bool=True) -> Part:
        token = self._part_cache.create_token("part_factory", "ruler", cm, is_2d)

        def _do():
            cm_notches = self._factory.capsule(5, 0.4).tr.rz(math.radians(90))\
                .pattern(range(0, cm), lambda i, p: p.tr.mv(dx=10 * i).name(str(i + 1)))

            self._factory.compound(*[ self._factory.sphere(1).align().by("xmidymidzmid", c.inspect.com()) for c in cm_notches.explore.face.get()])

            numbers = self._factory.compound(*[
                self._factory
                     .text(str(i), "serif", 5)
                     .align().com(cm_notches.sp(str(i)))
                     .align().by("yminmaxzmin", cm_notches.sp(str(i)))
                     .tr.mv(dy=1) for i in range(1, cm + 1)])

            cuts = numbers.add(cm_notches).extrude.prism(dz=-1)

            ruler = self._factory.box(cuts.xts.x_span + 2, cuts.xts.y_span - 1, 1)\
                .align().by("xmidymaxzmaxmid", cuts)\
                .tr.mv(dy=1)

            if is_2d:
                ruler = ruler.explore.face.get_max(lambda f: f.xts.z_mid).bool.cut(cuts)
            else:
                ruler = ruler.bool.cut(cuts)

            return ruler.with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def bearing_thrust_8mm(self, is_simple: bool = True):
        race_od = 16
        race_id = 8.2

        race_thickness = 1.2

        cage_thickness = 1.68
        total_thickness = 5

        if is_simple:
            return self._factory.cylinder(race_od / 2, total_thickness)\
                .bool.cut(self._factory.cylinder(race_id / 2, total_thickness))\
                .cleanup()

        ball_count = 9
        ball_dia = 3


        top = self._factory.cylinder(race_od / 2, 1.2)\
            .bool.cut(self._factory.cylinder(race_id / 2, 1.2)).cleanup()

        ball_center_dia = race_id + (race_od - race_id) / 2

        cut = self._factory.circle(ball_dia / 2)\
            .transform.rotate(gp.gp.OX(), math.pi / 2)\
            .transform.translate(dx=ball_center_dia / 2)\
            .loft.pipe(self._factory.circle(ball_center_dia / 2))

        def apply_ball_pattern(ball: Part) -> Part:
            return ball.align().xy_mid_to(x=0, y=0)\
                .transform.translate(dx=ball_center_dia / 2)\
                .pattern(range(0, 9), lambda i, p: p.transform.rotate(gp.gp.OZ(), i * 2 * math.pi / 9))

        ball_bearing = self._factory.sphere(ball_dia / 2)
        balls = apply_ball_pattern(self._factory.sphere(ball_dia / 2))

        cage = top.transform.scale_to_z_span(cage_thickness)\
            .align().z_mid_to(z=0)\
            .bool.cut(apply_ball_pattern(self._factory.cylinder(ball_dia / 2, ball_dia).align().z_mid_to(z=0)))\
            .cleanup()

        top: Part = top.align().z_max_to(z=2.5)\
            .bool.cut(cut).cleanup()

        bottom = top.mirror.z()

        top = top.name("top").add(
            bottom.name("bottom"),
            cage.name("cage"),
            balls.name("balls"))

        return top.print()

    def bearing_608(self) -> Part:
        token = self._part_cache.create_token("part_factory", "bearing_608")

        def _do():
            INNER_RACE_ID = 8
            INNER_RACE_OD = 12.1

            OUTER_RACE_ID = 19.2
            OUTER_RACE_OD = 22

            inner_race = self._factory.cylinder(INNER_RACE_OD/2, 7)\
                .fillet.chamfer_edges(0.2)

            outer_race = self._factory.cylinder(OUTER_RACE_OD / 2, 7)\
                .bool.cut(self._factory.cylinder(OUTER_RACE_ID / 2, 7))\
                .fillet.chamfer_edges(0.2)

            cut = self._factory.circle(2)\
                .transform.rotate(gp.gp.OY(), math.pi / 2)\
                .transform.translate(dy=op.MathUtils.lerp(y0=INNER_RACE_OD / 2, y1=OUTER_RACE_ID / 2, coordinate_proportional=0.5)[1])\
                .align().z_mid_to_mid(outer_race)\
                .loft.pipe(self._factory.circle(10))

            inner_race = inner_race.bool.cut(cut).cleanup()
            outer_race = outer_race.bool.cut(cut).cleanup()

            # get the bearing ball coordinate
            b0 = inner_race.pick.from_dir(-1, 0, 0).first()
            b1 = outer_race.pick.from_dir(-1, 0, 0).all().explore.vertex.get()[1]

            ball = self._factory.sphere(abs(b0.xts.x_mid - b1.xts.x_mid) / 2)\
                .align().by("xminmaxymidzmid", b0)

            race = ball.pattern(range(0, 9), lambda i, p: p.transform.rotate(gp.gp.OZ(), 2 * math.pi * i / 9)) #self._factory.cylinder(11, 5).align().z_mid_to_mid(outer_race)

            return self._factory.compound(inner_race, outer_race, race)\
                .bool.cut(self._factory.cylinder(INNER_RACE_ID / 2, 7).name_recurse("axle", lambda s: s.ShapeType() == OCC.Core.TopAbs.TopAbs_FACE))\
                .cleanup()\
                .with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def i2c_oled(self) -> Part:
        hole_dx = 23.5
        hole_dy = hole_dx
        hole_dia = 2
        hole_offs = 1.5

        screen_dy = 14
        screen_dx = 26

        dx = 26.5
        dy = 27

        board_clearance = 2

        layout = self._factory.square_centered(dx, dy).make.face()
        hole_template = self._factory.cylinder(hole_dia / 2, 3).align().z_mid_to_mid(layout)
        holes = hole_template.do_and_add(lambda p: p.transform.translate(dx=hole_dx))\
            .do_and_add(lambda p: p.transform.translate(dy=hole_dy))\
            .align().xy_mid_to_mid(layout)

        screen: Part = self._factory.square_centered(screen_dx, screen_dy)\
            .align().xz_mid_to_mid(layout)\
            .align().y_max_to_max(layout)\
            .transform.translate(dy=-4.5)\
            .extrude.prism(dz=1.5)
        screen = screen.name_subshape(screen.explore.face.get_max(lambda f: f.extents.z_mid), "screen_top")

        board = layout.bool.cut(holes).extrude.prism(dz=-2)

        return screen.add(board.name("board")).add(holes.name("holes").align().z_mid_to_mid(board))

    def pot_rotary(self) -> Part:
        body = self._factory.cylinder(17/2, 7).name("body")
        flange = self._factory.cylinder(17/2, 2).do(lambda p: p.bool.common(
            self._factory.box_surrounding(p).transform.scale_to_y_span(11)
        )).align().xy_mid_to_mid(body).align().stack_z1(body).name("flange")

        result = body.add(flange)

        post_lower = self._factory.cylinder(3.5, 7)
        post_upper = self._factory.cylinder(6.2 / 2, 8.2)\
            .do(lambda p: p.bool.cut(self._factory.box_surrounding(p).transform.scale_to_x_span(1.5)))

        post = post_lower.bool.union(post_upper
                              .align().xy_mid_to_mid(post_lower)
                              .align().stack_z1(post_lower))\
            .transform.scale_to_z_span(15)\
            .align().xy_mid_to_mid(result)\
            .align().stack_z1(result)\
            .name("post")

        board = self._factory.box(15, 7.5, 1.5)\
            .align().x_mid_to_mid(body)\
            .align().z_max_to_max(body)\
            .align().y_min_to_max(body).transform.translate(dy=-20)

        detent = body.do(lambda p: p.bool.common(self._factory.box_surrounding(p)
                          .transform.scale_to_x_span(1.5)
                          .transform.scale_to_y_span(2.7)
                          .transform.scale_to_z_span(3.7)
                          .align().xz_min_to_min(p).transform.translate(dx=-0.001, dz=-0.001)
                          .align().y_mid_to_mid(p))).align().stack_z1(body)\
            .name("detent")

        pins = self._factory.cylinder(0.5, 5).transform.rotate(gp.gp.OX(), math.pi / 2)\
            .pattern(range(0, 3), lambda i, p: p.transform.translate(dx=5*i))\
            .align().stack_z0(board)\
            .align().stack_y0(board)\
            .align().x_mid_to_mid(board)

        result = board.add(body, post, flange, detent).add(pins)

        return result

    def swtich_automotive(self):
        threaded_part = self._factory.cylinder(6, 9.5)
        plain_part = self._factory.cylinder(11/2, 13)

        pins = self._factory.cylinder(1.5, 5.5)\
            .transform.scale_to_x_span(2.2)\
            .do_and_add(lambda p: p.transform.translate(dx=5))

        shank = threaded_part.align().stack_z1(plain_part).bool.union(plain_part)
        shank = shank.bool.union(pins.align().xy_mid_to_mid(shank).align().stack_z0(shank))

        result = shank

        key = self._factory.square_centered(15.5, 15.5)\
            .fillet.fillet2d_verts(2)\
            .make.face()
        key = self._factory.loft([key, key.transform.translate(dz=6.5)
                               .transform.scale_to_x_span(14)
                               .transform.scale_to_y_span(14).align().xy_mid_to_mid(key)])

        result = result.add(key.align().xy_mid_to_mid(result).align().stack_z1(result))

        button = self._factory.square_centered(11, 11)\
            .fillet.fillet2d_verts(1)\
            .make.face()\
            .extrude.prism(dz=4)\
            .align().xy_mid_to_mid(result)\
            .align().stack_z1(result)

        result = result.add(button).bool.union().cleanup()

        return result

    def i2c_oled_with_mount(self) -> Part:
        plate = self._factory.square_centered(10, 10)

        result: Part = self.i2c_oled()\
            .align().stack_z0(plate)\
            .align().y_max_to_max(plate)\
            .transform.translate(dy=-6.5) \
            .do(lambda p:
                p.align().x_min_to_min(plate).transform.translate(dx=-p.single_subpart("screen_top").extents.y_max + plate.extents.y_max))

        mount = self._factory.cone(1/2, 1.7/2, 5)\
            .align().stack_z0(plate).do(lambda p: p.fillet.chamfer_faces(0.1, p.explore.face.get_min(lambda f: f.extents.z_mid)))

        mount = self._factory.compound(*[mount.align().xy_mid_to_mid(s) for s in result.compound_subpart("holes").explore.solid.get()])

        mount_screw_x0 = self._factory.cone(2, 3, result.extents.z_span)\
            .bool.cut(self._factory.cylinder(2.9/2, result.extents.z_span))\
            .align().z_max_to_max(plate)\
            .align().y_mid_to_mid(result)\
            .align().stack_x0(result)

        mount_screw_x1 = mount_screw_x0.align().stack_x1(result)

        mount_screw = mount_screw_x1.add(mount_screw_x0)

        screw_spacing = mount_screw_x1.extents.x_mid - mount_screw_x0.extents.x_mid

        mount_pad = self._factory.capsule(screw_spacing, mount_screw_x1.extents.y_span).make.face().extrude.prism(dz=-3)\
            .do(lambda p: p.bool.cut(self._factory.cylinder(3 / 2, p.extents.z_span).do_and_add(lambda pp:
                                     pp.transform.translate(dx=screw_spacing)).align().xyz_mid_to_mid(p)))\
            .align().xy_mid_to_mid(mount_screw)\
            .align().stack_z0(result, offset=-1)

        mount = mount.add(mount_screw)

        return result.add(mount.name("mount"), mount_pad.name("clamp"))

    def pot_rotary_with_mount(self) -> Part:
        plate = self._factory.square_centered(10, 10)
        adjusted_knob: Part = StockParts.pot_rotary()\
            .transform.rotate(gp.gp.OZ(), math.pi / 2)\
            .do(lambda p: p.transform.translate(dx= -p.single_subpart("post").extents.x_mid))\
            .align().stack_z0(plate, offset=13)

        # create a cut cylinder for the detent
        knob_body = adjusted_knob.compound_subpart("body")
        detent_rest = self._factory.cylinder(
            knob_body.extents.x_span / 2, plate.extents.z_max - knob_body.extents.z_max + 1)\
            .align().xy_mid_to_mid(knob_body)\
            .align().stack_z1(adjusted_knob.single_subpart("flange"))\
            .bool.cut(adjusted_knob).cleanup()

        return adjusted_knob.add(detent_rest.name("mount"))


    def matrix_keypad(self):
        keypad = self._factory.square_centered(dx=60, dy=57) \
            .fillet.fillet2d_verts(3) \
            .make.face() \
            .extrude.prism(dz=3.5)

        keypad_back = self._factory.square_centered(65, 65) \
            .fillet.fillet2d_verts(2) \
            .make.face() \
            .extrude.prism(dz=3) \
            .align().xy_mid_to_mid(keypad) \
            .align().stack_z0(keypad) \
            .do(lambda p: p.bool.cut(
            self._factory.box(5.5, 3.5, p.extents.z_span)
            .align().xz_mid_to_mid(p)
            .align().y_max_to_max(p)
            .fillet.fillet_edges(1,
                                 lambda e: op.InterrogateUtils.is_dz_line(e) and Part(e).extents.y_max < p.extents.y_max)))

        mounts = self._factory.cylinder(1, 6.5)\
            .align().x_min_to_min(keypad_back).transform.translate(dx=1.5)\
            .do_and_add(lambda p: p.align().x_max_to_max(keypad_back).transform.translate(dx=-1.5))\
            .align().y_max_to_max(keypad_back).transform.translate(dy=-1.5)\
            .do_and_add(lambda p: p.align().y_min_to_min(keypad_back).transform.translate(dy=1.5))\
            .align().xy_mid_to_mid(keypad_back)\
            .align().z_max_to_max(keypad)\
            .name("mount")

        pcb = self._factory.square_centered(50, 5).cleanup() \
            .do(lambda p: p.fillet.fillet2d_verts(0.5, lambda v: Part(v).extents.y_mid < p.extents.y_max)) \
            .make.face() \
            .extrude.prism(dz=1.5) \
            .align().z_min_to_min(keypad_back) \
            .align().x_mid_to_mid(keypad_back) \
            .align().stack_y0(keypad_back)

        keys = self._factory.box(8.5, 7.5, 2.5) \
            .pattern(range(0, 4), lambda i, p: p.transform.translate(dx=i * 14)) \
            .pattern(range(0, 4), lambda i, p: p.transform.translate(dy=i * 13)) \
            .align().xy_mid_to_mid(keypad) \
            .align().stack_z1(keypad)

        return self._factory.compound(mounts, keypad.name("keypad"), keypad_back.name("back"), pcb.name("pcb"), keys.name("keys"))

    def bottom_fastened_rect_enclosure(
            self,
            interior_space_dx: float,
            interior_space_dy: float,
            interior_space_dz: float,
            wall_thickness_x0: float = 2,
            wall_thickness_x1: typing.Optional[float] = None,
            wall_thickness_y0: float = 2,
            wall_thickness_y1: typing.Optional[float] = None,
            wall_thickness_z0: float = 2,
            wall_thickness_z1: typing.Optional[float] = None,
            exterior_blank_modifier: typing.Optional[typing.Callable[[Part], Part]] = None,
            interior_blank_modifier: typing.Optional[typing.Callable[[Part], Part]] = None):

        if wall_thickness_x1 is None:
            wall_thickness_x1 = wall_thickness_x0

        if wall_thickness_y1 is None:
            wall_thickness_y1 = wall_thickness_y0

        if wall_thickness_z1 is None:
            wall_thickness_z1 = wall_thickness_z0

        interior = self._factory.box(interior_space_dx, interior_space_dy, interior_space_dz)
        exterior = self._factory.box(interior_space_dx + wall_thickness_x0 + wall_thickness_x1,
                                   interior_space_dy + wall_thickness_y0 + wall_thickness_y1,
                                   interior_space_dz + wall_thickness_z0 + wall_thickness_z1)

        interior = interior \
            .align().x_min_to_min(exterior).transform.translate(dx=wall_thickness_x0) \
            .align().y_min_to_min(exterior).transform.translate(dy=wall_thickness_y0)\
            .align().z_min_to_min(exterior).transform.translate(dz=wall_thickness_z0)

        if exterior_blank_modifier is not None:
            exterior = exterior_blank_modifier(exterior)

        if interior_blank_modifier is not None:
            interior = interior_blank_modifier(interior)

        # create the bolt pattern to drill
        bolt = self._factory.cylinder(6 / 2, 3.5)\
            .do(lambda p: p.bool.union(self._factory.cylinder(1.5, wall_thickness_z0 - 3.5).align().stack_z1(p)))\
            .do(lambda p: p.bool.union(self._factory.cylinder(2.8/2, 10)))\
            .cleanup()

        bolt_pattern = bolt.array.on_verts_of(
            self._factory.box_surrounding(exterior).explore.face.get_min(lambda f: f.extents.z_mid)\
            .extrude.offset(-6))

        return exterior.bool.cut(interior).add(bolt_pattern)

    def flexure_link(self,
                     body_thickness: float,
                     body_length: float,
                     link_thickness: float,
                     link_length: float):

        body = self._factory.box(body_length, body_thickness, 1, x_min_face_name="a", x_max_face_name="b")

        body = body.bool.union(
            self._factory.loft([
                body.single_subpart("a"),
                body.single_subpart("a")
                    .transform.scale_to_y_span(link_thickness)
                    .align().y_mid_to_mid(body)
                    .align().stack_x0(body, offset=-10)
            ], last_shape_name="a"),
            self._factory.loft([
                body.single_subpart("b"),
                body.single_subpart("b")
                .transform.scale_to_y_span(link_thickness)
                .align().y_mid_to_mid(body)
                .align().stack_x1(body, offset=10)
            ], last_shape_name="b")
        )

        body = body.bool.union(body.single_subpart("a").extrude.prism(dx=-link_length, last_shape_name="a"))
        body = body.bool.union(body.single_subpart("b").extrude.prism(dx=link_length, last_shape_name="b"))

        body = body.cleanup(concat_b_splines=True, fix_small_face=True)

        body = body.fillet.fillet_edges(2,
                                        lambda e: op.InterrogateUtils.is_dz_line(e) and
                                                  (not body.single_subpart("a").inspect.contains(e)) and
                                                  (not body.single_subpart("b").inspect.contains(e)))

        return body

    def mg90s_servo(self) -> Part:
        token = self._part_cache.create_token("stock_parts", "mg90s_servo")
        def _do():
            body = self._factory.box(23, 12.2, 24.2)
            flange = self._factory.box(32.3, body.xts.y_span, 2.5) \
                .align().by("xmidymidzmin", body) \
                .tr.mv(dz=17.4)

            flange = flange.bool.cut(
                self._factory.cylinder(1.5, flange.xts.z_span + 1)
                    .name_recurse("mount_point", lambda f: Part.of_shape(f).inspect.is_face())
                .do_and_add(lambda p: p.tr.mv(dx=27.4))
                .align().by("xmidymidzmid", flange))

            shaft_surround = self._factory.cylinder(11.4 / 2, 4.2) \
                .align().stack_z1(body) \
                .align().by("ymid", body) \
                .align().by("xmin", flange).tr.mv(dx=4.7)
            shaft_surround_side = self._factory.cylinder(5.4 / 2, shaft_surround.xts.z_span) \
                .do(lambda p: p.bool.union(
                self._factory.box_surrounding(p).align().by("xmaxmid", p).tr.mv(dx=-Precision.precision.Confusion()))) \
                .align().by("ymidzmid", shaft_surround) \
                .align().by("xmax", body).tr.mv(dx=-7) \
                .cleanup()
            shaft = self._factory.cylinder(4.8 / 2, 3.4) \
                .align().by("xmidymid", shaft_surround) \
                .align().stack_z1(shaft_surround) \
                .name_recurse("shaft", lambda f: Part.of_shape(f).inspect.is_face())

            return body.bool.union(flange, shaft, shaft_surround, shaft_surround_side) \
                .cleanup().name("main") \
                .add(body.name("body")) \
                .add(flange.name("flange")) \
                .add(shaft_surround.name("shaft_surround")) \
                .add(shaft_surround_side.name("shaft_surround_side")) \
                .add(shaft.name("shaft"))\
                .with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def stepper_28byJ48(self) -> Part:

        token = self._part_cache.create_token("stock_parts", inspect.getsource(StockParts.stepper_28byJ48))

        def _do():
            body = self._factory.cylinder(28 / 2, 19) #.do(lambda p: p.fillet.chamfer_faces(2, p.pick.from_dir(0, 0, -1).first_face()))

            feet = self._factory.capsule(35, 7).extrude.prism(dz=0.5).do(lambda p: p.bool.cut(
                self._factory.cylinder(4.2 / 2, p.xts.z_span).name_recurse("foot_clearance")
                    .do_and_add(lambda pp: pp.tr.mv(dx=35))
                    .align().by("xmidymidzmid", p)
            )).align().by("xmidymidzmin", body)

            shaft = self._factory.cylinder(2.5, 10)\
                .do(lambda p: p.bool.union(self._factory.cylinder(9.5 / 2, 2).align().by("xmidymidzmax", p)))

            shaft = shaft.bool.cut(self._factory.box_surrounding(shaft)
                                   .tr.mv(dz=-4)
                                   .align().by("xminmid", shaft)
                                   .tr.mv(dx=1.5)
                                   .do_and_add(lambda p: p.mirror.x(center_x=shaft.xts.x_mid)))

            shaft = shaft.align().by("xmidymidzmaxmin", body)\
                .tr.mv(dy=8)

            body = body.bool.union(
                self._factory.box(14.6, 17, body.xts.z_span - (17 - body.xts.y_span / 2))
                .align().by("xmidymaxmidzmin", body)
                .do(lambda p: p.fillet.chamfer_faces(2, p.pick.from_dir(0, 0, -1).first_face())))

            body = body.cleanup(concat_b_splines=True, fix_small_face=True).make.solid()

            feet = feet.make.solid().cleanup(concat_b_splines=True, fix_small_face=True)

            return self._factory.compound(
                shaft.name("shaft"),
                body.name("body"),
                feet.name("feet")).with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def nema_17_stepper(self) -> Part:
        token = self._part_cache.create_token("stock_parts", "nema_17_stepper", inspect.getsource(StockParts))

        def _do():
            def make_chamfered_square(square_length: float,
                                      chamfer_to_chamfer_dist: float,
                                      height: float):
                body = self._factory.box(square_length, square_length, height)
                chamfer_box = self._factory.box(chamfer_to_chamfer_dist, chamfer_to_chamfer_dist, height + 1)\
                    .tr.rz(math.radians(45))\
                    .align().by("xmidymidzmid", body)

                return body.bool.common(chamfer_box).cleanup()

            stepper_height = 47.4

            stepper_body = make_chamfered_square(42.3, 50.2, stepper_height)\
                .name("main_body")\
                .annotate("color", "cobalt")

            stepper_cap_top = make_chamfered_square(42.3, 53.8, 7.6)\
                .name("cap_top")\
                .annotate("color", "silver")\
                .align().by("xmidymidzmax", stepper_body)

            stepper_cap_bottom = make_chamfered_square(42.3, 53.8, 9.5)\
                .name("cap_bottom")\
                .annotate("color", "silver")\
                .align().by("xmidymidzmin", stepper_body)

            stepper_body = stepper_body.bool.cut(stepper_cap_top, stepper_cap_bottom)\
                .add(stepper_cap_top, stepper_cap_bottom)

            top_ring = self._factory.ring(22 / 2, 9.8 / 2, 1.8)\
                .align()\
                .by("xmidymidzminmax", stepper_body)

            top_ring_clearance = self._factory.cylinder(top_ring.xts.x_span / 2, top_ring.xts.z_span)\
                .align()\
                .by("xmidymidzmid", top_ring)

            shaft_clearance = self._factory.cylinder(5 / 2, 23 + top_ring.xts.z_span)\
                .align().by("xmidymidzminmax", stepper_body)

            shaft = shaft_clearance\
                .do(lambda p: p.bool.cut(self._factory.box_surrounding(p).tr.mv(dx=4.5, dz=8)))

            stepper_body = stepper_body.add(top_ring.name("top_right").annotate("color", "silver"))

            electronics_connector = self._factory.box(15.5, 6.5, 10)\
                .align().by("xmidyminmaxzmin", stepper_body)

            mount_holes = self._factory.cylinder(1.5, 5)\
                .do_and_add(lambda p: p.tr.mv(dx=31.2))\
                .do_and_add(lambda p: p.tr.mv(dy=31.2))\
                .align().by("xmidymidzmax", stepper_body)\
                .name_recurse("screw_hole", lambda f: f.ShapeType() == OCC.Core.TopAbs.TopAbs_FACE and Part.of_shape(f).xts.z_span > 1)

            stepper_body_clearance = self._factory.union(*stepper_body.explore.solid.get())
            stepper_body = stepper_body.bool.cut(*mount_holes.explore.solid.get())

            return self._factory.compound(
                stepper_body.name("body"),
                stepper_body_clearance.name("body_clearance"),
                electronics_connector.name("connector"),
                shaft.name("shaft").annotate("color", "silver"),
                shaft_clearance.name("shaft_clearance"),
                top_ring_clearance.name("top_ring_clearance"))\
                .with_driver(StepperDriver)\
                .with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def gear_motor(self) -> Part:
        token = self._part_cache.create_token("stock_parts", "gear_motor", inspect.getsource(StockParts))

        def _do():
            gearbox = self._factory.box(46.1, 23, 32) \
                .fillet.fillet_edges(2, lambda e: op.InterrogateUtils.is_dy_line(e))

            mount = self._factory.cylinder(7.5 / 2, 2) \
                .do(lambda p: self._factory.compound(
                p.name("mount"),
                self._factory.cylinder(2.8 / 2, 4).align().by("xmidymidzmax", p).name("screw_mount"))) \
                .tr.rx(math.radians(90))

            mounts = mount.do_and_add(lambda p: p.tr.mv(dx=33.1)).do_and_add(lambda p: p.tr.mv(dz=18)) \
                .align().by("xmidyminzmid", gearbox.pick.from_dir(0, 1, 0).first_face()) \
                .tr.mv(dy=-2)

            motor_body = self._factory.cylinder(24.2 / 2, 31).tr.ry(math.radians(90)) \
                .align().by("xmaxminyminzmin", gearbox) \
                .tr.mv(dz=1.5)

            shaft = self._factory.cylinder(13.5 / 2, 1.5) \
                .do_and_add(lambda p: self._factory.cylinder(3, 14).align().by("xmidymidzminmax", p).do(lambda p: p.bool.cut(self._factory.box_surrounding(p).tr.mv(dx=5.5)))) \
                .tr.rx(math.radians(90)) \
                .align().by("xmaxymaxzmid", gearbox.pick.from_dir(0, 1, 0).first_face()) \
                .tr.mv(dx=-8)

            return self._factory.compound(
                gearbox.make.solid().name("gearbox"),
                mounts.name("mounts"),
                motor_body.name("motor_body"),
                shaft.name("shaft")
            ).with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)
