import typing

import OCC.Core.TopAbs

from ezocc.cad.gui.rendering_specifications.rendering_annotation_values import RenderingAnnotationValues
from ezocc.cad.gui.rendering_specifications.selection_palette import SelectionPalette
from ezocc.humanization import Humanize
from ezocc.occutils_python import SetPlaceablePart, SetPlaceableShape, InterrogateUtils


class RenderingColorSpec:
    """
    Specifies the color for various entities based on their selection states.
    """

    def __init__(self,
                 part: SetPlaceablePart,
                 vertices_palette: SelectionPalette,
                 edges_palette: SelectionPalette,
                 faces_palette: SelectionPalette,
                 vertices_labelled_palette: SelectionPalette,
                 edges_labelled_palette: SelectionPalette,
                 faces_labelled_palette: SelectionPalette):
        self._vertices_palette = vertices_palette
        self._edges_palette = edges_palette
        self._faces_palette = faces_palette
        self._vertices_labelled_palette = vertices_labelled_palette
        self._edges_labelled_palette = edges_labelled_palette
        self._faces_labelled_palette = faces_labelled_palette

        self._selection_palettes: typing.Dict[SetPlaceableShape, SelectionPalette] = dict()

        def _get_modified_palette(shape: SetPlaceableShape, new_color: str):
            return SelectionPalette(
                    SelectionPalette.color_to_rgb(new_color),
                    self._get_palette_for_shape_type(shape, True).highlight_color)

        def _is_face(s):
            return s.ShapeType() == OCC.Core.TopAbs.TopAbs_FACE

        for label, annotated_shapes in part.part.subshapes.items():
            for annotated_shape in annotated_shapes:

                self._selection_palettes[SetPlaceableShape(annotated_shape.shape)] = \
                    self._get_palette_for_shape_type(part.part.set_placeable_shape, True)

                for s in InterrogateUtils.traverse_all_subshapes(annotated_shape.shape):
                    sps = SetPlaceableShape(s)
                    self._selection_palettes[sps] = self._get_palette_for_shape_type(sps, True)

        # cache the color map ahead of time
        if RenderingAnnotationValues.FACE_COLOR in part.part.annotations:
            new_color = part.part.annotations[RenderingAnnotationValues.FACE_COLOR]

            if _is_face(part.part.shape):
                self._selection_palettes[part.part.set_placeable_shape] = (
                    _get_modified_palette(part.part.set_placeable_shape, new_color))

            for s in InterrogateUtils.traverse_all_subshapes(part.part.shape):
                if _is_face(s):
                    self._selection_palettes[SetPlaceableShape(s)] = (
                        _get_modified_palette(SetPlaceableShape(s), new_color))

        for label, annotated_shapes in part.part.subshapes.items():
            for annotated_shape in annotated_shapes:
                if RenderingAnnotationValues.FACE_COLOR in annotated_shape.attributes.values:
                    new_face_color = annotated_shape.part.part.annotations[RenderingAnnotationValues.FACE_COLOR]

                    if _is_face(annotated_shape.shape):
                        self._selection_palettes[SetPlaceableShape(annotated_shape.shape)] = (
                            _get_modified_palette(annotated_shape.shape, new_face_color))

                    for s in InterrogateUtils.traverse_all_subshapes(annotated_shape.shape):
                        if _is_face(s):
                            self._selection_palettes[SetPlaceableShape(s)] = (
                                _get_modified_palette(SetPlaceableShape(s), new_face_color))

    def _get_palette_for_shape_type(self, shape: SetPlaceableShape, is_labelled: bool) -> \
            typing.Optional[SelectionPalette]:

        if shape.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_FACE:
            return self._faces_labelled_palette if is_labelled else self._faces_palette
        elif shape.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_EDGE:
            return self._edges_labelled_palette if is_labelled else self._edges_palette
        elif shape.shape.ShapeType() == OCC.Core.TopAbs.TopAbs_VERTEX:
            return self._vertices_labelled_palette if is_labelled else self._vertices_palette
        else:
            return None #raise ValueError(f"No palette for shape type: {Humanize.shape_type(shape.shape.ShapeType())}")

    def establish_color(self,
                        shape: SetPlaceableShape,
                        is_labelled: bool,
                        is_highlighted: bool) -> typing.Tuple[int, int, int]:
        spec = None

        if shape in self._selection_palettes:
            spec = self._selection_palettes[shape]

        if spec is None:
            spec = self._get_palette_for_shape_type(shape, is_labelled)

        return spec.highlight_color if is_highlighted else spec.base_color
