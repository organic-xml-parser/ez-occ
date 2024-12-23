import unittest

from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import PartFactory


class TestPartAlgorithm(unittest.TestCase):

    def setUp(self) -> None:
        self._part_cache = InMemoryPartCache()
        self._factory = PartFactory(self._part_cache)

    def test_project(self):
        part = self._factory.box(10, 10, 10)

        projection = part.alg.project_to_edge_network(
            cam_origin=(20, 20, 20),
            cam_direction=(-1, -1, -1),
            is_perspective=False,
            cam_focus=100)

        self.assertEqual(12, len(projection.explore.edge.get()))

    def test_project_to_outer_wire(self):

        part = self._factory.box(10, 10, 10)

        projection = part.alg.project_to_edge_network(
            cam_origin=(20, 20, 20),
            cam_direction=(0, 0, -1),
            is_perspective=False,
            cam_focus=100)

        self.assertEqual(4, len(projection.explore.edge.get()))
        self.assertEqual(4, len(projection.explore.vertex.get_compound().bool.union().explore.vertex.get()))

    def test_projection_loft(self):
        part = self._factory.box(10, 10, 10)

        cam_origin = (40, 40, 40)
        cam_direction = (-1, -1, -1)

        projection_a = (part.alg.project_to_edge_network(
            cam_origin=cam_origin,
            cam_direction=cam_direction,
            is_perspective=True,
            cam_focus=100)
            .alg.edge_network_to_outer_wire()
                        .cleanup(concat_b_splines=True, fix_small_face=True)
                        .make.face())

        self.assertEqual(6, len(projection_a.explore.edge.get()))
        self.assertEqual(6, len(projection_a.explore.vertex.get_compound().bool.union().explore.vertex.get()))

        projection_b = (part.alg.project_to_edge_network(
            cam_origin=cam_origin,
            cam_direction=cam_direction,
            is_perspective=True,
            cam_focus=20)
            .alg.edge_network_to_outer_wire()
                        .cleanup(concat_b_splines=True, fix_small_face=True)
                        .make.face())

        self.assertEqual(6, len(projection_b.explore.edge.get()))
        self.assertEqual(6, len(projection_b.explore.vertex.get_compound().bool.union().explore.vertex.get()))

    def test_feature_removal(self):
        part_pre_feature = self._factory.box(10, 10, 10)

        featured_part = part_pre_feature.bool.cut(self._factory.cylinder(3, part_pre_feature.xts.z_span * 2)
                             .align().by("xmidymidzmid", part_pre_feature).name_recurse("cut_cylinder"))

        defeatured_part = featured_part.alg.remove_features(
            featured_part.sp("cut_cylinder", part_filter=lambda p: p.print().inspect.is_face()))

        self.assertEqual(len(part_pre_feature.explore.face.get()), len(defeatured_part.explore.face.get()))
        self.assertEqual(len(part_pre_feature.explore.edge.get()), len(defeatured_part.explore.edge.get()))
        self.assertEqual(len(part_pre_feature.explore.vertex.get()), len(defeatured_part.explore.vertex.get()))