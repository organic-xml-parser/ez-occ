import unittest

from ezocc.gcs_solver.deprecated.gcs import GCS_2d
from ezocc.part_manager import NoOpPartCache


class TestExtents(unittest.TestCase):

    def setUp(self) -> None:
        self._gcs = GCS_2d(NoOpPartCache.instance())

    def test_circle_intersection(self):
        c0 = self._gcs.circ_2d(-5, 0, 12)
        c1 = self._gcs.circ_2d(5, 0, 12)

        p0, p1 = self._gcs.get_circle_intersection_points(c0, c1)

        self.assertAlmostEqual(p0.X(), 0)
        self.assertAlmostEqual(p1.X(), 0)

        self.assertEqual(abs(p0.Y()), abs(p1.Y()))
        self.assertNotEqual(p0.Y(), p1.Y())
