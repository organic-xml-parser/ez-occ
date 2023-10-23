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
from pythonoccutils.part_manager import PartFactory, NoOpPartCache
from pythonoccutils.type_utils import TypeValidator

class TestTypeUtils(unittest.TestCase):

    def setUp(self) -> None:
        self._cache = NoOpPartCache.instance()

    def test_check(self):
        part = PartFactory(self._cache).box(10, 10, 10)

        self.assertFalse(TypeValidator.is_any_shape(part))
        self.assertTrue(TypeValidator.is_any_shape(part.shape))

    def test_assert(self):
        part = PartFactory(self._cache).box(10, 10, 10)

        self.assertRaises(ValueError, lambda : TypeValidator.assert_is_any_shape(part))

        TypeValidator.assert_is_any_shape(part.shape)

