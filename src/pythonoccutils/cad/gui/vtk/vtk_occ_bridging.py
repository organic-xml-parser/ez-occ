from __future__ import annotations

import logging
import math
import pdb
import time
import typing

from OCC.Core.TCollection import TCollection_AsciiString
from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkCommonCore import vtkUnsignedCharArray, vtkPoints
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyLine, vtkTriangle, vtkPolyData
from vtkmodules.vtkFiltersCore import vtkPolyDataNormals
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkAssembly

from pythonoccutils.cad.gui.render_spec import RenderingColorSpec, RenderSpec
from pythonoccutils.occutils_python import InterrogateUtils, Explorer, SetPlaceableShape
from pythonoccutils.part_manager import Part

import vtk_occ_bridge_swig

"""
Provides utility classes for briding OCC and VTK.
"""
import OCC

logger = logging.getLogger(__name__)


class VtkOccActor:

    def __init__(self,
                 name: str,
                 color_spec: RenderingColorSpec,
                 actor: vtkActor,
                 part: Part,
                 cell_ids_to_subshapes: typing.Dict[int, OCC.Core.TopoDS.TopoDS_Shape],
                 subshapes_to_cell_ids: typing.Dict[OCC.Core.TopoDS.TopoDS_Shape, typing.Set[int]]):
        self.name = name
        self.color_spec = color_spec
        self.actor = actor
        self.part = part
        self.cell_ids_to_subshapes = cell_ids_to_subshapes
        self.subshapes_to_cell_ids = subshapes_to_cell_ids

        self._saved_cell_states: typing.Dict[int, typing.Tuple[float, float, float]] = {}

    def clear_highlights(self):
        cell_scalars: vtkUnsignedCharArray = \
            self.actor.GetMapper().GetInput().GetCellData().GetScalars()

        for cell_id, saved_color in self._saved_cell_states.items():
            cell_scalars.SetTypedTuple(cell_id, saved_color)

        self._saved_cell_states.clear()

        self.actor.GetMapper().GetInput().Modified()

    def highlight_subshape(self, subshape: SetPlaceableShape):
        cell_ids = self.subshapes_to_cell_ids.get(subshape)

        if subshape.shape.ShapeType() == OCC.Core.TopoDS.TopoDS_Face:
            entity_colorspec = self.color_spec.faces_spec
        else:
            entity_colorspec = self.color_spec.edges_spec

        is_highlight = self.part.subshapes.contains_shape(subshape)

        rgb = entity_colorspec.highlight_color if is_highlight else entity_colorspec.base_color

        self._highlight_cells(rgb, cell_ids)

    def _highlight_cells(self, rgb, ids_to_highlight: typing.Set[int]):
        cell_scalars: vtkUnsignedCharArray = \
            self.actor.GetMapper().GetInput().GetCellData().GetScalars()

        for i in ids_to_highlight:
            t_out = [0, 0, 0]
            cell_scalars.GetTypedTuple(i, t_out)

            if i not in self._saved_cell_states:
                self._saved_cell_states[i] = (t_out[0], t_out[1], t_out[2])

            cell_scalars.SetTypedTuple(i, rgb)

        self.actor.GetMapper().GetInput().Modified()


class VtkOccActorMap:
    """
    Used to track the relationship between vtk and OCC entities. This can be useful for
    determining e.g. the Part corresponding to a given vtkActor.
    """

    def __init__(self):
        # records relation between vtk actors and associated parts etc.
        self._actor_map: typing.Dict[vtkActor, VtkOccActor] = {}

        # records part relations back to actors
        self._part_map: typing.Dict[Part, typing.Set[vtkActor]] = {}

    def clear(self):
        self._actor_map.clear()
        self._part_map.clear()

    def add_entry(self, vtk_actor: vtkActor, vtk_occ_actor: VtkOccActor):
        if vtk_actor in self._actor_map:
            raise ValueError("Actor already present")

        self._actor_map[vtk_actor] = vtk_occ_actor

        if vtk_occ_actor.part not in self._part_map:
            self._part_map[vtk_occ_actor.part] = set()

        self._part_map[vtk_occ_actor.part].add(vtk_actor)

    def get_vtk_occ_actor(self, vtk_actor: vtkActor) -> VtkOccActor:
        return self._actor_map[vtk_actor]

    def get_vtk_actors(self, part: Part) -> typing.Set[vtkActor]:
        return self._part_map[part].copy()


