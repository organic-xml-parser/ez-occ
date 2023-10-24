import pdb
import tempfile
import unittest
import uuid
from unittest.mock import MagicMock

import OCC.Core.TopoDS

from ezocc.part_cache import DefaultCacheToken, InMemoryPartCache, FileBasedPartCache
from ezocc.part_manager import PartFactory, PartSave, CacheToken, PartCache, NoOpPartCache, Part, LazyLoadedPart

import util_wrapper_swig


class TestInMemoryPartCache(unittest.TestCase):

    def test_in_memory_part_cache(self):
        get_cache = lambda: InMemoryPartCache()
        self._test_consistent(get_cache())
        self._test_association_with_part(get_cache())

    def test_noop_part_cache(self):
        get_cache = lambda: NoOpPartCache.instance()

    def test_file_based_part_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            get_cache = lambda: FileBasedPartCache(tmpdir)
            self._test_consistent(get_cache())
            self._test_association_with_part(get_cache())
            self._test_duplication_avoided(get_cache())

    def _test_duplication_avoided(self, cache: PartCache):

        token = cache.create_token("custom expensive operation")

        # todo replace this with mocking at some point
        part_make_calls = []
        def _make_part():
            part_make_calls.append(True)
            return PartFactory(cache).box(10, 10, 10).with_cache_token(token)

        part_0 = cache.ensure_exists(token, _make_part)
        part_1 = cache.ensure_exists(token, _make_part)

        self.assertEqual(len(part_make_calls), 1)

    def _test_consistent(self, cache):
        self.assertEqual(cache.create_token().compute_uuid(),
                         cache.create_token().compute_uuid())

        self.assertEqual(cache.create_token("test").compute_uuid(),
                         cache.create_token("test").compute_uuid())

    def _test_association_with_part(self, cache):
        factory = PartFactory(cache)

        p0 = factory.box(10, 10, 10)
        p1 = factory.box(10, 10, 10)

        p2 = factory.box(20, 10, 10)

        self.assertEqual(p0.cache_token.compute_uuid(), p1.cache_token.compute_uuid())
        self.assertNotEqual(p0.cache_token.compute_uuid(), p2.cache_token.compute_uuid())

        p0_dx = p0.tr.mv(dx=1)
        p1_dx = p1.tr.mv(dx=1)
        p2_dx = p2.tr.mv(dx=1)

        self.assertNotEqual(p0_dx.cache_token.compute_uuid(), p0.cache_token.compute_uuid())
        self.assertNotEqual(p1_dx.cache_token.compute_uuid(), p1.cache_token.compute_uuid())
        self.assertNotEqual(p2_dx.cache_token.compute_uuid(), p2.cache_token.compute_uuid())

        # p0 / p1 have gone through the same "chain" of operations, so should have the same uuid
        self.assertEqual(p0_dx.cache_token.compute_uuid(), p1_dx.cache_token.compute_uuid())
        self.assertNotEqual(p0_dx.cache_token.compute_uuid(), p2_dx.cache_token.compute_uuid())
