import copy
import typing

from ezocc.cad.model.directors.session_director import SessionDirector
from ezocc.cad.model.directors.session_director_range import SessionDirectorRange
from ezocc.cad.model.scene_transforms.scene_transforms import SceneTransforms
from ezocc.occutils_python import SetPlaceablePart


class RigidLinkDirector(SessionDirector):

    def __init__(self,
                 source_part: SetPlaceablePart,
                 parts: typing.Set[SetPlaceablePart]):
        super().__init__()
        self._source_part = source_part
        self._parts = copy.copy(parts)
        self._value = 0

    def get_range(self) -> typing.Optional[SessionDirectorRange]:
        return None

    def get_display_name(self) -> str:
        return f"rigid link"

    def set_value(self, value: float):
        self._value = value

    def get_value(self) -> float:
        return self._value

    def push_transform(self,
                         transforms: SceneTransforms,
                         part: SetPlaceablePart) -> None:
        transforms.set_transform_stack(part, transforms.get_transform_stack(self._source_part))

    def get_affected_parts(self) -> typing.Set[SetPlaceablePart]:
        return self._parts
