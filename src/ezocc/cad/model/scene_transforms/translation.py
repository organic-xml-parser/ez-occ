from __future__ import annotations

import typing

from OCC.Core.gp import gp_Dir, gp_Vec, gp_Trsf, gp_Quaternion, gp_EulerSequence, gp_Intrinsic_XYZ, gp_Pnt
import scipy.spatial.transform


class Translation:

    def __init__(self, delta_x: float, delta_y: float, delta_z: float):
        self.delta_x = delta_x
        self.delta_y = delta_y
        self.delta_z = delta_z

    def __str__(self) -> str:
        return "Translation(" + str((self.delta_x, self.delta_y, self.delta_z)) + ")"

    def added(self, other: Translation):
        return Translation(
            self.delta_x + other.delta_x,
            self.delta_y + other.delta_y,
            self.delta_z + other.delta_z
        )

    def inverse(self) -> Translation:
        return Translation(-self.delta_x, -self.delta_y, -self.delta_z)

