import math
import random

# noinspection PyUnresolvedReferences
import vtkmodules.vtkInteractionStyle
# noinspection PyUnresolvedReferences
import vtkmodules.vtkRenderingOpenGL2
from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkFiltersGeneral import vtkTransformFilter
from vtkmodules.vtkFiltersSources import vtkPlaneSource
from vtkmodules.vtkFiltersTexture import vtkTransformTextureCoords
from vtkmodules.vtkImagingSources import vtkImageCanvasSource2D
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkPolyDataMapper,
    vtkRenderWindow,
    vtkRenderWindowInteractor,
    vtkRenderer, vtkTexture, vtkColorTransferFunction, vtkSkybox, vtkProperty
)

from vtkmodules.vtkRenderingOpenGL2 import vtkEquirectangularToCubeMapTexture


class EnvironmentCubemaps:

    def __init__(self,
                 skybox_cubemap_texture: vtkTexture,
                 environment_cubemap_texture: vtkTexture):
        self.skybox_cubemap_texture = skybox_cubemap_texture
        self.environment_cubemap_texture = environment_cubemap_texture


class TextureFactory:

    @staticmethod
    def _draw_cubemap_canvas() -> vtkImageCanvasSource2D:
        # create the source skybox texture
        x_res = 4
        y_res = 4
        y_mid = int(y_res / 2)
        x_mid = int(x_res / 2)

        canvas_2d = vtkImageCanvasSource2D()
        canvas_2d.SetNumberOfScalarComponents(4)
        canvas_2d.SetScalarTypeToUnsignedChar()
        canvas_2d.SetExtent(0, x_res - 1, 0, y_res - 1, 0, 0)

        # draw the sky
        canvas_2d.SetDrawColor(230, 230, 233, 255)
        canvas_2d.FillBox(0, x_res, 0, y_mid)

        # draw the sky 1
        canvas_2d.SetDrawColor(0, 250, 253, 255)
        canvas_2d.FillBox(x_mid, x_mid, y_mid - 1, y_mid)

        # draw the ground
        canvas_2d.SetDrawColor(203, 203, 203, 255)
        canvas_2d.FillBox(0, x_res, y_mid, y_res)

        # draw the horizon
        # canvas_2d.SetDrawColor(192 + 20, 198 + 20, 207 - 0, 255)
        # canvas_2d.FillBox(0, x_res, y_mid, y_mid + 1)
        canvas_2d.Update()

        return canvas_2d

    @staticmethod
    def _draw_skybox_canvas() -> vtkImageCanvasSource2D:
        # create the source skybox texture
        x_res = 64
        y_res = 64

        rng = random.Random()

        canvas_2d = vtkImageCanvasSource2D()
        canvas_2d.SetNumberOfScalarComponents(4)
        canvas_2d.SetScalarTypeToUnsignedChar()
        canvas_2d.SetExtent(0, x_res - 1, 0, y_res - 1, 0, 0)

        for x in range(0, x_res):
            for y in range(0, y_res):
                brightness = rng.randint(150, 250)
                canvas_2d.SetDrawColor(brightness, brightness, brightness, 255)
                canvas_2d.FillBox(x, x, y, y)

        canvas_2d.Update()

        return canvas_2d


    @staticmethod
    def _canvas_to_cubemap(canvas: vtkImageCanvasSource2D) -> vtkTexture:
        texture = vtkTexture()
        texture.SetColorModeToDirectScalars()
        texture.UseSRGBColorSpaceOn()
        texture.InterpolateOn()
        texture.MipmapOn()
        texture.SetWrap(False)
        texture.SetInputData(canvas.GetOutput())

        to_cubemap = vtkEquirectangularToCubeMapTexture()

        to_cubemap.SetInputTexture(texture)
        to_cubemap.CubeMapOn()
        to_cubemap.InterpolateOn()
        to_cubemap.MipmapOn()
        to_cubemap.SetCubeMapSize(64)

        return to_cubemap

    @staticmethod
    def get_cubemap() -> EnvironmentCubemaps:
        cubemap_canvas = TextureFactory._draw_cubemap_canvas()
        cubemap_texture = TextureFactory._canvas_to_cubemap(cubemap_canvas)

        skybox_canvas = TextureFactory._draw_cubemap_canvas() #TextureFactory._draw_skybox_canvas()
        skybox_texture = TextureFactory._canvas_to_cubemap(skybox_canvas)

        return EnvironmentCubemaps(cubemap_texture, skybox_texture)
