import argparse
import importlib
import importlib.resources
import inspect
import logging
import math
import pdb
import typing

import js2py
from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Dir, gp_Ax1

import ezocc.gears.gears_js_translated as gear
from ezocc.occutils_python import WireSketcher, InterrogateUtils
from ezocc.part_manager import Part, PartFactory, PartCache, PartDriver
from ezocc.svg_parser import SVGPathParser

gear_outline_fn = gear.var.own['createGearOutline']['value']
gear_int_outline_fn = gear.var.own['createIntGearOutline']['value']

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

    def __init__(self, module: float,
                 num_teeth: int,
                 pressure_angle_deg: float = 20,
                 preview_mode: bool = False):
        """
        @param module:
        @param num_teeth:
        @param pressure_angle_deg:
        @param preview_mode: Since gear generation can be slow due to model complexity, this option allows for an
        alternative course representation to be produced for the gear body.
        """
        self.module = module
        self.num_teeth = num_teeth
        self.pressure_angle_deg = pressure_angle_deg
        self.preview_mode = preview_mode

    @property
    def pitch_diameter(self) -> float:
        return GearMath.pitch_diameter(self.module, self.num_teeth)

    @property
    def outside_diameter(self) -> float:
        return GearMath.outside_diameter(self.module, self.num_teeth)

    @property
    def root_diameter(self) -> float:
        return GearMath.root_diameter(self.module, self.num_teeth)

    def as_dict(self) -> typing.Dict:
        return {
            "module": self.module,
            "num_teeth": self.num_teeth,
            "pressure_angle_deg": self.pressure_angle_deg,
            "pitch_diameter": self.pitch_diameter,
            "outside_diameter": self.outside_diameter,
            "root_diameter": self.root_diameter,
            "preview_mode": self.preview_mode
        }


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

    @property
    def bull_to_pinion_ratio(self) -> float:
        return self.gear_spec_bull.num_teeth / self.gear_spec_pinion.num_teeth

    @property
    def pinion_to_bull_ratio(self) -> float:
        return self.gear_spec_pinion.num_teeth / self.gear_spec_bull.num_teeth

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


class PlanetaryGearSpec:

    def __init__(self,
                 sun: GearSpec,
                 planets: GearSpec,
                 num_planets: int,
                 ring: GearSpec,
                 clearance: float = 0):
        self._sun = sun
        self._planets = planets
        self._num_planets = num_planets
        self._ring = ring
        self._clearance = clearance

        if num_planets < 1:
            raise ValueError("num_planets must be > 0")

        if self._sun.module != self._planets.module or self._sun.module != self._ring.module:
            raise ValueError("Gear modules must be consistent.")

        if self._ring.num_teeth != (2 * self._planets.num_teeth + self._sun.num_teeth):
            raise ValueError("Number of teeth on ring gear does not satisfy R = 2P + S")

    @staticmethod
    def with_reduction(module: float,
                       reduction: float,
                       num_planets: int,
                       num_teeth_sun: int,
                       clearance: float = 0):
        if reduction <= 0 or reduction >= 1:
            raise ValueError("Reduction should be between 0..1 exclusive")

        num_teeth_ring: int = int(num_teeth_sun / reduction + num_teeth_sun)
        num_teeth_planet: int = int((num_teeth_ring - num_teeth_sun) / 2)

        if num_teeth_sun % num_planets != 0:
            raise ValueError("Number of sun teeth should be divisible by planet number")

        if num_teeth_ring % num_planets != 0:
            raise ValueError("Number of ring teeth should be divisible by planet number")

        return PlanetaryGearSpec(
            sun=GearSpec(module, num_teeth_sun),
            planets=GearSpec(module, num_teeth_planet),
            num_planets=num_planets,
            ring=GearSpec(module, num_teeth_ring),
            clearance=clearance)

    @property
    def ring(self) -> GearSpec:
        return self._ring

    @property
    def sun(self) -> GearSpec:
        return self._sun

    @property
    def planets(self) -> GearSpec:
        return self._planets

    @property
    def num_planets(self) -> int:
        return self._num_planets

    @property
    def clearance(self) -> float:
        return self._clearance


