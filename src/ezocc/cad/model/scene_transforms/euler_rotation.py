from __future__ import annotations

import typing

from OCC.Core.gp import gp_Dir, gp_Vec, gp_Trsf, gp_Quaternion, gp_EulerSequence, gp_Intrinsic_XYZ, gp_Pnt
import scipy.spatial.transform


class EulerRotation:

    def __init__(self, theta_x: float, theta_y: float, theta_z: float):
        self.theta_x = theta_x
        self.theta_y = theta_y
        self.theta_z = theta_z

    def __str__(self) -> str:
        return "EulerRotation(" + str((self.theta_x, self.theta_y, self.theta_z)) + ")"

    def added(self, other: EulerRotation):
        return EulerRotation(
            self.theta_x + other.theta_x,
            self.theta_y + other.theta_y,
            self.theta_z + other.theta_z
        )

    def rotate_point(self, x: float, y: float, z: float) -> typing.Tuple[float, float, float]:
        # xy vector is rotated about z
        rotation = scipy.spatial.transform.Rotation.from_euler("xyz", [self.theta_x, self.theta_y, self.theta_z])

        result = [x, y, z]

        rotation.apply(result)

        return tuple(result)

    def quaternion(self) -> typing.Tuple[float, float, float, float]:
        rotation = scipy.spatial.transform.Rotation.from_euler("xyz", [self.theta_x, self.theta_y, self.theta_z])
        return tuple(rotation.as_quat())

    @staticmethod
    def from_quaternion(quat: gp_Quaternion):
        a, b, c = quat.GetEulerAngles(gp_Intrinsic_XYZ)
        return EulerRotation(a, b, c)