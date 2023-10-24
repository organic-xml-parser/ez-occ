from __future__ import annotations

import math
import typing

import OCC.Core.Precision as Precision
from OCC.Core.gp import gp_Pnt

"""
Provides a set of utilities for accessing OCCs Precision module.
"""


class Compare:

    @staticmethod
    def are_points_equal(p0: gp_Pnt, p1: gp_Pnt) -> bool:
        return p0.SquareDistance(p1) <= Precision.precision.SquareConfusion()

    @staticmethod
    def lin_eq(*args: float) -> bool:
        return Compare._compare_args(lambda a, b: math.fabs(a - b) < Precision.precision.Confusion(), *args)

    @staticmethod
    def ang_eq(*args: float) -> bool:
        return Compare._compare_args(lambda a, b: math.fabs(a - b) < Precision.precision.Angular(), *args)

    @staticmethod
    def _compare_args(comparator: typing.Callable[[float, float], bool], *args):
        if len(args) == 0:
            raise ValueError("At least two arguments must be supplied")

        if len(args) % 2 != 0:
            raise ValueError("Number of arguments to compare cannot be odd")

        index_midpoint = math.floor(len(args) / 2)

        args_a = args[0:index_midpoint]
        args_b = args[index_midpoint:]

        return all(comparator(args_a[i], args_b[i]) for i in range(0, len(args_a)))