class InvoluteRackFactory:
    # source: https://khkgears.net/new/gear_knowledge/gear_technical_reference/involute_gear_profile.html

    def __init__(self, cache: PartCache):
        self._cache = cache

    def create_involute_rack_profile(self, gear_spec: GearSpec):

        token = self._cache.create_token(gear_spec, inspect.getsource(InvoluteRackFactory))

        def _do():

            factory = PartFactory(self._cache)

            root_clearance = 0.25 * gear_spec.module

            period = math.pi * gear_spec.module
            dedendum_fillet_radius = 0.38 * gear_spec.module

            working_depth = 2 * gear_spec.module
            tooth_slope_length = working_depth / math.cos(math.radians(gear_spec.pressure_angle_deg))
            tooth_slope_dx = tooth_slope_length * math.sin(math.radians(gear_spec.pressure_angle_deg))

            tooth_profile = (WireSketcher()
                             .line_to(x=tooth_slope_dx, y=working_depth, is_relative=True)
                             .get_wire_part(self._cache)
                             .do_and_add(lambda p: p.mirror.x(center_x=p.xts.x_mid + period * 0.25)))

            top_verts = (tooth_profile.explore.vertex
                         .order_by(lambda v: v.xts.y_mid)
                         .get()[-2:])

            tooth_profile = tooth_profile.add(
                WireSketcher(*top_verts[0].xts.xyz_mid)
                    .line_to(*top_verts[1].xts.xyz_mid)
                .get_wire_part(self._cache))

            dedendum_fillet = (factory.circle_arc(
                dedendum_fillet_radius,
                0,
                -math.radians(90 - gear_spec.pressure_angle_deg)).tr.rz(-math.radians(gear_spec.pressure_angle_deg))
                               .align().by("xmaxminymaxmin", tooth_profile))

            tooth_profile = tooth_profile.add(
                dedendum_fillet,
                dedendum_fillet.mirror.x(center_x=tooth_profile.xts.x_mid)
            )

            tooth_profile = tooth_profile.add(
                WireSketcher(tooth_profile.xts.x_min, tooth_profile.xts.y_min, tooth_profile.xts.z_mid)
                .line_to(x=tooth_profile.xts.x_max)
                .get_wire_part(self._cache)
            )

            tooth_profile = (factory.union(*tooth_profile.explore.edge.get())
                             .make.wire()
                             .make.face()
                             .cleanup())

            result = tooth_profile.incremental_pattern(
                range(0, gear_spec.num_teeth),
                lambda p: p.tr.mv(dx=period))

            pitch_line = (WireSketcher(result.xts.x_min,
                                      result.xts.y_min + root_clearance + working_depth / 2,
                                      result.xts.z_mid)
                          .line_to(x=result.xts.x_max).get_wire_part(self._cache))

            pitch_perpendicular_line = (WireSketcher(*pitch_line.xts.xyz_mid).line_to(y=1, is_relative=True)
                                        .get_wire_part(self._cache))

            result = factory.compound(result.name("body"),
                                      pitch_line.name("pitch_line"),
                                      pitch_perpendicular_line.name("pitch_perpendicular_line"))

            for k, v in gear_spec.as_dict().items():
                result = result.annotate(f"gear_spec/{k}", v)

            return result.with_driver(RackDriver).with_cache_token(token)

        return self._cache.ensure_exists(token, _do)


