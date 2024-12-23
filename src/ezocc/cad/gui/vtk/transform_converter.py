from vtkmodules.vtkCommonMath import vtkMatrix4x4
from vtkmodules.vtkCommonTransforms import vtkTransform, vtkLinearTransform
import OCC.Core.gp


class TransformConverter:

    @staticmethod
    def convert_occ_to_vtk_transform(occ_transform: OCC.Core.gp.gp_GTrsf) -> vtkLinearTransform:
        result = vtkTransform()
        result.PostMultiply()

        matrix = vtkMatrix4x4()
        for row in range(0, 3):
            for col in range(0, 4):
                matrix.SetElement(row, col, occ_transform.Value(row + 1, col + 1))

        result.SetMatrix(matrix)

        return result

    @staticmethod
    def convert_vtk_to_occ_transform(vtk_transform: vtkTransform) -> OCC.Core.gp.gp_GTrsf:
        result = OCC.Core.gp.gp_GTrsf()

        matrix = vtkMatrix4x4()
        vtk_transform.GetMatrix(matrix)

        for row in range(0, 3):
            for col in range(0, 4):
                result.SetValue(row + 1, col + 1, matrix.GetElement(row, col))

        return result
