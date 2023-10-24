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
from ezocc.part_manager import Part, PartFactory, NoOpPartCache


class PartFactoryTest(unittest.TestCase):

    def setUp(self) -> None:
        self._factory = PartFactory(NoOpPartCache.instance())

    def test_ra_triangle(self):
        t = self._factory.right_angle_triangle(math.sqrt(2), math.pi / 4)
        self.assertAlmostEqual(t.extents.x_span, 1)
        self.assertAlmostEqual(t.extents.y_span, 1)

        t = self._factory.right_angle_triangle(10, math.pi / 3, pln=gp.gp.YOZ())
        self.assertAlmostEqual(t.extents.y_span, 10 * math.cos(math.pi/3))
        self.assertAlmostEqual(t.extents.z_span, 10 * math.sin(math.pi/3))

    def test_conical_helix_0(self):
        helix = self._factory.conical_helix(10, 20, 10, 1)

        p_bottom, p_top = helix.explore.vertex.order_by(lambda v: v.xts.z_mid).get()

        self.assertAlmostEqual(p_bottom.xts.x_mid - p_top.xts.x_mid, 10, 5)
        self.assertAlmostEqual(helix.xts.z_span, 10, 5)

    def test_conical_helix_1(self):
        helix = self._factory.conical_helix(10, 20, 5, 1)

        p_bottom, p_top = helix.explore.vertex.order_by(lambda v: v.xts.z_mid).get()

        p_bottom.print()
        p_top.print()

        self.assertAlmostEqual(p_bottom.xts.x_mid - p_top.xts.x_mid, 15, 5)
        self.assertAlmostEqual(helix.xts.z_span, 10, 5)