class InvoluteGearFactory:

    def __init__(self, part_cache: PartCache):
        self._part_cache = part_cache
        self._part_factory = PartFactory(part_cache)

    def _add_gear_local_axes(self, gear: Part, gear_spec: GearSpec) -> Part:
        if "center" in gear.subshapes.map.keys():
            raise ValueError("Gear is already annotated with center etc.")

        gear = gear.add(WireSketcher().line_to(0, 0, 1).get_wire_part(self._part_cache).name("rotation_axis"))
        gear = gear.insert(WireSketcher().line_to(1, 0, 0).get_wire_part(self._part_cache).name("local_x"))
        gear = gear.insert(WireSketcher().line_to(0, 1, 0).get_wire_part(self._part_cache).name("local_y"))
        gear = gear.insert(self._part_factory.vertex(0, 0, 0).name("center"))

        for k, v in gear_spec.as_dict().items():
            gear = gear.annotate(f"gear_spec/{k}", v)

        return gear

    def create_int_involute_profile(self, gear_spec: GearSpec) -> Part:
        token = self._part_cache.create_token("involute_gear_factory", "int_involute_profile", gear_spec,
                                              inspect.getsource(InvoluteGearFactory))

        def _do():
            logger.info("Generating gear...")
            gear_result = gear_int_outline_fn(gear_spec.module,
                                              gear_spec.num_teeth,
                                              gear_spec.pressure_angle_deg)

            # generate the svg path string
            logger.info("Creating svg path")
            svg_path = ' '.join(str(s) for s in gear_result.to_python())

            logger.info("Building wire")
            svg_result = SVGPathParser.parse_wire(svg_path)

            result = Part.of_shape(svg_result).make.wire()

            result = result.name("body")

            return self._add_gear_local_axes(result, gear_spec).with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def create_involute_profile(self, gear_spec: GearSpec) -> Part:

        token = self._part_cache.create_token("involute_gear_factory",
                                              "involute_profile",
                                              gear_spec,
                                              inspect.getsource(InvoluteGearFactory))

        def _do():
            if gear_spec.preview_mode:
                return self._part_factory.polygon(gear_spec.pitch_diameter / 2, gear_spec.num_teeth).sp("body") \
                    .do(lambda p: self._add_gear_local_axes(p, gear_spec)) \
                    .with_cache_token(token)

            logger.info("Generating gear...")
            gear_result = gear_outline_fn(gear_spec.module, gear_spec.num_teeth, gear_spec.pressure_angle_deg)

            # generate the svg path string
            logger.info("Creating svg path")
            svg_path = ' '.join(str(s) for s in gear_result.to_python())

            logger.info("Building wire")
            wire = SVGPathParser.parse_wire(svg_path)

            result = Part.of_shape(wire).explore.wire.get()[0]

            result = result.name("body")

            return self._add_gear_local_axes(result, gear_spec).with_driver(GearDriver).with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def create_involute_gear(self, gear_spec: GearSpec, height: float) -> Part:

        token = self._part_cache.create_token("involute_gear_factory",
                                              "involute_gear",
                                              gear_spec, height,
                                              inspect.getsource(InvoluteGearFactory))

        def _do():
            return self._add_gear_local_axes(
                self.create_involute_profile(gear_spec).sp("body").make.face().extrude.prism(dz=height), gear_spec) \
                .with_driver(GearDriver) \
                .with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def create_planetary_gear_set(self, gear_spec: PlanetaryGearSpec) -> Part:

        token = self._part_cache.create_token("involute_gear_factory",
                                              "create_planetary_gear_set",
                                              gear_spec,
                                              inspect.getsource(InvoluteGearFactory))

        def _do():
            logger.info("Creating planetary gear: ring")
            ring = self.create_int_involute_profile(gear_spec.ring)

            logger.info("Creating planetary gear: planet")
            planet = self.create_involute_profile(gear_spec.planets)\
                .tr.rz(math.radians(180 / gear_spec.planets.num_teeth))

            logger.info("Creating planetary gear: ring")
            sun = self.create_involute_profile(gear_spec.sun)

            import OCC.Core.GeomAbs

            if gear_spec.clearance != 0:
                sun = sun.do_on("body", consumer=lambda p: p.extrude.offset(-gear_spec.clearance / 2))
                planet = planet.do_on("body", consumer=lambda p: p.extrude.offset(-gear_spec.clearance / 2))

                # for some reason with join_type == Arc, I was running into problems here
                ring = ring.do_on("body", consumer=lambda p: p.extrude.offset(gear_spec.clearance / 2, join_type=OCC.Core.GeomAbs.GeomAbs_JoinType.GeomAbs_Intersection))

            r_planet = (gear_spec.sun.pitch_diameter + gear_spec.planets.pitch_diameter) / 2

            planets = planet.tr.mv(dx=r_planet)\
                .pattern(
                range(0, gear_spec.num_planets),
                lambda i, p: p.tr.rz(math.radians(i * 360 / gear_spec.num_planets)).name(str(i)))

            return self._part_factory.compound(
                sun.name("sun"), planets.name("planets"), ring.name("ring")).with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def create_involute_gear_pair(self, gear_pair_spec: GearPairSpec, height: float) -> Part:

        token = self._part_cache.create_token("involute_gear_factory",
                                              "involute_gear_pair",
                                              gear_pair_spec,
                                              height,
                                              inspect.getsource(InvoluteGearFactory))

        def _do():
            bull = self.create_involute_profile(gear_pair_spec.gear_spec_bull).sp("body").make.face().extrude.prism(dz=height).make.solid()\
                .name("body")\
                .do(lambda p: self._add_gear_local_axes(p, gear_pair_spec.gear_spec_bull))\
                .insert(self._part_factory.cylinder(gear_pair_spec.gear_spec_bull.outside_diameter / 2, height).name("clearance"))

            pinion = self.create_involute_profile(gear_pair_spec.gear_spec_pinion).sp("body").make.face().extrude.prism(dz=height).make.solid()\
                .name("body")\
                .do(lambda p: self._add_gear_local_axes(p, gear_pair_spec.gear_spec_pinion))\
                .insert(self._part_factory.cylinder(gear_pair_spec.gear_spec_pinion.outside_diameter / 2, height).name("clearance"))\
                .tr.rz(math.radians(360 / (2.0 * gear_pair_spec.gear_spec_pinion.num_teeth)))\
                .tr.mv(dx=0.5 * (gear_pair_spec.gear_spec_pinion.pitch_diameter + gear_pair_spec.gear_spec_bull.pitch_diameter + gear_pair_spec.clearance))

            return self._part_factory.compound(
                bull.with_driver(GearDriver).name("bull"),
                pinion.with_driver(GearDriver).name("pinion")).with_cache_token(token)

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
            base_profile = self.create_involute_profile(gear_spec).sp("body")

            top_profile_spec = GearSpec(target_module, gear_spec.num_teeth, gear_spec.pressure_angle_deg)
            top_profile = self.create_involute_profile(top_profile_spec).sp("body")

            height = hypot_length * math.sin(bevel_angle)

            return self._part_factory.loft([
                base_profile,
                top_profile.tr.mv(dz=height)
            ])\
                .do(lambda p: self._add_gear_local_axes(p, gear_spec))\
                .with_driver(GearDriver).with_cache_token(token)

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
                self._part_factory.cone(gear_pair_spec.gear_spec_bull.outside_diameter / 2,
                                        gear_pair_spec.gear_spec_bull.outside_diameter * scale_factor_bull / 2,
                                        hypot_length * math.sin(bevel_angle_bull)).name("clearance"))

            pinion = pinion.name("body").add(
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

            return self._part_factory.compound(
                bull.with_driver(GearDriver).name("bull"),
                pinion.with_driver(GearDriver).name("pinion"))\
                .with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def create_herringbone_gear_pair(self,
                                     gear_pair_spec: GearPairSpec,
                                     height: float,
                                     helix_angle_deg: float = 45,
                                     chamfer: typing.Optional[float] = None,
                                     sweep_sense: bool = True,
                                     make_solid: bool = True):

        token = self._part_cache.create_token("involute_gear_factory", "create_herringbone_gear_pair",
                                              gear_pair_spec,
                                              height,
                                              sweep_sense,
                                              helix_angle_deg,
                                              chamfer,
                                              make_solid,
                                              inspect.getsource(InvoluteGearFactory))

        def _do():

            pinion = self.create_herringbone_gear(gear_pair_spec.gear_spec_pinion,
                                                  height=height,
                                                  sweep_sense=sweep_sense,
                                                  helix_angle_deg=helix_angle_deg,
                                                  chamfer=chamfer,
                                                  make_solid=make_solid)

            bull = self.create_herringbone_gear(gear_pair_spec.gear_spec_bull,
                                                  height=height,
                                                  sweep_sense=not sweep_sense,
                                                  helix_angle_deg=helix_angle_deg,
                                                  chamfer=chamfer,
                                                  make_solid=make_solid)

            pinion = pinion.tr.rz(math.radians(360 / (2.0 * gear_pair_spec.gear_spec_pinion.num_teeth)))\
                .tr.mv(dx=0.5 * (gear_pair_spec.gear_spec_pinion.pitch_diameter + gear_pair_spec.gear_spec_bull.pitch_diameter + gear_pair_spec.clearance))

            return self._part_factory.compound(
                bull.with_driver(GearDriver).name("bull"),
                pinion.with_driver(GearDriver).name("pinion")).with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)

    def create_herringbone_gear(
            self,
            gear_spec: GearSpec,
            height: float,
            sweep_sense: bool = True,
            helix_angle_deg: float = 45,
            chamfer: typing.Optional[float] = None,
            make_solid: bool = True):

        token = self._part_cache.create_token("involute_gear_factory", "create_herringbone_gear",
                                              gear_spec,
                                              height,
                                              sweep_sense,
                                              helix_angle_deg,
                                              chamfer,
                                              make_solid,
                                              inspect.getsource(InvoluteGearFactory))

        def extrude_gear_profile(gear: Part, sense: bool) -> Part:
            gear = gear.make.face()

            pitch_dia = gear_spec.pitch_diameter

            helix = self._part_factory.helix_by_angle(
                height / 2,
                pitch_dia,
                helix_angle=math.radians(45 if sense else -45))
            helix = helix.add(helix.mirror.z().align().stack_z0(helix))\
                .bool.union()\
                .cleanup(concat_b_splines=True)\
                .cleanup.fuse_wires()\
                .print()\
                .make.wire()\
                .align().stack_z1(gear)\
                .cleanup.build_curves_3d()

            spine = WireSketcher().line_to(z=height, is_relative=True).get_wire_part(self._part_cache)

            gear = gear.cleanup.build_curves_3d()
            gear = gear.loft.pipe(spine_part=spine, aux_spine=helix)

            return gear

        def _do():
            profile = self.create_involute_profile(gear_spec)

            result = extrude_gear_profile(profile.sp("body"), sense=sweep_sense)

            if chamfer is not None:
                logger.info(f"Applying chamfer: {chamfer}")
                cylinder_common = self._part_factory.cylinder(gear_spec.outside_diameter / 2, height).fillet.chamfer_edges(chamfer)

                result = result.bool.common(cylinder_common)

            clearance = self._part_factory.cylinder(gear_spec.outside_diameter / 2, height)

            return profile.do_on("body", consumer=lambda p: result).insert(clearance.name("clearance"))\
                .with_driver(GearDriver)\
                .with_cache_token(token)

        return self._part_cache.ensure_exists(token, _do)


