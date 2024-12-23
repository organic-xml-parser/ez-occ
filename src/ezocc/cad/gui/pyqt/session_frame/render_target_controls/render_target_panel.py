import OCC.Core.TopAbs
from PyQt5.QtWidgets import QGroupBox, QWidget, QHBoxLayout, QPushButton

from ezocc.cad.gui.pyqt.icons.icons import Icons
from ezocc.cad.gui.pyqt.session_frame.render_target_policy import RenderTargetPolicy
from ezocc.cad.gui.vtk.mouse_picking_interactor_style import MousePickingInteractorStyle
from ezocc.cad.gui.vtk.vtk_occ_actor_map import VtkOccActorMap


class RenderTargetGroupBox(QGroupBox):

    def __init__(self, render_target_policy: RenderTargetPolicy, parent: QWidget = None):
        super().__init__("Render Targets", parent)

        self._render_target_policy = render_target_policy

        layout = QHBoxLayout()

        self._vertex_toggle_button = QPushButton(Icons.vertex_icon(), "", self)
        self._vertex_toggle_button.setIconSize(Icons.default_size())
        self._vertex_toggle_button.setCheckable(True)
        self._vertex_toggle_button.clicked.connect(
            lambda b: self.set_shape_type_renderable(OCC.Core.TopAbs.TopAbs_VERTEX, b))
        layout.addWidget(self._vertex_toggle_button)

        self._edge_toggle_button = QPushButton(Icons.edge_icon(), "", self)
        self._edge_toggle_button.setIconSize(Icons.default_size())
        self._edge_toggle_button.setCheckable(True)
        self._edge_toggle_button.clicked.connect(
            lambda b: self.set_shape_type_renderable(OCC.Core.TopAbs.TopAbs_EDGE, b))
        layout.addWidget(self._edge_toggle_button)

        self._face_toggle_button = QPushButton(Icons.face_icon(), "", self)
        self._face_toggle_button.setIconSize(Icons.default_size())
        self._face_toggle_button.setCheckable(True)
        self._face_toggle_button.clicked.connect(
            lambda b: self.set_shape_type_renderable(OCC.Core.TopAbs.TopAbs_FACE, b))
        layout.addWidget(self._face_toggle_button)

        self.update_button_check_states()

        render_target_policy.emitter.signal.connect(lambda: self.update_button_check_states())

        self.setLayout(layout)

    def set_shape_type_renderable(self, shape_type: OCC.Core.TopAbs.TopAbs_ShapeEnum, is_visible: bool):
        self._render_target_policy.set_shape_type_renderable(shape_type, is_visible)

    def update_button_check_states(self):
        renderable_shape_types = self._render_target_policy.rendered_shape_types

        should_check_verts = OCC.Core.TopAbs.TopAbs_VERTEX in renderable_shape_types
        should_check_edges = OCC.Core.TopAbs.TopAbs_EDGE in renderable_shape_types
        should_check_faces = OCC.Core.TopAbs.TopAbs_FACE in renderable_shape_types

        if self._vertex_toggle_button.isChecked() != should_check_verts:
            self._vertex_toggle_button.setChecked(should_check_verts)

        if self._edge_toggle_button.isChecked() != should_check_edges:
            self._edge_toggle_button.setChecked(should_check_edges)

        if self._face_toggle_button.isChecked() != should_check_faces:
            self._face_toggle_button.setChecked(should_check_faces)
