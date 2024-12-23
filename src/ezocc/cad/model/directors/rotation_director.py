import copy
import typing

import OCC.Core.gp

from ezocc.cad.model.directors.session_director import SessionDirector
from ezocc.cad.model.directors.session_director_range import SessionDirectorRange
from ezocc.cad.model.scene_transforms.scene_transforms import SceneTransforms
from ezocc.occutils_python import SetPlaceablePart


class RotationDirector(SessionDirector):

    def __init__(self,
                 range: typing.Optional[SessionDirectorRange],
                 rotation_multiplier: float,
                 rotation_axis: OCC.Core.gp.gp_Ax1,
                 parts: typing.Set[SetPlaceablePart]):
        super().__init__()
        self._range = range
        self._rotation_axis = rotation_axis
        self._rotation_multiplier = rotation_multiplier

        self._parts = copy.copy(parts)
        self._value = 0

    def get_range(self) -> SessionDirectorRange:
        return self._range

    def get_display_name(self) -> str:
        return f"rotation {self._rotation_axis}"

    def set_value(self, value: float):
        self._value = value

    def get_value(self) -> float:
        return self._value

    def push_transform(self, transforms: SceneTransforms, part: SetPlaceablePart) -> None:
        direction_vec = (
            self._rotation_axis.Direction().X(),
            self._rotation_axis.Direction().Y(),
            self._rotation_axis.Direction().Z())

        location = [
            self._rotation_axis.Location().X(),
            self._rotation_axis.Location().Y(),
            self._rotation_axis.Location().Z()]

        transforms.get_transform_stack(part)\
            .append_rotation_on_axis_about_point(direction_vec, location, self._rotation_multiplier * self._value)

    def get_affected_parts(self) -> typing.Set[SetPlaceablePart]:
        return self._parts
