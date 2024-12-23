import logging
import math
import pdb

import OCC.Core.GeomAbs
import OCC.Core.gp
import typing

from OCC.Core import Precision, gp

import ezocc
from ezocc.constants import Constants
from ezocc.humanization import Humanize
from ezocc.occutils_python import WireSketcher, SetPlaceablePart
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import PartCache, PartFactory, Part
from ezocc.stock_parts.living_hinge import LivingHingeFactory, CapsuleHingeGenerator

logger = logging.getLogger(__name__)


class AluTubeStockParts:

    logger = logging.getLogger(__name__)

    def __init__(self, cache: PartCache, tube_radius: float):
        if tube_radius <= 0:
            raise ValueError(f"Tube radius must be > 0 (was {tube_radius})")

        self._cache = cache
        self._tube_radius = tube_radius
        self._factory = PartFactory(cache)

    def wireframe_to_tubes(self,
                           wireframe: Part, extra_trim_clearance: float = 0,
                           veto_trim_edge_vert: typing.Callable[[SetPlaceablePart, SetPlaceablePart], bool] = None) -> Part:
        # convert each edge in the wireframe to a cylinder
        # tube ends are trimmed so that they do not touch

        if veto_trim_edge_vert is None:
            def veto_trim_edge_vert(*_):
                return False

        # for each tube
        # tube end should be paired with an edge endpoint

        edges_to_untrimmed_tubes = {e.set_placeable: self.edge_to_tube(e) for e in wireframe.explore.edge.get()}
        untrimmedtubes_to_edges = {t.set_placeable: e.part for e, t in edges_to_untrimmed_tubes.items()}

        # determine which tubes share a vertex
        verts_to_edge_groups: typing.Dict[SetPlaceablePart, typing.Set[SetPlaceablePart]] = {}
        for e in wireframe.explore.edge.get():
            for v in e.explore.vertex.get():
                vs = v.set_placeable

                if vs not in verts_to_edge_groups:
                    verts_to_edge_groups[vs] = set()

                verts_to_edge_groups[vs].add(e.set_placeable)

        def _trim_incident_tube(vertex: Part,
                                edge: Part,
                                tube: Part,
                                other_tubes: typing.Set[Part]):
            if len(other_tubes) == 0:
                return tube

            # establish how much interference there is
            tube_interference = self._factory.compound(*[tube.bool.common(t) for t in other_tubes])

            # determine which end of the edge we are dealing with
            is_source_edge_start = vertex.bool.intersects(tube.sp("start"))

            face_to_modify = tube.sp("start") if is_source_edge_start else tube.sp("end")

            edge_direction = edge.inspect.edge.edge_tangents()[0]

            if tube_interference.inspect.is_empty_compound():
                AluTubeStockParts.logger.warning("No intersections found")

                # tube_interference.print()
                # tube.preview(*other_tubes, tube.tr.mv(dx=1))

                excess_length = 0
            else:
                excess_length = tube_interference\
                    .tr.mv(*(-x for x in vertex.xts.xyz_mid))\
                    .tr(lambda t:
                         t.SetRotationPart(OCC.Core.gp.gp_Quaternion(
                             OCC.Core.gp.gp_Vec(*edge_direction),
                             OCC.Core.gp.gp_Vec(0, 0, 1)
                         )))\
                    .xts.z_span

            excess_length += extra_trim_clearance

            if excess_length < 0:
                raise ValueError("Logic error")

            if excess_length == 0:
                # nothing to do
                return tube

            removal_direction_multiplier = 1 if is_source_edge_start else -1
            tube_geometry_to_remove = face_to_modify.extrude.prism(
                *(removal_direction_multiplier * excess_length * x for x in edge_direction), last_shape_name="start" if is_source_edge_start else "end")

            #tube_geometry_to_remove.tr.mv(dx=1)\
            #    .preview(tube, self._factory.sphere(1).tr.mv(*vertex.xts.xyz_mid),
            #             self._factory.sphere(2).tr.mv(*edge.explore.vertex.get()[0].xts.xyz_mid), *other_tubes)

            return tube.bool.cut(tube_geometry_to_remove).cleanup()

        untrimmed_tubes_to_trimmed_tubes = {t: t.part for t in untrimmedtubes_to_edges.keys()}

        num_verts = len(verts_to_edge_groups.keys())
        i = 1
        veto_count = 0
        bool_ops_count = 0
        for vertex, shared_edges in verts_to_edge_groups.items():
            AluTubeStockParts.logger.info(
                f"Processing shared edges for vertex {i}/{num_verts}: ({len(shared_edges)} edges) {vertex}")
            i += 1

            # edge -> untrimmed tube -> result tube
            for e in shared_edges:
                untrimmed_tube = edges_to_untrimmed_tubes[e]
                trimmed_tube = untrimmed_tubes_to_trimmed_tubes[untrimmed_tube.set_placeable]

                other_tubes = {edges_to_untrimmed_tubes[ee] for ee in shared_edges if ee != e}

                if veto_trim_edge_vert(e, vertex):
                    AluTubeStockParts.logger.info("Vetoing trim")
                    veto_count += 1
                else:
                    bool_ops_count += 1
                    trimmed_tube = _trim_incident_tube(vertex.part, e.part, trimmed_tube, other_tubes)
                    untrimmed_tubes_to_trimmed_tubes[untrimmed_tube.set_placeable] = trimmed_tube

        AluTubeStockParts.logger.info(f"Total boolean operations: {bool_ops_count}")
        AluTubeStockParts.logger.info(f"Total vetoed boolean operations: {veto_count}")

        return factory.compound(
            *untrimmed_tubes_to_trimmed_tubes.values())

    def edge_to_tube(self, linear_edge: Part) -> Part:

        extrusion_dir = linear_edge.inspect.edge.edge_tangents()[0]
        extrusion_origin = linear_edge.inspect.edge.edge_end_points()[0]

        # create circle at v0, rotate, extrude based on length
        result = self._factory.circle(radius=self._tube_radius) \
            .make.face() \
            .tr(lambda t: t.SetRotationPart(OCC.Core.gp.gp_Quaternion(
                OCC.Core.gp.gp_Vec(0, 0, 1),
                OCC.Core.gp.gp_Vec(*extrusion_dir)
            )))\
            .tr.mv(*extrusion_origin)

        length = linear_edge.inspect.edge.length

        extrusion_vec = (e * length for e in extrusion_dir)

        result = result.extrude.prism(*extrusion_vec,
                                      first_shape_name="start",
                                      last_shape_name="end")

        return result


