import unittest

import OCC.Core.TopAbs
import OCC.Core.TopoDS

from pythonoccutils.humanization import Humanize
from pythonoccutils.part_manager import NoOpPartCache, PartFactory


class TestPart(unittest.TestCase):

    def setUp(self) -> None:
        self._factory = PartFactory(NoOpPartCache.instance())

    def test_pattern(self):
        box = self._factory.box(10, 10, 10)

        array_result = box.pattern(range(0, 10), lambda i, p: p.tr.mv(dx=i * 20))

        self.assertEqual(box.extents.x_span * 19, array_result.extents.x_span)
        self.assertEqual(10, len(array_result.explore.solid.get()))

    def test_bool_cut(self):
        box = self._factory.box(10, 10, 10)
        box = box.bool.cut(box.tr.mv(dx=5))

        self._assert_shape_is_type(OCC.Core.TopAbs.TopAbs_SOLID, box)

        self.assertEqual(box.extents.x_span, 5)
        self.assertEqual(box.extents.y_span, 10)
        self.assertEqual(box.extents.z_span, 10)
        self.assertEqual(1, len(box.explore.solid.get()))

    def test_bool_union(self):
        box = self._factory.box(10, 10, 10)
        box = box.bool.union(box.tr.mv(dx=5))

        self._assert_shape_is_type(OCC.Core.TopAbs.TopAbs_SOLID, box)

        self.assertEqual(box.extents.x_span, 15)
        self.assertEqual(box.extents.y_span, 10)
        self.assertEqual(box.extents.z_span, 10)
        self.assertEqual(1, len(box.explore.solid.get()))

    def test_bool_common(self):
        box = self._factory.box(10, 10, 10)
        x_min = box.extents.x_min
        box = box.bool.common(box.tr.mv(dx=5))

        self._assert_shape_is_type(OCC.Core.TopAbs.TopAbs_SOLID, box)

        self.assertEqual(box.extents.x_span, 5)
        self.assertEqual(x_min + 5, box.extents.x_min)
        self.assertEqual(box.extents.y_span, 10)
        self.assertEqual(box.extents.z_span, 10)
        self.assertEqual(1, len(box.explore.solid.get()))

    def test_prism(self):
        sq = self._factory.square_centered(10, 10)\
            .make.face()\
            .extrude.prism(dz=10)

        self._assert_shape_is_type(OCC.Core.TopAbs.TopAbs_SOLID, sq)

        self.assertEqual(1, len(sq.explore.solid.get()))
        self.assertEqual(10, sq.extents.x_span)
        self.assertEqual(10, sq.extents.y_span)
        self.assertEqual(10, sq.extents.z_span)

    def _assert_shape_is_type(self, expected_shape_type, part):
        expected = Humanize.shape_type(expected_shape_type)
        actual = Humanize.shape_type(part.shape.ShapeType())
        self.assertEqual(actual, expected)
