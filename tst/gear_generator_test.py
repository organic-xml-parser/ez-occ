import logging
import math
import unittest

import OCC
import OCC.Core.BOPAlgo
import OCC.Core.BRepAlgoAPI
import OCC.Core.BRepAlgoAPI
import OCC.Core.BRepBuilderAPI
import OCC.Core.BRepBuilderAPI
import OCC.Core.BRepFilletAPI
import OCC.Core.BRepOffsetAPI
import OCC.Core.BRepPrimAPI
import OCC.Core.GeomAbs
import OCC.Core.ShapeUpgrade
import OCC.Core.TopOpeBRepBuild
import OCC.Core.TopoDS
import OCC.Core.gp
import OCC.Core.gp as gp
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.gp import gp_Vec

import pythonoccutils.occutils_python as op
from pythonoccutils.gears.gear_generator import InvoluteGearFactory, GearSpec, GearPairSpec
from pythonoccutils.part_manager import Part, PartFactory, NoOpPartCache


class GearGeneratorTest(unittest.TestCase):

    def setUp(self) -> None:
        self._factory = InvoluteGearFactory(NoOpPartCache.instance())

    def test_basic_profile(self):
        gear_spec = GearSpec(1, 8)
        result = self._factory.create_involute_profile(gear_spec)

        self.assertGreater(result.xts.x_span, gear_spec.root_diameter)

    def test_involute_gear(self):
        gear_spec = GearSpec(3, 8)
        result = self._factory.create_involute_gear(gear_spec, 10)

        self.assertAlmostEqual(result.xts.z_span, 10, 3)
        self.assertGreater(result.xts.x_span, gear_spec.root_diameter)

    def test_involute_pair(self):
        gear_spec = GearPairSpec.matched_pair(12, 10, 5)
        self._factory.create_involute_gear_pair(gear_spec, 10)

    def test_bevel_pair(self):
        gear_spec = GearPairSpec.matched_pair(12, 10, 5)
        self._factory.create_bevel_gear_pair(gear_spec, 10, math.radians(45))