class VtkActorBuilder:

    def __init__(self, color_spec: RenderingColorSpec, part: Part):
        self._color_spec = color_spec
        self._part = part
        self._named_colors = vtkNamedColors()

        self.points = vtkPoints()
        self._current_point_id = 0

        self._tris_cell_array = vtkCellArray()
        self._tris_cell_array_colors = vtkUnsignedCharArray()
        self._tris_cell_array_colors.SetNumberOfComponents(3)
        self._tris_cell_ids_to_shapes = {}
        self._tris_shapes_to_cell_ids = {}

        self._lines_cell_array = vtkCellArray()
        self._lines_cell_array_colors = vtkUnsignedCharArray()
        self._lines_cell_array_colors.SetNumberOfComponents(3)
        self._lines_cell_ids_to_shapes = {}
        self._lines_shapes_to_cell_ids = {}

    @property
    def part(self) -> Part:
        return self._part

    def current_point_id(self):
        return self._current_point_id

    def push_point(self, x: float, y: float, z: float) -> int:
        self.points.InsertNextPoint([x, y, z])

        result = self._current_point_id

        self._current_point_id += 1
        return result

    def push_line(self,
                  poly_line: vtkPolyLine,
                  rgb: typing.Tuple[float, float, float],
                  shape: OCC.Core.TopoDS.TopoDS_Shape = None):

        lcid = self._lines_cell_array.InsertNextCell(poly_line)
        if shape is not None:
            self._lines_cell_ids_to_shapes[lcid] = shape
            self._lines_shapes_to_cell_ids[shape] = self._lines_shapes_to_cell_ids.get(shape, set())
            self._lines_shapes_to_cell_ids[shape].add(lcid)

        self._lines_cell_array_colors.InsertNextTypedTuple(rgb)

    def push_tri(self,
                 tri: vtkTriangle,
                 rgb: typing.Tuple[float, float, float],
                 shape: OCC.Core.TopoDS.TopoDS_Shape = None):

        tcid = self._tris_cell_array.InsertNextCell(tri)
        if shape is not None:
            self._tris_cell_ids_to_shapes[tcid] = shape

            self._tris_shapes_to_cell_ids[shape] = self._tris_shapes_to_cell_ids.get(shape, set())
            self._tris_shapes_to_cell_ids[shape].add(tcid)

        self._tris_cell_array_colors.InsertNextTypedTuple(rgb)

    def build_actor_solid(self) -> VtkOccActor:
        data = vtkPolyData()
        data.SetPoints(self.points)

        data.SetPolys(self._tris_cell_array)
        data.GetCellData().SetScalars(self._tris_cell_array_colors)

        poly_data_normals = vtkPolyDataNormals()
        poly_data_normals.SetInputData(data)
        poly_data_normals.ComputeCellNormalsOff()
        poly_data_normals.ComputePointNormalsOn()
        poly_data_normals.Update()

        data = poly_data_normals.GetOutput()

        data_mapper = vtkPolyDataMapper()
        data_mapper.SetInputData(data)

        result = vtkActor()
        result.SetMapper(data_mapper)

        # result.GetProperty().SetRenderLinesAsTubes(True)
        result.GetProperty().SetColor(self._named_colors.GetColor3d("lamp_black"))
        result.GetProperty().SetInterpolationToGouraud()

        return VtkOccActor("solidactor",
                           self._color_spec,
                           result,
                           self._part,
                           self._tris_cell_ids_to_shapes,
                           self._tris_shapes_to_cell_ids)

    def build_actor_edges(self) -> VtkOccActor:
        data = vtkPolyData()
        data.SetPoints(self.points)

        data.SetLines(self._lines_cell_array)
        data.GetCellData().SetScalars(self._lines_cell_array_colors)

        data_mapper = vtkPolyDataMapper()
        data_mapper.SetInputData(data)

        result = vtkActor()
        result.SetMapper(data_mapper)

        result.GetProperty().SetRenderLinesAsTubes(True)
        result.GetProperty().ShadingOff()
        result.GetProperty().SetLineWidth(1.5)
        result.GetProperty().SetInterpolationToFlat()
        result.GetProperty().BackfaceCullingOff()
        result.GetProperty().LightingOff()

        return VtkOccActor("edgeactor",
                           self._color_spec,
                           result,
                           self._part,
                           self._lines_cell_ids_to_shapes,
                           self._lines_shapes_to_cell_ids)

    def build_assembly(self, actor_map: VtkOccActorMap) -> vtkAssembly:
        solid_actor = self.build_actor_solid()
        edge_actor = self.build_actor_edges()

        actor_map.add_entry(solid_actor.actor, solid_actor)
        actor_map.add_entry(edge_actor.actor, edge_actor)

        result = vtkAssembly()
        result.AddPart(solid_actor.actor)
        result.AddPart(edge_actor.actor)

        return result


