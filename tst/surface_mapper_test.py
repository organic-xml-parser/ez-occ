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
from ezocc.part_manager import Part, PartFactory, PartDriver, NoOpPartCache
from ezocc.workplane.surface_mapping import SurfaceMapper


class SurfaceMapperTest(unittest.TestCase):

    def setUp(self) -> None:
        self._cache = NoOpPartCache.instance()
        self._part_factory = PartFactory(self._cache)

    def test_surface_mapping(self):
        from_face = self._part_factory.square_centered(10, 10).make.face()

        to_face = op.WireSketcher().circle_arc_to(10, 0, 0, radius=100, direction=OCC.Core.gp.gp.DZ())\
            .get_wire_part(self._cache)\
            .extrude.prism(dz=10)\
            .make.face()

        mapper = SurfaceMapper(self._part_factory, from_face, to_face)

        mapper.map_face(self._part_factory.polygon(2, 3).sp("body").make.face())
