from __future__ import annotations

import typing

import OCC.Core.TopAbs
from vtkmodules.vtkCommonCore import vtkUnsignedCharArray
from vtkmodules.vtkRenderingCore import vtkActor

from ezocc.cad.gui.rendering_specifications.rendering_color_spec import RenderingColorSpec
from ezocc.occutils_python import SetPlaceableShape, SetPlaceablePart


class VtkOccActor:
    """
    Associates a single part with a vtk actor
    """

    def __init__(self,
                 color_spec: RenderingColorSpec,
                 actor: vtkActor,
                 part: SetPlaceablePart,
                 shape_type: OCC.Core.TopAbs.TopAbs_ShapeEnum,
                 cell_ids_to_subshapes: typing.Dict[int, SetPlaceableShape],
                 subshapes_to_cell_ids: typing.Dict[SetPlaceableShape, typing.Set[int]]):
        self._shape_type = shape_type
        self._color_spec = color_spec
        self._actor = actor
        self._part = part
        self._cell_ids_to_subshapes = cell_ids_to_subshapes.copy()
        self._subshapes_to_cell_ids = subshapes_to_cell_ids.copy()

        self._saved_cell_states: typing.Dict[int, typing.Tuple[float, float, float]] = {}

    @property
    def shape_type(self) -> OCC.Core.TopAbs.TopAbs_ShapeEnum:
        """
        @return: the type of rendered shape this actor is associated with (vert, edge, face)
        """

        return self._shape_type

    @property
    def actor(self) -> vtkActor:
        return self._actor

    @property
    def part(self) -> SetPlaceablePart:
        return self._part

    def get_subshape_for_cell_id(self, cell_id: int) -> typing.Optional[SetPlaceableShape]:
        if cell_id in self._cell_ids_to_subshapes:
            return self._cell_ids_to_subshapes[cell_id]
        else:
            return None

    def clear_highlights(self):
        cell_scalars: vtkUnsignedCharArray = \
            self._actor.GetMapper().GetInput().GetCellData().GetScalars()

        for cell_id, saved_color in self._saved_cell_states.items():
            cell_scalars.SetTypedTuple(cell_id, saved_color)

        self._saved_cell_states.clear()

        self._actor.GetMapper().GetInput().Modified()

    def highlight_subshape(self, subshape: SetPlaceableShape):
        cell_ids = self._subshapes_to_cell_ids.get(subshape)

        is_labelled = self._part.part.subshapes.contains_shape(subshape)

        rgb = self._color_spec.establish_color(subshape, is_labelled=is_labelled, is_highlighted=True)

        self._highlight_cells(rgb, cell_ids)

    def _highlight_cells(self, rgb, ids_to_highlight: typing.Set[int]):
        cell_scalars: vtkUnsignedCharArray = \
            self._actor.GetMapper().GetInput().GetCellData().GetScalars()

        for i in ids_to_highlight:
            t_out = [0, 0, 0]
            cell_scalars.GetTypedTuple(i, t_out)

            if i not in self._saved_cell_states:
                self._saved_cell_states[i] = (t_out[0], t_out[1], t_out[2])

            cell_scalars.SetTypedTuple(i, rgb)

        self._actor.GetMapper().GetInput().Modified()
