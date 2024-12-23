import copy
import typing

from ezocc.cad.model.cache.session_cache import SessionCache
from ezocc.cad.model.directors.session_director import SessionDirector
from ezocc.cad.model.event import Listenable
from ezocc.cad.model.scene_transforms.scene_transforms import SceneTransforms
from ezocc.cad.model.widgets.widget import Widget
from ezocc.occutils_python import SetPlaceablePart


class Session(Listenable):
    """
    Represents an interactive view session with input drivers. Each driver can be thought of as
    A "knob" to enact some kind of change on the input parts. The changes are limited to those
    requiring simple transforms of existing parts, basically anything that does not require
    re-triangulation.
    """

    def __init__(self,
                 cache: SessionCache,
                 parts: typing.Set[SetPlaceablePart],
                 directors: typing.List[SessionDirector],
                 widgets: typing.Set[Widget]):
        super().__init__()

        self._cache = cache
        self._parts = copy.copy(parts)
        self._directors = copy.copy(directors)
        self._widgets = copy.copy(widgets)
        self._scene_transforms = SceneTransforms()

    @property
    def cache(self) -> SessionCache:
        return self._cache

    @property
    def scene_transforms(self) -> SceneTransforms:
        return self._scene_transforms

    def update(self):
        self._scene_transforms = SceneTransforms()

        # iterate over all drivers to apply transforms
        for director in self.directors:
            for part in director.get_affected_parts():
                director.push_transform(self._scene_transforms, part)

    def change_parts(self, new_parts: typing.Set[SetPlaceablePart]):
        self._parts = new_parts.copy()
        self.listener_manager.notify(self)

    @property
    def parts(self) -> typing.Set[SetPlaceablePart]:
        return copy.copy(self._parts)

    @property
    def directors(self) -> typing.List[SessionDirector]:
        return copy.copy(self._directors)

    @property
    def widgets(self) -> typing.Set[Widget]:
        return copy.copy(self._widgets)
