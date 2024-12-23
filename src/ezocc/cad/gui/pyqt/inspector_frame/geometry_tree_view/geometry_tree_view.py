import typing

from PyQt5.QtCore import QModelIndex, QItemSelectionModel
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QTreeView

from ezocc.humanization import Humanize
from ezocc.occutils_python import SetPlaceablePart, SetPlaceableShape


class GeomItem(QStandardItem):

    def __init__(self, part: SetPlaceablePart):
        super().__init__(Humanize.shape_type(part.part.shape.ShapeType()))
        self._part = part


class GeometryItemModel(QStandardItemModel):

    def __init__(self, part: SetPlaceablePart, parent=...):
        super().__init__(parent)
        self._part = part

        item = GeomItem(self._part)

        self._item_list: typing.List[GeomItem] = []
        self._model_indices: typing.Dict[SetPlaceableShape, QModelIndex] = \
            {part.part.set_placeable_shape: item.index()}

        self.invisibleRootItem().appendRow(item)
        self._populate_items(item, self._part)

    def index_for_shape(self, shape: SetPlaceableShape) -> QModelIndex:
        if shape not in self._model_indices:
            raise ValueError("Subshape does not seem to belong to root part.")

        return self._model_indices[shape]

    def _populate_items(self,
                        item: QStandardItem,
                        part: SetPlaceablePart):

        self._item_list = []

        for subshape in part.part.explore.direct_subshapes.get():
            subshape_item = GeomItem(subshape.set_placeable)
            self._item_list.append(subshape_item)
            item.appendRow(subshape_item)
            self._model_indices[subshape.set_placeable_shape] = subshape_item.index()

            self._populate_items(subshape_item, subshape.set_placeable)


class GeometryTreeView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)

    def clear_part(self):
        self.setModel(QStandardItemModel())
        self.update()

    def expand_and_select(self, model_index: QModelIndex):
        parent_indices = []
        current = model_index
        while current.parent().isValid():
            current = current.parent()
            parent_indices.append(current)

        for p in parent_indices:
            self.expand(p)

        self.selectionModel().select(model_index, QItemSelectionModel.SelectCurrent)
        self.selectionModel().setCurrentIndex(model_index, QItemSelectionModel.SelectCurrent)

    def set_part(self,
                 root_part: SetPlaceablePart,
                 selected_subshape: SetPlaceableShape):

        model = GeometryItemModel(root_part, self)
        self.setModel(model)

        model_index = model.index_for_shape(selected_subshape)

        self.expand_and_select(model_index)

        self.show()




        