import typing

from PyQt5.QtCore import QObject, pyqtSignal
from vtkmodules.vtkRenderingCore import vtkCamera
from vtkmodules.vtkRenderingOpenGL2 import vtkOpenGLCamera

from ezocc.cad.model.session import Session


class CameraPolicy:

    class CameraChangeEmitter(QObject):
        parallel_projection_signal = pyqtSignal()

    def __init__(self,
                 session: Session,
                 parent_cache_key: str,
                 camera: vtkCamera,
                 render_callback: typing.Callable[[], None]):
        self._camera = camera
        self._session = session
        self._cache_key = parent_cache_key + ".camera"
        self.camera_change_emitter = CameraPolicy.CameraChangeEmitter()
        self._camera.AddObserver("ModifiedEvent", self._cam_modified)
        self._render_callback = render_callback

        self.attempt_load_camera_from_cache()

    def set_parallel_projection(self, is_parallel_projection: bool):
        self._camera.SetParallelProjection(is_parallel_projection)
        self.camera_change_emitter.parallel_projection_signal.emit()
        self._render_callback()

    def get_parallel_projection(self) -> bool:
        return self._camera.GetParallelProjection()

    def _cam_modified(self, cam: vtkOpenGLCamera, b):
        cache_val = '!'.join(str(i) for i in [
            *cam.GetPosition(),
            *cam.GetFocalPoint(),
            *cam.GetViewUp(),
            cam.GetDistance(),
            *cam.GetClippingRange(),
            cam.GetParallelScale(),
            1 if cam.GetParallelProjection() else 0
        ])

        self._session.cache.write_entry(self._cache_key, cache_val)

    def attempt_load_camera_from_cache(self):
        existing_cam_position = self._session.cache.read_entry(self._cache_key)

        if existing_cam_position is None:
            return

        try:
            entries = [float(i) for i in existing_cam_position.split('!')]

            self._camera.SetPosition(*entries[0:3])
            self._camera.SetFocalPoint(*entries[3:6])
            self._camera.SetClippingRange(entries[10], entries[11])
            self._camera.SetViewUp(*entries[6:9])
            self._camera.SetDistance(entries[9])
            self._camera.SetParallelScale(entries[12])
            self._camera.SetParallelProjection(entries[13] == 0)
        except (AttributeError, ValueError, IndexError) as _:
            pass

        self.camera_change_emitter.parallel_projection_signal.emit()
        self._render_callback()
