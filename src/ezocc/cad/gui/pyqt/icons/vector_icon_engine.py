import typing

from PyQt5.QtCore import Qt, QRect, QSize, QPointF
from PyQt5.QtGui import QIconEngine, QImage, qRgba, QPixmap, QPainter, QIcon, QPainterPath

from ezocc.cad.gui.pyqt.icons.vector_icon_defaults import VectorIconDefaults


class VectorIconEngine(QIconEngine):

    def __init__(self):
        super().__init__()

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State):
        image = QImage(size, QImage.Format_ARGB32)
        image.fill(qRgba(0, 0, 0, 0))

        pixmap = QPixmap.fromImage(image, Qt.ImageConversionFlag.NoFormatConversion)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        self.paint(painter, QRect(0, 0, size.width(), size.height()), mode, state)

        return pixmap

    @staticmethod
    def draw_vertex(x0: float,
                    y0: float,
                    painter: QPainter,
                    rect: QRect,
                    mode: QIcon.Mode,
                    state: QIcon.State):
        vdt = VectorIconDefaults.vertex_draw_tools(rect.size())
        radius = VectorIconDefaults.vertex_radius(rect.size())
        painter.setPen(vdt.pen)
        painter.setBrush(vdt.brush)
        painter.drawEllipse(QPointF(x0, y0), radius, radius)

    @staticmethod
    def draw_edge(x0: float,
                  y0: float,
                  x1: float,
                  y1: float,
                  painter: QPainter,
                  rect: QRect,
                  mode: QIcon.Mode,
                  state: QIcon.State):
        draw_tools = VectorIconDefaults.edge_draw_tools(rect.size())
        painter.setPen(draw_tools.pen)
        painter.setBrush(draw_tools.brush)

        path = QPainterPath(QPointF(x0, y0))
        path.lineTo(QPointF(x1, y1))

        painter.drawPath(path)

    @staticmethod
    def draw_face(path: typing.List[typing.Tuple[float, float]],
                  painter: QPainter,
                  rect: QRect,
                  mode: QIcon.Mode,
                  state: QIcon.State,
                  draw_edges: bool=True):

        if len(path) < 3:
            raise ValueError("Path must have at least 3 points to make a face")

        painter_path = QPainterPath(QPointF(*path[0]))
        for p in path[1:]:
            painter_path.lineTo(QPointF(*p))

        painter_path.closeSubpath()

        draw_tools = VectorIconDefaults.face_draw_tools(rect.size())

        painter.setPen(draw_tools.pen)
        painter.setBrush(draw_tools.brush)
        painter.drawPath(painter_path)

        if draw_edges:
            draw_tools = VectorIconDefaults.edge_draw_tools(rect.size())

            painter.setPen(draw_tools.pen)
            painter.setBrush(draw_tools.brush)
            painter.drawPath(painter_path)
