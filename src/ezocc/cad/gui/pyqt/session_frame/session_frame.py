from __future__ import annotations

import logging
import time
import typing

import OCC.Core.TopAbs
import vtkmodules
import vtkmodules.vtkInteractionWidgets
import vtkmodules.vtkRenderingAnnotation
from PyQt5 import QtWidgets
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkInteractionWidgets import vtk3DWidget, vtkCaptionRepresentation, vtkCaptionWidget
from vtkmodules.vtkRenderingCore import vtkActor, vtkCamera, vtkRenderWindowInteractor, vtkRenderWindow, vtkSkybox, \
    vtkInteractorStyle, vtkRenderer
from vtkmodules.vtkRenderingOpenGL2 import vtkSSAOPass, vtkRenderStepsPass, vtkOpenGLFXAAPass, vtkOpenGLCamera

from vtkmodules.vtkRenderingAnnotation import vtkCaptionActor2D

from ezocc.cad.gui.pyqt.session_frame.camera_policy import CameraPolicy
from ezocc.cad.gui.pyqt.session_frame.render_target_policy import RenderTargetPolicy
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


class VtkComponentsFactory:

    def get_interactor(self) -> typing.Optional[vtkRenderWindowInteractor]:
        raise NotImplementedError()

    def get_interactor_style(self,
                             session_frame: SessionFrame,
                             actor_map: VtkOccActorMap,
                             session_renderer: SessionRenderer,
                             camera_policy: CameraPolicy,
                             interactor: vtkRenderWindowInteractor,
                             render_target_policy: RenderTargetPolicy) -> typing.Optional[vtkInteractorStyle]:
        raise NotImplementedError()

    def get_render_window(self) -> vtkRenderWindow:
        raise NotImplementedError()

    def render_callback(self):
        raise NotImplementedError()

    def start_callback(self):
        raise NotImplementedError()

    def session_changed_callback(self, session: Session):
        raise NotImplementedError()


