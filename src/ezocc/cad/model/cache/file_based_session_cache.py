import json
import os.path
import typing

from ezocc.cad.model.cache.session_cache import SessionCache


class FileBasedSessionCache(SessionCache):

    def __init__(self, file_path: str):
        if not os.path.isabs(file_path):
            raise ValueError("File path must be absolute")

        self._file_path = file_path
        self._cache: typing.Dict[str, str] = {}

        self.load()

    def read_entry(self, key: str) -> typing.Optional[str]:
        return self._cache.get(key, None)

    def write_entry(self, key: str, value: str) -> None:
        self._cache[key] = value

    def save(self) -> None:
        with open(self._file_path, 'w') as f:
            json.dump(self._cache, f)

    def load(self) -> None:
        if not os.path.exists(self._file_path):
            return

        with open(self._file_path) as f:
            stored_cache = json.load(f)

        if not isinstance(stored_cache, dict):
            raise ValueError("Stored data in cache file is not a dict")

        if any(not isinstance(k, str) or not isinstance(v, str) for k, v in stored_cache.items()):
            raise ValueError("Stored data contains non-string values")

        self._cache = stored_cache
