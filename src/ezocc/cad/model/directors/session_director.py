import typing

from ezocc.cad.model.directors.session_director_range import SessionDirectorRange
from ezocc.cad.model.scene_transforms.scene_transforms import SceneTransforms
from ezocc.occutils_python import SetPlaceablePart


class SessionDirector:
    """
    An entity which may affect the transformation of a part displayed in the scene.
    """

    def get_display_name(self) -> str:
        raise NotImplementedError()

    def get_range(self) -> typing.Optional[SessionDirectorRange]:
        raise NotImplementedError()

    def set_value(self, value: float):
        raise NotImplementedError()

    def get_value(self) -> float:
        raise NotImplementedError()

    def push_transform(self,
                       scene_transforms: SceneTransforms,
                       part: SetPlaceablePart) -> None:
        raise NotImplementedError()

    def get_affected_parts(self) -> typing.Set[SetPlaceablePart]:
        raise NotImplementedError()
