from __future__ import annotations

import typing

import OCC.Core.TopoDS
from OCC.Core import Precision
from OCC.Core.gp import gp_Pnt

from ezocc.occutils_python import InterrogateUtils


class SetPlaceablePnt:

    def __init__(self, x: float, y: float, z: float):
        conf = Precision.precision_Confusion()

        self._x = conf * round(x / conf)
        self._y = conf * round(y / conf)
        self._z = conf * round(z / conf)

    @staticmethod
    def get(value: typing.Union[gp_Pnt, OCC.Core.TopoDS.TopoDS_Shape]):
        if isinstance(value, OCC.Core.TopoDS.TopoDS_Shape):
            if value.ShapeType() != OCC.Core.TopoDS.TopoDS_Vertex:
                raise ValueError("Shape is not a vertex")

            return SetPlaceablePnt(*InterrogateUtils.vertex_to_xyz(value))
        elif isinstance(value, gp_Pnt):
            return SetPlaceablePnt(value.X(), value.Y(), value.Z())
        else:
            raise ValueError()

    def __hash__(self) -> int:
        return (self._x, self._y, self._z).__hash__()

    def __eq__(self, other: SetPlaceablePnt) -> bool:
        return self._x == other._x and self._y == other._y and self._z == other._z