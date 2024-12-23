import logging
import pdb
import tempfile
import unittest

import OCC.Core.BRep
import OCC.Core.TopoDS

from ezocc.occutils_python import SetPlaceableShape
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import NoOpPartCache, PartFactory, PartSave

import util_wrapper_swig

from ezocc.subshape_mapping import SubshapeMap


class TestPartSubshapes(unittest.TestCase):

    def setUp(self) -> None:
        self._part_factory = PartFactory(NoOpPartCache.instance())

    #def test_naming(self):
    #    gear_a = self._part_factory.cylinder(3, 1).name("gear_a").add(self._part_factory.vertex(0, 0, 0).name("center"))
    #    gear_b = self._part_factory.cylinder(3, 1)\
    #        .name("gear_b").add(self._part_factory.vertex(0, 0, 0).name("center"))

    #    gears = gear_a.add(gear_b)

    #    gear_a_recovered = gears.single_subpart("gear_a")
    #    gear_b_recovered = gears.single_subpart("gear_b")

    #    gear_a_center_recovered = gear_a_recovered.single_subpart("center")
    #    gear_b_center_recovered = gear_b_recovered.single_subpart("center")

    def test_place_conflicting_annotated_shape(self):
        box = self._part_factory.box(10, 10, 10)

        face = box.pick.from_dir(1, 0, 0).first_face()

        face_a = face.annotate("a", "b")
        face_b = face.annotate("c", "d")

        box = box.name_subshape(face_a, "face_a")

        self.assertRaises(ValueError, lambda: box.name_subshape(face_b, "face_b"))


    def test_do_on_single_subpart(self):

        gear_a = self._part_factory.cylinder(3, 1).name("body").add(self._part_factory.sphere(0.1).name("center"))
        gear_b = self._part_factory.cylinder(3, 1).name("body").add(self._part_factory.sphere(0.1).name("center")).tr.mv(dx=10)

        gears = gear_a.name("gear_a").add(gear_b.name("gear_b"))

        gears.single_subpart("gear_a").single_subpart("center")

        gears = gears.do_on(
            "gear_a",
            consumer=lambda p: p.do_on(
                "body", consumer=lambda pp: pp.bool.cut(self._part_factory.box(1, 1, 1)))).print()

        self.assertEqual(
            SetPlaceableShape(gear_a.single_subpart("center").shape),
            SetPlaceableShape(gears.single_subpart("gear_a").single_subpart("center").shape),
            msg="Sphere should not be modified")

        self.assertEqual(
            SetPlaceableShape(gear_b.shape),
            SetPlaceableShape(gears.single_subpart("gear_b").shape),
            msg="gear_b should not be modified")

        self.assertNotEqual(
            SetPlaceableShape(gear_a.shape),
            SetPlaceableShape(gears.single_subpart("gear_a").shape))


if __name__ == "__main__":
    box = PartFactory(InMemoryPartCache()).box(10, 10, 10)

    face = box.pick.from_dir(1, 0, 0).first_face()

    face_a = face.annotate("a", "b")
    face_b = face.annotate("c", "d")

    face_a.print("FACE A")

    logging.basicConfig(level=logging.DEBUG)

    box = box.name_subshape(face_a, "face_a")

    box.print("BOX")

    box = box.name_subshape(face_b, "face_b")