class AluExtrusionStockParts:

    def __init__(self, cache: PartCache, base_profile: Part = None):
        self._cache = cache
        self._factory = PartFactory(cache)

        if base_profile is None:
            base_profile = self._factory.square_centered(10, 10)

        if not base_profile.inspect.is_face():
            raise ValueError(f"Base profile must be a face (was instead "
                             f"{Humanize.shape_type(base_profile.shape.ShapeType())})")

        if base_profile.xts.z_span > Precision.precision.Confusion():
            raise ValueError("Base profile is expected to lie in xy plane")

        self._base_profile = base_profile

    def ball_end(self) -> Part:

        alu = self._base_profile.extrude.prism(dz=20)

        result = self._factory.sphere(5 + math.hypot(alu.xts.x_span / 2, alu.xts.y_span / 2))\
            .align().by("xmidymidzmidmin", alu)\
            .tr.mv(dz=5)\
            .do(lambda p: p.bool.cut(self._factory.box_surrounding(p).align().by("zminmid", p).tr.mv(dz=2)))\
            .make.solid().cleanup(concat_b_splines=True, fix_small_face=True)\
            .do(lambda p: p.bool.union(
                self._factory.loft([alu.pick.from_dir(0, 0, -1).first_face().extrude.offset(3), p.explore.face.get_max(lambda f: f.xts.z_mid)])))\
            .make.solid()\
            .cleanup(concat_b_splines=True, fix_small_face=True) \
            .do(lambda p: p.bool.common(self._factory.box_surrounding(p).align().by("zmax", alu)))\
            .bool.cut(alu.extrude.make_thick_solid(Constants.clearance_mm()))

        result = result.bool.cut(
            self._factory.cylinder(2.8 / 2, 1000).tr.rx(math.radians(90)).align().by("xmidymidzmax", alu).tr.mv(dz=-3),
            self._factory.cylinder(2.8 / 2, 1000).tr.ry(math.radians(90)).align().by("xmidymidzmax", alu).tr.mv(dz=-3))

        return result

    def snap_joint_parallel_axis(self, detent_count: int) -> Part:

        alu = self._base_profile.extrude.prism(dz=20)

        bolt = self._factory.cylinder(4, alu.xts.z_span)\
            .align().by("xmidymidzmid", alu)\
            .align().stack_y1(alu).tr.mv(dy=10)

        result = self._factory.loft([
            alu.pick.from_dir(0, 0, -1).first_face().extrude.offset(5),
            bolt.pick.from_dir(0, 0, -1).first_face().extrude.offset(5)
        ], is_solid=False)\
            .alg.project_z()\
            .alg.edge_network_to_outer_wire()\
            .make.face()\
            .cleanup(concat_b_splines=True, fix_small_face=True)\
            .make.face()\
            .extrude.prism(dz=alu.xts.z_span)\
            .do(lambda p: p.fillet.chamfer_faces(2, {p.pick.from_dir(0, 0, 1).first_face()}))\
            .bool.cut(alu.extrude.make_thick_solid(Constants.clearance_mm()))\
            .bool.cut(bolt.extrude.make_thick_solid(Constants.clearance_mm()))

        result = result.bool.cut(self._factory.cylinder(2.8 / 2, alu.xts.z_span).tr.ry(math.radians(90))
                                 .align().by("xmidymidzmid", alu))

        result = result.bool.cut(self._factory.cylinder(2.8 / 2, alu.xts.z_span).tr.rx(math.radians(90))
                                 .align().by("xmidymaxmidzmid", alu))

        snap_detent_height = 2
        snap_cut = AluExtrusionStockParts._get_snap_fan(self._cache,
                                                    bolt=bolt,
                                                    cut_part=result,
                                                    snap_detent_height=snap_detent_height,
                                                    detent_count=detent_count)

        result_a = result
        for s in snap_cut.explore.solid.get():
            result_a = result_a.bool.cut(s)

        result_b = result
        for s in snap_cut.tr.rz(math.radians(180.0 / detent_count), offset=bolt.xts.xyz_mid).explore.solid.get():
            result_b = result_b.bool.cut(s)

        a_marking = self._factory.text("A", "sans-serif", 1, is_composite_curve=True) \
            .do(lambda p: p.tr.scale(8 / p.xts.y_span)) \
            .align().by("xmidymidzmin", result_a) \
            .align().stack_y1(alu).tr.mv(dy=1)\
            .extrude.prism(dz=2)

        b_marking = self._factory.text("B", "sans-serif", 1, is_composite_curve=True) \
            .do(lambda p: p.tr.scale(8 / p.xts.y_span)) \
            .align().by("xmidymidzmin", result_a) \
            .align().stack_y1(alu).tr.mv(dy=1)\
            .extrude.prism(dz=2)

        result_a = result_a.bool.cut(a_marking)
        result_b = result_b.bool.cut(b_marking)

        result_a = result_a.mirror.z().align().stack_z1(result_b).tr.mv(dz=-snap_detent_height + Constants.clearance_mm())

        return self._factory.compound(
            result_a.name("a"),
            result_b.name("b"))

    @staticmethod
    def __snap_joint_parallel_axis_old(cache: PartCache, detent_count: int) -> Part:
        """
        Axis of rotation is parallel to the aluminium rod
        """

        factory = PartFactory(cache)

        clamp_height = 20

        alu = factory.box(10, 10, clamp_height + 10)

        clamp = factory.cylinder(math.hypot(5, 5) + 3, clamp_height)\
            .align().by("xmidymidzmin", alu)\
            .do(lambda p: p.bool.union(alu.extrude.make_thick_solid(3)))\
            .do(lambda p: p.bool.common(factory.box_surrounding(p, z_length=alu.xts.z_span)))\
            .cleanup()

        def _make_detented_face(detent_r0, detent_r1):
            detent_angle = math.radians(360.0 / detent_count)
            detent_h_angle = detent_angle * 0.5

            return WireSketcher(*clamp.xts.xy_mid, clamp.xts.z_min)\
                .line_to(x=clamp.xts.x_mid + detent_r0 * math.cos(0),
                         y=clamp.xts.y_mid + detent_r0 * math.sin(0))\
                .line_to(x=clamp.xts.x_mid + detent_r1 * math.cos(detent_angle / 2),
                         y=clamp.xts.y_mid + detent_r1 * math.sin(detent_angle / 2))\
                .line_to(x=clamp.xts.x_mid + detent_r0 * math.cos(detent_angle),
                         y=clamp.xts.y_mid + detent_r0 * math.sin(detent_angle))\
                .close()\
                .get_face_part(cache)\
                .pattern(range(0, detent_count), lambda i, p: p.tr.rz(detent_angle * i, offset=clamp.xts.xyz_mid))\
                .bool.union()\
                .cleanup()\
                .make.face()

        detent_r0 = clamp.xts.x_span / 2 + 1
        detent_r1 = detent_r0 + 5.5
        detent_r2 = detent_r0 + 2

        detent_bottom = _make_detented_face(detent_r0, detent_r1).fillet.fillet2d_verts(1.3)
        detent_center = _make_detented_face(detent_r0, detent_r2)\
            .align().by("zmin", clamp)\
            .tr.mv(dz=clamp_height / 2)\
            .fillet.fillet2d_verts(0.5)
        detent_top = detent_bottom\
            .align().by("zmin", clamp).tr.mv(dz=clamp_height)

        detent = factory.loft([detent_bottom, detent_center, detent_top])

        detent_clearance = factory.loft([
            detent_bottom.extrude.offset(Constants.clearance_mm()),
            detent_center.extrude.offset(Constants.clearance_mm()),
            detent_top.extrude.offset(Constants.clearance_mm())
        ]).make.solid()

        detent = detent.bool.common(
            factory.cylinder(detent_r0 + 3, detent.xts.z_span).align().by("xmidymidzmid", detent)
            .fillet.chamfer_edges(0.5)).cleanup()

        clamp = clamp.bool.union(detent).cleanup()

        clamp = clamp.fillet.fillet_edges(1, {
            *clamp.explore.face.filter_by(lambda p: abs(p.xts.z_mid - detent.xts.z_max) < 0.001)
                                          .get_single()
                                          .explore.wire.get()[1]
                                          .explore.edge.get()
        })

        clamp = clamp.fillet.chamfer_faces(1, {clamp.pick.from_dir(0, 0, -1).first_face()})

        clamp = clamp.bool.cut(alu.extrude.make_thick_solid(Constants.clearance_mm()))

        clamp = clamp.bool.cut(*
            factory.cylinder(2.8 / 2, clamp.xts.z_span)
                .tr.rx(math.radians(90))
                .align().by("xmidymidzmidmax", alu)
                .tr.mv(dz=-5)
            .do_and_add(lambda p: p.tr.rz(math.radians(90), offset=p.xts.xyz_mid))
            .explore.solid.get())

        clamp_outer = factory.cylinder(max(detent_r0, detent_r1, detent_r2) + 3, detent.xts.z_span)\
            .align().by("xmidymid", alu)\
            .align().by("zmin", detent)

        clamp_outer_fastener = factory.cylinder(8, clamp_outer.xts.y_span).tr.rx(math.radians(90))\
            .align().by("xmaxminymidzmid", clamp_outer).tr.mv(dx=1)

        clamp_outer = clamp_outer.extrude.make_thick_solid(5).bool.union(clamp_outer_fastener.extrude.make_thick_solid(5))\
            .alg.project_z().alg.edge_network_to_outer_wire()\
            .extrude.offset(-5)\
            .make.face().extrude.prism(dz=detent_clearance.xts.z_span)\
            .align().by("zmid", detent_clearance)

        clamp_outer = clamp_outer.bool.cut(detent_clearance)

        clamp_outer = clamp_outer.bool.cut(factory.cylinder(4.5, clamp_outer.xts.y_span)
                                           .tr.rx(math.radians(90))
                                           .align().by("xmidymidzmid", clamp_outer_fastener))

        clamp_outer = clamp_outer.bool.cut(*factory.cylinder(2.8 / 2, clamp_outer.xts.z_span)
                                           .align().by("xmidymidzmid", clamp_outer_fastener)
                                           .tr.mv(dy=-clamp_outer.xts.y_span / 3)
                                           .do_and_add(lambda p: p.mirror.y(center_y=clamp_outer.xts.y_mid))
                                           .explore.solid.get())

        clamp_outer = clamp_outer.do(lambda p: p.bool.cut(factory.box_surrounding(p, y_length=5)))

        clamp_outer = LivingHingeFactory(cache).create_living_hinge(
            clamp_outer.explore.solid.get_max(lambda s: s.xts.y_mid).cleanup(),
            clamp_outer.explore.solid.get_min(lambda s: s.xts.y_mid).cleanup(),
            hinge_center_point=(clamp_outer.xts.x_max + 5, clamp_outer.xts.y_mid, clamp_outer.xts.z_min),
            preload_angle=5,
            hinge_generator=CapsuleHingeGenerator(5, 8))\
            .bool.union()\
            .cleanup(concat_b_splines=True, fix_small_face=True)

        clamp_outer = clamp_outer.bool.cut(factory.cylinder(4.5, clamp_outer.xts.y_span)
                                           .tr.rx(math.radians(90))
                                           .align().by("xmidymidzmid", clamp_outer_fastener))
        return clamp.add(clamp_outer)

    @staticmethod
    def _get_snap_fan(cache: PartCache,
                      bolt: Part,
                      cut_part: Part,
                      snap_detent_height: float,
                      detent_count: int) -> Part:
        factory = PartFactory(cache)

        # create the snap pattern that will allow multiple aluminium profiles to fit together
        snap_a1 = factory.vertex(*bolt.xts.xyz_mid).tr.mv(dy=bolt.xts.y_span / 2)
        snap_a2 = factory.vertex(*bolt.xts.xyz_mid).tr.mv(dy=max(cut_part.xts.y_span, cut_part.xts.x_span))

        snap_w = WireSketcher(*snap_a1.xts.xyz_mid).line_to(*snap_a2.xts.xyz_mid).get_wire_part(cache)

        snap = factory.loft([
            snap_w,
            snap_w.tr.rz(math.radians((1 / 6) * 360.0 / detent_count), offset=bolt.xts.xyz_mid),
            snap_w.tr.rz(math.radians((1 / 3) * 360.0 / detent_count), offset=bolt.xts.xyz_mid).tr.mv(
                dz=snap_detent_height),
            snap_w.tr.rz(math.radians((2 / 3) * 360.0 / detent_count), offset=bolt.xts.xyz_mid).tr.mv(
                dz=snap_detent_height),
            snap_w.tr.rz(math.radians((5 / 6) * 360.0 / detent_count), offset=bolt.xts.xyz_mid),
            snap_w.tr.rz(math.radians(1.0 * 360.0 / detent_count), offset=bolt.xts.xyz_mid)
        ], is_solid=False) \
            .pattern(range(0, detent_count),
                     lambda i, p: p.tr.rz(math.radians(i * 360.0 / detent_count), offset=bolt.xts.xyz_mid)) \
            .do(lambda p: factory.shell(*p.explore.face.get())) \
            .cleanup(concat_b_splines=True, fix_small_face=True) \
            .extrude.prism(dz=cut_part.xts.z_span) \
            .align().stack_z1(cut_part) \
            .tr.mv(dz=-snap_detent_height) \
            .make.solid() \
            .cleanup()

        snap_cut = snap.bool.common(factory.box_surrounding(cut_part, x_clearance=100000, y_clearance=100000)) \
            .do(lambda p: factory.compound(
            *[s.bool.common(factory.box_surrounding(s)).cleanup().extrude.make_thick_solid(Constants.clearance_mm() / 2,
                                                                                           join_type=OCC.Core.GeomAbs.GeomAbs_Intersection)
              for s in p.explore.solid.get()]))

        return snap_cut

    def snap_joint_perpendicular_axis(self, detent_count: int) -> Part:
        """
        Axis of rotation is perpendicular to the aluminium rod
        """

        alu = self._base_profile.extrude.prism(dz=50).tr.ry(math.radians(90))
        bolt = self._factory.cylinder(4, alu.xts.z_span) \
            .align().by("xmidymaxminzmid", alu).tr.mv(dy=-3)

        wall_thickness = 3.5

        result = self._factory.box_surrounding(alu.add(bolt), x_clearance=-10).bool.common(alu.bool.union(bolt)) \
            .do(lambda p: self._factory.union(
            *[s.alg.project_z().alg.edge_network_to_outer_wire().align().by("zmin", alu) for s in
              p.explore.solid.get()])) \
            .do(lambda p: self._factory.union(*[w.make.face().extrude.offset(15,
                                                                       join_type=OCC.Core.GeomAbs.GeomAbs_JoinType.GeomAbs_Intersection).make.face()
                                          for w in p.explore.wire.get()])) \
            .cleanup() \
            .extrude.offset(-15) \
            .extrude.offset(wall_thickness) \
            .make.face() \
            .extrude.prism(dz=alu.xts.z_span + wall_thickness * 2) \
            .align().by("zmid", alu) \
            .do(lambda p: p.fillet.chamfer_faces(2, {p.pick.from_dir(0, 0, -1).first_face(),
                                                     p.pick.from_dir(0, 0, 1).first_face()})) \
            .bool.cut(alu.extrude.make_thick_solid(Constants.clearance_mm())) \
            .do(lambda p: p.bool.cut(
            bolt.alg.project_z()
            .alg.edge_network_to_outer_wire()
            .make.face()
            .extrude.prism(dz=p.xts.z_span)
            .extrude.make_thick_solid(Constants.clearance_mm())
            .align().by("zmid", p))) \
            .do(lambda p: p.bool.cut(self._factory.cylinder(2.8 / 2, p.xts.y_span).tr.rx(math.radians(90))
                                     .align().by("xmidymidzmid", p)
                                     .align().stack_x0(bolt, offset=-8)
                                     .do_and_add(lambda pp: pp.mirror.x(center_x=bolt.xts.x_mid))))

        snap_detent_height = 2
        snap_cut = AluExtrusionStockParts._get_snap_fan(self._cache,
                                                    bolt=bolt,
                                                    cut_part=result,
                                                    snap_detent_height=snap_detent_height,
                                                    detent_count=detent_count)

        result_a = result
        cut_count = 0
        for s in snap_cut.explore.solid.get():
            cut_count += 1
            result_a = result_a.bool.cut(s)

        result_b = result
        cut_count = 0
        for s in snap_cut.tr.rz(math.radians(180.0 / detent_count), offset=bolt.xts.xyz_mid).explore.solid.get():
            cut_count += 1
            result_b = result_b.bool.cut(s)

        a_marking = self._factory.text("A", "sans-serif", 1, is_composite_curve=True)\
            .do(lambda p: p.tr.scale(alu.xts.y_span / p.xts.y_span))\
            .align().by("xmidymidzmin", result_a)\
            .align().by("ymax", alu)\
            .extrude.prism(dz=2)

        b_marking = self._factory.text("B", "sans-serif", 1, is_composite_curve=True) \
            .do(lambda p: p.tr.scale(alu.xts.y_span / p.xts.y_span)) \
            .align().by("xmidymidzmin", result_a) \
            .align().by("ymax", alu) \
            .extrude.prism(dz=2)

        result_a = result_a.bool.cut(a_marking)

        result_b = result_b.bool.cut(b_marking)

        result_a = result_a.mirror.z().align().stack_z1(result_b).tr.mv(dz=-snap_detent_height + Constants.clearance_mm())

        return self._factory.compound(
            result_a.name("a"),
            result_b.name("b"))

    def ball_joint(self) -> Part:
        factory = self._factory

        ball = factory.sphere(15)

        male = ball.bool.union(factory.cylinder(ball.xts.x_span / 4, ball.xts.z_span * 1.5)
                               .align().by("xmidymidzmaxmid", ball))

        male = male.fillet.fillet_edges(
            1,
            {*male.explore.edge.filter_by(lambda e: e.xts.z_span < 0.0001 and e.xts.z_mid > male.xts.z_min and e.xts.z_mid < male.xts.z_max).get()})

        female = (factory.sphere(ball.xts.z_span / 2 + 5)
                  .align().by("xmidymidzmid", ball)
                  .do(lambda p: p.bool.union(factory.cylinder(p.xts.x_span / 2, p.xts.z_span / 2)
                                             .align().by("xmidymidzmaxmid", p)))
                  .bool.cut(ball.extrude.make_thick_solid(Constants.clearance_mm())))
        female = female.bool.cut(factory.box_surrounding(female).tr.mv(dz=-female.xts.z_span * 3 / 4))
        female = female.bool.cut(
            factory.cylinder(ball.xts.x_span / 4, female.xts.y_span)
                .tr.rx(math.radians(90))
                .align().by("xmidymidzmid", ball)
                .do(lambda p: p.bool.union(factory.box_surrounding(p, z_length=10000)
                                           .align().by("zmaxmid", p)))
            .align().by("yminmid", female))

        female_joint = (factory.circle(ball.xts.x_span / 2)
                            .align().by("xmidymid", ball)
                            .align().by("zmax", female)
                            .cast.to(female, direction=gp.gp_Dir(0, 0, -1)))

        female = female.bool.union(factory.loft([
            female_joint,
            female_joint.extrude.offset(5).tr.mv(dz=5),
            female_joint.extrude.offset(5).tr.mv(dz=15)
        ]).bool.cut(female).explore.solid.get_max(lambda s: s.xts.z_mid))

        female_extrusion = (self._base_profile.tr.rx(math.radians(90))
                            .align().by("xmaxminyminzmax", female)
                            .extrude.prism(dy=female.xts.y_span)
                            .tr.mv(dx=-3, dz=-3))

        female_base = (female.add(female_extrusion)
                       .do(lambda p: p.bool.common(factory.square_centered(*p.xts.xy_span)
                                                    .align().by("xmidymid", p)
                                                    .align().by("zmid", female_extrusion)))
                       .do(lambda p: factory.union(*[f.extrude.offset(3).make.face() for f in p.explore.face.get()]))
                       .sew.faces()
                       .cleanup()
                       .align().by("zmax", female)
                       .extrude.prism(dz=-female_extrusion.xts.z_span - 6).fillet.chamfer_edges(1))

        female_base = (female_base.bool.cut(female.extrude.make_thick_solid(Constants.clearance_mm() * 1.5))
                       .explore.solid.get_max(lambda s: s.xts.z_mid))

        female_base = female_base.bool.cut(female_extrusion.bool.union(
                                           female_extrusion.pick.from_dir(0, 1, 0).first_face().extrude.prism(dy=-100),
                                           female_extrusion.pick.from_dir(0, -1, 0).first_face().extrude.prism(dy=100)).extrude.make_thick_solid(Constants.clearance_mm()))

        female = female.bool.cut(factory.box_surrounding(female, z_length=Constants.clearance_mm())
                                 .align().by("zmid", ball))

        female_screw = (factory.stacked_cylinder((3, 3), (2.8 / 2, 10))
                        .align().by("xmidymidzmaxmid", ball)
                        .align().by("yminzmin", female.explore.face.get_min(lambda f: f.xts.z_mid))
                        .tr.mv(dy=-0.5))

        female = female.bool.cut(
            female_screw,
            female_screw.tr.rz(math.radians(-120), offset=ball.xts.xyz_mid),
            female_screw.tr.rz(math.radians(120), offset=ball.xts.xyz_mid))

        female_base = female_base.bool.cut(
            factory.cylinder(2.8 / 2, female_base.xts.x_span)
                .tr.ry(math.radians(90))
                .align().by("xmidymid", female_base).align().by("zmid", female_extrusion)
        )

        female = female.bool.cut(
            factory.stacked_cylinder((2.8 / 2, female.xts.z_span), (3, 6)).align().by("xmidymidzmax", female)
        )

        male_extrusion = female_extrusion.align().by("zmin", male).tr.mv(dz=3)

        male = (male.bool.union(
            factory.loft([
                male_extrusion.pick.from_dir(-1, 0, 0).first_face(),
                factory.square_centered(male_extrusion.xts.z_span, male_extrusion.xts.y_span)
                    .tr.ry(math.radians(90))
                    .align().by("xmidymid", male).align().by("zmin", male_extrusion)
                .bool.common(male)
            ]).make.solid()
            .bool.union(male_extrusion).cleanup()
            .do(lambda p: p.bool.common(factory.box_surrounding(p).align().by("zminmid", p)
                                        .pick.from_dir(0, 0, 1)
                                        .first_face()))
            .extrude.offset(3).make.face()
            .align().by("zmin", male)
            .extrude.prism(dz=male_extrusion.xts.z_span + 6)))

        male = (male.bool.cut(male_extrusion.bool.union(
                               male_extrusion.pick.from_dir(0, 1, 0).first_face().extrude.prism(dy=-100),
                               male_extrusion.pick.from_dir(0, -1, 0).first_face().extrude.prism(dy=100)).extrude.make_thick_solid(Constants.clearance_mm()))
                .cleanup())

        male = male.bool.cut(factory.cylinder(2.8 / 2, male.xts.z_span)
                             .tr.ry(math.radians(90))
                             .align().by("xmaxminymidzmid", male_extrusion))

        male = male.bool.cut(factory.box_surrounding(male, z_length=Constants.clearance_mm()).align().by("zmid", ball))

        male = male.bool.cut(factory.stacked_cylinder((3, male.xts.z_span), (2.8 / 2, ball.xts.z_span / 2))
                             .align().by("xmidymidzmax", ball).tr.mv(dz=-5))

        result = factory.compound(
            male.name("male"),
            factory.compound(female.explore.solid.get_max(lambda s: s.xts.z_mid), female_base).name("female"),
            female.explore.solid.get_min(lambda s: s.xts.z_mid).name("female_1")
        )

        return result



