import typing

import OCC.Core.TopAbs
import vtkmodules.vtkInteractionStyle
import vtkmodules.vtkRenderingOpenGL2
from PyQt5 import QtCore
from vtkmodules.vtkRenderingCore import vtkPropCollection, vtkCellPicker, vtkRenderer, vtkRenderWindow
from vtkmodules.vtkRenderingVolume import vtkVolumePicker

from ezocc.cad.gui.vtk.rendering_utils.renderer_factory import SessionRenderer
from ezocc.cad.gui.vtk.vtk_occ_actor import VtkOccActor
from ezocc.cad.gui.vtk.vtk_occ_actor_map import VtkOccActorMap
from ezocc.cad.model.session import Session
from ezocc.occutils_python import SetPlaceableShape


class MousePickingEmitter(QtCore.QObject):

    selectionChangedSignal = QtCore.pyqtSignal(tuple, dict)


class MousePickingInteractorStyle(vtkmodules.vtkInteractionStyle.vtkInteractorStyleTrackballCamera):

    class SelectionTracker:

        def __init__(self):
            self._primary_selection: typing.Optional[typing.Tuple[VtkOccActor, typing.Set[SetPlaceableShape]]] = None
            self._selected_elements: typing.Dict[VtkOccActor, typing.Set[SetPlaceableShape]] = {}
            self.mousePickingEmitter = MousePickingEmitter()

        @property
        def selected_elements(self) -> typing.Dict[VtkOccActor, typing.Set[SetPlaceableShape]]:
            return self._selected_elements.copy()

        def append_selection(self,
                             vtk_occ_actor: VtkOccActor,
                             subshape: SetPlaceableShape):

            if vtk_occ_actor not in self._selected_elements:
                self._selected_elements[vtk_occ_actor] = set()

            vtk_occ_actor.highlight_subshape(subshape)

            self._selected_elements[vtk_occ_actor].add(subshape)

            self._primary_selection = (vtk_occ_actor, subshape)

            self.mousePickingEmitter.selectionChangedSignal.emit(self._primary_selection, self._selected_elements)

        def clear_selection(self):

            for vtk_occ_actor, _ in self._selected_elements.items():
                vtk_occ_actor.clear_highlights()

            self._selected_elements.clear()
            self._primary_selection = None

            self.mousePickingEmitter.selectionChangedSignal.emit((), {})

    class PickDiscriminator:

        def __init__(self, pickable_shape_types: typing.Set[OCC.Core.TopAbs.TopAbs_ShapeEnum]):
            self._pickable_shape_types = pickable_shape_types.copy()

        def can_pick(self, vtk_occ_actor: VtkOccActor, subshape: SetPlaceableShape) -> bool:
            return subshape.shape.ShapeType() in self.pickable_shape_types

        @property
        def pickable_shape_types(self) -> typing.Set[OCC.Core.TopAbs.TopAbs_ShapeEnum]:
            return self._pickable_shape_types.copy()

    def __init__(self,
                 actor_map: VtkOccActorMap,
                 session_renderer: SessionRenderer,
                 *args,
                 **kwargs):
        super().__init__(*args, **kwargs)

        self._session_renderer = session_renderer

        self._last_click_pos = None
        self._pick_discriminator = MousePickingInteractorStyle.PickDiscriminator(set())
        self.AddObserver("LeftButtonPressEvent", self.left_button_press_event)
        self.AddObserver("LeftButtonReleaseEvent", self.left_button_release_event)

        self._actor_map = actor_map

        self.selection_tracker = MousePickingInteractorStyle.SelectionTracker()

    @property
    def pick_discriminator(self) -> PickDiscriminator:
        return self._pick_discriminator

    def set_pick_discriminator(self, pick_discriminator: PickDiscriminator):
        self._pick_discriminator = pick_discriminator

        new_selected_elements = {}

        for k, v in self.selection_tracker.selected_elements.items():
            new_selected_elements[k] = set()
            for vv in v:
                if self._pick_discriminator.can_pick(k, vv):
                    new_selected_elements[k].add(vv)

        self.selection_tracker.clear_selection()

        for k, v in new_selected_elements.items():
            for vv in v:
                self.selection_tracker.append_selection(k, vv)

    def clear(self):
        self.selection_tracker.clear_selection()

    def left_button_press_event(self, obj, event):
        self._last_click_pos = self.GetInteractor().GetEventPosition()
        self.OnLeftButtonDown()

    def left_button_release_event(self, obj, event):
        click_pos = self.GetInteractor().GetEventPosition()

        if click_pos[0] == self._last_click_pos[0] and click_pos[1] == self._last_click_pos[1]:
            self.pick(self._last_click_pos[0], self._last_click_pos[1])

        self.OnLeftButtonUp()

    def pick(self, click_x, click_y):
        print("Picking...")
        selection: typing.List[typing.Tuple[VtkOccActor, SetPlaceableShape]] = []
        self._pick_with_renderer(click_x, click_y, self._session_renderer.vertex_selection_renderer, 0.01, selection)
        self._pick_with_renderer(click_x, click_y, self._session_renderer.edge_selection_renderer, 0.01, selection)
        self._pick_with_renderer(click_x, click_y, self._session_renderer.face_selection_renderer, 0.00001, selection)

        selection = [(k, v) for k, v in selection if self._pick_discriminator.can_pick(k, v)]

        if len(selection) == 0:
            print("Clearing selection")
            self.selection_tracker.clear_selection()
        else:
            for k, v in selection:
                self.selection_tracker.append_selection(k, v)

    def _pick_with_renderer(self,
                            click_x,
                            click_y,
                            renderer: vtkRenderer,
                            tol: float,
                            selection: typing.List[typing.Tuple[VtkOccActor, SetPlaceableShape]]):

        rw = vtkRenderWindow()
        rw.AddRenderer(renderer)
        rw.SetSize(self.GetDefaultRenderer().GetRenderWindow().GetSize())

        renderer.SetActiveCamera(self.GetDefaultRenderer().GetActiveCamera())

        cell_picker = vtkVolumePicker()
        cell_picker.SetTolerance(tol)

        cell_picker.Pick(click_x, click_y, 0, renderer)

        if cell_picker.GetCellId() == -1:
            return

        picked_prop3d = cell_picker.GetProp3D()

        prop_collection = vtkPropCollection()
        picked_prop3d.GetActors(prop_collection)

        vtk_occ_actors = [self._actor_map.get_vtk_occ_actor(a) for a in prop_collection]

        actors_to_subshapes = {a: a.get_subshape_for_cell_id(cell_picker.GetCellId()) for a in vtk_occ_actors}
        actors_to_subshapes = {k: v for k, v in actors_to_subshapes.items() if self._pick_discriminator.can_pick(k, v)}

        if len(actors_to_subshapes.items()) == 0:
            return

        for k, v in actors_to_subshapes.items():
            selection.append((k, v))
