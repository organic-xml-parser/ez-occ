import typing

import OCC
import vtkmodules.vtkInteractionStyle
import vtkmodules.vtkRenderingOpenGL2
from PyQt5 import QtCore
from vtkmodules.vtkRenderingCore import vtkCellPicker, vtkActor, vtkPropCollection

from pythonoccutils.cad.gui.render_spec import EntityRenderingColorSpec
from pythonoccutils.cad.gui.vtk.vtk_occ_bridging import VtkOccActor, VtkOccActorMap
from pythonoccutils.cad.model.session import Session
from pythonoccutils.subshape_mapping import AnnotatedShape


class MousePickingEmitter(QtCore.QObject):

    selectionChangedSignal = QtCore.pyqtSignal(dict)


class MousePickingInteractorStyle(vtkmodules.vtkInteractionStyle.vtkInteractorStyleTrackballCamera):

    class SelectionTracker:

        def __init__(self, session: Session):
            self._session = session
            self._selected_elements: typing.Dict[VtkOccActor, typing.Set[OCC.Core.TopoDS.TopoDS_Shape]] = {}
            self.mousePickingEmitter = MousePickingEmitter()

            self._locked = False

        def lock(self):
            if self._locked:
                raise ValueError("Already Locked")

            self._locked = True

        def unlock(self):
            if not self._locked:
                raise ValueError("Already Unlocked")

            self._locked = False

        def append_selection(self,
                             vtk_occ_actor: VtkOccActor,
                             subshape: AnnotatedShape):
            if self._locked:
                return

            if vtk_occ_actor not in self._selected_elements:
                self._selected_elements[vtk_occ_actor] = set()

            vtk_occ_actor.highlight_subshape(subshape)

            self._selected_elements[vtk_occ_actor].add(subshape)

            self._session.workspace.select(subshape)

            self.mousePickingEmitter.selectionChangedSignal.emit(self._selected_elements)

        def clear_selection(self):
            if self._locked:
                return

            for vtk_occ_actor, _ in self._selected_elements.items():
                vtk_occ_actor.clear_highlights()

            self._selected_elements.clear()

            wsp = self._session.workspace
            if wsp is not None:
                wsp.clear_selection()

            self.mousePickingEmitter.selectionChangedSignal.emit({})

    def __init__(self,
                 session: Session,
                 actor_map: VtkOccActorMap,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._last_click_pos = None
        self.AddObserver("LeftButtonPressEvent", self.left_button_press_event)
        self.AddObserver("LeftButtonReleaseEvent", self.left_button_release_event)

        self._cell_picker = vtkCellPicker()
        self._cell_picker.SetTolerance(0.000001)

        self._actor_map = actor_map

        self.selection_tracker = MousePickingInteractorStyle.SelectionTracker(session)
        self._selection_color = EntityRenderingColorSpec.color_to_rgb("tomato")

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
        self._cell_picker.Pick(click_x, click_y, 0, self.GetDefaultRenderer())

        if self._cell_picker.GetCellId() == -1:
            self.selection_tracker.clear_selection()
            return

        picked_prop3d = self._cell_picker.GetProp3D()

        prop_collection = vtkPropCollection()
        picked_prop3d.GetActors(prop_collection)

        actor: vtkActor = [a for a in prop_collection][0]

        vtk_occ_actor = self._actor_map.get_vtk_occ_actor(actor)

        subshape = vtk_occ_actor.cell_ids_to_subshapes.get(self._cell_picker.GetCellId(), None)

        self.selection_tracker.append_selection(vtk_occ_actor, subshape)
