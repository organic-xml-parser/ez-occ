import math
import unittest

from OCC.Core.gp import gp_Dir, gp_Pnt

from ezocc.alg.geometry_exploration.edges.intersection_angle import get_edge_intersection_angle
from ezocc.alg.remove_internal_faces import remove_internal_faces
from ezocc.cad.visualization_widgets.visualization_widgets import EdgeWidgets, FaceWidgets
from ezocc.occutils_python import WireSketcher
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import PartFactory


class TestRemoveInternalFaces(unittest.TestCase):

    def setUp(self) -> None:
        self._part_cache = InMemoryPartCache()
        self._factory = PartFactory(self._part_cache)

    def test_right_angle_acute_section(self):
        edge_from = WireSketcher().line_to(1, 0, 0).get_wire_part(self._part_cache).explore.edge.get_single()
        edge_to = WireSketcher(1, 0, 0).line_to(1, 1, 0).get_wire_part(self._part_cache).explore.edge.get_single()

        angle = get_edge_intersection_angle(edge_from,
                                    gp_Dir(0, 0, -1),
                                    edge_to,
                                    gp_Pnt(*edge_from.bool.section(edge_to).xts.xyz_mid))

        self.assertEqual(math.degrees(angle), 90)

    def test_45deg_angle_acute_section(self):
        edge_from = WireSketcher().line_to(1, 0, 0).get_wire_part(self._part_cache).explore.edge.get_single()
        edge_to = WireSketcher(1, 0, 0).line_to(0, 1, 0).get_wire_part(self._part_cache).explore.edge.get_single()

        angle = get_edge_intersection_angle(edge_from,
                                    gp_Dir(0, 0, -1),
                                    edge_to,
                                    gp_Pnt(*edge_from.bool.section(edge_to).xts.xyz_mid))

        self.assertEqual(math.degrees(angle), 45)

    def test_right_angle_obtuse_section(self):
        edge_from = WireSketcher().line_to(1, 0, 0).get_wire_part(self._part_cache).explore.edge.get_single()
        edge_to = WireSketcher(1, 0, 0).line_to(1, 1, 0).get_wire_part(self._part_cache).explore.edge.get_single()

        angle = get_edge_intersection_angle(
            edge_from,
            gp_Dir(0, 0, 1),
            edge_to,
            gp_Pnt(*edge_from.bool.section(edge_to).xts.xyz_mid))

        self.assertEqual(math.degrees(angle), 270)

    def test_45deg_angle_obtuse_section(self):
        edge_from = WireSketcher().line_to(1, 0, 0).get_wire_part(self._part_cache).explore.edge.get_single()
        edge_to = WireSketcher(1, 0, 0).line_to(0, 1, 0).get_wire_part(self._part_cache).explore.edge.get_single()

        angle = get_edge_intersection_angle(edge_from,
                                    gp_Dir(0, 0, 1),
                                    edge_to,
                                    gp_Pnt(*edge_from.bool.section(edge_to).xts.xyz_mid))

        self.assertEqual(math.degrees(angle), 360 - 45)