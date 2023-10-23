import typing

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStyle, QFormLayout, QLabel

from pythonoccutils.cad.gui.pyqt.utils import WidgetUtils
from pythonoccutils.cad.model.event import SessionEvent, SessionEventType
from pythonoccutils.cad.model.session import Session
from pythonoccutils.cad.model.work_unit import CmdArg, WorkUnit, WorkUnitCommand


class CmdArgEditor(QtWidgets.QLineEdit):

    def __init__(self, cmd_arg: CmdArg):
        super().__init__(cmd_arg.to_str())
        self._cmd_arg = cmd_arg

        cmd_arg.listener_manager.add_listener(self)

        self.textChanged.connect(self._update_cmd_arg)

    def _update_cmd_arg(self, *args, **kwargs):
        try:
            self._cmd_arg.from_str(self.text())
        except ValueError as e:
            # ignore invalid command arg values
            pass

    def deleteLater(self) -> None:
        self._cmd_arg.listener_manager.remove_listener(self)
        super().deleteLater()

    def __call__(self, *args, **kwargs):
        arg_str = self._cmd_arg.to_str()
        if CmdArg.str_to_value(self.text(), self._cmd_arg.expected_type) != self._cmd_arg.value:
            self.setText(arg_str)


class WorkUnitEditor(QtWidgets.QFrame):

    def __init__(self, session: Session, parent: QWidget) -> None:
        super().__init__(parent)
        self._session = session

        self.setLayout(QVBoxLayout(self))

        self._work_unit: typing.Optional[WorkUnit] = None
        self._last_updated_work_unit = None

        self.session_changed(session)
        self._session.listener_manager.add_listener(lambda se: self.session_changed(se.target))

    def _create_command_field_editor(self,
                                    work_unit: WorkUnit,
                                    command: WorkUnitCommand,
                                    cmd_arg_name: str) -> QtWidgets.QWidget:

        if cmd_arg_name not in command.cmd_args.keys():
            raise ValueError("Command arg not present")

        cmd_arg = command.cmd_args[cmd_arg_name]

        return CmdArgEditor(cmd_arg)

    def _create_button_bar(self, work_unit: WorkUnit):
        result = QtWidgets.QFrame()
        layout = QHBoxLayout(result)

        cmd_select = QtWidgets.QComboBox()
        for cmd_name in self._session.work_unit_command_factory.get_command_list():
            cmd_select.addItem(cmd_name)

        layout.addWidget(cmd_select)

        layout.addSpacerItem(QtWidgets.QSpacerItem(
            0,
            0,
            hPolicy=QtWidgets.QSizePolicy.Policy.Expanding,
            vPolicy=QtWidgets.QSizePolicy.Policy.Expanding
        ))

        add_cmd_button = QPushButton("Add")
        add_cmd_button.clicked.connect(lambda _: self._work_unit.add_command(
            self._session.work_unit_command_factory.create_command(cmd_select.currentText())))

        layout.addWidget(add_cmd_button)

        result.setLayout(layout)
        return result

    def _create_command_button_bar(self, work_unit: WorkUnit, command: WorkUnitCommand) -> QtWidgets.QWidget:
        result = QtWidgets.QFrame()
        result_layout = QHBoxLayout(result)

        btn_mv_cmd_up = QPushButton(self.style().standardIcon(QStyle.SP_TitleBarShadeButton), "", result)
        btn_mv_cmd_dn = QPushButton(self.style().standardIcon(QStyle.SP_TitleBarUnshadeButton), "", result)

        btn_mv_cmd_up.clicked.connect(lambda _: work_unit.move_command_previous(command))
        btn_mv_cmd_dn.clicked.connect(lambda _: work_unit.move_command_next(command))

        result_layout.addWidget(btn_mv_cmd_up)
        result_layout.addWidget(btn_mv_cmd_dn)

        result_layout.addSpacerItem(QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        ))

        btn_rm_cmd = QPushButton(self.style().standardIcon(QStyle.SP_TrashIcon), "", result)
        btn_rm_cmd.clicked.connect(lambda _: work_unit.remove_command(command))
        result_layout.addWidget(btn_rm_cmd)

        result.setLayout(result_layout)
        return result

    def _create_command_frame(self, work_unit: WorkUnit, command: WorkUnitCommand) -> QtWidgets.QWidget:
        form = QtWidgets.QFrame()
        layout = QFormLayout(form)

        for cmd_arg_name, value in command.cmd_args.items():
            layout.addRow(cmd_arg_name, self._create_command_field_editor(work_unit, command, cmd_arg_name))

        form.setLayout(layout)

        result = QtWidgets.QGroupBox()
        result_layout = QVBoxLayout(result)
        result_layout.addWidget(QLabel(command.__class__.__name__))
        result_layout.addWidget(form)
        result_layout.addWidget(self._create_command_button_bar(work_unit, command))

        return result

    def work_unit_updated(self, session_event: SessionEvent):
        # only repopulate the UI if the WorkUnit itself was modified
        if session_event.type.value != SessionEventType.INDIRECT.value:
            WidgetUtils.clear_widget(self)

            if self._work_unit is None:
                return

            self.layout().addWidget(QLabel(self._work_unit.name))

            for c in self._work_unit.commands:
                self.layout().addWidget(self._create_command_frame(self._work_unit, c))

            self.layout().addWidget(self._create_button_bar(self._work_unit))

            self.repaint()

    def session_changed(self, session: Session):
        if session.selected_work_unit == self._work_unit:
            # nothing to do
            return

        if self._work_unit is not None:
            self._work_unit.listener_manager.remove_listener(self.work_unit_updated)

        self._work_unit = session.selected_work_unit

        if self._work_unit is not None:
            self._work_unit.listener_manager.add_listener(self.work_unit_updated)

        # re-render the new work unit
        self.work_unit_updated(SessionEvent(self._work_unit, SessionEventType.CREATED))

    def deleteLater(self) -> None:
        self._session.listener_manager.remove_listener(self.session_changed)
        super().deleteLater()
