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
from pythonoccutils.part_manager import Part, PartFactory, NoOpPartCache


class PartQueryTest(unittest.TestCase):

    def setUp(self) -> None:
        self._factory = PartFactory(NoOpPartCache.instance())

    def test_get_quantities(self):
        box = self._factory.box_centered(10, 20, 30)

        faces = box.query_shapes("*f")

        self.assertEqual(len(faces), 6)

        self.assertEqual(box.query_shapes("*f"), box.query_shapes("6f"))
        self.assertEqual(box.query_shapes("*f"), box.query_shapes("[:]f"))
        self.assertEqual(box.query_shapes("*f"), box.query_shapes("[0:6]f"))

    def test_get_subparts(self):
        box = self._factory.box_centered(10, 10, 10)
        verts = box.query("*f").query("*e").query_shapes("*v")

        self.assertEqual(len(verts), 48)

    def test_get_labelled_part(self):
        box = self._factory.box_centered(10, 10, 10, x_min_face_name="x/min", x_max_face_name="x/max")

        box.print()

        self.assertEqual(len(set(box.query_shapes("*f,l(x/*)"))), 2)

        self.assertEqual(len(box.query_shapes("*f,l(x/min)")), 1)
        self.assertEqual(len(box.query_shapes("*f,l(x/max)")), 1)
