import math
import typing

from PyQt5.QtCore import QRect, QPointF
from PyQt5.QtGui import QIcon, QPainter

from ezocc.cad.gui.pyqt.icons.vector_icon_defaults import VectorIconDefaults
from ezocc.cad.gui.pyqt.icons.vector_icon_engine import VectorIconEngine


class ViewAlignIconEngine(VectorIconEngine):

    def __init__(self, view_dir: typing.Tuple[float, float, float]):
        super().__init__()
        self._view_dir = view_dir

    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State):

        point_is_foreground = all(v >= 0 for v in self._view_dir)

        cen = rect.x() + rect.width() * 0.5, rect.y() + rect.height() * 0.5

        radius = rect.height() / 2 - VectorIconDefaults.vertex_radius(rect.size())

        points = [
            (round(cen[0] + radius * math.sin(math.radians(d))), round(cen[1] + radius * math.cos(math.radians(d)))) for d in range(0, 360, 60)
        ]

        def _draw_cube():

            self.draw_face([
                cen,
                points[2],
                points[3],
                points[4]
            ], painter, rect, mode, state)

            self.draw_face([
                cen,
                points[4],
                points[5],
                points[0]
            ], painter, rect, mode, state)

            self.draw_face([
                cen,
                points[0],
                points[1],
                points[2]
            ], painter, rect, mode, state)

        circ_radius = radius / 5

        vis_point_dx = ((radius - circ_radius * 2) *
                        math.sin(math.radians(-60 - 0)), radius * math.cos(math.radians(-60 - 0)))
        vis_point_dy = ((radius - circ_radius * 2) *
                        math.sin(math.radians(60 - 0)), radius * math.cos(math.radians(60 - 0)))
        vis_point_dz = ((radius - circ_radius * 2) *
                        math.sin(math.radians(180 - 0)), radius * math.cos(math.radians(180 - 0)))

        vis_point = cen[0], cen[1]

        x_mult = self._view_dir[0] / math.fabs(self._view_dir[0]) if self._view_dir[0] != 0 else 0
        y_mult = self._view_dir[1] / math.fabs(self._view_dir[1]) if self._view_dir[1] != 0 else 0
        z_mult = self._view_dir[2] / math.fabs(self._view_dir[2]) if self._view_dir[2] != 0 else 0

        vis_point = vis_point[0] + x_mult * vis_point_dx[0], vis_point[1] + x_mult * vis_point_dx[1]
        vis_point = vis_point[0] + y_mult * vis_point_dy[0], vis_point[1] + y_mult * vis_point_dy[1]
        vis_point = vis_point[0] + z_mult * vis_point_dz[0], vis_point[1] + z_mult * vis_point_dz[1]

        def _draw_marker():
            painter.setPen(VectorIconDefaults.vertex_draw_tools(rect.size()).pen)
            painter.setBrush(VectorIconDefaults.vertex_draw_tools(rect.size()).brush)
            painter.drawEllipse(
                QPointF(vis_point[0], vis_point[1]),
                VectorIconDefaults.vertex_radius(rect.size()), VectorIconDefaults.vertex_radius(rect.size()))

        if point_is_foreground:
            _draw_cube()
            _draw_marker()
        else:
            _draw_marker()
            _draw_cube()

class ViewAlignIcon(QIcon):

    def __init__(self, view_dir: typing.Tuple[float, float, float]):
        super().__init__(ViewAlignIconEngine(view_dir))
