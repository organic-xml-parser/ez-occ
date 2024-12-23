import math
import pdb
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
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import Part, PartFactory, NoOpPartCache, CacheToken, NoOpCacheToken

from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE

from ezocc.subshape_mapping import SubshapeMap


class TestPartBool(unittest.TestCase):

    def setUp(self) -> None:
        self._part_cache = InMemoryPartCache()
        self._factory = PartFactory(self._part_cache)

    def test_intersects(self):
        part_a = self._factory.box(10, 10, 10)

        self.assertTrue(part_a.bool.intersects(part_a.tr.mv(5, 5, 5)))
        self.assertFalse(part_a.bool.intersects(part_a.tr.mv(25, 25, 25)))
