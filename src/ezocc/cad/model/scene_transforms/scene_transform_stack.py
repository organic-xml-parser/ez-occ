from __future__ import annotations

import typing

from OCC.Core.gp import gp_Vec, gp_Trsf, gp_Quaternion, gp_Pnt

from ezocc.cad.model.scene_transforms.euler_rotation import EulerRotation
from ezocc.cad.model.scene_transforms.translation import Translation


class SceneTransformStack:

    def __init__(self):
        self._stack: typing.List[typing.Union[EulerRotation, Translation]] = []

    def append_translation(self, translation: Translation):
        self._stack.append(translation)

    def append_rotation_on_axis_about_point(self,
                                             axis: typing.Tuple[float, float, float],
                                             point: typing.Tuple[float, float, float],
                                             rotation_amount: float):

        rotation_dir_to_norm = gp_Quaternion(gp_Vec(0, 0, 1), gp_Vec(*axis))

        self._stack = self._stack + [
                          Translation(-point[0], -point[1], -point[2]),
                          EulerRotation.from_quaternion(rotation_dir_to_norm),
                          EulerRotation(0, 0, rotation_amount),
                          EulerRotation.from_quaternion(rotation_dir_to_norm.Inverted()),
                          Translation(point[0], point[1], point[2]),
                    ]

    @property
    def stack(self) -> typing.Generator[typing.Union[EulerRotation, Translation]]:
        for s in self._stack:
            yield s

    def append_rotation(self, rotation: EulerRotation):
        self._stack.append(rotation)

    def prepend_rotation(self, rotation: EulerRotation):
        self._stack = [rotation] + self._stack

    def prepend_translation(self, translation: Translation):
        self._stack = [translation] + self._stack

    def total_translation(self) -> Translation:
        result = Translation(0, 0, 0)
        for s in self._stack:
            if isinstance(s, Translation):
                result = result.added(s)

        return result

    def total_rotation(self) -> EulerRotation:
        result = EulerRotation(0, 0, 0)
        for s in self._stack:
            if isinstance(s, EulerRotation):
                result = result.added(s)

        return result

    def get_gp_Trsf(self) -> gp_Trsf:
        result = gp_Trsf()
        for s in self._stack:
            trsf = gp_Trsf()
            if isinstance(s, Translation):
                trsf.SetTranslation(gp_Vec(s.delta_x, s.delta_y, s.delta_z))
            elif isinstance(s, EulerRotation):
                trsf.SetRotation(gp_Quaternion(*s.quaternion()))

            result = trsf.Multiplied(result)

        return result

    def transform_point(self, x: float, y: float, z: float) -> typing.Tuple[float, float, float]:
        trsf = self.get_gp_Trsf()
        pnt = gp_Pnt(x, y, z)
        pnt.Transformed(trsf)

        return pnt.X(), pnt.Y(), pnt.Z()

    def transform_vector(self, x: float, y: float, z: float) -> typing.Tuple[float, float, float]:
        trsf = self.get_gp_Trsf()
        pnt = gp_Vec(x, y, z)
        pnt.Transformed(trsf)

        return pnt.X(), pnt.Y(), pnt.Z()

    def measure_total_rotation_about_axis(self, axis: typing.Tuple[float, float, float]):
        rotation_dir_to_norm = gp_Quaternion(gp_Vec(0, 0, 1), gp_Vec(*axis))

        self.append_rotation(EulerRotation.from_quaternion(rotation_dir_to_norm))
        result = self.total_rotation().theta_z

        self._stack.pop()

        return result
