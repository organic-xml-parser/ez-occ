import OCC.Core.TopAbs
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

from ezocc.cad.gui.pyqt.driver_frame.session_driver_frame import SessionDirectorFrame
from ezocc.cad.gui.pyqt.session_frame.session_frame import SessionFrame
from ezocc.cad.gui.pyqt.inspector_frame.subshape_inspector_frame import SubShapeInspectorFrame
from ezocc.cad.gui.pyqt.session_frame.session_frame_qt import SessionFrameQt
from ezocc.cad.gui.vtk.mouse_picking_interactor_style import MousePickingInteractorStyle
from ezocc.cad.model.session import Session


class DisplayWindow(QtWidgets.QMainWindow):

    def __init__(self, session: Session):
        super().__init__()
        self._session = session

        self._session_frame = SessionFrameQt(session, "main", enable_skybox=True, enable_selection=True, parent=self)
        self._session_frame.session_frame.render_target_policy.set_shape_type_renderable(OCC.Core.TopAbs.TopAbs_VERTEX, False)
        self._session_frame.session_frame.interactor_style.set_pick_discriminator(
            MousePickingInteractorStyle.PickDiscriminator({OCC.Core.TopAbs.TopAbs_FACE}))

        self._session_driver_frame = SessionDirectorFrame(
            session,
            self._session_frame.session_frame.process_session_director_event)

        self._subshape_inspector_frame = SubShapeInspectorFrame(self._session_frame)

        session_inspector_pane = QtWidgets.QSplitter(Qt.Orientation.Horizontal, parent=self)
        session_inspector_pane.addWidget(self._session_frame)
        session_inspector_pane.addWidget(self._subshape_inspector_frame)
        session_inspector_pane.setStretchFactor(0, 10)
        session_inspector_pane.setStretchFactor(1, 3)

        driver_split_pane = QtWidgets.QSplitter(Qt.Orientation.Vertical, parent=self)
        driver_split_pane.addWidget(session_inspector_pane)
        driver_split_pane.addWidget(self._session_driver_frame)

        self.setCentralWidget(driver_split_pane)

    def deleteLater(self) -> None:
        self._session.listener_manager.remove_listener(self._session_changed)
        super().deleteLater()

    def start(self):
        self.show()
