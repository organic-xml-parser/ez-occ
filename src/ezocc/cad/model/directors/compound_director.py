import copy
import typing

from ezocc.cad.model.directors.session_director import SessionDirector
from ezocc.cad.model.directors.session_director_range import SessionDirectorRange
from ezocc.cad.model.scene_transforms.scene_transforms import SceneTransforms
from ezocc.occutils_python import SetPlaceablePart


class CompoundDirector(SessionDirector):

    def __init__(self,
                 range: SessionDirectorRange,
                 delegates: typing.Dict[SessionDirector, typing.Callable[[float], float]]):
        super().__init__()

        self._range = range
        self._value = 0
        self._delegates = copy.copy(delegates)

    def get_range(self) -> typing.Optional[SessionDirectorRange]:
        return self._range

    def get_display_name(self) -> str:
        return f"compound director"

    def set_value(self, value: float):
        self._value = value

    def get_value(self) -> float:
        return self._value

    def push_transform(self, transforms: SceneTransforms, part: SetPlaceablePart) -> None:
        for delegate, value_mapper in self._delegates.items():
            if part in delegate.get_affected_parts():
                delegate.set_value(value_mapper(self._value))
                delegate.push_transform(transforms, part)
                return

        raise ValueError("Unexpected part")

    def get_affected_parts(self) -> typing.Set[SetPlaceablePart]:
        result = set()

        for d in self._delegates.keys():
            for p in d.get_affected_parts():
                result.add(p)

        return result
