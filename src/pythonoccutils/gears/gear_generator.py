import importlib
import importlib.resources
import inspect
import logging
import math
import pdb

import OCC.Core.GCE2d
import OCC.Core.Geom2d
import js2py
import typing
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
from OCC.Core.Geom import Geom_CylindricalSurface
from OCC.Core._gp import gp_XOY
from OCC.Core.gp import gp_Pnt2d, gp_Ax3, gp_OZ, gp_OX

import pythonoccutils.gears.gears_js_translated as gear
from pythonoccutils.occutils_python import WireSketcher
from pythonoccutils.part_manager import Part, PartFactory, PartCache, NoOpCacheToken
from pythonoccutils.svg_parser import SVGPathParser

gear_outline_fn = gear.var.own['createGearOutline']['value']

logger = logging.getLogger(__name__)


class GearMath:

    @staticmethod
    def pitch_diameter(module: float, num_teeth: int) -> float:
        return num_teeth * module

    @staticmethod
    def outside_diameter(module: float, num_teeth: int) -> float:
        return module * (num_teeth + 2)

    @staticmethod
    def root_diameter(module: float, num_teeth: int) -> float:
        return module * (num_teeth - 2.5)


class GearSpec:

    def __init__(self, module: float, num_teeth: int, pressure_angle_deg: float = 20):
        self.module = module
        self.num_teeth = num_teeth
        self.pressure_angle_deg = pressure_angle_deg

    @property
    def pitch_diameter(self) -> float:
        return GearMath.pitch_diameter(self.module, self.num_teeth)

    @property
    def outside_diameter(self) -> float:
        return GearMath.outside_diameter(self.module, self.num_teeth)

    @property
    def root_diameter(self) -> float:
        return GearMath.root_diameter(self.module, self.num_teeth)


class GearPairSpec:

    def __init__(self,
                 gear_spec_bull: GearSpec,
                 gear_spec_pinion: GearSpec,
                 center_distance: float,
                 clearance: float = 0):
        self.gear_spec_bull = gear_spec_bull
        self.gear_spec_pinion = gear_spec_pinion
        self.center_distance = center_distance
        self.clearance = clearance

    @staticmethod
    def matched_pair(module: float,
                     num_teeth_bull: int,
                     num_teeth_pinion: int,
                     clearance: float = 0,
                     **kwargs):

        # z = d / m
        pitch_diameter_bull = GearMath.pitch_diameter(module, num_teeth_bull)
        pitch_diameter_pinion = GearMath.pitch_diameter(module, num_teeth_pinion) # num_teeth_pinion * module

        minimum_distance = (pitch_diameter_bull + pitch_diameter_pinion) / 2

        return GearPairSpec(
            GearSpec(module, num_teeth_bull, **kwargs),
            GearSpec(module, num_teeth_pinion, **kwargs),
            minimum_distance,
            clearance)


