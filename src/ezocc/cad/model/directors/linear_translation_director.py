import copy
import typing

import OCC.Core.gp

from ezocc.cad.model.directors.session_director import SessionDirector
from ezocc.cad.model.directors.session_director_range import SessionDirectorRange
from ezocc.cad.model.scene_transforms.scene_transform_stack import Translation
from ezocc.cad.model.scene_transforms.scene_transforms import SceneTransforms
from ezocc.occutils_python import SetPlaceablePart


class LinearTranslationDirector(SessionDirector):

    def __init__(self,
                 session_director_range: typing.Optional[SessionDirectorRange],
                 direction: OCC.Core.gp.gp_Dir,
                 parts: typing.Set[SetPlaceablePart]):
        super().__init__()
        self._range = session_director_range
        self._direction = direction
        self._parts = copy.copy(parts)
        self._value = 0

    def get_range(self) -> SessionDirectorRange:
        return self._range

    def get_display_name(self) -> str:
        return f"linear translation"

    def set_value(self, value: float):
        self._value = value

    def get_value(self) -> float:
        return self._value

    def push_transform(self, transforms: SceneTransforms, part: SetPlaceablePart) -> None:
        translation = OCC.Core.gp.gp_Vec(self._direction).Multiplied(self._value)

        transforms.get_transform_stack(part).append_translation(
            Translation(translation.X(), translation.Y(), translation.Z()))

    def get_affected_parts(self) -> typing.Set[SetPlaceablePart]:
        return self._parts
