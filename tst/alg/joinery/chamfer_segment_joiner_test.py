import math
import unittest

from ezocc.alg.joinery.chamfer_segment_joiner import ChamferSegmentJoiner
from ezocc.occutils_python import WireSketcher
from ezocc.part_manager import PartFactory, NoOpPartCache


class ChamferSegmentJoinerTest(unittest.TestCase):

    def setUp(self) -> None:
        self._cache = NoOpPartCache.instance()
        self._factory = PartFactory(self._cache)

    def test_join_squares(self):
        face_a = self._factory.square_centered(10, 10)
        face_b = self._factory.square_centered(10, 10).tr.ry(math.radians(90))\
            .align().by("xmaxymidzmin", face_a)

        joint = ChamferSegmentJoiner().get_joint(face_a, face_b)

        self.assertTrue(joint.inspect.is_solid())
        self.assertAlmostEqual(10, joint.xts.x_span, places=6)
        self.assertAlmostEqual(10, joint.xts.y_span, places=6)
        self.assertAlmostEqual(10, joint.xts.z_span, places=6)

    def test_join_uneven_squares(self):
        face_a = self._factory.square_centered(10, 10)
        face_b = self._factory.square_centered(20, 10).tr.ry(math.radians(90)) \
            .align().by("xmaxymidzmin", face_a)

        joint = ChamferSegmentJoiner().get_joint(face_a, face_b)

        self.assertTrue(joint.inspect.is_solid())
        self.assertAlmostEqual(10, joint.xts.x_span, places=6)
        self.assertAlmostEqual(10, joint.xts.y_span, places=6)
        self.assertAlmostEqual(20, joint.xts.z_span, places=6)

    def test_join_multi_edge(self):
        face_a = self._factory.square_centered(10, 10)
        face_b = WireSketcher(face_a.xts.x_max, face_a.xts.y_min, face_a.xts.z_min)\
            .line_to(z=5, is_relative=True)\
            .line_to(y=face_a.xts.y_mid, z=10)\
            .line_to(y=face_a.xts.y_max)\
            .line_to(z=face_a.xts.z_mid)\
            .close()\
            .get_face_part(self._cache)

        joint = ChamferSegmentJoiner().get_joint(face_a, face_b)

        self.assertTrue(joint.inspect.is_solid())
        self.assertAlmostEqual(10, joint.xts.x_span, places=6)
        self.assertAlmostEqual(10, joint.xts.y_span, places=6)
        self.assertAlmostEqual(10, joint.xts.z_span, places=6)

        self.assertTrue(joint.inspect.is_solid())
        self.assertAlmostEqual(10, joint.xts.x_span, places=6)
        self.assertAlmostEqual(10, joint.xts.y_span, places=6)
        self.assertAlmostEqual(10, joint.xts.z_span, places=6)