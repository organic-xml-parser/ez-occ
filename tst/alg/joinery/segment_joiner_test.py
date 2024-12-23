import math
import unittest

from ezocc.alg.joinery.segment_joiner import SegmentJoiner
from ezocc.occutils_python import WireSketcher
from ezocc.part_manager import PartFactory, NoOpPartCache


class SegmentJoinerTest(unittest.TestCase):

    def setUp(self) -> None:
        self._cache = NoOpPartCache.instance()
        self._factory = PartFactory(self._cache)

    def test_faces_must_be_connected(self):
        face_a = self._factory.square_centered(10, 10)
        face_b = self._factory.square_centered(10, 10).tr.ry(math.radians(90))\
            .align().by("xmaxymidzmin", face_a).tr.mv(dx=1)

        self.assertRaises(ValueError, lambda: SegmentJoiner().get_joint(face_a, face_b))

