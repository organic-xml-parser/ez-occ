import typing

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QHBoxLayout

from ezocc.cad.gui.pyqt.widgets.translate_widget import TranslateWidgetToolFactory
from ezocc.cad.gui.pyqt.widgets.widgets import WidgetToolFactoryButton, WidgetTool
from ezocc.cad.gui.vtk.interaction import MousePickingInteractorStyle
from ezocc.cad.gui.vtk.vtk_occ_bridging import VtkOccActorMap
from ezocc.cad.model.session import Session

class WidgetToolbar(QtWidgets.QFrame):

    def __init__(self,
                 mps: MousePickingInteractorStyle,
                 session: Session,
                 actor_map: VtkOccActorMap,
                 parent: QtWidgets.QWidget):
        super().__init__(parent)

        layout = QHBoxLayout(self)

        self._interactor_style = mps
        self._session = session
        self._widget_tool: typing.Optional[WidgetTool] = None

        self._widget_buttons = [
            WidgetToolFactoryButton(mps,
                                    session,
                                    TranslateWidgetToolFactory(session, mps, actor_map),
                                    self.widget_created,
                                    self)
        ]

        for wb in self._widget_buttons:
            layout.addWidget(wb)

        layout.addSpacerItem(QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed))

        self._widget_commit_button = QtWidgets.QPushButton("Commit", self)
        self._widget_commit_button.setEnabled(False)
        self._widget_commit_button.clicked.connect(lambda _: self.commit())

        self._widget_detach_button = QtWidgets.QPushButton("Cancel", self)
        self._widget_detach_button.setEnabled(False)
        self._widget_detach_button.clicked.connect(lambda _: self.detach())

        layout.addWidget(self._widget_commit_button)
        layout.addWidget(self._widget_detach_button)

        self.setLayout(layout)

    def widget_created(self, widget_tool: WidgetTool):
        if self._widget_tool is not None:
            raise RuntimeError("A widget has already been created and activated!")

        for wb in self._widget_buttons:
            wb.setEnabled(False)

        self._interactor_style.selection_tracker.lock()
        self._widget_tool = widget_tool

        self._widget_commit_button.setEnabled(True)
        self._widget_detach_button.setEnabled(True)

    def detach(self):
        """
        Detaches all added widgets, freeing their resources and removing them from the scene.
        """
        if self._widget_tool is not None:
            self._interactor_style.selection_tracker.unlock()
            self._widget_tool.detach()
            self._widget_tool = None

            for wb in self._widget_buttons:
                wb.update_state()

            self._widget_commit_button.setEnabled(False)
            self._widget_detach_button.setEnabled(False)

    def commit(self):
        if self._widget_tool is None:
            raise RuntimeError("There is no widget tool to commit.")

        self._widget_tool.commit(self._session)
        self.detach()
