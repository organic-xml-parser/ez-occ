import math
import unittest

from OCC.Core.gp import gp

from ezocc.occutils_python import SetPlaceablePart, WireSketcher
from ezocc.part_manager import PartFactory, NoOpPartCache


class BugfixTest(unittest.TestCase):

    def setUp(self) -> None:
        self._cache = NoOpPartCache.instance()
        self._factory = PartFactory(self._cache)

    def test_compound_of_named_parts(self):
        p0 = self._factory.box(1, 1, 1).name("foo")
        p1 = self._factory.box(1, 1, 1).tr.mv(dx=10).name("bar")

        comp = self._factory.compound(p0, p1)

        self.assertEqual(SetPlaceablePart(p0), SetPlaceablePart(comp.single_subpart("foo")))
        self.assertEqual(SetPlaceablePart(p1), SetPlaceablePart(comp.single_subpart("bar")))

    def test_pattern_compound(self):
        part = self._factory.box(1, 1, 1).tr.mv(dx=10)
        part = part.pattern(range(0, 4), lambda i, p: p.tr.rz(math.radians(90 * i)).name(f"g{i}"))

        self.assertEqual(4, len(part.explore.solid.get()))

        part.single_subpart("g0")
        part.single_subpart("g1")
        part.single_subpart("g2")
        part.single_subpart("g3")

        self.assertRaises(Exception, lambda : part.single_subpart("g4"))

    def test_mirror_bug(self):
        to_mirror = self._factory.box(3, 8, 22) \
            .do(lambda p: p.bool.cut(
            self._factory.box_surrounding(p)
            .align().stack_x0(p, offset=2)
            .align().stack_z0(p, offset=12.5))) \
            .name("contact") \
            .print("After subshape is named") \
            .do(lambda p: p.bool.union(self._factory.cylinder(5.5 / 2, 11).align().xy_mid_to_mid(p).align().stack_z1(p))) \
            .print("After bool operation") \
            .cleanup()

        to_mirror.mirror.x()

    def test_edge_network_overlapping_circles(self):
        """
        Contrived example where the definite outer edge check results in ignoring a necessary edge.
        """

        pulley = (WireSketcher()
                  .line_to(x=10, z=10, is_relative=True)
                  .line_to(z=0)
                  .close()
                  .get_face_part(self._cache)
                  .do(lambda p: p.bool.union(p.mirror.z().align().stack_z0(p)))
                  .alg.project_y().alg.edge_network_to_outer_wire()
                  .make.face()
                  .tr.mv(dx=30)
                  .do(lambda p: p.fillet.fillet2d_verts(1, {p.explore.vertex.get_min(lambda v: v.xts.x_mid)}))
                  .revol.about(gp.OZ(), math.radians(360))
                  .cleanup()
                  .do(
            lambda p: self._factory.cylinder(p.xts.x_span / 2, p.xts.z_span).align().by("xmidymidzmid", p).bool.cut(p))
                  .do(lambda p: p.bool.cut(self._factory.cylinder(4, p.xts.z_span).align().by("xmidymidzmid", p))))

        edge_network = self._factory.loft([
            self._factory.circle(8).align().by("xmaxymid", pulley).tr.mv(dz=-1, dx=-15),
            self._factory.circle(2.5).align().by("xmidymid", pulley).tr.mv(dx=10)
        ], is_solid=False).alg.project_z().bool.union()

        self._factory.compound(*[
            e.tr.mv(dz=i * 1) for i, e in enumerate(edge_network.explore.edge.get())
        ])

        edge_network.alg.edge_network_to_outer_wire()
