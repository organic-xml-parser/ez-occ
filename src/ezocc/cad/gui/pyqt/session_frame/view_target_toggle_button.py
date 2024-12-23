import OCC.Core.TopAbs
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QPushButton, QWidget


class ViewTargetToggleButton(QPushButton):

    def __init__(self, shape_type: OCC.Core.TopAbs.TopAbs_ShapeEnum, parent: QWidget = None):
        super().__init__("", parent)
        self.setIconSize(QSize(32, 32))
        self._shape_type = shape_type
        self.setCheckable(True)
