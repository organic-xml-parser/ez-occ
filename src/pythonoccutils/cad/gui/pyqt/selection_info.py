import typing

import OCC
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QLabel, QWidget

from pythonoccutils.cad.gui.pyqt.utils import WidgetUtils
from pythonoccutils.cad.gui.vtk.vtk_occ_bridging import VtkOccActor
from pythonoccutils.occutils_python import SetPlaceableShape
from pythonoccutils.part_manager import PartSelectionResolver


class InfoFrame(QtWidgets.QFrame):

    class ShapeEntry(QtWidgets.QGroupBox):

        def __init__(self, parent, part, shape):
            super().__init__(parent)
            self._part = part
            self._shape = shape

            layout = QtWidgets.QVBoxLayout(self)
            layout.addWidget(QLabel(str(shape)))

    def __init__(self, parent: QWidget):
        super().__init__(parent)

        self.selection_hints_area = None
        self.update_selection({})

    def update_selection(self, selection: typing.Dict[VtkOccActor, typing.Set[SetPlaceableShape]]):
        WidgetUtils.clear_widget(self)

        layout = QtWidgets.QVBoxLayout(self) if self.layout() is None else self.layout()

        layout.addWidget(QtWidgets.QLabel("Current Selection"))

        self.selection_hints_area = QtWidgets.QFrame()
        layout.addWidget(self.selection_hints_area)

        for vtk_occ_actor, shapes in selection.items():
            layout.addWidget(QLabel(vtk_occ_actor.name))

            for s in shapes:
                layout.addWidget(InfoFrame.ShapeEntry(self, vtk_occ_actor.part, s))

            layout.addWidget(QLabel("Part query suggestions"))

            for suggestion in PartSelectionResolver(vtk_occ_actor.part, *[s.shape for s in shapes]).get_suggested_selections():
                layout.addWidget(QtWidgets.QLineEdit(suggestion))

        layout.addSpacerItem(QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        ))

        self.setLayout(layout)