if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.getLogger(ezocc.part_manager.__name__).setLevel(level=logging.WARNING)

    cache = InMemoryPartCache()
    factory = PartFactory(cache)

    buggy = WireSketcher().line_to(y=10, label="veto").line_to(x=3, y=5, z=-5, is_relative=True)\
        .get_wire_part(cache)\
        .do_and_add(lambda p: p.mirror.y(p.xts.y_min))\
        .do_and_add(lambda p: p.add(p.mirror.x(center_x=p.xts.x_mid - 5)))\
        .do_and_add(lambda p: WireSketcher(p.xts.x_min + 3, p.xts.y_mid, p.xts.z_max).line_to(x=p.xts.x_max - 3)
                    .get_wire_part(cache))\
        .bool.union()

    vetoed_edges = {e.set_placeable for e in buggy.compound_subpart("veto").explore.edge.get()}

    vetoed_verts = {v.set_placeable for v in
                    buggy.explore.vertex.filter_by(lambda v: abs(v.xts.y_mid - buggy.xts.y_mid) < 0.001).get()}

    def _veto_edge_vert(e, v):
        is_edge_vetoed = e in vetoed_edges
        is_vert_vetoed = v in vetoed_verts

        return is_edge_vetoed and is_vert_vetoed

    AluTubeStockParts(cache, 0.5)\
        .wireframe_to_tubes(buggy, veto_trim_edge_vert=_veto_edge_vert)\
        .preview()
