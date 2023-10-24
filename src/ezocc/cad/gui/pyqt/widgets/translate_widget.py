import typing

from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkInteractionWidgets import vtkBoxWidget, vtkLineWidget, vtkSliderWidget, vtkSphereWidget
from vtkmodules.vtkRenderingCore import vtkActor, vtkRenderWindowInteractor

from ezocc.cad.gui.pyqt.widgets.widgets import WidgetToolFactory, WidgetTool
from ezocc.cad.gui.vtk.interaction import MousePickingInteractorStyle
from ezocc.cad.gui.vtk.vtk_occ_bridging import VtkOccActorMap
from ezocc.cad.model.session import Session
from ezocc.cad.model.work_unit_factory import TranslateWorkUnitCommand
from ezocc.part_manager import Part


class TranslateWidgetTool(WidgetTool):

    def __init__(self,
                 session: Session,
                 part_name: str,
                 part: Part,
                 vtk_actors: typing.Set[vtkActor],
                 interactor_style: MousePickingInteractorStyle):
        self._session = session
        self._part_name = part_name
        self._part = part
        self._vtk_actors: typing.Dict[vtkActor, vtkTransform] = \
            {v: v.GetUserTransform() for v in vtk_actors}

        self._interactor: vtkRenderWindowInteractor = interactor_style.GetInteractor()
        prop_3d = next(iter(self._vtk_actors))

        self._widget = vtkSphereWidget()
        self._widget.SetInteractor(self._interactor)
        self._widget.SetRepresentationToWireframe()
        self._widget.SetProp3D(prop_3d)
        self._widget.SetPlaceFactor(1.25)
        self._widget.PlaceWidget()
        self._widget.On()

        self._initial_handle_posiiton = self._widget.GetHandlePosition()

        self._widget.AddObserver('InteractionEvent', self._widget_callback)

    def _widget_callback(self, obj, event):
        self._handle_position = self._widget.GetHandlePosition()

        for a, at in self._vtk_actors.items():
            at_copy = at.DeepCopy() if at is not None else vtkTransform()
            at_copy.Translate(*self._translation)
            a.SetUserTransform(at_copy)

    @property
    def _translation(self) -> typing.Tuple[float, float, float]:
        return (
            self._handle_position[0] - self._initial_handle_posiiton[0],
            self._handle_position[1] - self._initial_handle_posiiton[1],
            self._handle_position[2] - self._initial_handle_posiiton[2]
        )

    def commit(self, session):
        cmd = TranslateWorkUnitCommand(self._part_name, *self._translation)
        self._session.selected_work_unit.add_command(cmd)

    def detach(self):
        self._widget.Off()
        self._widget.RemoveAllObservers()
        self._widget.SetInteractor(None)

        for v, t in self._vtk_actors.items():
            v.SetUserTransform(t)

        self._interactor.GetRenderWindow().Render()


class TranslateWidgetToolFactory(WidgetToolFactory):

    def __init__(self,
                 session: Session,
                 interactor_style: MousePickingInteractorStyle,
                 actor_map: VtkOccActorMap):
        self._session = session
        self._interactor_style = interactor_style
        self._actor_map = actor_map

    def name(self) -> str:
        return "Translate"

    def can_create(self) -> bool:
        if self._session.workspace is None:
            return False

        selected_parts = self._session.workspace.selected_parts

        return len(selected_parts) == 1

    def create(self) -> WidgetTool:
        part_name = next(iter(self._session.workspace.selected_parts))

        part = self._session.workspace.parts[part_name]

        vtk_actors = self._actor_map.get_vtk_actors(part)

        return TranslateWidgetTool(self._session, part_name, part, vtk_actors, self._interactor_style)

