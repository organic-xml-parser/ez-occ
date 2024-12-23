from __future__ import annotations

import logging
import math
import time
import typing
import OCC.Core.TopoDS
import OCC.Core.TopAbs
import OCC.Core.BRepTools
import OCC.Core.BRepMesh
import OCC.Core.Poly
import OCC.Core.TopLoc
import OCC.Core.gp
import OCC.Core.BRep
from OCC.Core import TopExp
from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape

from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkCommonDataModel import vtkPolyLine, vtkTriangle, vtkSphere

from ezocc.alg.geometry_exploration.seam_identifier import SeamIdentifier
from ezocc.cad.gui.rendering_specifications.rendered_entities_spec import RenderedEntitiesSpec
from ezocc.cad.gui.rendering_specifications.rendering_color_spec import RenderingColorSpec
from ezocc.cad.gui.vtk.vtk_actor_builder import VtkActorBuilder
from ezocc.cad.gui.vtk.vtk_occ_actor_map import VtkOccActorMap
from ezocc.occutils_python import InterrogateUtils, Explorer, SetPlaceableShape, SetPlaceablePart

import vtk_occ_bridge_swig

from ezocc.part_manager import Part

"""
Provides utility classes for briding OCC and VTK.
"""
import OCC

logger = logging.getLogger(__name__)


class PerformanceTracker:

    def __init__(self):
        self._cumulative_time_s = 0.0
        self._t_latest: typing.Optional[float] = None

    def triangulation_started(self):
        if self._t_latest is not None:
            raise ValueError("Triangulation already started")

        self._t_latest = time.time()

    def triangulation_finished(self):
        if self._t_latest is None:
            raise ValueError("Triangulation not started")

        self._cumulative_time_s += (time.time() - self._t_latest)
        self._t_latest = None

    @property
    def cumulative_time_s(self) -> float:
        return self._cumulative_time_s

