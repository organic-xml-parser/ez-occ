import logging
import math
import os.path
import typing

import OCC.Core.TopAbs
import vtkmodules
import vtkmodules.vtkInteractionWidgets
import vtkmodules.vtkRenderingAnnotation
from PyQt5 import QtWidgets
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkIOImage import vtkPNGWriter
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkInteractionWidgets import vtk3DWidget, vtkCaptionRepresentation, vtkCaptionWidget
from vtkmodules.vtkRenderingCore import vtkActor, vtkCamera, vtkRenderWindowInteractor, vtkRenderWindow, vtkSkybox, \
    vtkWindowToImageFilter, vtkInteractorStyle
from vtkmodules.vtkRenderingOpenGL2 import vtkSSAOPass, vtkRenderStepsPass, vtkOpenGLFXAAPass, vtkOpenGLCamera

from vtkmodules.vtkRenderingAnnotation import vtkCaptionActor2D
from vtkmodules.vtkRenderingUI import vtkGenericRenderWindowInteractor

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


class SessionFrameOffscreen(VtkComponentsFactory):

    def get_interactor(self) -> typing.Optional[vtkRenderWindowInteractor]:
        return vtkRenderWindowInteractor()

    def get_interactor_style(self,
                             session_frame: SessionFrame,
                             actor_map: VtkOccActorMap,
                             session_renderer: SessionRenderer,
                             camera_policy: CameraPolicy,
                             interactor: vtkRenderWindowInteractor, render_target_policy: RenderTargetPolicy) -> \
    typing.Optional[vtkInteractorStyle]:
        self._session_renderer = session_renderer

    def get_render_window(self) -> vtkRenderWindow:
        self._render_window = vtkRenderWindow()
        self._render_window.SetSize(*self._resolution)
        self._render_window.OffScreenRenderingOn()
        return self._render_window

    def session_changed_callback(self, session: Session):
        self._session = session
        self._recalculate_camera_clipping_planes()

    def _recalculate_camera_clipping_planes(self):
        # recalculate the camera clipping plane to 0 -> Greatest possible distance to an object + 1

        part_xts = [p.part.xts for p in self._session.parts]
        x_min = part_xts[0].x_min
        x_max = part_xts[0].x_max

        y_min = part_xts[0].y_min
        y_max = part_xts[0].y_max

        z_min = part_xts[0].z_min
        z_max = part_xts[0].z_max

        for px in part_xts:
            x_min = min(x_min, px.x_min)
            x_max = max(x_max, px.x_max)

            y_min = min(y_min, px.y_min)
            y_max = max(y_max, px.y_max)

            z_min = min(z_min, px.z_min)
            z_max = max(z_max, px.z_max)

        camera: vtkCamera = self._session_renderer.scene_renderer.GetActiveCamera()
        cx, cy, cz = camera.GetPosition()

        x_dist = max(abs(x_min - cx), abs(x_max - cx))
        y_dist = max(abs(y_min - cy), abs(y_max - cy))
        z_dist = max(abs(z_min - cz), abs(z_max - cz))

        dist = math.hypot(x_dist, y_dist, z_dist)

        camera.SetClippingRange(0, dist + 1)

    def start_callback(self):
        pass

    def render_callback(self):
        pass

    def __init__(self,
                 session: Session,
                 enable_skybox: bool,
                 resolution: typing.Tuple[int, int],
                 rendered_entities_spec: typing.Optional[RenderedEntitiesSpec] = None):

        self._session = session
        self._resolution = resolution
        self._session_renderer: typing.Optional[SessionRenderer] = None
        self._session_frame = SessionFrame(
                     session,
                     "offscreen_renderer",
                     enable_skybox,
                     self,
                     rendered_entities_spec)

    @property
    def session_frame(self) -> SessionFrame:
        return self._session_frame

    def render(self, output_file_path: str):
        if not os.path.isabs(output_file_path):
            raise ValueError(f"Specified output file path is not absolute: \"{output_file_path}\"")

        self._recalculate_camera_clipping_planes()

        self._render_window.Render()

        filter = vtkWindowToImageFilter()
        filter.SetInput(self._render_window)
        filter.Update()

        writer = vtkPNGWriter()
        writer.SetFileName(output_file_path)
        writer.SetInputConnection(filter.GetOutputPort())
        writer.Write()
