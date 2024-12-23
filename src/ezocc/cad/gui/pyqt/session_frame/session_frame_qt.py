import logging
import typing

import OCC.Core.TopAbs
import vtkmodules
import vtkmodules.vtkInteractionWidgets
import vtkmodules.vtkRenderingAnnotation
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QLayout
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkInteractionWidgets import vtk3DWidget, vtkCaptionRepresentation, vtkCaptionWidget
from vtkmodules.vtkRenderingCore import vtkActor, vtkCamera, vtkRenderWindowInteractor, vtkRenderWindow, vtkSkybox, \
    vtkInteractorStyle
from vtkmodules.vtkRenderingOpenGL2 import vtkSSAOPass, vtkRenderStepsPass, vtkOpenGLFXAAPass, vtkOpenGLCamera

from vtkmodules.vtkRenderingAnnotation import vtkCaptionActor2D

from ezocc.cad.gui.pyqt.session_frame.camera_policy import CameraPolicy
from ezocc.cad.gui.pyqt.session_frame.render_target_policy import RenderTargetPolicy
from ezocc.cad.gui.pyqt.session_frame.session_frame import SessionFrame, VtkComponentsFactory
from ezocc.cad.gui.pyqt.session_frame.session_frame_toolbar import SessionFrameToolbar
from ezocc.cad.gui.rendering_specifications.rendered_entities_spec import RenderedEntitiesSpec
from ezocc.cad.gui.rendering_specifications.rendering_color_spec import RenderingColorSpec
from ezocc.cad.gui.rendering_specifications.selection_palette import SelectionPalette
from ezocc.cad.gui.vtk.mouse_picking_interactor_style import MousePickingInteractorStyle
from ezocc.cad.gui.vtk.rendering_utils.renderer_factory import RendererFactory, SessionRenderer
from ezocc.cad.gui.vtk.transform_converter import TransformConverter
from ezocc.cad.gui.vtk.vtk_actor_collection_builder import VtkActorCollectionBuilder
from ezocc.cad.gui.vtk.vtk_occ_actor_map import VtkOccActorMap
from ezocc.cad.model.session import Session
from ezocc.cad.model.widgets.widget import Widget
from ezocc.occutils_python import SetPlaceablePart

logger = logging.getLogger(__name__)


class SessionFrameQt(QtWidgets.QFrame, VtkComponentsFactory):

    def __init__(self,
                 session: Session,
                 name: str,
                 enable_selection: bool,
                 enable_skybox: bool,
                 parent: QtWidgets.QWidget = None,
                 rendered_entities_spec: typing.Optional[RenderedEntitiesSpec] = None):
        super().__init__(parent)

        self._layout = QtWidgets.QVBoxLayout(self)

        self._enable_selection = enable_selection

        self.session_frame = SessionFrame(
            session,
            name,
            enable_skybox,
            vtk_components_factory=self,
            rendered_entities_spec=rendered_entities_spec)

        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._interactor)

        self.setLayout(self._layout)

    def start_callback(self):
        self.show()

    def get_interactor(self) -> vtkRenderWindowInteractor:
        self._interactor = QVTKRenderWindowInteractor(self)
        return self._interactor

    def get_render_window(self) -> vtkRenderWindow:
        return self._interactor.GetRenderWindow()

    def get_interactor_style(self,
                             session_frame: SessionFrame,
                             actor_map: VtkOccActorMap,
                             session_renderer: SessionRenderer,
                             camera_policy: CameraPolicy,
                             interactor: vtkRenderWindowInteractor,
                             render_target_policy: RenderTargetPolicy) -> \
            typing.Optional[vtkInteractorStyle]:

        if self._enable_selection:
            result = MousePickingInteractorStyle(actor_map, session_renderer)
            self.selection_changed_signal = \
                result.selection_tracker.mousePickingEmitter.selectionChangedSignal

            def _callback(*_):
                interactor.update()

            self.selection_changed_signal.connect(_callback)

            self._layout.addWidget(SessionFrameToolbar(
                session_renderer.scene_renderer,
                camera_policy,
                interactor.update,
                result,
                render_target_policy,
                self))

            return result
        else:
            return vtkmodules.vtkInteractionStyle.vtkInteractorStyleTrackballCamera()

    def render_callback(self):
        self._interactor.update()

    def session_changed_callback(self, session: Session):
        pass


