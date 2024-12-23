import pdb
import typing

from OCC.Core import Precision

import OCC.Core.ShapeAnalysis
import OCC.Core
import OCC.Core.gp as gp
import OCC.Core.TopoDS


class ShapeCanonicalizer:

    def __init__(self, shape: OCC.Core.TopoDS.TopoDS_Shape,
                 tolerance: float = None):
        self._tolerance = tolerance if tolerance is not None else Precision.precision.Confusion()
        self._recog = OCC.Core.ShapeAnalysis.ShapeAnalysis_CanonicalRecognition(shape)

    def _try_get_as(self, type, method):
        value = type()
        if method(self._tolerance, value):
            return value
        else:
            return None

    @property
    def line(self) -> typing.Optional[gp.gp_Lin]:
        return self._try_get_as(gp.gp_Lin, self._recog.IsLine)

    @property
    def circle(self) -> typing.Optional[gp.gp_Circ]:
        return self._try_get_as(gp.gp_Circ, self._recog.IsCircle)

    def plane(self) -> typing.Optional[gp.gp_Pln]:
        return self._try_get_as(gp.gp_Pln, self._recog.IsPlane)

