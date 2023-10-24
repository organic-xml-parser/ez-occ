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
from ezocc.part_manager import Part, PartFactory


class TestUtils(unittest.TestCase):

    def test_lerp(self):
        self.assertEqual(
            op.MathUtils.lerp(0, 0, 0,
                              1, 1, 1,
                              coordinate_proportional=0.5),
            (0.5, 0.5, 0.5))

        self.assertEqual(
            op.MathUtils.lerp(0, 0, 0,
                              0, 0, 10,
                              coordinate_absolute=3),
            (0, 0, 3))

        self.assertEqual(
            op.MathUtils.lerp(1, 1, 1,
                              1, 1, 11,
                              coordinate_absolute=3),
            (1, 1, 4))
