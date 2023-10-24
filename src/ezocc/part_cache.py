from __future__ import annotations

import logging
import pdb
import traceback

"""
Manages a cache of Part objects. Expensive operations (e.g. gear generation) can be persisted in the cache and only
recomputed when necessary.
"""
import copyreg
import io
import os.path
import pickle
import typing
import uuid
import OCC.Core.TopoDS

from util_wrapper_swig import UtilWrapper

import ezocc
from ezocc.part_manager import Part, PartFactory, PartSave, CacheToken, PartCache, LazyLoadedPart, \
    NoOpCacheToken

logger = logging.getLogger(__name__)


class DefaultCacheToken(CacheToken):
    """
    Note that CacheToken is not required to persist the arguments passed to it. Only the UUID need be stored.
    UUID generation can occur on the fly or
    """

    def __init__(self, cache, *args, **kwargs):
        self._cache = cache
        self._args = args
        self._kwargs = kwargs

        self._uuid = None

    @staticmethod
    def with_uuid(uuid_value: str, part_cache: PartCache) -> CacheToken:
        """
        Creates a cache token that is guaranteed to have the specified ID. This should almost never be used, except when
        loading or recovering a saved part.
        """
        result = DefaultCacheToken(part_cache)
        result._args = None
        result._kwargs = None
        result._uuid = uuid_value
        return result

    def get_cache(self) -> PartCache:
        return self._cache

    @staticmethod
    def _pickle_part(part):
        # reconstruction is never actually performed, so we can just use a string
        # with the specified uuid in place.
        uuid = part.cache_token.compute_uuid()

        return str.__class__, tuple(str(uuid))

    def compute_uuid(self) -> str:
        if self._uuid is None:
            f = io.BytesIO()
            pickler = pickle.Pickler(f)
            updated_dispatch_table = copyreg.dispatch_table.copy()
            updated_dispatch_table[Part] = DefaultCacheToken._pickle_part
            updated_dispatch_table[LazyLoadedPart] = DefaultCacheToken._pickle_part
            updated_dispatch_table[CacheToken] = lambda t: (str.__class__, tuple(t.compute_uuid()))
            updated_dispatch_table[DefaultCacheToken] = lambda t: (str.__class__, tuple(t.compute_uuid()))
            updated_dispatch_table[OCC.Core.TopoDS.TopoDS_Shape] = lambda s: UtilWrapper.shape_to_string(s)
            pickler.dispatch_table = updated_dispatch_table

            try:
                pickler.dump((self._args, self._kwargs))
            except Exception as e:
                raise RuntimeError(f"Could not generate pickle for uuid, params are: ({self._args}) ({self._kwargs})", e)

            self._uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, str(f.getvalue())))

        return self._uuid

    def mutated(self, *args, **kwargs) -> CacheToken:
        result = DefaultCacheToken(self._cache, self, *args, **kwargs)

        #print(f"{self.compute_uuid()} "
        #      f"(cache = {self._cache}) being mutated with {self}, {args}, {kwargs}, leading to: {result.compute_uuid()}")

        return result

    def __str__(self) -> str:
        return f"DefaultCacheToken(uuid={self.compute_uuid()})"


class InMemoryPartCache(PartCache):

    def __init__(self):
        self._cached_parts: typing.Dict[str, Part] = dict()

    def create_token(self, *args, **kwargs):
        return DefaultCacheToken(self, *args, **kwargs)

    def ensure_exists(self, cache_token: CacheToken, factory_method: typing.Callable[[], Part]) -> Part:
        part_uuid = cache_token.compute_uuid()
        if part_uuid not in self._cached_parts:
            part = factory_method()
            if part.cache_token.compute_uuid() != part_uuid:
                raise ValueError("Generated Part UUID does not match expected")

            self._cached_parts[part_uuid] = part

        return self._cached_parts[part_uuid]


class FileBasedPartCache(PartCache):

    def __init__(self, cache_directory: str):
        self._cache_directory = cache_directory
        self._loaded_parts: typing.Dict[str, Part] = dict()

    def create_token(self, *args, **kwargs):
        return DefaultCacheToken(self, *args, **kwargs)

    def ensure_exists(self, cache_token: CacheToken, factory_method: typing.Callable[[], Part]) -> Part:
        token_uuid = cache_token.compute_uuid()

        if token_uuid in self._loaded_parts:
            return self._loaded_parts[token_uuid]

        if not self._has(cache_token):
            logger.info(f"Generating part for cache token uuid: {token_uuid}")
            part = factory_method()

            part_uuid = part.cache_token.compute_uuid()

            if part_uuid != token_uuid:
                raise ValueError(f"Cache token uuid is not as expected (expected {token_uuid}, got {part_uuid})")

            self._update(part, cache_token)

        logger.debug(f"Retrieving part for cache token uuid: {cache_token.compute_uuid()}")
        result = self._get(cache_token)

        if result.cache_token.compute_uuid() != cache_token.compute_uuid():
            raise ValueError("Cache retrieved object not as expected")

        self._loaded_parts[token_uuid] = result

        return result

    def _get(self, token) -> typing.Optional[LazyLoadedPart]:
        cache_uuid = token.compute_uuid()
        return self._get_from_uuid(cache_uuid)

    def _has(self, cache_token: CacheToken) -> bool:
        cache_uuid = cache_token.compute_uuid()
        file_path = os.path.join(self._cache_directory, cache_uuid) + ".part.cbf"
        return os.path.exists(file_path)

    def _update(self, part: Part, cache_token: CacheToken) -> Part:
        cache_uuid = cache_token.compute_uuid()
        file_path = os.path.join(self._cache_directory, cache_uuid)

        logger.info(f"Saving part uuid: {cache_uuid}")

        part.save.ocaf(file_path)

        return part

    def _get_from_uuid(self, uuid: str) -> typing.Optional[LazyLoadedPart]:
        file_path = os.path.join(self._cache_directory, uuid)

        return LazyLoadedPart(DefaultCacheToken.with_uuid(uuid, self),
                              lambda: PartSave.load_ocaf(file_path, self))
