from PyQt5.QtCore import QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QPushButton, QWidget

from ezocc.cad.gui.pyqt.icons.vector_icon_engine import VectorIconEngine
from ezocc.cad.gui.pyqt.session_frame.camera_policy import CameraPolicy


class ParallelPerspectiveToggleButton(QPushButton):

    class IconEngine(VectorIconEngine):

        def __init__(self, camera_policy: CameraPolicy):
            super().__init__()
            self._camera_policy = camera_policy

        def paint(self, painter, rect, mode, state):

            if self._camera_policy.get_parallel_projection():
                super().draw_face([
                    (rect.x() + rect.width() * 0.4, rect.y() + rect.height() * 0.2),
                    (rect.x() + rect.width() * 0.6, rect.y() + rect.height() * 0.2),
                    (rect.x() + rect.width() * 0.8, rect.y() + rect.height() * 0.8),
                    (rect.x() + rect.width() * 0.2, rect.y() + rect.height() * 0.8),
                ], painter, rect, mode, state)
            else:
                super().draw_face([
                    (rect.x() + rect.width() * 0.3, rect.y() + rect.height() * 0.8),
                    (rect.x() + rect.width() * 0.7, rect.y() + rect.height() * 0.8),
                    (rect.x() + rect.width() * 0.7, rect.y() + rect.height() * 0.2),
                    (rect.x() + rect.width() * 0.3, rect.y() + rect.height() * 0.2),
                ], painter, rect, mode, state)

    def __init__(self, camera_policy: CameraPolicy, parent: QWidget = None):
        super().__init__(QIcon(ParallelPerspectiveToggleButton.IconEngine(camera_policy)), "", parent)
        self.setIconSize(QSize(32, 32))
        self._camera_policy = camera_policy
        self._camera_policy.camera_change_emitter.parallel_projection_signal.connect(lambda: self.repaint())

        self.clicked.connect(lambda *_: self.toggle_projection())

    def toggle_projection(self):
        new_setting = not self._camera_policy.get_parallel_projection()
        self._camera_policy.set_parallel_projection(new_setting)

