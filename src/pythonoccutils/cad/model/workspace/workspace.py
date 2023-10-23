import typing

from pythonoccutils.cad.gui.vtk.vtk_occ_bridging import SetPlaceableShape
from pythonoccutils.cad.model.event import Listenable, SessionEvent, SessionEventType
from pythonoccutils.occutils_python import InterrogateUtils
from pythonoccutils.part_manager import Part


class Workspace(Listenable):
    """
    Captures the state of the workspace at any given moment between WorkUnit operations.
    """

    def __init__(self, parts: typing.Dict[str, Part]):
        super().__init__()
        self._parts = parts.copy()
        self._selection: typing.Set[SetPlaceableShape] = set()

    def select(self, shape: SetPlaceableShape):
        self._selection.add(shape)

        self.listener_manager.notify(SessionEvent(self, SessionEventType.UPDATED))

    def clear_selection(self):
        self._selection.clear()

        self.listener_manager.notify(SessionEvent(self, SessionEventType.UPDATED))

    @property
    def selection(self):
        return self._selection.copy()

    @property
    def selected_parts(self) -> typing.Set[str]:
        """
        Determines which parts have been selected.
        """

        result = set()

        for name, part in self._parts.items():
            if any(InterrogateUtils.is_parent_shape(part.shape, s.shape) for s in self._selection):
                result.add(name)

        return result

    def create_part(self, name: str, part: Part):
        if part is None:
            raise ValueError("Part may not be none.")

        if name in self._parts:
            raise ValueError(f"Part with name \"{name}\" already exists.")

        self._parts[name] = part

        self.listener_manager.notify(SessionEvent(self, SessionEventType.UPDATED))

    def update_part(self, name: str, updater: typing.Callable[[Part], Part]):
        self._parts[name] = updater(self._parts[name])

        self.listener_manager.notify(SessionEvent(self, SessionEventType.UPDATED))

    def get_part(self, name: str):
        return self._parts[name]

    @property
    def parts(self) -> typing.Dict[str, Part]:
        return self._parts.copy()

    def copy(self):
        return Workspace(self.parts.copy())
