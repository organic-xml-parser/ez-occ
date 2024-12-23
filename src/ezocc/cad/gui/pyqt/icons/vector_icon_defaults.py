import math
import typing

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QColor, QPen, QBrush


class VectorIconDrawTools:

    def __init__(self, pen: typing.Optional[QPen], brush: typing.Optional[QBrush]):
        self._pen = pen
        self._brush = brush

    @property
    def pen(self):
        if self._pen is None:
            return QPen(QColor("transparent"), 0)

        return self._pen

    @property
    def brush(self):
        if self._brush is None:
            return QBrush(QColor("transparent"))

        return self._brush


class VectorIconDefaults:

    @staticmethod
    def vertex_color() -> QColor:
        return QColor("red")

    @staticmethod
    def edge_color() -> QColor:
        return QColor("grey")

    @staticmethod
    def face_color() -> QColor:
        result = QColor("blue")
        result.setAlpha(100)
        return result

    @staticmethod
    def face_draw_tools(size: QSize) -> VectorIconDrawTools:
        return VectorIconDrawTools(None, QBrush(VectorIconDefaults.face_color()))

    @staticmethod
    def edge_draw_tools(size: QSize) -> VectorIconDrawTools:
        return VectorIconDrawTools(
            QPen(QColor(VectorIconDefaults.edge_color()),
                 VectorIconDefaults.edge_thickness(size),
                 Qt.SolidLine,
                 Qt.RoundCap,
                 Qt.RoundJoin),
            None)

    @staticmethod
    def vertex_draw_tools(size: QSize) -> VectorIconDrawTools:
        return VectorIconDrawTools(None, QBrush(VectorIconDefaults.vertex_color()))

    @staticmethod
    def vertex_radius(size: QSize) -> float:
        return math.hypot(size.width(), size.height()) / 10

    @staticmethod
    def edge_thickness(size: QSize) -> float:
        return 0.75 * VectorIconDefaults.vertex_radius(size)
