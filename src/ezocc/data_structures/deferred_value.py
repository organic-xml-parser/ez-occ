from __future__ import annotations

import typing
from typing import TypeVar, Generic

S = TypeVar("S")
T = TypeVar("T")


class DeferredValue(Generic[S, T]):

    def __init__(self, delegate: typing.Callable[[S], T]):
        self._delegate = delegate

    @staticmethod
    def of(value: T) -> DeferredValue[S, T]:
        if isinstance(value, DeferredValue):
            return value
        elif isinstance(value, typing.Callable):
            return DeferredValue(value)
        else:
            return DeferredValue(lambda *_: value)

    def resolve(self, args: S = None) -> T:
        return self._delegate(args)

    def __add__(self, other: typing.Union[DeferredValue[S, T], T]) -> DeferredValue[S, T]:
        other = DeferredValue.of(other)
        return DeferredValue(lambda a: self.resolve(a) + other.resolve(a))

    def __sub__(self, other: typing.Union[DeferredValue[S, T], T]) -> DeferredValue[S, T]:
        other = DeferredValue.of(other)
        return DeferredValue(lambda a: self.resolve(a) - other.resolve(a))

    def __mul__(self, other: typing.Union[DeferredValue[S, T], T]) -> DeferredValue[S, T]:
        other = DeferredValue.of(other)
        return DeferredValue(lambda a: self.resolve(a) * other.resolve(a))

    def __neg__(self):
        return self * -1