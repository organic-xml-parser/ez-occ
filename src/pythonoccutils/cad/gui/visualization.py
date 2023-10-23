#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys

from PyQt5 import QtWidgets

from pythonoccutils.cad.gui.pyqt.window import DisplayWindow
from pythonoccutils.cad.model.session import Session
from pythonoccutils.cad.model.work_unit import WorkUnit
from pythonoccutils.cad.model.work_unit_factory import ShowCachedPartCommand
from pythonoccutils.part_manager import Part


def visualize_parts(*parts: Part):
    session = Session()
    session.root_unit.add_child(WorkUnit(
        name="visualize-part",
        parent=session.root_unit,
        commands=[ShowCachedPartCommand(f"part-{i}", p) for i, p in enumerate(parts)]))

    session.select_work_unit(session.root_unit.child_nodes[0])

    visualize(session)


def visualize(session: Session):
    app = QtWidgets.QApplication(sys.argv)

    display_window = DisplayWindow(session)

    display_window.resize(1200, 800)

    display_window.start()

    app.exec_()

