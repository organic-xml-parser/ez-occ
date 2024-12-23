import math
import unittest

import OCC
import OCC.Core.BOPAlgo
import OCC.Core.BRepAlgoAPI
import OCC.Core.BRepAlgoAPI
import OCC.Core.BRepBuilderAPI
import OCC.Core.BRepBuilderAPI
import OCC.Core.BRepFilletAPI
import OCC.Core.BRepOffsetAPI
import OCC.Core.BRepPrimAPI
import OCC.Core.GeomAbs
import OCC.Core.ShapeUpgrade
import OCC.Core.TopOpeBRepBuild
import OCC.Core.TopoDS
import OCC.Core.gp
import OCC.Core.gp as gp
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.gp import gp_Vec

import ezocc.occutils_python as op
from ezocc.part_manager import Part, PartFactory, NoOpPartCache

from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE

from ezocc.stock_parts.misc import StockParts


class TestPart(unittest.TestCase):

    def setUp(self) -> None:
        self._stock_parts = StockParts(NoOpPartCache.instance())

    def test_bearing_thrust_8mm(self):
        self._stock_parts.bearing_thrust_8mm()

    def test_bearing_608(self):
        self._stock_parts.bearing_608()

    def test_sd_card_micro(self):
        self._stock_parts.sd_card_micro()

    def test_switch_momentary(self):
        self._stock_parts.switch_momentary(4)

    def test_ruler(self):
        self._stock_parts.ruler(10)

    def test_screw_m3(self):
        self._stock_parts.screw_m3(50)

    def test_servo(self):
        self._stock_parts.mg90s_servo()

    def test_stepper(self):
        self._stock_parts.nema_17_stepper()
