import pdb
import tempfile
import unittest

from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import NoOpPartCache, PartFactory, PartSave

import util_wrapper_swig


class TestPartSave(unittest.TestCase):

    def test_save_and_load(self):
        box = PartFactory(InMemoryPartCache()).box(10, 10, 10, x_min_face_name="xmin").annotate("foo", "bar")
        box = box.annotate_subshape("xmin", ("baz", "qux"))

        with tempfile.NamedTemporaryFile() as f:
            filename = str(f.name)

            box.save.ocaf(filename)

            loaded = PartSave.load_ocaf(filename, InMemoryPartCache())

        self.assertEqual(box.cache_token.compute_uuid(), loaded.cache_token.compute_uuid())
        self.assertEqual(
            util_wrapper_swig.UtilWrapper.shape_to_string(box.shape),
            util_wrapper_swig.UtilWrapper.shape_to_string(loaded.shape))

        self.assertEqual(box.annotations, loaded.annotations)
        self.assertEqual(box.sp("xmin").annotations, loaded.sp("xmin").annotations)

        self.assertEqual(box.annotation("foo"), "bar")
        self.assertEqual(box.sp("xmin").annotation("baz"), "qux")
