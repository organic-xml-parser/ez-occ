from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QModelIndex, Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QPushButton, QHBoxLayout

from pythonoccutils.cad.model.session import Session
from pythonoccutils.cad.model.work_unit import WorkUnit


class WorkUnitTreeView(QtWidgets.QTreeView):

    class SessionModel(QStandardItemModel):

        def __init__(self, session: Session, parent: QtWidgets.QWidget):
            super().__init__(0, 1, parent)
            self._session = session
            self.setHorizontalHeaderLabels(["Work Units"])

            work_units = []
            for wu in session.root_unit.traverse():
                work_units.append(wu)

            item_stack = [
                (None, self.invisibleRootItem())
            ]

            self._work_units_to_items = {}

            for w in work_units:

                while w.parent != item_stack[-1][0]:
                    item_stack.pop(-1)

                next_item = QStandardItem(w.name)
                next_item.setData(w, Qt.UserRole + 1)
                next_item.setEditable(False)

                self._work_units_to_items[w] = next_item

                item_stack[-1][1].appendRow(next_item)
                item_stack.append((w, next_item))

        def get_item_for_work_unit(self, work_unit: WorkUnit):
            return self._work_units_to_items[work_unit]

        def get_work_unit(self, model_index: QModelIndex):
            return self.data(model_index, Qt.UserRole + 1)

    def __init__(self, session: Session, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self._session = session
        self.rebuild_model(self._session)
        self._session.listener_manager.add_listener(lambda se: self.rebuild_model(se.target))
        self.clicked.connect(self._emit_work_unit_selection_changed)

    def rebuild_model(self, session: Session):
        self.setModel(WorkUnitTreeView.SessionModel(session, self))
        self.expandAll()
        if session.selected_work_unit is not None:
            item: QStandardItem = self.model().get_item_for_work_unit(session.selected_work_unit)
            self.selectionModel().select(item.index(), QtCore.QItemSelectionModel.Select)

    def _emit_work_unit_selection_changed(self, sel: QModelIndex):
        work_unit = self.model().get_work_unit(sel)
        self._session.select_work_unit(work_unit)


class WorkUnitTreeButtonBar(QtWidgets.QFrame):

    def __init__(self, session: Session, parent):
        super().__init__(parent)

        self._session = session

        self._btn_add_work_unit = QPushButton("New WorkUnit")
        self._btn_add_work_unit.clicked.connect(lambda _: self._session.add_work_unit_to_selected())

        self._btn_delete_work_unit = QPushButton("Delete WorkUnit")
        self._btn_delete_work_unit.clicked.connect(lambda _: self._session.delete_selected_work_unit())

        layout = QHBoxLayout(self)

        layout.addWidget(self._btn_add_work_unit)
        layout.addWidget(self._btn_delete_work_unit)

        self.setLayout(layout)
