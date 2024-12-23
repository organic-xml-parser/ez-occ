from __future__ import annotations

import logging
import typing

from OCC.Core.BRep import BRep_Tool
from vtkmodules.util.vtkConstants import VTK_UNSIGNED_CHAR
from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkCommonCore import vtkUnsignedCharArray, vtkPoints, vtkDoubleArray, vtkIdTypeArray, vtkDataArray, \
    vtkIdList
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyLine, vtkTriangle, vtkPolyData, vtkImageData
from vtkmodules.vtkFiltersCore import vtkPolyDataNormals
from vtkmodules.vtkFiltersSources import vtkSphereSource
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkProperty, vtkTexture

from ezocc.alg.geometry_exploration.seam_identifier import SeamIdentifier
from ezocc.cad.gui.rendering_specifications.rendering_color_spec import RenderingColorSpec
from ezocc.cad.gui.rendering_specifications.selection_palette import SelectionPalette
from ezocc.cad.gui.vtk.vtk_occ_actor import VtkOccActor
from ezocc.cad.gui.vtk.vtk_occ_actor_map import VtkOccActorMap
from ezocc.humanization import Humanize
from ezocc.occutils_python import SetPlaceableShape, SetPlaceablePart, InterrogateUtils
import OCC.Core.TopAbs


logger = logging.getLogger(__name__)


class VertexPointsBuilder:

    def __init__(self, color_spec: RenderingColorSpec):
        self._color_spec = color_spec
        self._vtk_points = vtkPoints()
        self._points_cell_array = vtkCellArray()
        self._points_cell_array_colors = vtkUnsignedCharArray()
        self._points_cell_array_colors.SetNumberOfComponents(3)
        self._points_cell_ids_to_shapes: typing.Dict[int, SetPlaceableShape] = {}
        self._points_shapes_to_cell_ids: typing.Dict[SetPlaceableShape, typing.Set[int]] = {}

    def insert_vertex(self,
                      xyz: typing.Tuple[float, float, float],
                      is_labelled: bool,
                      shape: SetPlaceableShape):
        point_id = self._vtk_points.InsertNextPoint(xyz)
        self._points_cell_array.InsertNextCell(1, [point_id])

        if shape not in self._points_shapes_to_cell_ids:
            self._points_shapes_to_cell_ids[shape] = set()

        self._points_shapes_to_cell_ids[shape].add(point_id)
        self._points_cell_ids_to_shapes[point_id] = shape

        rgb = self._color_spec.establish_color(shape, is_labelled=is_labelled, is_highlighted=False)

        self._points_cell_array_colors.InsertNextTypedTuple(rgb)


    def build_actor(self, color_spec, part) -> VtkOccActor:
        poly_data = vtkPolyData()
        poly_data.SetPoints(self._vtk_points)
        poly_data.SetVerts(self._points_cell_array)
        poly_data.GetCellData().SetScalars(self._points_cell_array_colors)

        mapper = vtkPolyDataMapper()
        mapper.SetInputData(poly_data)

        result = vtkActor()
        result.SetMapper(mapper)

        prop: vtkProperty = result.GetProperty()

        prop.SetPointSize(5)
        prop.SetRenderPointsAsSpheres(True)

        return VtkOccActor(color_spec,
                           result,
                           part,
                           OCC.Core.TopAbs.TopAbs_VERTEX,
                           self._points_cell_ids_to_shapes,
                           self._points_shapes_to_cell_ids)


