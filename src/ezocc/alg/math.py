import math


def snap(value: float, grid_spacing: float) -> float:
    value /= grid_spacing
    value = round(value)
    value *= grid_spacing

    return value


def lerp(x0: float, x1: float, proportion: float) -> float:
    return x0 + (x1 - x0) * proportion
