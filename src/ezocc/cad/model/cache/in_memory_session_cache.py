import typing

from ezocc.cad.model.cache.session_cache import SessionCache


class InMemorySessionCache(SessionCache):

    def __init__(self):
        self._data: typing.Dict[str, str] = {}

    def read_entry(self, key: str) -> typing.Optional[str]:
        return self._data.get(key, None)

    def write_entry(self, key: str, value: str) -> None:
        self._data[key] = value

    def save(self) -> None:
        pass

    def load(self) -> None:
        pass
