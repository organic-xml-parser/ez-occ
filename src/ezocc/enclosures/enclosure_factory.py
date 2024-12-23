import inspect
import logging
import math

import typing
from OCC.Core.gp import gp_Pnt2d, gp_Vec2d, gp_Vec, gp_Pnt, gp_XY, gp_Ax1, gp_Dir, gp_Ax2, gp_XOY, gp

from ezocc.cad.visualization_widgets.visualization_widgets import PartWidgets
from ezocc.constants import Constants
from ezocc.enclosures.shadow_line import ShadowLine
from ezocc.humanization import Humanize
from ezocc.occutils_python import InterrogateUtils, WireSketcher
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import PartCache, Part, PartFactory
import OCC.Core.BRep
import OCC.Core.BRepAdaptor
import OCC.Core.Geom2d
import OCC.Core.BRepBuilderAPI


logger = logging.getLogger(__name__)


class ShadowLineParams:

    def __init__(self, origin: gp_Pnt, out_dir: gp_Dir, up_dir: gp_Dir, wall_thickness: float):
        self.origin = origin
        self.out_dir = out_dir
        self.up_dir = up_dir
        self.wall_thickness = wall_thickness


class ShadowLineGenerator:

    def create_wire(self, cache: PartCache, shadow_line_params: ShadowLineParams) -> Part:
        raise NotImplementedError()


class DefaultShadowLineGenerator(ShadowLineGenerator):

    def __init__(self,
                 invert: bool = False,
                 shadow_line_height: typing.Optional[float] = None):
        self.invert = invert
        self.shadow_line_height = shadow_line_height

    def create_wire(self, cache: PartCache, shadow_line_params: ShadowLineParams) -> Part:
        out_dir = gp_Vec(*Humanize.xyz(shadow_line_params.out_dir))
        up_dir = gp_Vec(*Humanize.xyz(shadow_line_params.up_dir))
        wall_thickness = shadow_line_params.wall_thickness
        origin = shadow_line_params.origin

        if self.invert:
            out_dir = out_dir.Reversed()

        shadow_line_height = self.shadow_line_height if self.shadow_line_height is not None else wall_thickness

        start_point = origin.Translated(out_dir.Scaled(-wall_thickness * 2)).Translated(up_dir.Scaled(-shadow_line_height / 2))

        return WireSketcher(*Humanize.xyz(start_point)) \
            .line_to(*Humanize.xyz(out_dir.Scaled(wall_thickness * 1.5)), is_relative=True) \
            .line_to(*Humanize.xyz(up_dir.Scaled(shadow_line_height)), is_relative=True) \
            .line_to(*Humanize.xyz(out_dir.Scaled(wall_thickness)), is_relative=True) \
            .get_wire_part(cache)


class FastenerTool:

    def apply_fasteners(self, cache: PartCache, enclosure: Part) -> Part:

        raise NotImplementedError()


class DefaultFastenerTool(FastenerTool):

    def __init__(self, fasten_from_top=True):
        self._fasten_from_top = fasten_from_top

    def apply_fasteners(self, cache: PartCache, enclosure: Part) -> Part:
        factory = PartFactory(cache)

        fastener = factory.cylinder(3, 3).do(lambda p: p.bool.union(factory.cylinder(2.8 / 2, 15).align().stack_z0(p)))\
            .cleanup()

        if not self._fasten_from_top:
            fastener = fastener.tr.rx(math.radians(180))\
                .align().by("zmin", enclosure.sp("bottom"))
        else:
            fastener = fastener.align().by("zmax", enclosure.sp("top"))

        fasteners = []

        volume_name = "bottom_usable_volume" if self._fasten_from_top else "top_usable_volume"

        standoff = factory.box(7, 7, enclosure.sp(volume_name).xts.z_span)\
            .do(lambda p: p.fillet.fillet_edges(4, {p.explore.edge.get_max(lambda e: e.xts.x_mid + e.xts.y_mid)}))\
            .do(lambda p: p.add(factory.vertex(p.xts.x_min + 3, p.xts.y_min + 3, p.xts.z_mid).name("fastener_point")))

        face = enclosure.sp(volume_name).pick.from_dir(0, 0, 1 if self._fasten_from_top else -1).first_face()

        standoffs = []
        z_offset = 0
        for edge in face.make.wire().explore.explore_wire_edges_ordered().get()[0:]:
            v0, v1 = InterrogateUtils.line_points(edge.shape)
            tv0, tv1 = InterrogateUtils.line_tangent_points(edge.shape)

            # create an axis based off the edge angle
            axis = gp_Ax2(gp_Pnt(*Humanize.xyz(v0)), gp_Dir(tv0))
            rotation_angle = math.atan2(tv0.Y(), tv0.X())

            standoff_unit = standoff.align().z_min_to(z=v0.Z()) if self._fasten_from_top else standoff.align().z_max_to(z=v0.Z())

            standoff_unit = standoff_unit\
                .align().x_min_to(x=v0.X())\
                .align().y_min_to(y=v0.Y())\
                .tr.mv(dz=z_offset)\
                .tr.rz(rotation_angle, offset=Humanize.xyz(v0))

            standoffs.append(standoff_unit.explore.solid.get()[0])

            fasteners.append(fastener.align().by("xmidymid", standoff_unit.sp("fastener_point")))

            standoffs[-1] = standoffs[-1]

        standoffs = [factory.compound(
            s.bool.common(enclosure.sp(volume_name)).clear_subshape_map().bool.cut(*fasteners).name("body"),
            s.name("clearance")) for s in standoffs]

        def add_standoffs(top_or_bottom):
            return factory.compound(
                top_or_bottom.clear_subshape_map().name("enclosure_body"),
                factory.compound(*standoffs).name("standoffs"))

        result = enclosure\
            .do_on("top", consumer=lambda p: add_standoffs(p) if not self._fasten_from_top else p.bool.cut(*fasteners))\
            .do_on("bottom", consumer=lambda p: add_standoffs(p) if self._fasten_from_top else p.bool.cut(*fasteners))

        return result.print()


