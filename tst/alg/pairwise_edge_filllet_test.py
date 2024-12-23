import unittest

from ezocc.alg.pairwise_edge_fillet import pairwise_edge_fillet
from ezocc.alg.remove_internal_faces import remove_internal_faces
from ezocc.cad.visualization_widgets.visualization_widgets import EdgeWidgets, FaceWidgets
from ezocc.occutils_python import WireSketcher
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import PartFactory


class TestPairwiseEdgeFillet(unittest.TestCase):

    def setUp(self) -> None:
        self._part_cache = InMemoryPartCache()
        self._factory = PartFactory(self._part_cache)

    def test_right_angle(self):
        result = (WireSketcher().line_to(x=10).line_to(y=10).get_wire_part(self._part_cache)
         .do(lambda p: pairwise_edge_fillet(1, p)))

        self.assertEqual(len(result.explore.edge.get()), 3)

    def test_two_right_angle(self):
        result = (WireSketcher()
                  .line_to(x=10)
                  .line_to(y=10)
                  .line_to(z=10)
                  .get_wire_part(self._part_cache)
                  .do(lambda p: pairwise_edge_fillet(1, p)))

        self.assertEqual(len(result.explore.edge.get()), 5)

    def test_three_angle(self):
        result = (WireSketcher()
                  .line_to(x=10, y=2)
                  .line_to(y=10, z=1)
                  .line_to(z=10, x=2, y=2)
                  .get_wire_part(self._part_cache)
                  .do(lambda p: pairwise_edge_fillet(1, p)))

        self.assertEqual(len(result.explore.edge.get()), 5)

    def test_four_angle(self):
        shape = (WireSketcher()
                            .line_to(z=5, is_relative=True)
                            .line_to(x=20, z=20, is_relative=True)
                            .line_to(x=30, is_relative=True)
                            .line_to(y=20, is_relative=True)
                            .get_wire_part(self._part_cache)
                            .cleanup.build_curves_3d())

        result = pairwise_edge_fillet(3, shape)

        self.assertEqual(len(result.explore.edge.get()), 7)
