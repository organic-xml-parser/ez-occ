from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QVBoxLayout


class WidgetUtils:

    @staticmethod
    def vbox_frame(*widgets: QtWidgets.QWidget) -> QtWidgets.QFrame:
        result = QtWidgets.QFrame()
        layout = QVBoxLayout(result)

        for w in widgets:
            layout.addWidget(w)

        result.setLayout(layout)
        return result

    @staticmethod
    def clear_widget(widget: QtWidgets.QWidget):
        if widget.layout() is None:
            return

        while widget.layout().count() > 0:
            l_item = widget.layout().itemAt(0)
            if l_item.widget() is not None:
                WidgetUtils.clear_widget(l_item.widget())
                l_item.widget().deleteLater()

            widget.layout().removeItem(l_item)
