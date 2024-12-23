import math
import typing

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QVBoxLayout, QFrame, QHBoxLayout, QWidget, QLabel, QSlider

from ezocc.cad.model.directors.session_director import SessionDirector
from ezocc.cad.model.session import Session


ValueCallback = typing.Callable[[], None]


class SessionDirectorFrame(QtWidgets.QFrame):

    def __init__(self,
                 session: Session,
                 on_value_changed: ValueCallback,
                 parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        for director in session.directors:
            if director.get_range() is not None:
                layout.addWidget(
                    SessionDirectorFrame._create_director_control(director, on_value_changed))

        self.setLayout(layout)

    @staticmethod
    def _create_director_control(driver: SessionDirector, on_value_changed: ValueCallback) -> QWidget:
        driver_control = QFrame()
        layout = QHBoxLayout(driver_control)
        layout.addWidget(QLabel(driver.get_display_name()))

        number_display = QLabel(str(driver.get_value()))

        def _update_number_display() -> None:
            updated_text = "{:.2f}".format(driver.get_value())
            number_display.setText(updated_text)
            on_value_changed()

        _update_number_display()

        layout.addWidget(number_display)

        input = QSlider(QtCore.Qt.Orientation.Horizontal, parent=driver_control)

        input_range = (driver.get_range().max - driver.get_range().min)
        ticks = math.ceil(input_range / driver.get_range().increment)

        input.setMaximum(ticks)
        input.setMinimum(0)

        def _slider_value_changed(value: float) -> None:
            real_value = driver.get_range().min + driver.get_range().increment * value
            driver.set_value(real_value)
            _update_number_display()

        input.valueChanged.connect(_slider_value_changed)

        layout.addWidget(input)
        driver_control.setLayout(layout)

        return driver_control
