import typing

import OCC.Core.BRep
import OCC.Core.GeomAdaptor
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QVBoxLayout, QLabel, QTextEdit, QScrollArea, QGroupBox

from ezocc.cad.gui.pyqt.inspector_frame.geometry_tree_view.geometry_tree_view import GeometryTreeView
from ezocc.cad.gui.pyqt.session_frame.session_frame_qt import SessionFrameQt
from ezocc.cad.gui.vtk.vtk_occ_actor import VtkOccActor
from ezocc.cad.model.cache.in_memory_session_cache import InMemorySessionCache
from ezocc.cad.model.session import Session
from ezocc.humanization import Humanize
from ezocc.occutils_python import SetPlaceableShape, SetPlaceablePart, InterrogateUtils
from ezocc.part_manager import Part


class SubShapeInspectorFrame(QtWidgets.QFrame):

    def __init__(self, commanding_session_frame: SessionFrameQt):
        super().__init__()

        self.setStyleSheet("""
            QGroupBox {
                font: bold;
                border: 1px solid silver;
                border-radius: 6px;
                margin-top: 6px;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 7px;
                padding: 0px 5px 0px 5px;
            }
        """)

        self._commanding_session_frame = commanding_session_frame
        self._commanding_session_frame.selection_changed_signal.connect(self.update_selection)

        self._session = Session(cache=InMemorySessionCache(), parts=set(), directors=[], widgets=set())
        self._session_frame = SessionFrameQt(
            self._session,
            "subshape_inspector",
            enable_skybox=False,
            enable_selection=False,
            parent=self)
        self._subshape_information_panel = GeometryTreeView(self) #SubshapeInformationPanel(self)

        self.setLayout(QVBoxLayout(self))
        self.layout().addWidget(self._session_frame)
        self.layout().addWidget(self._subshape_information_panel)

    def update_selection(self,
                         primary_selection: typing.Tuple[VtkOccActor, SetPlaceableShape],
                         selected_elements: typing.Dict[VtkOccActor, typing.Set[SetPlaceableShape]]):

        if len(primary_selection) == 0:
            self._session.change_parts(set())
            self._subshape_information_panel.clear_part()
        else:
            part = SetPlaceablePart(Part.of_shape(primary_selection[1].shape))
            self._session.change_parts({part})
            self._subshape_information_panel.set_part(primary_selection[0].part, primary_selection[1])

    def start(self):
        self.show()
        self._session_frame.start()


class SubshapeInformationPanel(QtWidgets.QFrame):

    def __init__(self, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self._part: typing.Optional[SetPlaceablePart] = None

        self._face_properties_frame: typing.Optional[FacePropertiesFrame] = None

        self.setLayout(QVBoxLayout(self))

    def set_part(self, new_part: typing.Optional[SetPlaceablePart]):
        if self._face_properties_frame is not None:
            self.layout().removeWidget(self._face_properties_frame)
            self._face_properties_frame = None

        self._part = new_part

        if new_part is not None:
            self._face_properties_frame = FacePropertiesFrame(new_part.part, self)
            self.layout().addWidget(self._face_properties_frame)
            self.update()


class FacePropertiesFrame(QtWidgets.QFrame):

    def __init__(self, part: Part, parent: QtWidgets.QWidget = None):
        super().__init__(parent)

        if not part.inspect.is_face():
            raise ValueError("Expected face part")

        self._part = part

        self.setLayout(QVBoxLayout(self))

        sf = OCC.Core.BRep.BRep_Tool.Surface(self._part.shape)
        gas = OCC.Core.GeomAdaptor.GeomAdaptor_Surface(sf)

        surface_properties = InterrogateUtils.surface_properties(self._part.shape)

        self.layout().addWidget(QTextEdit(f"Part: {str(self._part)}"))
        self.layout().addWidget(QLabel(f"Surface type: {Humanize.surface_type(gas.GetType())}"))
        self.layout().addWidget(QLabel(f"Area: {surface_properties.Mass()}"))

        scroll_area_contents = QtWidgets.QWidget()
        scroll_area_contents.setLayout(QVBoxLayout(scroll_area_contents))

        for w in part.explore.wire.get():
            scroll_area_contents.layout().addWidget(WirePropertiesFrame(w, scroll_area_contents))

        scroll_area = QScrollArea(self)
        scroll_area.setWidget(scroll_area_contents)
        scroll_area.setWidgetResizable(True)

        wires_group_box = QGroupBox(f"{len(part.explore.wire.get())} wires total")
        wires_group_box.setLayout(QVBoxLayout(wires_group_box))
        wires_group_box.layout().addWidget(scroll_area)

        self.layout().addWidget(wires_group_box)


class WirePropertiesFrame(QtWidgets.QFrame):

    def __init__(self, part: Part, parent: QtWidgets.QWidget):
        super().__init__(parent)

        if not part.inspect.is_wire():
            raise ValueError("Expected wire part")

        self.setLayout(QVBoxLayout(self))

        linear_props = InterrogateUtils.linear_properties(part.shape)
        self.layout().addWidget(QLabel(f"Length: {linear_props.Mass()}"))

        scroll_area_contents = QtWidgets.QWidget()
        scroll_area_contents.setLayout(QVBoxLayout(scroll_area_contents))

        for e in part.explore.wire.get_single().explore.explore_wire_edges_ordered().get():
            scroll_area_contents.layout().addWidget(EdgePropertiesFrame(e, scroll_area_contents))

        scroll_area = QScrollArea(self)
        scroll_area.setWidget(scroll_area_contents)
        scroll_area.setWidgetResizable(True)

        edges_group_box = QGroupBox(f"{len(part.explore.edge.get())} Edges Total")
        edges_group_box.setLayout(QVBoxLayout(edges_group_box))
        edges_group_box.layout().addWidget(scroll_area)

        self.layout().addWidget(edges_group_box)


class EdgePropertiesFrame(QtWidgets.QFrame):

    def __init__(self, part: Part, parent: QtWidgets.QWidget):
        super().__init__(parent)

        if not part.inspect.is_edge():
            raise ValueError("Expected edge part")

        self.setLayout(QVBoxLayout(self))

        linear_props = InterrogateUtils.linear_properties(part.shape)

        self.layout().addWidget(QLabel(f"Curve type: {Humanize.curve_type(part.inspect.edge.curve_type)}"))
        self.layout().addWidget(QLabel(f"Length: {linear_props.Mass()}"))
