import sys
import typing

import OCC.Display.OCCViewer
from OCC.Core.AIS import AIS_Shape, AIS_InteractiveContext
import OCC.Core.TopAbs
import OCC.Core.TopoDS
import OCC.Core.gp
from OCC.Core.TColStd import TColStd_ListOfInteger
from PyQt5 import QtWidgets, QtGui, QtCore

import ezocc.occutils_python as op
import ezocc.part_manager as part_manager


class SelectionPropertiesWidget(QtWidgets.QFrame):

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)

        layout.addWidget(QtWidgets.QPushButton(text="Test", parent=self))

        self.setLayout(layout)

    def selection_changed(self, selection: typing.List[OCC.Core.TopoDS.TopoDS_Shape]):

        # remove the current items from the layout
        for i in reversed(range(self.layout().count())):
            self.layout().itemAt(i).widget().deleteLater()

        for shape in selection:
            self.layout().addWidget(self._get_shape_properties_widget(shape))

    def _get_shape_properties_widget(self, shape: OCC.Core.TopoDS.TopoDS_Shape):
        return QtWidgets.QLabel(f"{shape.ShapeType()}", self)


class SelectionFrame(QtWidgets.QFrame):

    def __init__(self, parent: QtWidgets.QWidget, part: part_manager.Part):
        super().__init__(parent)
        self._part = part

        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(QtWidgets.QLabel("Selected:"), 0, 0)

        self._selection_label = QtWidgets.QLabel("")
        layout.addWidget(self._selection_label, 0, 1)

        self._query_suggestions = QtWidgets.QPlainTextEdit()

        layout.addWidget(self._query_suggestions, 1, 0, 1, 2)

        self._selection_properties_widget = SelectionPropertiesWidget(self)

        layout.addWidget(self._selection_properties_widget, 2, 0, 1, 2)

        self.setLayout(layout)

    @QtCore.pyqtSlot(list, name="selection_changed_slot")
    def selection_changed_slot(self, selected_shapes: typing.List[OCC.Core.TopoDS.TopoDS_Shape]):
        self._selection_properties_widget.selection_changed(selected_shapes)

        if len(selected_shapes) == 0:
            self._selection_label.clear()
            self._query_suggestions.clear()
            return

        self._selection_label.setText(", ".join([str(s) for s in selected_shapes]))

        pr = part_manager.PartSelectionResolver(self._part, *selected_shapes)

        self._query_suggestions.clear()
        self._query_suggestions.setPlainText(", ".join(pr.get_suggested_selections()))


class SelectionTypeFrame(QtWidgets.QFrame):

    def __init__(self,
                 face_annotations_slot,
                 edge_annotations_slot,
                 toggle_selection_mode_slot):
        super().__init__()
        layout = QtWidgets.QHBoxLayout(self)

        self._selection_toggle_buttons = [
            (PartDisplay.Vertex, QtWidgets.QPushButton("Vertex")),
            (PartDisplay.Edge, QtWidgets.QPushButton("Edge")),
            (PartDisplay.Wire, QtWidgets.QPushButton("Wire")),
            (PartDisplay.Face, QtWidgets.QPushButton("Face"))
        ]

        layout.addWidget(QtWidgets.QLabel("Selection Modes:"))

        for i in range(0, len(self._selection_toggle_buttons)):
            val = self._selection_toggle_buttons[i][0]

            def toggle(toggle_val):

                def result():
                    toggle_selection_mode_slot(toggle_val)

                return result

            self._selection_toggle_buttons[i][1].clicked.connect(toggle(val))

            layout.addWidget(self._selection_toggle_buttons[i][1])

        self._toggle_edge_annotations = QtWidgets.QPushButton("Edge Dirs")
        self._toggle_edge_annotations.clicked.connect(edge_annotations_slot)
        self._toggle_face_normals = QtWidgets.QPushButton("Face Normals")
        self._toggle_face_normals.clicked.connect(face_annotations_slot)

        layout.addItem(QtWidgets.QSpacerItem(0, 0, hPolicy=QtWidgets.QSizePolicy.Policy.Expanding))
        layout.addWidget(self._toggle_edge_annotations)
        layout.addWidget(self._toggle_face_normals)

        self.setLayout(layout)
        self.sizePolicy().setVerticalPolicy(QtWidgets.QSizePolicy.Policy.Minimum)
        self.updateGeometry()

    @staticmethod
    def update_button(button: QtWidgets.QPushButton, is_button_enabled: bool):
        if is_button_enabled:
            button.setStyleSheet("background-color : green; color: black")
        else:
            button.setStyleSheet("background-color : lightgrey; color: grey")

    @QtCore.pyqtSlot(bool, name="face_annotation_set")
    def face_annotation_set(self, is_visible: bool):
        SelectionTypeFrame.update_button(self._toggle_face_normals, is_visible)

    @QtCore.pyqtSlot(bool, name="edge_annotation_set")
    def edge_annotation_set(self, is_visible: bool):
        SelectionTypeFrame.update_button(self._toggle_edge_annotations, is_visible)

    def selection_set(self, active_modes: typing.Set[int]):
        for i, tb in self._selection_toggle_buttons:
            SelectionTypeFrame.update_button(tb, int(i) in active_modes)


