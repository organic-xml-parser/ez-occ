import pdb
import traceback
import typing

import OCC.Core.TopAbs
from vtkmodules.vtkCommonColor import vtkNamedColors

from ezocc.occutils_python import SetPlaceableShape, InterrogateUtils
from ezocc.part_manager import Part
from ezocc.subshape_mapping import AnnotatedShape


class EntityRenderingColorSpec:

    NAMED_COLORS = vtkNamedColors()

    ColorType = typing.Union[typing.Tuple[float, float, float], str]

    def __init__(self,
                 base_color: ColorType,
                 highlight_color: ColorType):
        self._base_color = EntityRenderingColorSpec.color_to_rgb(base_color)
        self._highlight_color = EntityRenderingColorSpec.color_to_rgb(highlight_color)

    @property
    def base_color(self):
        return self._base_color

    @property
    def highlight_color(self):
        return self._highlight_color

    @staticmethod
    def color_to_rgb(color_value: ColorType):
        if isinstance(color_value, str):
            named_color = EntityRenderingColorSpec.NAMED_COLORS.GetColor3ub(color_value)
            return named_color.GetRed(), named_color.GetGreen(), named_color.GetBlue()
        else:
            return color_value


class RenderingColorSpec:

    def __init__(self,
                 part: Part,
                 edges_spec: EntityRenderingColorSpec,
                 faces_spec: EntityRenderingColorSpec,
                 edges_labelled_spec: EntityRenderingColorSpec,
                 faces_labelled_spec: EntityRenderingColorSpec):
        self.edges_spec = edges_spec
        self.faces_spec = faces_spec
        self.edges_labelled_spec = edges_labelled_spec
        self.faces_labelled_spec = faces_labelled_spec

        self._color_map = dict()

        for label, annotated_shapes in part.subshapes.items():
            for annotated_shape in annotated_shapes:

                color_value = self.faces_labelled_spec.highlight_color if  \
                    annotated_shape.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_FACE else \
                    self.edges_labelled_spec.highlight_color

                self._color_map[SetPlaceableShape(annotated_shape.shape)] = color_value

                for s in InterrogateUtils.traverse_all_subshapes(annotated_shape.shape):
                    self._color_map[SetPlaceableShape(s)] = color_value

        # cache the color map ahead of time
        if "color" in part.annotations:
            self._color_map[SetPlaceableShape(part.shape)] = EntityRenderingColorSpec.color_to_rgb(part.annotations["color"])
            for s in InterrogateUtils.traverse_all_subshapes(part.shape):
                self._color_map[SetPlaceableShape(s)] = EntityRenderingColorSpec.color_to_rgb(part.annotations["color"])

        for label, annotated_shapes in part.subshapes.items():
            for annotated_shape in annotated_shapes:
                if "color" in annotated_shape.attributes.values:
                    color_value = EntityRenderingColorSpec.color_to_rgb(annotated_shape.attributes["color"])

                    self._color_map[SetPlaceableShape(annotated_shape.shape)] = color_value

                    for s in InterrogateUtils.traverse_all_subshapes(annotated_shape.shape):
                        self._color_map[SetPlaceableShape(s)] = color_value

    def establish_color(self, shape: SetPlaceableShape) -> typing.Tuple[int, int, int]:
        if shape in self._color_map:
            return self._color_map[shape]
        elif shape.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_FACE:
            return self.faces_spec.base_color
        elif shape.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_EDGE:
            return self.edges_spec.base_color
        else:
            raise ValueError()


class RenderSpec:

    def __init__(self,
                 visualize_face_normals: bool = True,
                 visualize_edge_directions: bool = True,
                 visualize_vertices: bool = True):
        self._visualize_face_normals = visualize_face_normals
        self._visualize_edge_directions = visualize_edge_directions
        self._visualize_vertices = visualize_vertices

    @property
    def visualize_face_normals(self):
        return self._visualize_face_normals

    @property
    def visualize_edge_directions(self):
        return self._visualize_edge_directions

    @property
    def visualize_vertices(self):
        return self._visualize_vertices
