#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import os.path
import pdb
import sys
import tempfile

import typing
import uuid

from PyQt5 import QtWidgets

from ezocc.cad.gui.pyqt.display_window import DisplayWindow
from ezocc.cad.gui.pyqt.session_frame.session_frame_offscreen import SessionFrameOffscreen
from ezocc.cad.model.cache.file_based_session_cache import FileBasedSessionCache
from ezocc.cad.model.cache.in_memory_session_cache import InMemorySessionCache
from ezocc.cad.model.directors.session_director import SessionDirector
from ezocc.cad.model.session import Session
from ezocc.cad.model.widgets.widget import Widget

from ezocc.occutils_python import SetPlaceablePart
from ezocc.part_manager import Part

from ezocc.cad.model.cache.cache_factory import create_session_cache


def visualize_parts(*parts: Part,
                    directors: typing.Tuple[SessionDirector] = (),
                    widgets: typing.Set[Widget] = None):
    part_set = {SetPlaceablePart(p) for p in parts}

    session = Session(create_session_cache(),
                      part_set,
                      [d for d in directors],
                      widgets if widgets is not None else set())
    visualize(session)


def visualize_parts_offscreen(*parts: Part,
                    resolution: typing.Tuple[int, int],
                    directors: typing.Tuple[SessionDirector] = (),
                    widgets: typing.Set[Widget] = None) -> SessionFrameOffscreen:

    part_set = {SetPlaceablePart(p) for p in parts}

    session = Session(create_session_cache(),
                      part_set,
                      [d for d in directors],
                      widgets if widgets is not None else set())

    return SessionFrameOffscreen(session, True, resolution, None)


def visualize(session: Session):
    app = QtWidgets.QApplication(sys.argv)

    display_window = DisplayWindow(session)

    display_window.resize(1200, 800)

    display_window.start()

    app.exec_()

    session.cache.save()

