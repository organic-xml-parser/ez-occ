import math
import pdb
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
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import Part, PartFactory, NoOpPartCache, CacheToken, NoOpCacheToken

from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE
from OCC.Core.gp import gp_Pnt

import OCC.Core.BRep

from ezocc.subshape_mapping import SubshapeMap, AnnotatedShape


class TestSubshapeMap(unittest.TestCase):

    def setUp(self) -> None:
        self._part_cache = InMemoryPartCache()
        self._part_factory = PartFactory(self._part_cache)

    def test_annotation_persists_through_compound(self):
        part_a = self._part_factory.box(10, 10, 10).annotate("keyA", "valueA")
        part_b = self._part_factory.box(10, 10, 10).annotate("keyB", "valueB")

        comp = self._part_factory.compound(part_a.name("part-a"), part_b.name("part-b"))

        self.assertEqual(dict(), comp.annotations)

        part_a_recovered = comp.sp("part-a")
        part_b_recovered = comp.sp("part-b")

        self.assertEqual(part_a.annotations, part_a_recovered.annotations)
        self.assertEqual(part_b.annotations, part_b_recovered.annotations)

    def test_annotation_persists_after_boolop(self):
        box = self._part_factory.box(10, 10, 10, x_max_face_name="xmax")\
            .annotate_subshape("xmax", ("color", "white"))

        box_after_bool = box.bool.cut(self._part_factory.box(10, 10, 10)
            .align().by("xminmidyminmidzmaxmid", box))

        for subpart in box_after_bool.list_subpart("xmax"):
            self.assertEqual(subpart.annotations, { "color": "white" })

    def test_annotated_shape(self):
        shp = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(gp_Pnt(0, 0, 0)).Shape()

        self.assertEqual(
            AnnotatedShape(shp),
            AnnotatedShape(shp))

        shp2 = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(gp_Pnt(0, 0, 0)).Shape()

        self.assertNotEqual(
            AnnotatedShape(shp),
            AnnotatedShape(shp2))

    def test_annotate_subshape(self):
        shp = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(gp_Pnt(0, 0, 0)).Shape()
        sshp = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(gp_Pnt(0, 0, 0)).Shape()

        map = SubshapeMap.from_unattributed_shapes(shp, {"label": {sshp}})

        self.assertTrue(len(map.get("label")) == 1)
        self.assertEqual(next(s for s in map.get("label")).attributes.values, {})

        map_modified = map.clone()
        map_modified.annotate_subshape("label", "foo", "bar")

        self.assertTrue(len(map.get("label")) == 1)
        self.assertEqual(next(s for s in map.get("label")).attributes.values, {})

        self.assertTrue(len(map_modified.get("label")) == 1)
        self.assertEqual(next(s for s in map_modified.get("label")).attributes.values, { "foo": "bar" })

    def test_root_shape(self):
        comp = OCC.Core.TopoDS.TopoDS_Compound()
        builder = OCC.Core.BRep.BRep_Builder()
        builder.MakeCompound(comp)

        map = SubshapeMap.from_single_shape(comp)

        self.assertEqual(comp, map.root_shape.set_placeable_shape.shape)

    def test_named_subshape(self):
        comp = OCC.Core.TopoDS.TopoDS_Compound()
        builder = OCC.Core.BRep.BRep_Builder()
        builder.MakeCompound(comp)

        v0 = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(gp_Pnt(0, 0, 0)).Shape()
        v1 = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(gp_Pnt(1, 0, 0)).Shape()

        builder.Add(comp, v0)
        builder.Add(comp, v1)

        map = SubshapeMap.from_unattributed_shapes(comp, {
            "v0": {v0},
            "v1": {v1}
        }).pruned()

        self.assertTrue(map.contains_shape(AnnotatedShape(v0)))
        self.assertTrue(map.contains_shape(AnnotatedShape(v1)))