class CutPlaneGenerator:

    def get_cut_plane(self, result: Part) -> Part:
        """
        @return: a plane or shell which may be used to slice the enclosure into two parts.
        """
        raise NotImplementedError()


class FlatCutPlaneGenerator(CutPlaneGenerator):

    def __init__(self, z_offset: typing.Optional[float]=None):
        self.z_offset = z_offset

    def get_cut_plane(self, result: Part) -> Part:
        interior, exterior = \
            result.explore.shell.order_by(lambda s: InterrogateUtils.volume_properties(s.make.solid().shape).Mass()).get()

        cut_face = PartFactory(result.cache_token.get_cache())\
            .square_centered(exterior.xts.x_span + 1, exterior.xts.y_span + 1)\
            .make.face()

        if self.z_offset is None:
            cut_face = cut_face.align().by("xmidymidzmid", interior)
        else:
            cut_face = cut_face.align().by("xmidymidzmin", interior).tr.mv(dz=self.z_offset)

        return cut_face


class EnclosureWallSpec:

    def __init__(self,
                 thickness: float,
                 z_min_thickness: float,
                 z_max_thickness: float,
                 cut_plane_generator: typing.Optional[CutPlaneGenerator] = None,
                 shadow_line_generator: typing.Optional[ShadowLineGenerator] = None):
        self.thickness = thickness
        self.z_min_thickness = z_min_thickness
        self.z_max_thickness = z_max_thickness

        if bool(cut_plane_generator is None) != bool(shadow_line_generator is None):
            raise ValueError("Cut plane/Shadow line generators must both be specified or both be None.")

        self.cut_plane_generator = cut_plane_generator
        self.shadow_line_generator = shadow_line_generator

class ExtrusionModifier:

    def modify_extruded_shape(self, part: Part, is_inner_body: bool) -> Part:
        raise NotImplementedError()


class DefaultExtrusionModifier(ExtrusionModifier):

    def modify_extruded_shape(self, part: Part, is_inner_body: bool) -> Part:
        return part


class ChamferExtrusionModifier(ExtrusionModifier):

    def __init__(self, chamfer_amount: float = 1):
        self.chamfer_amount = chamfer_amount

    def modify_extruded_shape(self, part: Part, is_inner_body: bool) -> Part:
        return part.fillet.chamfer_edges(self.chamfer_amount,
                                         {
                                             *part.explore.face.get_max(lambda f: f.xts.z_mid).explore.edge.get(),
                                             *part.explore.face.get_min(lambda f: f.xts.z_mid).explore.edge.get()
                                         })


