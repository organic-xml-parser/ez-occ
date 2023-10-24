import math


def snap(value: float, grid_spacing: float) -> float:
    value /= grid_spacing
    value = round(value)
    value *= grid_spacing

    return value