class ShapeSelectionTracker:

    def __init__(self):
        self._current_selection = []
        self._has_change = True

    def consume_change(self) -> typing.Generator[OCC.Core.TopoDS.TopoDS_Shape, None, None]:
        for s in self._current_selection:
            yield s

        self._has_change = False

    @property
    def has_change(self):
        return self._has_change

    def update_selection(self, *new_selection: OCC.Core.TopoDS.TopoDS_Shape):
        if [s for s in new_selection] != self._current_selection:
            self._current_selection = [s for s in new_selection]
            self._has_change = True


class InteractiveViewFrame(QtWidgets.QFrame):

    def __init__(self, occ_viewer, face_annotations_slot, edge_annotations_slot, toggle_selection_mode_slot):
        super().__init__()

        self._selection_type_frame = SelectionTypeFrame(
            face_annotations_slot,
            edge_annotations_slot,
            toggle_selection_mode_slot)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(occ_viewer)
        layout.addWidget(self._selection_type_frame)
        self.setLayout(layout)

        layout.setStretch(0, 100)

    @property
    def selection_type_frame(self):
        return self._selection_type_frame


class PartDisplay(QtWidgets.QMainWindow):

    selection_changed_signal = QtCore.pyqtSignal(list, name="selection_changed_signal")

    Vertex = int(OCC.Core.TopAbs.TopAbs_VERTEX)
    Edge = int(OCC.Core.TopAbs.TopAbs_EDGE)
    Wire = int(OCC.Core.TopAbs.TopAbs_WIRE)
    Face = int(OCC.Core.TopAbs.TopAbs_FACE)

    def __init__(self, part: part_manager.Part):
        super().__init__()
        self._part = part
        self._shape_selection_tracker = ShapeSelectionTracker()

        self._create_occ_viewer()

        self._interactive_view_frame = \
            InteractiveViewFrame(self._occ_viewer,
                                  self.toggle_face_annotations,
                                  self.toggle_edge_annotations,
                                  self.toggle_selection_type)
        right_frame = self._create_selection_frame()

        self._splitter = QtWidgets.QSplitter()

        self._splitter.addWidget(self._interactive_view_frame)
        self._splitter.addWidget(right_frame)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 1)

        self.selection_changed_signal.connect(self._selection_frame.selection_changed_slot)

        self.setCentralWidget(self._splitter)

        self._occ_viewer.InitDriver()
        self._occ_viewer._display.SetPerspectiveProjection()

        self._part_ais = self._occ_viewer._display.DisplayShape(self._part.shape)[0]

        for label, shapelist in self._part.subshapes.items():
            for shape in shapelist:
                display_pnt = OCC.Core.gp.gp_Pnt(*op.InterrogateUtils.center_of_mass(shape))

                self._occ_viewer._display.DisplayMessage(display_pnt, label, message_color=(1, 1, 1))
                self._occ_viewer._display.DisplayShape(shape, color="BLUE")

        self._face_annotations = None
        self._edge_annotations = None

        self.set_active_modes(PartDisplay.Vertex, PartDisplay.Edge, PartDisplay.Wire, PartDisplay.Face)

    @property
    def ais_interactive_ctx(self) -> AIS_InteractiveContext:
        return self._occ_viewer._display.GetContext()

    def fit(self):
        self._occ_viewer._display.FitAll()

    def resize(self, *args, **kwargs) -> None:
        super().resize(*args, **kwargs)
        self._occ_viewer._display.OnResize()

    def set_active_modes(self, *active_modes: int):
        self.ais_interactive_ctx.Deactivate()
        for mode in active_modes:
            self.ais_interactive_ctx.Activate(AIS_Shape.SelectionMode(mode), True)

        self.update_fields()

    def get_active_selection_types(self) -> typing.Set[int]:
        modes = set()
        loi = TColStd_ListOfInteger()
        self.ais_interactive_ctx.ActivatedModes(self._part_ais, loi)

        while loi.Size() > 0:
            modes.add(AIS_Shape.SelectionType(loi.First()))
            loi.RemoveFirst()

        return modes

    def update_fields(self):
        active_selection_types = self.get_active_selection_types()

        stf = self._interactive_view_frame.selection_type_frame

        stf.selection_set(active_selection_types)

        self._interactive_view_frame.selection_type_frame.face_annotation_set(self._face_annotations is not None)
        self._interactive_view_frame.selection_type_frame.edge_annotation_set(self._edge_annotations is not None)

    def toggle_selection_type(self, selection_type: int):
        #mode = AIS_Shape.SelectionMode(mode)

        if selection_type in self.get_active_selection_types():
            self.ais_interactive_ctx.Deactivate(AIS_Shape.SelectionMode(selection_type))
        else:
            self.ais_interactive_ctx.Activate(AIS_Shape.SelectionMode(selection_type))

        self.update_fields()

    @QtCore.pyqtSlot(name="toggle_face_annotations")
    def toggle_face_annotations(self):
        if self._face_annotations is not None:
            for f in self._face_annotations:
                self._occ_viewer._display.GetContext().Erase(f, True)

            self._face_annotations = None
        else:
            face_annotations = []
            for f in op.Explorer.face_explorer(self._part.shape).get():
                for annotation in op.VisualizationUtils.display_face(f, True):
                    face_annotations.append(annotation)

            face_annotations = op.GeomUtils.make_compound(*face_annotations)
            self._face_annotations = self._occ_viewer._display.DisplayShape(face_annotations,
                                                                            color="GREEN",
                                                                            update=False)
            for f in self._face_annotations:
                self.ais_interactive_ctx.Deactivate(f)

        self._occ_viewer._display.Repaint()
        self.update_fields()


    @QtCore.pyqtSlot(name="toggle_edge_annotations")
    def toggle_edge_annotations(self):
        if self._edge_annotations is not None:
            for e in self._edge_annotations:
                self._occ_viewer._display.GetContext().Erase(e, True)

            self._edge_annotations = None
        else:
            edge_annotations = []
            for f in op.Explorer.edge_explorer(self._part.shape).get():
                for annotation in op.VisualizationUtils.display_edge(f, True, False):
                    edge_annotations.append(annotation)

            edge_annotations = op.GeomUtils.make_compound(*edge_annotations)
            self._edge_annotations = self._occ_viewer._display.DisplayShape(edge_annotations,
                                                                            color="RED",
                                                                            update=False)
            for e in self._edge_annotations:
                self.ais_interactive_ctx.Deactivate(e)

        self._occ_viewer._display.Repaint()
        self.update_fields()


    def _selection_changed(self, selection, *coords):
        self._shape_selection_tracker.update_selection(*selection)

        if self._shape_selection_tracker.has_change:
            self.selection_changed_signal.emit([s for s in self._shape_selection_tracker.consume_change()])

    def _create_occ_viewer(self):
        from OCC.Display.backend import load_backend
        load_backend("qt-pyqt5")
        from OCC.Display.qtDisplay import qtViewer3d as OCCQtViewer3D
        viewer = OCCQtViewer3D(self)

        display: OCC.Display.OCCViewer.Viewer3d = viewer._display
        display.display_triedron()

        display.register_select_callback(self._selection_changed)

        self._occ_viewer = viewer

    def _create_selection_frame(self):
        self._selection_frame = SelectionFrame(self, self._part)

        #self._selection_frame.setMaximumSize(200, 200)

        scroll_bar = QtWidgets.QScrollArea(self)
        scroll_bar.verticalScrollBar()
        scroll_bar.setWidget(self._selection_frame)

        return scroll_bar
