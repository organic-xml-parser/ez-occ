import pdb
import unittest

import OCC.Core.ShapeAnalysis
import OCC.Core.gp as gp

import ezocc.occutils_python as op
from ezocc.part_manager import NoOpPartCache


class WireSketcherTest(unittest.TestCase):

    def setUp(self) -> None:
        self._cache = NoOpPartCache.instance()

    def test_code_sketch(self):
        w = op.WireSketcher(gp.gp_Pnt(0, 0, 0))

        length = 40
        for i in range(0, 7):
            w\
                .snap(length, length)\
                .line(lambda lf: lf.left())\
                .snap(length - 1, length - 1)\
                .line(lambda lf: lf.down())\
                .snap(length - 2, length - 2)\
                .line(lambda lf: lf.right())\
                .snap(length - 3, length - 3)\
                .line(lambda lf: lf.up())

            length -= 4


        #occutils.Visualization.visualizeList([w.get_wire()])

            #.line().right()\
            #.line().down()\
            #.line().left(2)\
            #.snap(10, 10).line().up().line().right().arc().up().left()

    def test_label_persistence(self):
        w = op.WireSketcher()\
            .line_to(x=2, label="a", is_relative=True) \
            .line_to(y=2, label="b", is_relative=True) \
            .line_to(x=-2, label="c", is_relative=True) \
            .line_to(y=-2, label="d", is_relative=True) \
            .get_wire_part(self._cache) \
            .pruned()\
            .print()

        self.assertEqual(len(w.subshapes["a"]), 1)
        self.assertEqual(len(w.subshapes["b"]), 1)
        self.assertEqual(len(w.subshapes["c"]), 1)
        self.assertEqual(len(w.subshapes["d"]), 1)

    def test_wire_sketcher(self):
        w = op.WireSketcher(gp.gp_Pnt(0, 0, 0))\
            .line_to(2, 0, 0)\
            .line_to(2, 2, 0)\
            .line_to(0, 2, 0)\
            .line_to(0, 0, 0)\
            .get_wire_part(self._cache)\
            .extrude.prism(dz=10)

        extents = op.Extents(w.shape)

        self.assertEqual(extents.x_min, 0)
        self.assertEqual(extents.y_min, 0)
        self.assertEqual(extents.z_min, 0)

        self.assertEqual(extents.x_max, 2)
        self.assertEqual(extents.y_max, 2)
        self.assertEqual(extents.z_max, 10)

    def test_zero_length_edge_throws_exception(self):
        ws = op.WireSketcher(gp.gp_Pnt(0, 0, 0))

        try:
            ws.line_to(0, 0, 0, is_relative=False)
            self.fail("Exception should have been thrown!")
        except ValueError as e:
            pass

    def test_buildcurves3d(self):
        w = op.WireSketcher(gp.gp_Pnt(0, 0, 0))\
            .line_to(2, 0, 0)\
            .line_to(2, 2, 0)\
            .line_to(0, 2, 0)\
            .line_to(0, 0, 0)\
            .get_wire()

        import OCC.Core.ShapeExtend

        se = OCC.Core.ShapeExtend.ShapeExtend_WireData(w)
        self.assertEqual(se.NbEdges(), 4)

        e0 = se.Edge(1)
        e1 = se.Edge(2)
        e2 = se.Edge(3)
        e3 = se.Edge(4)

        e0_verts = op.Explorer.vertex_explorer(e0).get()
        e1_verts = op.Explorer.vertex_explorer(e1).get()
        e2_verts = op.Explorer.vertex_explorer(e2).get()
        e3_verts = op.Explorer.vertex_explorer(e3).get()

        self.assertTrue(e0_verts[1].IsSame(e1_verts[0]))
        self.assertTrue(e1_verts[1].IsSame(e2_verts[0]))
        self.assertTrue(e2_verts[1].IsSame(e3_verts[0]))
        self.assertTrue(e3_verts[1].IsSame(e0_verts[0]))

        import OCC.Core.BRepBuilderAPI

        for e in op.Explorer.edge_explorer(w).get():
            sae = OCC.Core.ShapeAnalysis.ShapeAnalysis_Edge()

            self.assertTrue(sae.HasCurve3d(e))

        face = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(
            OCC.Core.gp.gp_Pln(gp.gp.Origin(), gp.gp.DZ())).Face()

        saw = OCC.Core.ShapeAnalysis.ShapeAnalysis_Wire(w, face, 0.001)
        self.assertFalse(saw.CheckClosed())
        self.assertFalse(saw.CheckConnected())
        self.assertFalse(saw.CheckSmall())

    def test_label_vertex(self):
        wire = op.WireSketcher().line_to(x=10).line_to(y=10, v0_label="test")\
            .close()\
            .get_wire_part(self._cache)

        self.assertEqual(["test"], list(wire.subshapes.keys()))

        result = wire.fillet.fillet2d_verts(1, {wire.sp("test")})

        # assert that an extra edge was added
        self.assertEqual(len(result.explore.edge.get()), 4)

        # assert that the total length has decreased
        self.assertLess(op.InterrogateUtils.linear_properties(result.shape).Mass(),
                        op.InterrogateUtils.linear_properties(wire.shape).Mass())