class SessionFrame:

    def __init__(self,
                 session: Session,
                 name: str,
                 enable_skybox: bool,
                 vtk_components_factory: VtkComponentsFactory,
                 rendered_entities_spec: typing.Optional[RenderedEntitiesSpec] = None):

        self._name = name
        self._session = session
        self._actor_map: VtkOccActorMap = VtkOccActorMap()
        self._vtk_components_factory = vtk_components_factory

        self._interactor = vtk_components_factory.get_interactor()

        self._render_target_policy = RenderTargetPolicy(
            self._actor_map,
            vtk_components_factory.render_callback,
            {
                OCC.Core.TopAbs.TopAbs_VERTEX,
                OCC.Core.TopAbs.TopAbs_EDGE,
                OCC.Core.TopAbs.TopAbs_FACE
            })

        self._renderer = RendererFactory.get_session_renderer(session)
        self._render_callback = vtk_components_factory.render_callback

        if enable_skybox:
            self._skybox = vtkSkybox()
            self._skybox.SetTexture(self._renderer.environment_cubemaps.skybox_cubemap_texture)

            self._skybox.SetFloorPlane(0, 0, -1, 0.0)
            self._skybox.SetFloorRight(-1, 0, 0)
            self._renderer.scene_renderer.AddActor(self._skybox)
        else:
            self._skybox = None

        self.camera: vtkCamera = self._renderer.scene_renderer.GetActiveCamera()

        self._camera_policy = CameraPolicy(
            self._session,
            self._name,
            self.camera,
            self._render_callback)

        self._interactor_style = vtk_components_factory.get_interactor_style(
            self, self._actor_map, self._renderer, self._camera_policy, self._interactor, self._render_target_policy)

        if self._interactor_style is not None:
            self._interactor_style.SetDefaultRenderer(self._renderer.scene_renderer)
            self._interactor.SetInteractorStyle(self._interactor_style)

        self._render_window = vtk_components_factory.get_render_window()
        self._render_window.SetInteractor(self._interactor)
        self._render_window.AddRenderer(self._renderer.scene_renderer)

        self._rendered_entities_spec = RenderedEntitiesSpec(False, False, False) \
            if rendered_entities_spec is None else rendered_entities_spec

        for w in self._session.widgets:
            w.init_vtk_widget(self._interactor)

        axes_actor = vtkmodules.vtkRenderingAnnotation.vtkAxesActor()
        self._marker_widget = vtkmodules.vtkInteractionWidgets.vtkOrientationMarkerWidget()
        self._marker_widget.SetOrientationMarker(axes_actor)
        self._marker_widget.SetInteractor(self._interactor)
        self._marker_widget.EnabledOn()
        self._marker_widget.InteractiveOn()

        self._render_window.SetMultiSamples(8)

        self._session.listener_manager.add_listener(self.session_changed)

        vtk_components_factory.start_callback()
        self.start()

    @property
    def render_target_policy(self) -> RenderTargetPolicy:
        return self._render_target_policy

    def process_session_director_event(self):
        self._session.update()

        # clear the transforms back to their defaults
        for actor in self._actor_map.occ_actors():
            actor.actor.SetUserTransform(vtkTransform())
            actor.actor.GetUserTransform().PostMultiply()

        for part, transform_stack in self._session.scene_transforms.transforms().items():
            # part may not be built yet
            if not self._actor_map.contains_part(part):
                continue

            transform = transform_stack.get_gp_Trsf()
            vtk_transform = TransformConverter.convert_occ_to_vtk_transform(transform)

            for occ_actor in self._actor_map.get_occ_actors(part):
                occ_actor.actor.SetUserTransform(vtk_transform)

        self._render_callback()

    def start(self):
        if self._interactor is not None:
            self._interactor.Initialize()

        # needed to kickstart rendering when first opened
        self.session_changed(self._session)

        self._camera_policy.attempt_load_camera_from_cache()
        self._render_window.Render()

    @property
    def session(self):
        return self._session

    @property
    def interactor(self) -> vtkRenderWindowInteractor:
        return self._interactor

    @property
    def interactor_style(self) -> vtkInteractorStyle:
        return self._interactor_style

    @property
    def actor_map(self) -> VtkOccActorMap:
        return self._actor_map

    def add_widget(self, widget: vtk3DWidget):
        if widget in self._widgets:
            raise ValueError("Widget already added")

        widget.SetInteractor(self._interactor)

        self._widgets.append(widget)

    @staticmethod
    def _get_color_spec(part: SetPlaceablePart):
        return RenderingColorSpec(
            part,
            vertices_palette=SelectionPalette("white", "green"),
            edges_palette=SelectionPalette("dark_grey", "red"),
            faces_palette=SelectionPalette("grey", "green"),
            vertices_labelled_palette=SelectionPalette("blue", "green"),
            edges_labelled_palette=SelectionPalette("blue", "green"),
            faces_labelled_palette=SelectionPalette("light_blue", "green"))

    def session_changed(self, _: Session):
        """
        Informs the frame that a change to the session has occurred, actors may have moved or need to be regenerated
        @return:
        """
        for oa in self.actor_map.occ_actors():
            self._renderer.remove_actor(oa)

        self._actor_map.clear()

        logger.info("Rebuilding VTK actors")

        timestamp = time.time()
        parts = self._session.parts
        VtkActorCollectionBuilder(
            {*parts},
            SessionFrame._get_color_spec,
            self._rendered_entities_spec).populate_vtk_actors(self._actor_map)
        duration = time.time() - timestamp

        logger.info(f"Total actor building duration: {duration}")

        for oa in self._actor_map.occ_actors():
            self._renderer.add_actor(oa)

        self._render_target_policy.apply()
        self._renderer.scene_renderer.ResetCamera()
        self._vtk_components_factory.session_changed_callback(self._session)
        self._render_callback()