class VtkActorCollectionBuilder:

    def __init__(self,
                 parts: typing.Set[SetPlaceablePart],
                 color_spec_generator: typing.Callable[[SetPlaceablePart], RenderingColorSpec],
                 rendered_entities_spec: RenderedEntitiesSpec):
        self._parts = parts.copy()
        self._color_spec_generator = color_spec_generator
        self._rendered_entities_spec = rendered_entities_spec
        self._named_colors = vtkNamedColors()

    @staticmethod
    def _triangulate_shape(shape: OCC.Core.TopoDS.TopoDS_Shape, performance_tracker: PerformanceTracker):
        performance_tracker.triangulation_started()
        OCC.Core.BRepTools.breptools.Clean(shape)

        tri_algo = OCC.Core.BRepMesh.BRepMesh_DiscretFactory.Get().Discret(shape, 0.5, 45 * 2 * math.pi / 360)
        tri_algo.Perform()
        performance_tracker.triangulation_finished()

    @staticmethod
    def _process_vertex(actor_builder: VtkActorBuilder, is_labelled: bool, shape: SetPlaceableShape):
        actor_builder.push_vertex(InterrogateUtils.vertex_to_xyz(shape.shape), is_labelled, shape)

    @staticmethod
    def _process_triangulated_edge_pot(actor_builder: VtkActorBuilder,
                                       is_labelled: bool,
                                       seam_identifier: SeamIdentifier,
                                       edge: SetPlaceableShape):
        pot_result = vtk_occ_bridge_swig.Visualization.processEdgeTest(edge.shape)

        if not pot_result.hasValue():
            # nothing to do
            return

        pot: OCC.Core.Poly.Poly_PolygonOnTriangulation = pot_result.pot()
        pt: OCC.Core.Poly.Poly_Triangulation = pot_result.pt()
        loc: OCC.Core.TopLoc.TopLoc_Location = pot_result.loc()

        # push points to the builder
        pt_ids_to_vtk_ids = {}
        for i in range(1, pt.NbNodes() + 1):
            pnt = pt.Node(i)
            pnt = pnt.Transformed(loc.Transformation())
            pt_ids_to_vtk_ids[i] = actor_builder.push_point(pnt.X(), pnt.Y(), pnt.Z())

        # now iterate through polygon, converting pt_ids to vtk ids
        poly_line = vtkPolyLine()
        poly_line.GetPointIds().SetNumberOfIds(pot.NbNodes())
        for i in range(1, pot.NbNodes() + 1):
            point_id = pot.Node(i)
            vtk_point_id = pt_ids_to_vtk_ids[point_id]
            poly_line.GetPointIds().SetId(i - 1, vtk_point_id)

        actor_builder.push_line(poly_line=poly_line,
                                is_labelled=is_labelled,
                                seam_identifier=seam_identifier,
                                shape=edge)

    @staticmethod
    def _process_triangulated_edge_p3d(actor_builder: VtkActorBuilder,
                                       is_labelled: bool,
                                       seam_identifier: SeamIdentifier,
                                       edge: SetPlaceableShape):
        loc = OCC.Core.TopLoc.TopLoc_Location()
        p3d = OCC.Core.BRep.BRep_Tool.Polygon3D(edge.shape, loc)

        if p3d is None:
            return

        poly_line = vtkPolyLine()
        poly_line.GetPointIds().SetNumberOfIds(p3d.NbNodes())
        for i in range(1, p3d.NbNodes() + 1):
            pnt: OCC.Core.gp.gp_Pnt = p3d.Nodes().Value(i)
            pnt = pnt.Transformed(loc.Transformation())
            pnt_id = actor_builder.push_point(pnt.X(), pnt.Y(), pnt.Z())
            poly_line.GetPointIds().SetId(i - 1, pnt_id)

        actor_builder.push_line(poly_line=poly_line,
                                is_labelled=is_labelled,
                                seam_identifier=seam_identifier,
                                shape=edge)

    @staticmethod
    def _process_triangulated_edge(actor_builder: VtkActorBuilder,
                                   is_labelled: bool,
                                   seam_identifier: SeamIdentifier,
                                   edge: SetPlaceableShape):
        VtkActorCollectionBuilder._process_triangulated_edge_pot(
            actor_builder, is_labelled, seam_identifier, edge)
        VtkActorCollectionBuilder._process_triangulated_edge_p3d(
            actor_builder, is_labelled, seam_identifier, edge)

    @staticmethod
    def _process_triangulated_face_normal(actor_builder: VtkActorBuilder,
                                          is_labelled: bool,
                                          face: SetPlaceableShape):

        max_dimension = max(*actor_builder.part.part.xts.xyz_span)
        line_length = max(max_dimension * 0.2, 1)

        norm_pnt, norm_dir = InterrogateUtils.face_normal(face.shape)

        p0_id = actor_builder.push_point(
            norm_pnt.X(), norm_pnt.Y(), norm_pnt.Z())

        p1_id = actor_builder.push_point(
            norm_pnt.X() + norm_dir.X() * line_length,
            norm_pnt.Y() + norm_dir.Y() * line_length,
            norm_pnt.Z() + norm_dir.Z() * line_length)

        line = vtkPolyLine()
        line.GetPointIds().SetNumberOfIds(2)
        line.GetPointIds().SetId(0, p0_id)
        line.GetPointIds().SetId(1, p1_id)
        actor_builder.push_line(line, is_labelled, face)

    @staticmethod
    def _process_triangulated_face(actor_builder: VtkActorBuilder,
                                   rendered_entities_spec: RenderedEntitiesSpec,
                                   is_labelled: bool,
                                   face: SetPlaceableShape):
        loc = OCC.Core.TopLoc.TopLoc_Location()
        tri = OCC.Core.BRep.BRep_Tool.Triangulation(face.shape, loc)

        if tri is None:
            return

        pnt_ids = {}
        for i in range(1, tri.NbNodes() + 1):
            pnt = tri.Node(i)
            pnt = pnt.Transformed(loc.Transformation())

            vtk_id = actor_builder.push_point(pnt.X(), pnt.Y(), pnt.Z())
            pnt_ids[i] = vtk_id

        tris = tri.Triangles()
        for i in range(1, tri.NbTriangles() + 1):
            ia, ib, ic = tris.Value(i).Get()
            vtk_ia = pnt_ids[ia]
            vtk_ib = pnt_ids[ib]
            vtk_ic = pnt_ids[ic]

            t = vtkTriangle()
            t.GetPointIds().SetId(0, vtk_ia)
            t.GetPointIds().SetId(1, vtk_ib)
            t.GetPointIds().SetId(2, vtk_ic)

            actor_builder.push_tri(t, is_labelled, shape=face)

        if rendered_entities_spec.visualize_face_normals:
            try:
                VtkActorCollectionBuilder._process_triangulated_face_normal(actor_builder, is_labelled, face)
            except RuntimeError:
                logger.exception("Triangulated face normal processing failed.")

    def populate_vtk_actors(self, actor_map: VtkOccActorMap) -> None:
        performance_tracker = PerformanceTracker()
        for part in self._parts:
            logger.info("building actor...")
            self._build_vtk_actor(part, self._color_spec_generator(part), actor_map, performance_tracker)

        logger.info(f"Cumulative triangulation time: {performance_tracker.cumulative_time_s} seconds")

    def _build_vtk_actor(self,
                         part: SetPlaceablePart,
                         color_spec,
                         actor_map: VtkOccActorMap,
                         performance_tracker: PerformanceTracker) -> None:

        logger.info("Triangulating....")
        VtkActorCollectionBuilder._triangulate_shape(part.part.shape, performance_tracker)

        # create a map of edge to faces. This will be used to determine which edges are "seam" edges.
        # i.e. edges that exist on closed faces (cylinders, spheres etc.) due to OCC internals
        seam_identifier = SeamIdentifier(part.part.shape)

        actor_builder = VtkActorBuilder(color_spec, part)
        added_shapes = set()

        logger.info("Processing named shapes....")
        for label, shapelist in part.part.subshapes_items():
            for s in shapelist:
                if s.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_VERTEX:
                    self._process_vertex(actor_builder, True, s.set_placeable_shape)
                    added_shapes.add(s.shape)
                elif s.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_EDGE:
                    self._process_triangulated_edge(actor_builder, True, seam_identifier, s.set_placeable_shape)
                    added_shapes.add(s.shape)
                elif s.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_FACE:
                    self._process_triangulated_face(
                        actor_builder, self._rendered_entities_spec, True, s.set_placeable_shape)
                    added_shapes.add(s.shape)

        logger.info("Processing verts....")
        for v in Explorer.vertex_explorer(part.part.shape).get():
            sp = SetPlaceableShape(v)
            if v in added_shapes:
                continue

            VtkActorCollectionBuilder._process_vertex(actor_builder, False, sp)
            added_shapes.add(v)

        logger.info("Processing faces....")
        for f in Explorer.face_explorer(part.part.shape).get():
            sp = SetPlaceableShape(f)
            if f in added_shapes:
                continue

            VtkActorCollectionBuilder._process_triangulated_face(
                actor_builder,
                self._rendered_entities_spec,
                False,
                sp)
            added_shapes.add(f)

        logger.info("Processing edges....")
        for e in Explorer.edge_explorer(part.part.shape).get():
            sp = SetPlaceableShape(e)
            if e in added_shapes:
                continue

            VtkActorCollectionBuilder._process_triangulated_edge(actor_builder, False, seam_identifier, sp)
            added_shapes.add(e)

        logger.info("building assembly")

        actor_builder.build_assembly(actor_map)