class GearDriver(PartDriver):

    def __init__(self, part: Part):
        super().__init__(part)

    @property
    def center(self) -> typing.Tuple[float, float, float]:
        return self.part.sp("center").xts.xyz_mid

    @property
    def gear_spec(self) -> GearSpec:
        return GearSpec(
            module=float(self.part.annotation("gear_spec/module")),
            num_teeth=int(self.part.annotation("gear_spec/num_teeth")),
            pressure_angle_deg=float(self.part.annotation("gear_spec/pressure_angle_deg")))

    def to(self, other: Part) -> Part:
        return self.part.align("center").by("xmidymidzmid", other.sp("center"))

    def get_rotation_axis(self) -> gp_Ax1:
        r0, r1 = InterrogateUtils.line_points(self.part.sp("rotation_axis").explore.edge.get()[0].shape)

        return gp_Ax1(
            gp_Pnt(*self.part.sp("center").xts.xyz_mid),
            gp_Dir(
                r1.X() - r0.X(),
                r1.Y() - r0.Y(),
                r1.Z() - r0.Z()))

    def get_local_x(self) -> gp_Vec:
        r0, r1 = InterrogateUtils.line_points(self.part.sp("local_x").explore.edge.get()[0].shape)
        return gp_Vec(r0, r1)

    def get_local_y(self) -> gp_Vec:
        r0, r1 = InterrogateUtils.line_points(self.part.sp("local_y").explore.edge.get()[0].shape)
        return gp_Vec(r0, r1)

    def single_tooth_rotation_radians(self) -> float:
        self_spec = self.gear_spec
        return 2.0 * math.pi / self_spec.num_teeth

    def rotate(self, tooth_count: float) -> Part:
        return self.part.tr.rotate(
            angle=tooth_count * self.single_tooth_rotation_radians(),
            ax1=self.get_rotation_axis())

    def position_with(self, other_gear_part: Part, clearance: float = 0) -> Part:
        self_spec = self.gear_spec
        other_spec = other_gear_part.driver(GearDriver).gear_spec

        if self_spec.module != other_spec.module:
            raise ValueError("Incompatible gear spec modules")

        required_distance = (self_spec.pitch_diameter + other_spec.pitch_diameter) / 2 + clearance

        center_pnt_from = gp_Pnt(*self.part.sp("center").xts.xyz_mid)

        center_pnt_to = gp_Pnt(*other_gear_part.sp("center").xts.xyz_mid)

        translation_vec = gp_Vec(center_pnt_from, center_pnt_to)

        if translation_vec.SquareMagnitude() == 0:
            translation_vec = gp_Vec(1, 0, 0)

        translation_vec = translation_vec.Normalized()

        translation_vec = translation_vec.Scaled(-required_distance)

        return self.part.align("center")\
            .by("xmidymidzmid", other_gear_part.sp("center"))\
            .tr.mv(dx=translation_vec.X(), dy=translation_vec.Y(), dz=translation_vec.Z())


