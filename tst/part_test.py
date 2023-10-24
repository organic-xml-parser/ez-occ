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

from ezocc.subshape_mapping import SubshapeMap


class TestPart(unittest.TestCase):

    def setUp(self) -> None:
        self._part_cache = InMemoryPartCache()

    def test_name_recurse(self):
        part = PartFactory(self._part_cache).box(1, 1, 1)\
            .name_recurse("box_face", lambda f: f.ShapeType() == OCC.Core.TopAbs.TopAbs_FACE)
        part_annotated = part.annotate_subshapes("box_face", ("color", "red"))

        pre_annotation_list = part.list_subpart("box_face")
        self.assertEqual(len(pre_annotation_list), 6)
        for p in pre_annotation_list:
            self.assertEqual(p.annotations, {})

        post_annotation_list = part_annotated.list_subpart("box_face")
        self.assertEqual(len(post_annotation_list), 6)
        for p in post_annotation_list:
            self.assertEqual(p.annotations, {"color": "red"})

    def test_root_part(self):
        shp = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(gp.gp_Pnt(0, 0, 0)).Shape()
        self.assertEqual(
            Part(NoOpCacheToken(), SubshapeMap.from_single_shape(shp)).shape, shp)

    def test_annotated_part(self):
        part = PartFactory(self._part_cache).box(1, 1, 1)\
            .annotate("color", "blue")

        part_translated = part.tr.mv(dx=100)

        self.assertEqual("blue", part_translated.annotation("color"))

    def test_annotated_subpart(self):
        part = PartFactory(self._part_cache).box(1, 1, 1) \
            .annotate("color", "blue")

        pre_annotated_part = part.name_subshape(
            part.pick.from_dir(0, 0, 1).first_face(),
            "top_face")

        self.assertEqual(len(part.subshapes.keys()), 0)
        self.assertEqual(len(pre_annotated_part.subshapes.keys()), 1)

        self.assertEqual(pre_annotated_part.sp("top_face").annotations, dict())

        annotated_part = pre_annotated_part.annotate_subshape("top_face", ("color", "red"))

        self.assertEqual(annotated_part.sp("top_face").annotation("color"), "red")
        self.assertEqual(pre_annotated_part.sp("top_face").annotations, dict())

    def test_name_vertex(self):
        def test_resolve_subpart(p):
            p.single_subpart("fillet")
            return p

        w = op.WireSketcher() \
            .line_to(y=-8, is_relative=True, v1_label="fillet") \
            .line_to(y=-9, z=-10, is_relative=True) \
            .line_to(y=0) \
            .close() \
            .get_wire_part(self._part_cache) \
            .print("before fillet")

        to_fillet0 = w.single_subpart("fillet")

        w.print("After subpart resolution 0")

        to_fillet1 = w.single_subpart("fillet")

        w.print("After subpart resolution 1")

        w1 = w.do(lambda p: p.fillet.fillet2d_verts(6, lambda v: v == to_fillet0.shape))

    def test_part_prism(self):
        p0 = op.WireSketcher()\
            .line_to(x=5, label="bottom")\
            .line_to(y=5, label="back")\
            .close()\
            .get_face_part(NoOpPartCache.instance())\
            .print()\
            .extrude.symmetric_prism(dz=10)

        bottom_parts = {s.shape for s in p0.list_subpart("bottom")}
        back_parts = {s.shape for s in p0.list_subpart("back")}

        bottom_types = sorted(s.ShapeType() for s in bottom_parts)
        back_types = sorted(s.ShapeType() for s in back_parts)

        self.assertEqual([TopAbs_FACE, TopAbs_FACE], bottom_types)
        self.assertEqual([TopAbs_FACE, TopAbs_FACE], back_types)

        self.assertEqual(0, len(bottom_parts.intersection(back_parts)))

        p0 = p0.cleanup().pruned()

        bottom = p0.single_subpart("bottom")
        back = p0.single_subpart("back")

        self.assertEqual(TopAbs_FACE, bottom.shape.ShapeType())
        self.assertEqual(TopAbs_FACE, back.shape.ShapeType())

        self.assertNotEqual(bottom, back)

    def test_part_translate(self):
        p0 = PartFactory(self._part_cache).box(1, 1, 1)

        p1 = p0.transform.translate(dx=1)
        p1_extents = p1.extents

        p0_extents = p0.extents

        self.assertNotEqual(p0.shape, p1.shape)

        self.assertEqual(p0_extents.xyz_mid, [0.5, 0.5, 0.5])
        self.assertEqual(p1_extents.xyz_mid, [1.5, 0.5, 0.5])

    def test_create_part_with_named_subpart(self):
        mkbox = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeBox(10, 2, 3)

        part = Part(NoOpCacheToken(), SubshapeMap.from_unattributed_shapes(mkbox.Shape(), {"front_face": [mkbox.FrontFace()]}))

        self.assertEqual(part.shape, mkbox.Shape())

        self.assertEqual(part.single_subpart("front_face").shape, mkbox.FrontFace())

    def test_create_part_with_named_subpart_after_prune(self):
        mkbox = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeBox(10, 2, 3)

        part = Part(NoOpCacheToken(),
                    SubshapeMap.from_unattributed_shapes(mkbox.Shape(), {"front_face": [mkbox.FrontFace()]})).pruned()

        self.assertEqual(part.shape, mkbox.Shape())
        self.assertEqual(part.single_subpart("front_face").shape, mkbox.FrontFace())

    def test_part_prune(self):
        mkbox = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeBox(10, 2, 3)

        orphan_face = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(gp.gp_Pln(gp.gp.Origin(), gp.gp.DZ())).Shape()
        pruned_part = Part(NoOpCacheToken(),
                           SubshapeMap.from_unattributed_shapes(mkbox.Shape(), {"front_face": [orphan_face]})).pruned()

        self.assertFalse("front_face" in pruned_part.subshapes.keys())

    def test_subpart_pruned(self):
        mkbox_a = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeBox(10, 10, 10)
        mkbox_b = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeBox(10, 10, 10)

        part = Part(self._part_cache.create_token("subpart_pruning"), SubshapeMap.from_unattributed_shapes(
            op.GeomUtils.make_compound(mkbox_a.Shape(), mkbox_b.Shape()), {
                "box_a": [mkbox_a.Shape()],
                "box_b": [mkbox_b.Shape()],
                "box_a_front_face": [mkbox_a.FrontFace()],
                "box_b_front_face": [mkbox_b.FrontFace()],
                "back_faces": [mkbox_a.BackFace(), mkbox_b.BackFace()]
            }))

        # sanity check
        self.assertNotEqual(mkbox_a.BackFace(), mkbox_b.BackFace())

        box_a_part = part.single_subpart("box_a").pruned()
        box_b_part = part.single_subpart("box_b").pruned()

        self.assertFalse("box_b_front_face" in box_a_part.subshapes.keys())
        self.assertFalse("box_a_front_face" in box_b_part.subshapes.keys())

        self.assertEqual(box_a_part.single_subpart("back_faces").shape, mkbox_a.BackFace())
        self.assertEqual(box_b_part.single_subpart("back_faces").shape, mkbox_b.BackFace())
        self.assertEqual(box_a_part.single_subpart("box_a_front_face").shape, mkbox_a.FrontFace())
        self.assertEqual(box_b_part.single_subpart("box_b_front_face").shape, mkbox_b.FrontFace())

        self.assertTrue("box_a" in box_a_part.subshapes.keys())
        self.assertFalse("box_b" in box_a_part.subshapes.keys())

        self.assertFalse("box_a" in box_b_part.subshapes.keys())
        self.assertTrue("box_b" in box_b_part.subshapes.keys())

    def test_remove_part(self):
        mkbox_a = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeBox(10, 10, 10)
        mkbox_b = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeBox(10, 10, 10)

        part = Part(self._part_cache.create_token("subpart_pruning"),
                    SubshapeMap.from_unattributed_shapes(
                    op.GeomUtils.make_compound(mkbox_a.Shape(), mkbox_b.Shape()), {
                        "box_a": [mkbox_a.Shape()],
                        "box_b": [mkbox_b.Shape()],
                        "box_a_front_face": [mkbox_a.FrontFace()],
                        "box_b_front_face": [mkbox_b.FrontFace()],
                        "back_faces": [mkbox_a.BackFace(), mkbox_b.BackFace()]
                    }))

        # sanity check
        self.assertNotEqual(mkbox_a.BackFace(), mkbox_b.BackFace())

        box_a_part = part.single_subpart("box_a")

        part = part.remove(box_a_part)

        self.assertEqual(mkbox_b.Shape(), part.explore.solid.get()[0].shape)

        self.assertTrue("box_b_front_face" in part.subshapes.keys())
        self.assertTrue("box_b" in part.subshapes.keys())
        self.assertFalse("box_a_front_face" in part.subshapes.keys())
        self.assertFalse("box_a" in part.subshapes.keys())

    def test_partfactory_loft(self):
        part_factory = PartFactory(self._part_cache)

        wires_or_faces = [
            part_factory.right_angle_triangle(10, math.pi / 3),
            part_factory.square_centered(10, 10).transform.translate(dz=10)
        ]

        part = part_factory.loft(
            wires_or_faces,
            is_solid=True,
            first_shape_name="bottom",
            loft_profile_name="loft-profile",
            last_shape_name="top")

        loft_profiles = part.list_subpart("loft-profile")

        bottom = part.single_subpart("bottom")
        top = part.single_subpart("top")

        self.assertTrue(top.shape not in [s.shape for s in loft_profiles])
        self.assertTrue(bottom.shape not in [s.shape for s in loft_profiles])

        self.assertEqual(len(set(loft_profiles)), 6)
        self.assertNotEqual(bottom.shape, top.shape)

        self.assertTrue(bottom.xts.z_max < top.xts.z_max)

    def test_make_thick_solid(self):
        part = PartFactory(self._part_cache).box(10, 10, 10)

        extruded = part.extrude.make_thick_solid(1)

        self.assertEqual(extruded.xts.x_span, part.xts.x_span + 2)
