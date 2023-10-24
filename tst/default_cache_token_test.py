import pdb
import tempfile
import unittest
import uuid
from unittest.mock import MagicMock

import OCC.Core.TopoDS
from OCC.Core import gp

from ezocc.gears.gear_generator import GearSpec, GearPairSpec
from ezocc.part_cache import DefaultCacheToken, InMemoryPartCache, FileBasedPartCache
from ezocc.part_manager import Part, LazyLoadedPart, NoOpPartCache

import OCC.Core.BRepBuilderAPI

import OCC.Core.gp

import util_wrapper_swig

from ezocc.subshape_mapping import SubshapeMap


class TestCacheToken(unittest.TestCase):

    def setUp(self) -> None:
        self._cache = NoOpPartCache.instance()

    def test_parallel_mutations(self):
        root_token = DefaultCacheToken(self._cache)

        self.assertEqual(
            root_token.mutated(1).compute_uuid(),
            root_token.mutated(1).compute_uuid())

        self.assertEqual(
            root_token.mutated([1, 2, 3]).compute_uuid(),
            root_token.mutated([1, 2, 3]).compute_uuid())

        self.assertEqual(
            root_token.mutated([1, 2, 3]).mutated([4, 5, 6]).compute_uuid(),
            root_token.mutated([1, 2, 3]).mutated([4, 5, 6]).compute_uuid())

    def test_part_pickle_equivalence(self):
        cache = NoOpPartCache.instance()

        token = DefaultCacheToken.with_uuid(str(uuid.uuid4()), cache)

        normal_part = Part(token,
                           SubshapeMap.from_unattributed_shapes(OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(gp.gp_Pnt(0, 0, 0)).Shape()))
        lazy_part = LazyLoadedPart(token, lambda: normal_part)
        lazy_part_1 = LazyLoadedPart(token, lambda: normal_part)

        self.assertEqual(
            DefaultCacheToken(cache, lazy_part).compute_uuid(),
            DefaultCacheToken(cache, lazy_part).compute_uuid())

        self.assertEqual(
            DefaultCacheToken(cache, lazy_part_1).compute_uuid(),
            DefaultCacheToken(cache, lazy_part_1).compute_uuid())

        self.assertEqual(
            DefaultCacheToken(cache, normal_part).compute_uuid(),
            DefaultCacheToken(cache, normal_part).compute_uuid())

        self.assertEqual(
            DefaultCacheToken(cache, lazy_part).compute_uuid(),
            DefaultCacheToken(cache, lazy_part_1).compute_uuid())

        self.assertEqual(
            DefaultCacheToken(cache, normal_part).compute_uuid(),
            DefaultCacheToken(cache, lazy_part_1).compute_uuid())

        self.assertEqual(
            DefaultCacheToken(cache, [1, 2, 3]).compute_uuid(),
            DefaultCacheToken(cache, [1, 2, 3]).compute_uuid())

    def test_consistent_uuid(self):

        # try with a few different kinds of arg to test consistency
        args = [
            [],
            ["string"],
            ["string", 1],
            [GearPairSpec.matched_pair(10, 20, 15)],
            [GearSpec(20, 15, 40)],
            ["string", DefaultCacheToken(self._cache)]
        ]

        for a in args:
            self.assertEqual(
                DefaultCacheToken(self._cache, *a).compute_uuid(),
                DefaultCacheToken(self._cache, *a).compute_uuid())
