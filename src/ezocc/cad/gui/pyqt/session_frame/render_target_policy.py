import typing

import OCC.Core.TopAbs
from PyQt5.QtCore import QObject, pyqtSignal

from ezocc.cad.gui.vtk.vtk_occ_actor_map import VtkOccActorMap
from ezocc.cad.model.event import Listenable


class RenderTargetPolicy:

    class Emitter(QObject):
        signal = pyqtSignal()

    def __init__(self,
                 vtk_occ_actor_map: VtkOccActorMap,
                 render_callback: typing.Callable[[], None],
                 rendered_shape_types: typing.Set[OCC.Core.TopAbs.TopAbs_ShapeEnum]):
        self._vtk_occ_actor_map = vtk_occ_actor_map
        self._render_callback = render_callback
        self._rendered_shape_types = rendered_shape_types.copy()
        self.emitter = RenderTargetPolicy.Emitter()

    @property
    def rendered_shape_types(self) -> typing.Set[OCC.Core.TopAbs.TopAbs_ShapeEnum]:
        return self._rendered_shape_types.copy()

    def set_shape_type_renderable(self, shape_type: OCC.Core.TopAbs.TopAbs_ShapeEnum, is_renderable: bool):
        if is_renderable:
            self._rendered_shape_types.add(shape_type)
        else:
            self._rendered_shape_types.remove(shape_type)

        self.apply()

    def apply(self):
        for a in self._vtk_occ_actor_map.occ_actors():
            a.actor.SetVisibility(a.shape_type in self._rendered_shape_types)

        self._render_callback()

        self.emitter.signal.emit()
