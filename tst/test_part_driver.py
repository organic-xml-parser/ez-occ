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

import ezocc.occutils_python as op
from ezocc.part_manager import Part, PartFactory, PartDriver, NoOpPartCache


class WheelDriver(PartDriver):

    def __init__(self, part: Part):
        super().__init__(part)

    def set_rotation(self, rotation: float) -> Part:
        current_rotation = float(self.part.annotation("wheel_rotation"))

        delta_r = rotation - current_rotation

        return self.part.tr.rz(delta_r, offset=self.part.single_subpart("origin").xts.xyz_mid)\
            .annotate("wheel_rotation", str(rotation))


class TestPartDriver(unittest.TestCase):

    def setUp(self) -> None:
        self._cache = NoOpPartCache.instance()
        self._part_factory = PartFactory(self._cache)

    def test_wheel(self):
        wheel = self._part_factory.cylinder(10, 3)\
            .add(self._part_factory.vertex(0, 0, 0).name("origin"),
                 self._part_factory.sphere(1).tr.mv(dx=10).name("indicator"))\
            .annotate("wheel_rotation", "0")\
            .with_driver(WheelDriver)

        wheel_rotated = wheel.driver(WheelDriver).set_rotation(math.radians(90))

        self.assertAlmostEqual(wheel.sp("indicator").xts.y_mid, wheel.xts.y_mid)
        self.assertNotAlmostEqual(wheel.sp("indicator").xts.x_mid, wheel.xts.x_mid)

        self.assertNotAlmostEqual(wheel_rotated.sp("indicator").xts.y_mid, wheel_rotated.xts.y_mid)
        self.assertAlmostEqual(wheel_rotated.sp("indicator").xts.x_mid, wheel_rotated.xts.x_mid)

        self.assertAlmostEqual(
            wheel.sp("indicator").xts.z_mid,
            wheel_rotated.sp("indicator").xts.z_mid)
