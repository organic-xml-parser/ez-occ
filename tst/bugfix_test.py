import math
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

import ezocc.occutils_python as op
from ezocc.part_manager import PartFactory, NoOpPartCache


class BugfixTest(unittest.TestCase):

    def setUp(self) -> None:
        self._cache = NoOpPartCache.instance()
        self._factory = PartFactory(self._cache)

    def test_compound_of_named_parts(self):
        p0 = self._factory.box(1, 1, 1).name("foo")
        p1 = self._factory.box(1, 1, 1).tr.mv(dx=10).name("bar")

        comp = self._factory.compound(p0, p1)

        self.assertEqual(op.SetPlaceablePart(p0), op.SetPlaceablePart(comp.single_subpart("foo")))
        self.assertEqual(op.SetPlaceablePart(p1), op.SetPlaceablePart(comp.single_subpart("bar")))

    def test_pattern_compound(self):
        part = self._factory.box(1, 1, 1).tr.mv(dx=10)
        part = part.pattern(range(0, 4), lambda i, p: p.tr.rz(math.radians(90 * i)).name(f"g{i}"))

        self.assertEqual(4, len(part.explore.solid.get()))

        part.single_subpart("g0")
        part.single_subpart("g1")
        part.single_subpart("g2")
        part.single_subpart("g3")

        self.assertRaises(Exception, lambda : part.single_subpart("g4"))

    def test_mirror_bug(self):
        to_mirror = self._factory.box(3, 8, 22) \
            .do(lambda p: p.bool.cut(
            self._factory.box_surrounding(p)
            .align().stack_x0(p, offset=2)
            .align().stack_z0(p, offset=12.5))) \
            .name("contact") \
            .print("After subshape is named") \
            .do(lambda p: p.bool.union(self._factory.cylinder(5.5 / 2, 11).align().xy_mid_to_mid(p).align().stack_z1(p))) \
            .print("After bool operation") \
            .cleanup()

        to_mirror.mirror.x()