class VtkActorsBuilder:

    def __init__(self,
                 parts: typing.Set[Part],
                 color_spec: typing.Callable[[Part], RenderingColorSpec],
                 render_spec: RenderSpec):
        self._parts = parts.copy()
        self._color_spec = color_spec
        self._render_spec = render_spec
        self._named_colors = vtkNamedColors()

    @staticmethod
    def _triangulate_shape(shape):
        OCC.Core.BRepTools.breptools.Clean(shape)

        tri_algo = OCC.Core.BRepMesh.BRepMesh_DiscretFactory_Get().Discret(shape, 0.2, 30 * 2 * math.pi / 360)
        tri_algo.Perform()

    @staticmethod
    def _process_triangulated_edge_pot(actor_builder: VtkActorBuilder,
                                       color_spec: RenderingColorSpec,
                                       edge: SetPlaceableShape):
        pot_result = vtk_occ_bridge_swig.Visualization.processEdgeTest(edge.shape)

        color = color_spec.establish_color(edge)

        if not pot_result.hasValue():
            # nothing to do
            return

        pot: OCC.Core.Poly.Poly_PolygonOnTriangulation = pot_result.pot()
        pt: OCC.Core.Poly.Poly_Triangulation = pot_result.pt()
        loc: OCC.Core.TopLoc.TopLoc_Location = pot_result.loc()

        # push points to the builder
        pt_ids_to_vtk_ids = {}
        for i in range(1, pt.NbNodes() + 1):
            pnt = pt.Nodes().Value(i)
            pnt = pnt.Transformed(loc.Transformation())
            pt_ids_to_vtk_ids[i] = actor_builder.push_point(pnt.X(), pnt.Y(), pnt.Z())

        # now iterate through polygon, converting pt_ids to vtk ids
        poly_line = vtkPolyLine()
        poly_line.GetPointIds().SetNumberOfIds(pot.NbNodes())
        for i in range(1, pot.NbNodes() + 1):
            point_id = pot.Nodes().Value(i)
            vtk_point_id = pt_ids_to_vtk_ids[point_id]
            poly_line.GetPointIds().SetId(i - 1, vtk_point_id)

        actor_builder.push_line(poly_line, color, shape=edge)

    @staticmethod
    def _process_triangulated_edge_p3d(actor_builder: VtkActorBuilder,
                                       color_spec: RenderingColorSpec,
                                       edge: SetPlaceableShape):
        color = color_spec.establish_color(edge)
        loc = OCC.Core.TopLoc.TopLoc_Location()
        p3d = OCC.Core.BRep.BRep_Tool_Polygon3D(edge.shape, loc)

        if p3d is None:
            return

        poly_line = vtkPolyLine()
        poly_line.GetPointIds().SetNumberOfIds(p3d.NbNodes())
        for i in range(1, p3d.NbNodes() + 1):
            pnt: OCC.Core.gp.gp_Pnt = p3d.Nodes().Value(i)
            pnt = pnt.Transformed(loc.Transformation())
            pnt_id = actor_builder.push_point(pnt.X(), pnt.Y(), pnt.Z())
            poly_line.GetPointIds().SetId(i - 1, pnt_id)

        actor_builder.push_line(poly_line, color, shape=edge)

    @staticmethod
    def _process_triangulated_edge(actor_builder: VtkActorBuilder,
                                   color_spec: RenderingColorSpec,
                                   edge: SetPlaceableShape):
        VtkActorsBuilder._process_triangulated_edge_pot(actor_builder, color_spec, edge)
        VtkActorsBuilder._process_triangulated_edge_p3d(actor_builder, color_spec, edge)

    @staticmethod
    def _process_triangulated_face_normal(color_spec: RenderingColorSpec,
                                          actor_builder: VtkActorBuilder,
                                          face: SetPlaceableShape):

        color = color_spec.establish_color(face)

        norm_pnt, norm_dir = InterrogateUtils.face_normal(face.shape)

        p0_id = actor_builder.push_point(
            norm_pnt.X(), norm_pnt.Y(), norm_pnt.Z())

        p1_id = actor_builder.push_point(
            norm_pnt.X() + norm_dir.X(),
            norm_pnt.Y() + norm_dir.Y(),
            norm_pnt.Z() + norm_dir.Z())

        line = vtkPolyLine()
        line.GetPointIds().SetNumberOfIds(2)
        line.GetPointIds().SetId(0, p0_id)
        line.GetPointIds().SetId(1, p1_id)
        actor_builder.push_line(line, color, face)

    @staticmethod
    def _process_triangulated_face(actor_builder: VtkActorBuilder,
                                   render_spec: RenderSpec,
                                   color_spec: RenderingColorSpec,
                                   face: SetPlaceableShape):
        loc = OCC.Core.TopLoc.TopLoc_Location()
        tri = OCC.Core.BRep.BRep_Tool_Triangulation(face.shape, loc)

        color = color_spec.establish_color(face)

        if tri is None:
            return

        point_array = tri.Nodes()
        pnt_ids = {}
        for i in range(1, tri.NbNodes() + 1):
            pnt = point_array.Value(i)
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

            actor_builder.push_tri(t, color, shape=face)

        if render_spec.visualize_face_normals:
            try:
                VtkActorsBuilder._process_triangulated_face_normal(color_spec, actor_builder, face)
            except RuntimeError:
                logger.exception("Triangulated face normal processing failed.")

    def get_vtk_actors(self, actor_map: VtkOccActorMap) -> typing.Set[vtkAssembly]:
        result = set()

        for part in self._parts:
            result.add(self._get_vtk_actor(part, self._color_spec(part), actor_map))

        return result

    def _get_vtk_actor(self, part: Part, color_spec, actor_map: VtkOccActorMap) -> vtkAssembly:

        VtkActorsBuilder._triangulate_shape(part.shape)

        actor_builder = VtkActorBuilder(color_spec, part)
        added_shapes = set()

        for label, shapelist in part.subshapes.items():
            for s in shapelist:
                if s.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_EDGE:
                    self._process_triangulated_edge(actor_builder, color_spec, s.set_placeable_shape)
                    added_shapes.add(s.set_placeable_shape)
                elif s.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_FACE:
                    self._process_triangulated_face(actor_builder, self._render_spec, color_spec, s.set_placeable_shape)
                    added_shapes.add(s.set_placeable_shape)

        for f in Explorer.face_explorer(part.shape).get():
            sp = SetPlaceableShape(f)
            if sp in added_shapes:
                continue

            VtkActorsBuilder._process_triangulated_face(
                actor_builder,
                self._render_spec,
                color_spec,
                sp)

        for e in Explorer.edge_explorer(part.shape).get():
            sp = SetPlaceableShape(e)
            if sp in added_shapes:
                continue

            VtkActorsBuilder._process_triangulated_edge(
                actor_builder,
                color_spec,
                sp)

        return actor_builder.build_assembly(actor_map)
