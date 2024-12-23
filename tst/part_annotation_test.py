import logging
import unittest

from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import PartFactory
from ezocc.subshape_mapping import ShapeAttributes


class TestPartAnnotation(unittest.TestCase):

    def setUp(self) -> None:
        self._part_cache = InMemoryPartCache()
        self._factory = PartFactory(self._part_cache)

    def test_copy_shape_attributes(self):
        a = ShapeAttributes({'a': '1', 'b':'2'})
        b = a.clone()

        self.assertEqual(a.values, b.values)

    def test_subshape_annotations(self):
        part = self._factory.box(10, 10, 10)

        fbottom = part.pick.from_dir(0, 0, 1).first_face().annotate("face", "fbottom").name("a")
        ftop = part.pick.from_dir(0, 0, -1).first_face().annotate("face", "ftop").name("a")

        comp = fbottom.add(ftop) #self._factory.compound(fbottom, ftop)

        f0, f1 = comp.explore.face.order_by(lambda f: f.xts.z_mid).get()

        self.assertEqual(fbottom.annotations, f0.annotations)
        self.assertEqual(ftop.annotations, f1.annotations)