class EnclosureFactory:

    def __init__(self, cache: PartCache):
        self._cache = cache

    def create_enclosure(self,
                         face: Part,
                         z_height: float,
                         wall_spec: EnclosureWallSpec,
                         fastener_tool: typing.Optional[FastenerTool],
                         extrusion_modifier: typing.Optional[ExtrusionModifier]):

        fastener_tool_source = inspect.getsource(fastener_tool.__class__) if fastener_tool is not None else None
        extrusion_modifier_source = inspect.getsource(extrusion_modifier.__class__) if extrusion_modifier is not None else None

        token = self._cache.create_token(inspect.getsource(EnclosureFactory),
                                         inspect.getsource(wall_spec.__class__),
                                         inspect.getsource(EnclosureFactory._create_enclosure),
                                         fastener_tool_source,
                                         extrusion_modifier_source,
                         face,
                         z_height,
                         wall_spec,
                         fastener_tool,
                         extrusion_modifier)

        def _do():
            logger.info("Regenerating enclosure...")
            result = self._create_enclosure(face, z_height, wall_spec, fastener_tool, extrusion_modifier)\
                .with_cache_token(token)

            return result

        return self._cache.ensure_exists(token, _do)

    def _create_enclosure(self,
                          face: Part,
                          z_height: float,
                          wall_spec: EnclosureWallSpec,
                          fastener_tool: typing.Optional[FastenerTool] = None,
                          extrusion_modifier: typing.Optional[ExtrusionModifier] = None):

        if not face.inspect.is_face():
            raise ValueError("Expected face input part")

        wall_0 = face
        wall_1 = face.extrude.offset(wall_spec.thickness).make.face().tr.mv(dz=-wall_spec.z_min_thickness)

        body_0 = wall_0.extrude.prism(dz=z_height)
        body_1 = wall_1.extrude.prism(dz=z_height + wall_spec.z_min_thickness + wall_spec.z_max_thickness)

        body_inner = body_0 if wall_spec.thickness > 0 else body_1
        body_outer = body_1 if wall_spec.thickness > 0 else body_0

        if extrusion_modifier is not None:
            body_inner = extrusion_modifier.modify_extruded_shape(body_inner, True)
            body_outer = extrusion_modifier.modify_extruded_shape(body_outer, False)

        result = body_outer.bool.cut(body_inner)

        if wall_spec.shadow_line_generator is None:
            return result

        cut_plane = wall_spec.cut_plane_generator.get_cut_plane(result)

        shadow_line_spine = ShadowLine.shadow_line_spine(result, cut_plane)\
            .cleanup(concat_b_splines=True, fix_small_face=True).cleanup.build_curves_3d()

        origin, wall_out, wall_up = ShadowLine.find_edge_normal_vector(shadow_line_spine, cut_plane)

        shadow_line = wall_spec.shadow_line_generator.create_wire(
            self._cache, ShadowLineParams(origin, wall_out, wall_up, wall_spec.thickness))

        if not shadow_line.inspect.is_wire():
            raise ValueError("Expected shadow line generator to produce a wire")

        shadow_line = shadow_line\
            .extrude.offset(Constants.clearance_mm() / 2)\
            .make.face()\
            .cleanup(concat_b_splines=True, fix_small_face=True)\
            .cleanup.build_curves_3d()

        shadow_line = shadow_line.loft.pipe(
            shadow_line_spine,
            transition_mode=OCC.Core.BRepBuilderAPI.BRepBuilderAPI_TransitionMode.BRepBuilderAPI_RoundCorner
        ).make.solid().cleanup().cleanup.fix_solid().make.solid()

        result = result.bool.cut(shadow_line)

        if len(result.explore.solid.get()) != 2:
            logger.warning("Cut did not result in two solids")
            result.preview()
            raise ValueError("Cut did not result in two solids")

        bottom, top = result.explore.solid.order_by(lambda s: s.xts.z_mid).get()

        top_usable_volume = body_inner\
            .extrude.make_thick_solid(Constants.clearance_mm())\
            .cleanup().make.solid()\
            .bool.common(bottom)\
            .cleanup().make.solid()\
            .extrude.make_thick_solid(Constants.clearance_mm())\
            .cleanup().make.solid()

        top_usable_volume = body_inner.bool.cut(top_usable_volume)

        bottom_usable_volume = body_inner \
            .extrude.make_thick_solid(Constants.clearance_mm()) \
            .cleanup().make.solid() \
            .bool.common(top) \
            .cleanup().make.solid() \
            .extrude.make_thick_solid(Constants.clearance_mm()) \
            .cleanup().make.solid()

        bottom_usable_volume = body_inner.bool.cut(bottom_usable_volume)

        result = PartFactory(self._cache).compound(
            top.name("top"),
            bottom.name("bottom"),
            top_usable_volume.name("top_usable_volume"),
            bottom_usable_volume.name("bottom_usable_volume")
        )

        if fastener_tool is not None:
            result = fastener_tool.apply_fasteners(self._cache, result)

        return result
