import typing

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QSpacerItem, QSizePolicy
from vtkmodules.vtkRenderingCore import vtkRenderer

from ezocc.cad.gui.pyqt.session_frame.camera_policy import CameraPolicy
from ezocc.cad.gui.pyqt.session_frame.parallel_perspective_toggle_button import ParallelPerspectiveToggleButton
from ezocc.cad.gui.pyqt.session_frame.render_target_controls.render_target_panel import RenderTargetGroupBox
from ezocc.cad.gui.pyqt.session_frame.render_target_policy import RenderTargetPolicy
from ezocc.cad.gui.pyqt.session_frame.selection_target_controls.selection_target_panel import SelectionTargetGroupBox
from ezocc.cad.gui.pyqt.session_frame.view_align_button.view_align_button import ViewAlignButton
from ezocc.cad.gui.vtk.mouse_picking_interactor_style import MousePickingInteractorStyle


class SessionFrameToolbar(QtWidgets.QWidget):

    def __init__(self,
                 renderer: vtkRenderer,
                 camera_policy: CameraPolicy,
                 redraw_callback: typing.Callable[[], None],
                 interactor_style: MousePickingInteractorStyle,
                 render_target_policy: RenderTargetPolicy,
                 parent: QtWidgets.QWidget):
        super().__init__(parent)
        self._renderer = renderer

        layout = QHBoxLayout()

        v_seg = QVBoxLayout()
        v_seg.addWidget(ViewAlignButton((1, 0, 0), (0, 0, 1), redraw_callback, renderer, self))
        v_seg.addWidget(ViewAlignButton((-1, 0, 0), (0, 0, 1), redraw_callback, renderer, self))
        layout.addItem(v_seg)

        v_seg = QVBoxLayout()
        v_seg.addWidget(ViewAlignButton((0, 1, 0), (0, 0, 1), redraw_callback, renderer, self))
        v_seg.addWidget(ViewAlignButton((0, -1, 0), (0, 0, 1), redraw_callback, renderer, self))
        layout.addItem(v_seg)

        v_seg = QVBoxLayout()
        v_seg.addWidget(ViewAlignButton((0, 0, 1), (0, 1, 0), redraw_callback, renderer, self))
        v_seg.addWidget(ViewAlignButton((0, 0, -1), (0, 1, 0), redraw_callback, renderer, self))
        layout.addItem(v_seg)

        layout.addWidget(ViewAlignButton((1, 1, 1), (0, 0, 1), redraw_callback, renderer, self))

        layout.addWidget(ParallelPerspectiveToggleButton(camera_policy, self))

        layout.addItem(QSpacerItem(1, 1, vPolicy=QSizePolicy.Minimum, hPolicy=QSizePolicy.Expanding))

        layout.addWidget(RenderTargetGroupBox(render_target_policy, self))
        layout.addWidget(SelectionTargetGroupBox(interactor_style, self))

        self.setLayout(layout)
