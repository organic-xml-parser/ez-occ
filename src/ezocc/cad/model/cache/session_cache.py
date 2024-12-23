import typing


class SessionCache:
    """
    Lightweight key-value store for session related data, e.g. camera positioning.
    """

    def read_entry(self, key: str) -> typing.Optional[str]:
        raise NotImplementedError()

    def write_entry(self, key: str, value: str) -> None:
        """
        Persist the entry to the cache.
        """
        raise NotImplementedError()

    def save(self) -> None:
        """
        Persist the current cache state to storage.
        """

        raise NotImplementedError()

    def load(self) -> None:
        """
        Overwrite values in the cache with last saved. Do nothing if no
        saved cache exists.
        """
        raise NotImplementedError()
