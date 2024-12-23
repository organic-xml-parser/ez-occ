import typing

from vtkmodules.vtkCommonCore import vtkObject
from vtkmodules.vtkRenderingCore import vtkActor, vtkRenderWindowInteractor


class Widget:
    """
    Additional entities to be rendered that are not OCC parts. For example text labels.
    """

    def __init__(self):
        self._vtk_object: typing.Optional[vtkObject] = None

    def init_vtk_widget(self, interactor: vtkRenderWindowInteractor) -> None:
        if self._vtk_object is not None:
            raise ValueError("Widget already initialized")

        self._vtk_object = self._create_vtk_widget(interactor)

    def _create_vtk_widget(self, interactor: vtkRenderWindowInteractor) -> vtkObject:
        raise NotImplementedError()