class VtkActorBuilder:

    def __init__(self, color_spec: RenderingColorSpec, part: SetPlaceablePart):
        self._color_spec = color_spec
        self._part = part
        self._named_colors = vtkNamedColors()

        self.points = vtkPoints()
        self._current_point_id = 0

        self._vertex_points_builder = VertexPointsBuilder(color_spec)

        self._tris_cell_array = vtkCellArray()
        self._tris_cell_array_colors = vtkUnsignedCharArray()
        self._tris_cell_array_colors.SetNumberOfComponents(3)
        self._tris_cell_ids_to_shapes: typing.Dict[int, SetPlaceableShape] = {}
        self._tris_shapes_to_cell_ids: typing.Dict[SetPlaceableShape, typing.Set[int]] = {}

        self._lines_cell_array = vtkCellArray()
        self._lines_cell_array_colors = vtkUnsignedCharArray()
        self._lines_cell_array_colors.SetNumberOfComponents(3)
        self._lines_cell_ids_to_shapes: typing.Dict[int, SetPlaceableShape] = {}
        self._lines_shapes_to_cell_ids: typing.Dict[SetPlaceableShape, typing.Set[int]] = {}

        # for e.g. a box there are 2 points for each straight line = 2 * 12 = 24 points that
        # need to have the length taken into account. other points can have 0 as their texture
        # coord as they are not used for lines
        self._point_ids_to_texture_coords: typing.Dict[int, float] = {}

        self._stipple_line_pattern = [True, False] * 16
        # Create texture
        dimension = len(self._stipple_line_pattern)

        self._stipple_line_image = vtkImageData()
        self._stipple_line_image.SetDimensions(dimension, 1, 1)
        self._stipple_line_image.SetExtent(0, dimension - 1, 0, 0, 0, 0)
        self._stipple_line_image.AllocateScalars(VTK_UNSIGNED_CHAR, 4)
        on = 255
        off = 0
        for i in range(0, len(self._stipple_line_pattern)):
            self._stipple_line_image.SetScalarComponentFromFloat(i, 0, 0, 0, on)
            self._stipple_line_image.SetScalarComponentFromFloat(i, 0, 0, 1, on)
            self._stipple_line_image.SetScalarComponentFromFloat(i, 0, 0, 2, on)
            self._stipple_line_image.SetScalarComponentFromFloat(i, 0, 0, 3, on if self._stipple_line_pattern[i] else off)

    @property
    def part(self) -> SetPlaceablePart:
        return self._part

    def current_point_id(self):
        return self._current_point_id

    def push_point(self, x: float, y: float, z: float) -> int:
        self.points.InsertNextPoint([x, y, z])

        result = self._current_point_id

        self._current_point_id += 1
        return result

    def push_vertex(self,
                    xyz: typing.Tuple[float, float, float],
                    is_labelled: bool,
                    shape: SetPlaceableShape):
        self._vertex_points_builder.insert_vertex(xyz, is_labelled, shape)

    def push_line(self,
                  poly_line: vtkPolyLine,
                  is_labelled: bool,
                  seam_identifier: SeamIdentifier,
                  shape: SetPlaceableShape = None):

        # shape does not start off highlighted
        rgb = self._color_spec.establish_color(shape, is_labelled=is_labelled, is_highlighted=False)

        lcid = self._lines_cell_array.InsertNextCell(poly_line)
        if shape is not None:
            self._lines_cell_ids_to_shapes[lcid] = shape
            self._lines_shapes_to_cell_ids[shape] = self._lines_shapes_to_cell_ids.get(shape, set())
            self._lines_shapes_to_cell_ids[shape].add(lcid)

        self._lines_cell_array_colors.InsertNextTypedTuple(rgb)

        if seam_identifier.is_degenerated(shape.shape):
            # unclear if this is ever called as triangulation may eliminate degenerate edges...
            return

        if seam_identifier.is_seam(shape.shape):
            line_length = InterrogateUtils.length(shape.shape)

            #print("Pushing line:")
            point_id_list: vtkIdList = poly_line.GetPointIds()
            #print("Line has n point ids: ", point_id_list.GetNumberOfIds())
            for i in range(0, point_id_list.GetNumberOfIds()):
                point_id = point_id_list.GetId(i)
                texture_coordinate = i * (line_length / point_id_list.GetNumberOfIds())
                self._point_ids_to_texture_coords[point_id] = texture_coordinate

    def push_tri(self,
                 tri: vtkTriangle,
                 is_labelled: bool,
                 shape: typing.Optional[SetPlaceableShape]):

        rgb = self._color_spec.establish_color(shape, is_labelled=is_labelled, is_highlighted=False)

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
        prop: vtkProperty = result.GetProperty()
        prop.SetInterpolationToPBR()
        prop.EdgeVisibilityOff()
        prop.SetMetallic(0)
        prop.SetRoughness(0.5)

        return VtkOccActor(self._color_spec,
                           result,
                           self._part,
                           OCC.Core.TopAbs.TopAbs_FACE,
                           self._tris_cell_ids_to_shapes,
                           self._tris_shapes_to_cell_ids)

    def StippledLine(self, actor: vtkActor):
        texture = vtkTexture()

        polyData: vtkPolyData = actor.GetMapper().GetInput()
        tcoords = vtkDoubleArray()
        tcoords.SetNumberOfComponents(1)
        tcoords.SetNumberOfTuples(polyData.GetNumberOfPoints())
        for i in range(0, polyData.GetNumberOfPoints()):
            value = self._point_ids_to_texture_coords.get(i, 0) / 10
            tcoords.SetTypedTuple(i, [value])
        polyData.GetPointData().SetTCoords(tcoords)
        texture.SetInputData(self._stipple_line_image)
        texture.InterpolateOff()
        texture.RepeatOn()

        #points: vtkPoints = polyData.GetPoints()
        #print("Number of points in poly data", points.GetNumberOfPoints())

        #lines: vtkCellArray = polyData.GetLines()
        #lines.DebugOn()
        #print("Number of lines in actor: ", lines.GetNumberOfCells())

        #print("Number of polys in polydata: ", polyData.GetNumberOfPolys())

        #print(self._point_ids_to_texture_coords)

        #polyData.DebugOn()
        actor.SetTexture(texture)

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
        result.GetProperty().SetLineWidth(2)
        result.GetProperty().SetInterpolationToFlat()
        result.GetProperty().BackfaceCullingOff()
        result.GetProperty().LightingOff()
        result.GetProperty().SetOpacity(0.6)

        result = VtkOccActor(self._color_spec,
                           result,
                           self._part,
                           OCC.Core.TopAbs.TopAbs_EDGE,
                           self._lines_cell_ids_to_shapes,
                           self._lines_shapes_to_cell_ids)

        self.StippledLine(result.actor)

        return result

    def build_assembly(self, actor_map: VtkOccActorMap) -> None:
        solid_actor = self.build_actor_solid()
        edge_actor = self.build_actor_edges()
        vertex_actor = self._vertex_points_builder.build_actor(self._color_spec, self._part)

        actor_map.add_entry(solid_actor)
        actor_map.add_entry(edge_actor)
        actor_map.add_entry(vertex_actor)
