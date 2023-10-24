from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout

from ezocc.cad.gui.pyqt.utils import WidgetUtils
from ezocc.cad.gui.pyqt.work_unit_editor import WorkUnitEditor
from ezocc.cad.gui.pyqt.work_unit_tree import WorkUnitTreeView, WorkUnitTreeButtonBar
from ezocc.cad.model.session import Session


class WorkUnitFrame(QtWidgets.QFrame):

    def __init__(self, session: Session, parent: QtWidgets.QWidget):
        super().__init__(parent)

        split_pane = QtWidgets.QSplitter(Qt.Orientation.Vertical, parent=self)

        self._session = session
        self._tree_view = WorkUnitTreeView(session, self)
        self._tree_button_bar = WorkUnitTreeButtonBar(session, self)
        self._work_unit_editor = WorkUnitEditor(session, self)

        split_pane.addWidget(WidgetUtils.vbox_frame(self._tree_view, self._tree_button_bar))
        split_pane.addWidget(self._work_unit_editor)

        layout = QVBoxLayout(self)
        layout.addWidget(split_pane)

        layout.addSpacerItem(QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        ))

        self.setLayout(layout)

    def deleteLater(self) -> None:
        super().deleteLater()

    @property
    def tree_view(self) -> WorkUnitTreeView:
        return self._tree_view
