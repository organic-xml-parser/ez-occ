import unittest

from ezocc.alg.remove_internal_faces import remove_internal_faces
from ezocc.cad.visualization_widgets.visualization_widgets import EdgeWidgets, FaceWidgets
from ezocc.occutils_python import WireSketcher
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import PartFactory


class TestRemoveInternalFaces(unittest.TestCase):

    def setUp(self) -> None:
        self._part_cache = InMemoryPartCache()
        self._factory = PartFactory(self._part_cache)

    def test_box(self):
        box = self._factory.box(10, 10, 10)
        box_internal_faces_removed = remove_internal_faces(box)

        self.assertEqual(len(box_internal_faces_removed.removed_faces), 0)
        self.assertEqual(len(box_internal_faces_removed.visited_faces), 6)

    def test_intersecting_boxes(self):
        input_shape = (self._factory.box(10, 10, 10).explore.shell.get_single()
                       .do(lambda p: p.bool.union(p.tr.mv(5, 5, 5)))
                       .do(lambda p: self._factory.compound(*p.explore.face.get())))

        internal_faces_removed = remove_internal_faces(input_shape)

        self.assertEqual(len(internal_faces_removed.removed_faces), 6)

    def test_self_intersecting_pipe(self):
        spine = (WireSketcher().line_to(z=10, is_relative=True)
                 .line_to(x=-10, is_relative=True)
                 .get_wire_part(self._part_cache)
                 .do(lambda p: p.fillet.fillet2d_verts(2, p.explore.vertex.get()[1])))

        input_shape = self._factory.circle(4).loft.pipe(spine)

        input_shape_fixed = remove_internal_faces(input_shape)

        # note: seam orientation will have an effect here
        self.assertTrue(input_shape_fixed.result.inspect.is_solid())
        self.assertEqual(len(input_shape_fixed.removed_faces), 2)
        self.assertEqual(len(input_shape_fixed.orphaned_faces), 1)
