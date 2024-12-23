from __future__ import annotations

import numpy as np
import scipy

import math
import typing


class Parameter:
    """
    Represents a single degree of freedom input to the constraint solver system.
    """

    def __init__(self, value: float, fixed: bool = False):
        self._value = value
        self._fixed = fixed

        self.index: typing.Optional[int] = None

    @property
    def fixed(self) -> bool:
        return self._fixed

    @fixed.setter
    def fixed(self, value: bool):
        self._fixed = value

    def write_to_array(self, params: typing.List[float]) -> None:
        if self.index is None:
            raise ValueError("Index has not been set")

        params[self.index] = self._value

    def read_from_array(self, params: typing.List[float]) -> None:
        if self.fixed:
            raise ValueError("Fixed parameters should not be updated")

        if self.index is None:
            raise ValueError("Index has not been set")

        self._value = params[self.index]

    @property
    def value(self) -> float:
        return self._value

    def __str__(self):
        return f"x_{self.index if self.index is not None else 'fixed'}({self.value})"
