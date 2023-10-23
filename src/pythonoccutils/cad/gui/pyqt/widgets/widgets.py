import typing

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QHBoxLayout

from pythonoccutils.cad.gui.pyqt.utils import WidgetUtils
from pythonoccutils.cad.gui.vtk.interaction import MousePickingInteractorStyle
from pythonoccutils.cad.model.event import SessionEvent
from pythonoccutils.cad.model.session import Session


class WidgetTool:

    def commit(self, session):
        """
        Commits the related changes to the session, usually by adding a work_unit/work_unit_command with the changes
        recorded as parameters.
        """
        raise NotImplementedError()

    def detach(self):
        """
        Removes rendered entities that were added to the scene. Makes no changes to the underlying work_unit or
        selection.
        """
        raise NotImplementedError()


class WidgetToolFactory:
    """
    Handles interaction of one or more VTK widgets. Widget interactions can be initiated
    via toolbox buttons, allowing the user to e.g. translate objects. Once the user has
    manipulated widgets to the desired state, the changes can be "committed". The widget
    will be removed and the resulting changes added to the work unit tree.
    """

    def name(self) -> str:
        raise NotImplementedError()

    def can_create(self) -> bool:
        """
        Indicates whether the session is in a state that permits the given widget to be created. Usually this relates to
        selections. For example, a translation widget would require an entity to be selected in order to be applied.
        """
        raise NotImplementedError()

    def create(self) -> WidgetTool:
        """
        Creates the required tool and adds it to the rendered scene.
        """
        raise NotImplementedError()


class WidgetToolFactoryButton(QtWidgets.QPushButton):

    def __init__(self,
                 mps: MousePickingInteractorStyle,
                 session: Session,
                 widget_tool_factory: WidgetToolFactory,
                 widget_consumer: typing.Callable[[WidgetTool], None],
                 parent: QtWidgets.QWidget):
        super().__init__(parent)
        self._widget_tool_factory = widget_tool_factory
        self._widget_consumer = widget_consumer

        self.setText(self._widget_tool_factory.name())

        self._session = session

        self.update_state()
        mps.selection_tracker.mousePickingEmitter.selectionChangedSignal.connect(self.update_state)
        session.listener_manager.add_listener(self.update_state)

        self.clicked.connect(self.btn_clicked)

    def btn_clicked(self):
        self._widget_consumer(self._widget_tool_factory.create())

    def update_state(self, *args):
        can_create = self._widget_tool_factory.can_create()

        self.setEnabled(can_create)

