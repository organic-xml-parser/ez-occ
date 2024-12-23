from PyQt5.QtCore import QSize
from PyQt5.QtGui import QIcon

from ezocc.cad.gui.pyqt.icons.vector_icon_defaults import VectorIconDefaults
from ezocc.cad.gui.pyqt.icons.vector_icon_engine import VectorIconEngine


class VertexIconEngine(VectorIconEngine):

    def paint(self, painter, rect, mode, state):
        x0 = rect.x() + rect.width() / 2 + VectorIconDefaults.edge_thickness(rect.size())
        y0 = rect.y() + rect.height() / 2 + VectorIconDefaults.edge_thickness(rect.size())

        self.draw_vertex(x0, y0, painter, rect, mode, state)


class EdgeIconEngine(VectorIconEngine):

    def paint(self, painter, rect, mode, state):
        x0 = rect.x() + VectorIconDefaults.edge_thickness(rect.size())
        y0 = rect.y() + VectorIconDefaults.edge_thickness(rect.size())

        x1 = rect.x() + rect.width() - VectorIconDefaults.edge_thickness(rect.size())
        y1 = rect.y() + rect.height() - VectorIconDefaults.edge_thickness(rect.size())

        self.draw_edge(x0, y0, x1, y1, painter, rect, mode, state)


class FaceIconEngine(VectorIconEngine):

    def paint(self, painter, rect, mode, state):
        x0 = rect.x() + VectorIconDefaults.edge_thickness(rect.size())
        y0 = rect.y() + VectorIconDefaults.edge_thickness(rect.size())

        x1 = rect.x() + rect.width() - VectorIconDefaults.edge_thickness(rect.size())
        y1 = rect.y() + rect.height() * 0.3

        x2 = rect.x() + rect.width() * 0.3 + VectorIconDefaults.edge_thickness(rect.size())
        y2 = rect.y() + rect.height() - VectorIconDefaults.edge_thickness(rect.size())

        self.draw_face([
            (x0, y0),
            (x1, y1),
            (x2, y2)
        ], painter, rect, mode, state)


class Icons:

    @staticmethod
    def default_size() -> QSize:
        return QSize(32, 32)

    @staticmethod
    def face_icon() -> QIcon:
        return QIcon(FaceIconEngine())

    @staticmethod
    def edge_icon() -> QIcon:
        return QIcon(EdgeIconEngine())

    @staticmethod
    def vertex_icon() -> QIcon:
        return QIcon(VertexIconEngine())
