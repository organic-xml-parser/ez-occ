import typing

from PyQt5 import QtWidgets
from PyQt5.QtCore import QSize
from vtkmodules.vtkRenderingCore import vtkRenderer, vtkCamera

from ezocc.cad.gui.pyqt.icons.icons import Icons
from ezocc.cad.gui.pyqt.session_frame.view_align_button.view_align_icon import ViewAlignIcon


class ViewAlignButton(QtWidgets.QPushButton):

    def __init__(self,
                 view_dir: typing.Tuple[float, float, float],
                 view_up: typing.Tuple[float, float, float],
                 redraw_callback: typing.Callable[[], None],
                 renderer: vtkRenderer, parent: QtWidgets.QWidget=None):
        super().__init__(ViewAlignIcon(view_dir), "", parent)
        self.setIconSize(Icons.default_size())

        self._view_dir = view_dir
        self._view_up = view_up
        self._renderer = renderer
        self._redraw_callback = redraw_callback

        self.clicked.connect(lambda _: self.align_camera())

    def align_camera(self):

        camera: vtkCamera = self._renderer.GetActiveCamera()

        distance = camera.GetDistance()
        camera.SetPosition(*self._view_dir)
        camera.SetViewUp(*self._view_up)
        camera.SetFocalPoint(0, 0, 0)
        camera.SetDistance(distance)

        self._renderer.ResetCamera()
        self._redraw_callback()

