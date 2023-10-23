import unittest

import OCC
import OCC.Core as occ
import OCC.Core.BOPAlgo
import OCC.Core.BRepAlgoAPI
import OCC.Core.BRepBuilderAPI
import OCC.Core.BRepFilletAPI
import OCC.Core.BRepOffsetAPI
import OCC.Core.BRepPrimAPI
import OCC.Core.GeomAbs
import OCC.Core.ShapeUpgrade
import OCC.Core.TopOpeBRepBuild
import OCC.Core.gp as gp

import pythonoccutils.occutils_python as op


class TestExtents(unittest.TestCase):

    def test_box(self):

        box = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeBox(gp.gp_Pnt(0, 1, 2), gp.gp_Pnt(10, 5, 19)).Shape()
        extents = op.Extents(box)
        self.assertEqual(extents.x_min, 0)
        self.assertEqual(extents.y_min, 1)
        self.assertEqual(extents.z_min, 2)

        self.assertEqual(extents.x_span, 10)
        self.assertEqual(extents.y_span, 4)
        self.assertEqual(extents.z_span, 17)

    def test_swizzle(self):
        box = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeBox(gp.gp_Pnt(0, 1, 2), gp.gp_Pnt(10, 5, 19)).Shape()
        extents = op.Extents(box)

        self.assertEqual(extents.xy_mid, [extents.x_mid, extents.y_mid])
        self.assertEqual(extents.xx_mid, [extents.x_mid, extents.x_mid])
        self.assertEqual(extents.xyz_mid, [extents.x_mid, extents.y_mid, extents.z_mid])

        self.assertEqual(extents.yx_min, [extents.y_min, extents.x_min])
        self.assertEqual(extents.xx_min, [extents.x_min, extents.x_min])
        self.assertEqual(extents.xyz_min, [extents.x_min, extents.y_min, extents.z_min])

        self.assertEqual(extents.yx_max, [extents.y_max, extents.x_max])
        self.assertEqual(extents.xx_max, [extents.x_max, extents.x_max])
        self.assertEqual(extents.xyz_max, [extents.x_max, extents.y_max, extents.z_max])
