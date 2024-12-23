from __future__ import annotations

import typing

import OCC.Core.TopoDS
import OCC.Core.TopAbs
import OCC.Core.gp
import OCC.Core.BRep


class P3DLike:

    P3D_TOPO_DS_XYZ_TYPES = (
        OCC.Core.gp.gp_Pnt,
        OCC.Core.gp.gp_Dir,
        OCC.Core.gp.gp_XYZ,
        OCC.Core.gp.gp_Vec)

    @staticmethod
    def create(*value: typing.Any) -> P3DLike:
        if len(value) == 1 and isinstance(value[0], P3DLike):
            return value[0]
        elif len(value) == 1:
            vals = value[0]
            if any(isinstance(vals, t) for t in P3DLike.P3D_TOPO_DS_XYZ_TYPES):
                return P3DLike(vals)
            else:
                return P3DLike(*vals)
        else:
            return P3DLike(*value)

    def __init__(self, *delegates: typing.Any):
        # check types are one of the supported values
        delegate_types = tuple(type(t) for t in delegates)

        if len(delegate_types) == 3 and all(t == int or t == float for t in delegate_types) or \
            len(delegate_types) == 1 and (delegate_types[0] in P3DLike.P3D_TOPO_DS_XYZ_TYPES or delegate_types[0] == OCC.Core.TopoDS.TopoDS_Vertex):
            self._delegates = delegates
        else:
            raise ValueError(f"Delegate types not supported: (supplied: {delegate_types})")

    def __str__(self):
        return str(self.xyz)

    T = typing.TypeVar("T")

    def get(self, expected_type: typing.Type[T]) -> T:
        if len(self._delegates) == 1 and isinstance(self._delegates[0], expected_type):
            return self._delegates[0]
        else:
            return expected_type(*self.xyz)

    @property
    def x(self):
        return self.xyz[0]

    @property
    def y(self):
        return self.xyz[1]

    @property
    def z(self):
        return self.xyz[2]

    @property
    def xyz(self) -> typing.Tuple[float, float, float]:
        if len(self._delegates) == 3 and all(isinstance(o, float) or isinstance(o, int) for o in self._delegates):
            return float(self._delegates[0]), float(self._delegates[1]), float(self._delegates[2])
        elif len(self._delegates) == 1:
            obj = self._delegates[0]

            if isinstance(obj, OCC.Core.TopoDS.TopoDS_Shape) and obj.ShapeType() == OCC.Core.TopAbs.TopAbs_VERTEX:
                p = OCC.Core.BRep.BRep_Tool.Pnt(obj)
                return p.X(), p.Y(), p.Z()
            elif any(isinstance(obj, t) for t in P3DLike.P3D_TOPO_DS_XYZ_TYPES):
                return obj.X(), obj.Y(), obj.Z()

        raise ValueError("Unable to convert core supported type into point-like value")
