import typing

from ezocc.cad.model.event import Listenable, SessionEvent, SessionEventType
from ezocc.cad.model.work_unit import WorkUnit
from ezocc.cad.model.work_unit_factory import WorkUnitCommandFactory
from ezocc.cad.model.workspace.workspace import Workspace


class Session(Listenable):

    def __init__(self):
        super().__init__()

        self._root_unit = WorkUnit(name="root", parent=None, commands=[])
        self._selected_unit: typing.Optional[WorkUnit] = None
        self._workspace: typing.Optional[Workspace] = None
        self._error_state: typing.Optional[BaseException] = None
        self.work_unit_command_factory = WorkUnitCommandFactory()

    @property
    def root_unit(self):
        return self._root_unit

    @property
    def selected_work_unit(self) -> typing.Optional[WorkUnit]:
        return self._selected_unit

    def select_work_unit(self, work_unit: WorkUnit):
        if work_unit is not None and not WorkUnit.is_parent(self._root_unit, work_unit):
            raise ValueError("Work unit not present in document")

        if self._selected_unit == work_unit:
            # no change made
            return

        self._set_selected_work_unit(work_unit)
        self.listener_manager.notify(SessionEvent(self, SessionEventType.UPDATED))

    def add_work_unit_to_selected(self):
        if self._selected_unit is None:
            raise ValueError("No Work Unit is currently selected")

        wu = WorkUnit("new work unit", self._selected_unit, [])
        self._selected_unit.add_child(wu)
        self._set_selected_work_unit(wu)
        self.listener_manager.notify(SessionEvent(self, SessionEventType.INDIRECT))

    def delete_selected_work_unit(self):
        if self._selected_unit is None:
            raise ValueError("No Work Unit is currently selected")

        if self._selected_unit.parent is None:
            raise ValueError("Cannot delete root work unit")

        to_remove = self._selected_unit
        self._set_selected_work_unit(self._selected_unit.parent)
        self._selected_unit.remove_child(to_remove)
        self.listener_manager.notify(SessionEvent(self, SessionEventType.UPDATED))

    def _set_selected_work_unit(self, new_unit: typing.Optional[WorkUnit]):
        if self._selected_unit is not None:
            self._selected_unit.listener_manager.remove_listener(self._selected_work_unit_changed)

        self._selected_unit = new_unit
        self._selected_unit.listener_manager.add_listener(self._selected_work_unit_changed)
        self._workspace = None
        self.build_workspace()

    def _selected_work_unit_changed(self, session_event: SessionEvent):
        self.build_workspace()
        self.listener_manager.notify(SessionEvent(self, SessionEventType.INDIRECT))

    @property
    def workspace(self):
        return self._workspace

    def build_workspace(self):
        if self._selected_unit is None:
            return None

        try:
            self._workspace = self._selected_unit.perform()
        except BaseException as e:
            self._workspace = None
            self._error_state = e
            print(e)

        self.listener_manager.notify(SessionEvent(self, SessionEventType.UPDATED))