class RackDriver(PartDriver):

    def __init__(self, part: Part):
        super().__init__(part)

    @property
    def gear_spec(self) -> GearSpec:
        return GearSpec(
            module=float(self.part.annotation("gear_spec/module")),
            num_teeth=int(self.part.annotation("gear_spec/num_teeth")),
            pressure_angle_deg=float(self.part.annotation("gear_spec/pressure_angle_deg")))

    def get_local_x(self) -> typing.Tuple[float, float, float]:
        r0, r1 = InterrogateUtils.line_points(self.part.sp("pitch_line").explore.edge.get()[0].shape)
        result = gp_Vec(r0, r1).Normalized()
        return result.X(), result.Y(), result.Z()

    def get_local_y(self) -> typing.Tuple[float, float, float]:
        r0, r1 = InterrogateUtils.line_points(self.part.sp("pitch_perpendicular_line").explore.edge.get()[0].shape)
        result = gp_Vec(r0, r1)
        return result.X(), result.Y(), result.Z()

    def single_tooth_translation(self) -> typing.Tuple[float, float, float]:
        gear_spec = self.gear_spec

        result = gp_Vec(*self.get_local_x()).Scaled(math.pi * gear_spec.module)

        return result.X(), result.Y(), result.Z()

    def translate(self, tooth_count: float) -> Part:
        translation = gp_Vec(*self.single_tooth_translation()).Scaled(tooth_count)
        return self.part.tr.translate(
            translation.X(),
            translation.Y(),
            translation.Z())

    def position_with(self, other_gear_part: Part, clearance: float = 0) -> Part:
        self_spec = self.gear_spec
        other_driver: GearDriver = other_gear_part.driver(GearDriver)
        other_spec = other_driver.gear_spec

        if self_spec.module != other_spec.module:
            raise ValueError("Incompatible gear spec modules")

        pitch_line_start_point = gp_Pnt(*self.part.sp("pitch_line").explore.vertex.get()[0].xts.xyz_mid)

        pitch_line_vec = gp_Vec(*self.get_local_x())
        pitch_line_start_to_center = gp_Vec(
            pitch_line_start_point,
            gp_Pnt(*other_driver.center))

        pitch_line_offset_amount = pitch_line_vec.Dot(pitch_line_start_to_center)
        pitch_line_tooth_count_offset = pitch_line_offset_amount / (math.pi * self_spec.module)

        from_point = pitch_line_start_point.Translated(pitch_line_vec.Normalized().Scaled(pitch_line_offset_amount))

        # at this point, from_point to center should be perpendicular to the pitch line

        pitch_line_to_center_vec = gp_Vec(from_point, gp_Pnt(*other_driver.center))

        part_overlapped = self.part.tr.mv(
            pitch_line_to_center_vec.X(),
            pitch_line_to_center_vec.Y(),
            pitch_line_to_center_vec.Z()
        )

        # back off in the reverse of the local y direction
        offset = (gp_Vec(*self.get_local_y()).Normalized()
                  .Reversed().Scaled(clearance + other_driver.gear_spec.pitch_diameter / 2))

        result = part_overlapped.tr.mv(
            offset.X(),
            offset.Y(),
            offset.Z()
        )

        return result


def translate_js_lib_to_python():
    """
    Translation of the js source to python for easy use.
    """

    with importlib.resources.open_text(package="ezocc.gears", resource="gears.js") as text:
        js_source = text.read()

    translate = js2py.translate_js6(js_source)

    return translate


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("output_file")

    args = parser.parse_args()

    translated = translate_js_lib_to_python()

    with open(args.output_file, 'w') as f:
        f.write(translated)
