import typing
from enum import Enum
from typing import TypeVar, Generic

from ezocc.occutils_python import SetPlaceablePart


TEvent = TypeVar("TEvent")
TListener = typing.Callable[[TEvent], None]


class ListenerManager(Generic[TEvent]):

    def __init__(self):
        self._listeners: typing.Set[TListener] = set()

    def add_listener(self, l: TListener):
        if l in self._listeners:
            raise ValueError("Duplicate entry.")

        self._listeners.add(l)

    def remove_listener(self, l: TListener):
        if l not in self._listeners:
            raise ValueError("Listener not present")

        self._listeners.remove(l)

    def notify(self, event: TEvent):
        for l in self._listeners:
            l(event)


class Listenable(Generic[TEvent]):

    def __init__(self):
        self.listener_manager: ListenerManager[TEvent] = ListenerManager()
