from vtkmodules.vtkCommonCore import vtkObject
from vtkmodules.vtkInteractionWidgets import vtkCaptionWidget, vtkCaptionRepresentation
from vtkmodules.vtkRenderingAnnotation import vtkCaptionActor2D
from vtkmodules.vtkRenderingCore import vtkActor

from ezocc.cad.model.widgets.widget import Widget
from ezocc.data_structures.point_like import P3DLike


class LabelWidget(Widget):

    def __init__(self, text: str, origin: P3DLike):
        super().__init__()
        self._text = text
        self._origin = P3DLike.create(origin)

    def _create_vtk_widget(self, interactor) -> vtkObject:
        # Create the widget and its representation.
        caption_actor = vtkCaptionActor2D()
        caption_actor.SetCaption(self._text)
        caption_actor.GetTextActor().GetTextProperty().SetFontSize(100)

        caption_representation = vtkCaptionRepresentation()
        caption_representation.SetCaptionActor2D(caption_actor)

        caption_representation.SetAnchorPosition(self._origin.xyz)

        result = vtkCaptionWidget()

        result.SetInteractor(interactor)
        result.SetRepresentation(caption_representation)

        result.On()

        return result
