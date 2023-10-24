import sys

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

from ezocc.cad.gui.pyqt.selection_info import InfoFrame
from ezocc.cad.gui.pyqt.view_3d import DisplayFrame
from ezocc.cad.gui.pyqt.work_unit import WorkUnitFrame
from ezocc.cad.model.session import Session


class DisplayWindow(QtWidgets.QMainWindow):

    def __init__(self, session: Session):
        super().__init__()
        self._session = session
        self._work_unit = session.selected_work_unit

        split_pane = QtWidgets.QSplitter(Qt.Orientation.Horizontal, parent=self)

        #self._work_unit_frame = WorkUnitFrame(session, parent=split_pane)
        self._display_frame = DisplayFrame(session, parent=split_pane)
        #self._info_frame = InfoFrame(parent=split_pane)

        #self._display_frame.selection_changed_signal.connect(self._info_frame.update_selection)

        #split_pane.addWidget(self._work_unit_frame)
        split_pane.addWidget(self._display_frame)
        #split_pane.addWidget(self._info_frame)

        self.setCentralWidget(split_pane)

    def deleteLater(self) -> None:
        self._session.listener_manager.remove_listener(self._session_changed)
        super().deleteLater()

    def start(self):
        self.show()
        self._display_frame.start()