class InvoluteGearFactory:

    def __init__(self, part_cache: PartCache):
        self._part_cache = part_cache
        self._part_factory = PartFactory(part_cache)

    def create_involute_profile(self, gear_spec: GearSpec) -> Part:

        token = self._part_cache.create_token("involute_gear_factory", "involute_profile", gear_spec,
                                              inspect.getsource(InvoluteGearFactory))

        def _do():
            logger.info("Generating gear...")
            gear_result = gear_outline_fn(gear_spec.module, gear_spec.num_teeth, gear_spec.pressure_angle_deg)

            # generate the svg path string
            logger.info("Creating svg path")
            svg_path = ' '.join(str(s) for s in gear_result.to_python())

            logger.info("Building wire")
            wire = SVGPathParser.parse_wire(svg_path)

            return Part.of_shape(wire).explore.wire.get()[0].with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def create_involute_gear(self, gear_spec: GearSpec, height: float) -> Part:

        token = self._part_cache.create_token("involute_gear_factory",
                                              "involute_gear",
                                              gear_spec, height,
                                              inspect.getsource(InvoluteGearFactory))

        def _do():
            return self.create_involute_profile(gear_spec).make.face().extrude.prism(dz=height)\
                .add(self._part_factory.vertex(0, 0, 0, "center"))\
                .with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def create_involute_gear_pair(self, gear_pair_spec: GearPairSpec, height: float) -> Part:

        token = self._part_cache.create_token("involute_gear_factory",
                                              "involute_gear_pair",
                                              gear_pair_spec,
                                              height,
                                              inspect.getsource(InvoluteGearFactory))

        def _do():
            bull = self.create_involute_profile(gear_pair_spec.gear_spec_bull).make.face().extrude.prism(dz=height).make.solid()\
                .name("body")\
                .add(
                    self._part_factory.vertex(0, 0, 0, "center"),
                    self._part_factory.cylinder(gear_pair_spec.gear_spec_bull.outside_diameter / 2, height).name("clearance")).print()

            pinion = self.create_involute_profile(gear_pair_spec.gear_spec_pinion).make.face().extrude.prism(dz=height).make.solid()\
                .name("body")\
                .add(
                    self._part_factory.vertex(0, 0, 0, "center"),
                    self._part_factory.cylinder(gear_pair_spec.gear_spec_pinion.outside_diameter / 2, height).name("clearance"))\
                .tr.rz(math.radians(360 / (2.0 * gear_pair_spec.gear_spec_pinion.num_teeth)))\
                .tr.mv(dx=0.5 * (gear_pair_spec.gear_spec_pinion.pitch_diameter + gear_pair_spec.gear_spec_bull.pitch_diameter + gear_pair_spec.clearance)).print()

            return self._part_factory.compound(
                bull.name("bull"),
                pinion.name("pinion")).with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def create_bevel_gear(self,
                          gear_spec: GearSpec,
                          hypot_length: float,
                          bevel_angle: float,
                          target_module: float):

        token = self._part_cache.create_token("involute_gear_factory",
                                              "bevel_gear",
                                              [gear_spec, hypot_length, bevel_angle, target_module],
                                              inspect.getsource(InvoluteGearFactory))

        def _do():
            base_profile = self.create_involute_profile(gear_spec)

            top_profile_spec = GearSpec(target_module, gear_spec.num_teeth, gear_spec.pressure_angle_deg)
            top_profile = self.create_involute_profile(top_profile_spec)

            height = hypot_length * math.sin(bevel_angle)

            return self._part_factory.loft([
                base_profile,
                top_profile.tr.mv(dz=height)
            ]).with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def create_bevel_gear_pair(self,
                               gear_pair_spec: GearPairSpec,
                               hypot_length: float,
                               bevel_angle_bull: float):

        # currently I can only get this to work for equal bevel angles . maybe spiral bevels are needed for differing
        # angles ??
        bevel_angle_pinion = bevel_angle_bull

        token = self._part_cache.create_token(
            "involute_gear_factory",
            "bevel_gear_pair",
            gear_pair_spec,
            hypot_length,
            bevel_angle_bull,
            bevel_angle_pinion,
            inspect.getsource(InvoluteGearFactory))

        def _do():
            bull_cone_height = gear_pair_spec.gear_spec_bull.pitch_diameter * 0.5 * math.tan(bevel_angle_bull)
            pinion_cone_height = gear_pair_spec.gear_spec_pinion.pitch_diameter * 0.5 * math.tan(bevel_angle_bull)

            bull_cone_side_length = math.hypot(bull_cone_height, gear_pair_spec.gear_spec_bull.pitch_diameter * 0.5)
            pinion_cone_side_length = math.hypot(pinion_cone_height, gear_pair_spec.gear_spec_pinion.pitch_diameter * 0.5)

            scale_factor_bull = ((bull_cone_side_length - hypot_length) / bull_cone_side_length)
            target_module_bull = gear_pair_spec.gear_spec_bull.module * scale_factor_bull

            scale_factor_pinion = ((pinion_cone_side_length - hypot_length) / pinion_cone_side_length)
            #target_module_pinion = gear_pair_spec.gear_spec_pinion.module * scale_factor_pinion

            bull = self.create_bevel_gear(gear_pair_spec.gear_spec_bull,
                                          hypot_length,
                                          bevel_angle_bull,
                                          target_module_bull)
            pinion = self.create_bevel_gear(gear_pair_spec.gear_spec_pinion,
                                            hypot_length,
                                            bevel_angle_pinion,
                                            target_module_bull)

            #bull_cone = self._part_factory.cone(gear_pair_spec.gear_spec_bull.pitch_diameter / 2,
            #                               gear_pair_spec.gear_spec_bull.pitch_diameter / 2 - math.cos(bevel_angle_bull) * hypot_length,
            #                               math.sin(bevel_angle_bull) * hypot_length)

            #pinion_cone = self._part_factory.cone(gear_pair_spec.gear_spec_pinion.pitch_diameter / 2,
            #                               gear_pair_spec.gear_spec_pinion.pitch_diameter / 2 - math.cos(bevel_angle_pinion) * hypot_length,
            #                               math.sin(bevel_angle_pinion) * hypot_length)

            bull = bull.name("body").add(
                self._part_factory.vertex(0, 0, 0, "center"),
                self._part_factory.cone(gear_pair_spec.gear_spec_bull.outside_diameter / 2,
                                        gear_pair_spec.gear_spec_bull.outside_diameter * scale_factor_bull / 2,
                                        hypot_length * math.sin(bevel_angle_bull)).name("clearance"))

            pinion = pinion.name("body").add(
                self._part_factory.vertex(0, 0, 0, "center"),
                self._part_factory.cone(gear_pair_spec.gear_spec_pinion.outside_diameter / 2,
                                        gear_pair_spec.gear_spec_pinion.outside_diameter * scale_factor_bull / 2,
                                        hypot_length * math.sin(bevel_angle_pinion)).name("clearance"))

            pinion = pinion.tr.rz(math.radians(0.5 * 360 / gear_pair_spec.gear_spec_pinion.num_teeth))
            gear_distance = (target_module_bull * gear_pair_spec.gear_spec_pinion.num_teeth +
                                      target_module_bull * gear_pair_spec.gear_spec_bull.num_teeth + gear_pair_spec.clearance) / 2
            pinion = pinion.tr.mv(dx=gear_distance)

            # rotation helps with visualizing to prevent teeth clipping into each other
            #pinion = pinion.tr.rz(math.radians(1.5 * 360.0 / gear_pair_spec.gear_spec_pinion.num_teeth))

            pinion = pinion.tr.ry(math.radians(-180) + (bevel_angle_pinion + bevel_angle_bull),
                                  offset=((target_module_bull * gear_pair_spec.gear_spec_bull.num_teeth / 2 + gear_pair_spec.clearance / 2), 0, bull.xts.z_max))

            return self._part_factory.compound(bull.name("bull"), pinion.name("pinion"))\
                .with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def create_herringbone_gear(
            self,
            gear_spec: GearSpec,
            height: float,
            sweep_sense: bool = True,
            helix_angle_deg: float = 45,
            chamfer: typing.Optional[float] = None,
            sweep_cycles: int = 1,
            make_solid: bool = True):

        token = self._part_cache.create_token("involute_gear_factory", "create_herringbone_gear",
                                              gear_spec,
                                              height,
                                              sweep_sense,
                                              helix_angle_deg,
                                              chamfer,
                                              sweep_cycles,
                                              make_solid,
                                              inspect.getsource(InvoluteGearFactory))

        def _do():
            profile = self.create_involute_profile(gear_spec)

            spine = WireSketcher(0, 0, 0).line_to(z=height).get_wire_part()

            # create a spiral aux spine to "encourage" OCC to make a helix sweep. unit radius
            logger.info(f"Height of cylinder surface: {height}")

            surf = Geom_CylindricalSurface(gp_Ax3(gp_XOY()), gear_spec.pitch_diameter / 2)

            # the actual angle of the circle that needs to be swept depends on the gear height
            helix_angle_rad = math.radians(helix_angle_deg)
            logger.info(f"Helix angle in degrees: {helix_angle_deg} -> radians: {helix_angle_rad}")

            sweep_distance_du = 0.5 * (height / sweep_cycles) * math.tan(helix_angle_rad)
            logger.info(f"Sweep distance (on pitch diameter) of gear: {sweep_distance_du}")

            sweep_angle_rad = sweep_distance_du / (gear_spec.pitch_diameter / 2)
            logger.info(f"Sweep angle in radians: {sweep_angle_rad}")

            if not sweep_sense:
                sweep_angle_rad *= -1

            mkw = BRepBuilderAPI_MakeWire()
            sweep_height = height / sweep_cycles
            for i in range(0, sweep_cycles):
                height_start = i * sweep_height
                height_mid = (i + 0.5) * sweep_height
                height_end = (i + 1) * sweep_height

                edge0 = BRepBuilderAPI_MakeEdge(
                    OCC.Core.GCE2d.GCE2d_MakeSegment(gp_Pnt2d(sweep_angle_rad, height_start), gp_Pnt2d(0, height_mid)).Value(), surf).Edge()
                edge1 = BRepBuilderAPI_MakeEdge(
                    OCC.Core.GCE2d.GCE2d_MakeSegment(gp_Pnt2d(0, height_mid), gp_Pnt2d(sweep_angle_rad, height_end)).Value(), surf).Edge()

                mkw.Add(edge0)
                mkw.Add(edge1)

            aux_spine = Part(NoOpCacheToken(), mkw.Wire())

            mkps = BRepOffsetAPI_MakePipeShell(spine.shape)
            mkps.SetMode(aux_spine.shape, True)
            mkps.Add(profile.shape)
            mkps.Build()

            if make_solid:
                mkps.MakeSolid()

            result = Part(NoOpCacheToken(), mkps.Shape())

            if chamfer is not None:
                logger.info(f"Applying chamfer: {chamfer}")
                cylinder_common = PartFactory.cylinder(gear_spec.outside_diameter / 2, height).fillet.chamfer_edges(chamfer)

                result = result.bool.common(cylinder_common)

            return result.with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)


def translate_js_lib_to_python():
    """
    Translation of the js source to python for easy use.
    """

    with importlib.resources.open_text(package="pythonoccutils.gears", resource="gears.js") as text:
        js_source = text.read()

    translate = js2py.translate_js6(js_source)

    pdb.set_trace()

