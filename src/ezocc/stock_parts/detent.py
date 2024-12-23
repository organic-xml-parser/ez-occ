import logging
import math
import pdb

import OCC.Core.GeomAbs
import OCC.Core.gp
import typing

from OCC.Core import Precision, gp

import ezocc
from ezocc.assertion_utils import assert_greater_than, assert_greater_than_0
from ezocc.constants import Constants
from ezocc.humanization import Humanize
from ezocc.occutils_python import WireSketcher, SetPlaceablePart
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import PartCache, PartFactory, Part
from ezocc.stock_parts.living_hinge import LivingHingeFactory, CapsuleHingeGenerator

logger = logging.getLogger(__name__)


class DetentStockParts:

    class SpringSpec:

        def __init__(self, radius: float, retracted_length: float, extended_length: float):
            self.radius = radius
            self.retracted_length = retracted_length
            self.extended_length = extended_length

            assert_greater_than("extended_length", self.extended_length, "retracted_length", self.retracted_length)
            assert_greater_than_0("radius", radius)
            assert_greater_than_0("extended_length", extended_length)
            assert_greater_than_0("retracted_length", retracted_length)

        @property
        def spring_travel(self):
            return self.extended_length - self.retracted_length

    def __init__(self, cache: PartCache):
        self._cache = cache
        self._factory = PartFactory(cache)

    def create(self,
               spring_spec: SpringSpec,
               box_wall_thickness: float,
               inner_component_clearance: float = 0.3,
               flat_roof_cavity: bool = True) -> Part:

        spring_extended = self._factory.helix(radius=spring_spec.radius, height=spring_spec.extended_length, n_turns=10) #  self._factory.cylinder(spring_spec.radius, spring_spec.extended_length)

        spring_retracted = (self._factory.helix(radius=spring_spec.radius, height=spring_spec.retracted_length, n_turns=10)
                            .align().by("zmin", spring_extended))

        pin_radius = 2
        flange_base_length = 1
        flange_length = 3

        pin = (self._factory.cylinder(2, spring_spec.spring_travel + flange_length * 2)
               .align().by("xmidymidzminmax", spring_extended).tr.mv(dz=flange_base_length))

        retention_flange = (self._factory.cylinder(max(spring_spec.radius, pin_radius) + 1, flange_length)
                            .align().by("xmidymidzmin", pin)
                            .tr.mv(dz=-flange_base_length)
                            .bool.cut(pin.extrude.make_thick_solid(Constants.clearance_mm() / 2)))

        pin = self._factory.compound(
            pin.name("pin"),
            retention_flange.name("retention_flange")
        )

        def _make_printable(shape: Part) -> Part:
            if not flat_roof_cavity:
                result = shape
            else:
                result =  (shape.bool.union(
                    self._factory.box_surrounding(shape).pick.from_dir(0, 1, 0).first_face().align().by("ymid", shape)
                    .bool.common(shape)
                    .make.face().cleanup()
                    .extrude.prism(dy=shape.xts.y_span / 2)))

            result = (result.make.solid()
                    .sew.faces()
                    .cleanup(concat_b_splines=True, fix_small_face=True)
                        .bool.common(self._factory.box_surrounding(shape)))

            return result

        cavity = (self._factory.cylinder(pin.xts.x_span / 2, pin.sp("retention_flange").add(spring_extended).xts.z_span)
                  .align().by("xmidymidzmin", spring_extended)
                  .extrude.make_thick_solid(inner_component_clearance)
                  .do(lambda p: _make_printable(p))
                  .bool.union(pin.sp("pin").extrude.make_thick_solid(inner_component_clearance).do(lambda p: _make_printable(p)))
                  .cleanup())

        box = (self._factory.box_surrounding(cavity, x_clearance=box_wall_thickness, y_clearance=box_wall_thickness, z_length=box_wall_thickness + cavity.xts.z_span - spring_spec.spring_travel)
               .align().by("zmax", cavity).tr.mv(dz=-spring_spec.spring_travel)
               .bool.cut(cavity))

        return self._factory.compound(
            cavity.name("cavity"),
            pin.name("detent"),
            spring_extended.name("spring"),
            box.name("box")
        )


def main():
    logging.basicConfig(level=logging.INFO)
    logging.getLogger(ezocc.part_manager.__name__).setLevel(level=logging.WARNING)

    cache = InMemoryPartCache()
    factory = PartFactory(cache)

    (DetentStockParts(cache)
     .create(DetentStockParts.SpringSpec(5.5 / 2, 10, 20))).preview()

if __name__ == '__main__':
    main()
