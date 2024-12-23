import typing
from vtkmodules.vtkCommonColor import vtkNamedColors


class SelectionPalette:
    """
    A color palette that may be sampled from based off selection/highlight state
    """

    NAMED_COLORS = vtkNamedColors()

    ColorInputType = typing.Union[typing.Tuple[float, float, float], str]

    ColorTupleType = typing.Tuple[float, float, float]

    def __init__(self,
                 base_color: ColorInputType,
                 highlight_color: ColorInputType):
        self._base_color = SelectionPalette.color_to_rgb(base_color)
        self._highlight_color = SelectionPalette.color_to_rgb(highlight_color)

    @property
    def base_color(self) -> ColorTupleType:
        return self._base_color

    @property
    def highlight_color(self) -> ColorTupleType:
        return self._highlight_color

    @staticmethod
    def color_to_rgb(color_value: ColorInputType) -> ColorTupleType:
        if isinstance(color_value, str):
            named_color = SelectionPalette.NAMED_COLORS.GetColor3ub(color_value)
            return named_color.GetRed(), named_color.GetGreen(), named_color.GetBlue()
        else:
            return color_value
