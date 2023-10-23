import unittest

import OCC
import OCC.Core as occ
import OCC.Core.BOPAlgo
import OCC.Core.BRepAlgoAPI
import OCC.Core.BRepBuilderAPI
import OCC.Core.BRepFilletAPI
import OCC.Core.BRepOffsetAPI
import OCC.Core.BRepPrimAPI
import OCC.Core.GeomAbs
import OCC.Core.ShapeUpgrade
import OCC.Core.TopOpeBRepBuild
import OCC.Core.gp as gp
import OCC.Core.TopAbs

import pythonoccutils.occutils_python as op
from pythonoccutils.humanization import Humanize
from pythonoccutils.part_manager import PartFactory, Part, NoOpCacheToken, NoOpPartCache
from pythonoccutils.precision import Compare
from pythonoccutils.subshape_mapping import SubshapeMap
from pythonoccutils.type_utils import TypeValidator


class TestProjects(unittest.TestCase):

    def setUp(self) -> None:
        self._factory = PartFactory(NoOpPartCache.instance())

    def test_stepper_mount(self):
        stepper_height = 47.4

        stepper_body = self._factory.box(42, 42, stepper_height)

        self.assertEqual(Humanize.shape_type(stepper_body.shape.ShapeType()), "solid")

        stepper_hole_clearances = self._factory.cylinder(3.1 / 2, 10) \
            .do_and_add(lambda p: p.transform.translate(dx=31)) \
            .do_and_add(lambda p: p.transform.translate(dy=31)) \
            .align().xy_mid_to_mid(stepper_body) \
            .align().stack_z1(stepper_body)
        stepper_hole_clearances = stepper_hole_clearances.add(
            self._factory.cylinder(22.5 / 2, 100).align().xy_mid_to_mid(stepper_body).align().stack_z1(stepper_body))

        # create an l shaped mount

        bracket_0 = self._factory.box(15, stepper_body.extents.y_span, 4) \
            .align().yx_min_to_min(stepper_body) \
            .align().stack_z1(stepper_body)

        bracket_1 = self._factory.box(6, stepper_body.extents.y_span,
                                    stepper_body.extents.z_span + bracket_0.extents.z_span) \
            .align().yz_min_to_min(stepper_body) \
            .align().stack_x0(stepper_body)

        bracket_2 = bracket_0.align().stack_x0(bracket_1).align().yz_min_to_min(bracket_1)

        bracket = bracket_0.bool.union(bracket_1, bracket_2) \
            .cleanup() \
            .bool.cut(stepper_hole_clearances) \
            .bool.cut(self._factory.cylinder(2.5, 100).do_and_add(lambda p: p.transform.translate(dy=28))
                      .align().xyz_mid_to_mid(bracket_2))

        def edge_fillet_selector(e) -> bool:
            pe = Part(NoOpCacheToken(), SubshapeMap.from_unattributed_shapes(e))

            if op.InterrogateUtils.is_dy_line(e):
                return Compare.lin_eq(pe.extents.z_max, bracket.extents.z_max) or \
                       Compare.lin_eq(pe.extents.z_max, bracket_2.extents.z_max)

            return False

        bracket = bracket.fillet.chamfer_edges(1, edge_fillet_selector).cleanup()

        self.assertEqual(1, len(bracket.explore.solid.get()))

        bracket = bracket.explore.solid.get()[0]

        self.assertEqual(Humanize.shape_type(bracket.shape.ShapeType()), "solid")

