import OCC.Core.TopAbs
from PyQt5.QtWidgets import QGroupBox, QWidget, QHBoxLayout, QPushButton

from ezocc.cad.gui.pyqt.icons.icons import Icons
from ezocc.cad.gui.vtk.mouse_picking_interactor_style import MousePickingInteractorStyle


class SelectionTargetGroupBox(QGroupBox):

    def __init__(self, interactor_style: MousePickingInteractorStyle, parent: QWidget = None):
        super().__init__("Selection Targets", parent)

        self._interactor_style = interactor_style

        layout = QHBoxLayout()

        self._vertex_toggle_button = QPushButton(Icons.vertex_icon(), "", self)
        self._vertex_toggle_button.setIconSize(Icons.default_size())
        self._vertex_toggle_button.setCheckable(True)
        self._vertex_toggle_button.clicked.connect(
            lambda b: self.set_shape_type_selectable(OCC.Core.TopAbs.TopAbs_VERTEX, b))
        layout.addWidget(self._vertex_toggle_button)

        self._edge_toggle_button = QPushButton(Icons.edge_icon(), "", self)
        self._edge_toggle_button.setIconSize(Icons.default_size())
        self._edge_toggle_button.setCheckable(True)
        self._edge_toggle_button.clicked.connect(
            lambda b: self.set_shape_type_selectable(OCC.Core.TopAbs.TopAbs_EDGE, b))
        layout.addWidget(self._edge_toggle_button)

        self._face_toggle_button = QPushButton(Icons.face_icon(), "", self)
        self._face_toggle_button.setIconSize(Icons.default_size())
        self._face_toggle_button.setCheckable(True)
        self._face_toggle_button.clicked.connect(
            lambda b: self.set_shape_type_selectable(OCC.Core.TopAbs.TopAbs_FACE, b))
        layout.addWidget(self._face_toggle_button)

        self.update_button_check_states()

        (interactor_style.selection_tracker
         .mousePickingEmitter.selectionChangedSignal.connect(lambda *_: self.update_button_check_states()))

        self.setLayout(layout)

    def set_shape_type_selectable(self, shape_type: OCC.Core.TopAbs.TopAbs_ShapeEnum, is_visible: bool):
        pickable_shape_types = self._interactor_style.pick_discriminator.pickable_shape_types

        if is_visible:
            pickable_shape_types.add(shape_type)
        else:
            pickable_shape_types.remove(shape_type)

        self._interactor_style.set_pick_discriminator(
            MousePickingInteractorStyle.PickDiscriminator(pickable_shape_types))

    def update_button_check_states(self):
        pickable_shape_types = self._interactor_style.pick_discriminator.pickable_shape_types

        self._vertex_toggle_button.setChecked(OCC.Core.TopAbs.TopAbs_VERTEX in pickable_shape_types)
        self._edge_toggle_button.setChecked(OCC.Core.TopAbs.TopAbs_EDGE in pickable_shape_types)
        self._face_toggle_button.setChecked(OCC.Core.TopAbs.TopAbs_FACE in pickable_shape_types)
