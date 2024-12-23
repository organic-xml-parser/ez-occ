import math
import typing

import OCC.Core.TopAbs
from OCC.Core.gp import gp_Ax2, gp_Pnt, gp_Dir, gp

from ezocc.cad.model.widgets.label_widget import LabelWidget
from ezocc.cad.model.widgets.widget import Widget
from ezocc.data_structures.point_like import P3DLike
from ezocc.humanization import Humanize
from ezocc.occutils_python import InterrogateUtils, WireSketcher, Extents
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import Part, PartCache, PartFactory


def size_text_to_shape(text: Part, shape: Part) -> Part:
    text_dim = math.hypot(*text.xts.xyz_span)
    shape_dim = math.hypot(*shape.xts.xyz_span)

    scale_factor = 0.1 * shape_dim / text_dim

    return text.tr.scale(scale_factor, *text.inspect.com().xts.xyz_mid)


class Utils:

    @staticmethod
    def conical_marker(cache: PartCache):
        factory = PartFactory(cache)

        return factory.cone(0, 0.25, 0.1) \
            .do(lambda p: p.bool.union(factory.cone(0.25, 0, 1).align().stack_z1(p))) \
            .cleanup().tr.ry(math.radians(90))

    @staticmethod
    def rotate_to_match_tangent_vector(part: Part, origin: gp_Pnt, tangent: gp_Dir) -> Part:
        """
        Assumes 'pointing direction' of specified part is DX
        """

        v_yrotation_angle = math.atan2(tangent.Z(), math.hypot(tangent.X(), tangent.Y()))
        v_zrotation_angle = math.atan2(tangent.Y(), tangent.X())

        part = part.tr.ry(-v_yrotation_angle, offset=Humanize.xyz(origin))
        part = part.tr.rz(v_zrotation_angle, offset=Humanize.xyz(origin))

        return part


class FaceWidgets:

    def __init__(self, cache: PartCache):
        self._cache = cache
        self._factory = PartFactory(cache)
        self._marker = Utils.conical_marker(cache)

    def orientation(self, face: Part):
        self._assert_face(face)

        def uv_mapper(umin, umax, vmin, vmax):
            return umin + 0.5 * (umax - umin), vmin + 0.5 * (vmax - vmin)

        v, tv = InterrogateUtils.face_normal(face.shape, uv_mapper)

        text = self._factory.text(Humanize.orientation_shorthand(face.shape.Orientation()),
                           "sans-serif",
                           2)
        text = size_text_to_shape(text, face)

        text = text.align().com(face).annotate("color", "green")

        text = Utils.rotate_to_match_tangent_vector(text, v, tv)

        return text

    def normals(self, face: Part, u_segments: int, v_segments: int) -> Part:
        self._assert_face(face)
        if u_segments <= 1 or v_segments <= 1:
            raise ValueError("U segments and v segments must be > 1")

        result = []
        u_spacing = 1 / (u_segments + 1)
        v_spacing = 1 / (v_segments + 1)
        for u in range(0, u_segments):
            for v in range(0, v_segments):

                u_param = u * u_spacing + u_spacing / 2
                v_param = v * v_spacing + v_spacing / 2

                def uv_mapper(umin, umax, vmin, vmax):
                    return umin + u_param * (umax - umin), vmin + v_param * (vmax - vmin)

                pnt, normal = InterrogateUtils.face_normal(face.shape, uv_mapper)

                # check to see if this point intersects with the face
                if len(self._factory.vertex(*Humanize.xyz(pnt)).bool.common(face).explore.vertex.get()) == 0:
                    continue

                marker = self._marker.align().x_min_to(x=pnt.X())\
                    .align().y_mid_to(y=pnt.Y())\
                    .align().z_mid_to(z=pnt.Z())

                if face.inspect.orientation() == OCC.Core.TopAbs.TopAbs_REVERSED:
                    normal = normal.Reversed()

                marker = Utils.rotate_to_match_tangent_vector(marker, pnt, normal)

                result.append(marker)

        return self._factory.compound(*result)

    def _assert_face(self, face: Part):
        if not face.inspect.is_face():
            raise ValueError("Part is not a face")


class EdgeWidgets:

    def __init__(self, cache: PartCache):
        self._cache = cache
        self._factory = PartFactory(cache)

        self._endpoint_marker = Utils.conical_marker(cache)

    def endpoints(self, edge: Part, segments: int = 3) -> Part:
        if segments <= 1:
            raise ValueError("At least two segments must be specified")

        result = []
        spacing = 1 / (segments - 1)
        for i in range(0, segments):
            v = InterrogateUtils.line_point(edge.shape, i * spacing)
            tv = InterrogateUtils.line_tangent_point(edge.shape, i * spacing)

            marker = self._endpoint_marker

            if i == 0:
                marker = marker\
                    .align().x_min_to(x=v.X())\
                    .align().y_mid_to(y=v.Y())\
                    .align().z_mid_to(z=v.Z())
            elif i == segments - 1:
                marker = marker\
                    .align().x_max_to(x=v.X())\
                    .align().y_mid_to(y=v.Y())\
                    .align().z_mid_to(z=v.Z())
            else:
                marker = marker\
                    .align().x_mid_to(x=v.X())\
                    .align().y_mid_to(y=v.Y())\
                    .align().z_mid_to(z=v.Z())

            marker = Utils.rotate_to_match_tangent_vector(marker, v, gp_Dir(tv.Normalized()))

            result.append(marker)

        return self._factory.compound(*result)

    def orientation(self, edge: Part):
        self._assert_edge(edge)

        v = InterrogateUtils.line_point(edge.shape, 0.5)
        tv = InterrogateUtils.line_tangent_point(edge.shape, 0.5)

        text = self._factory.text(Humanize.orientation_shorthand(edge.shape.Orientation()),
                           "sans-serif",
                           2)
        text = size_text_to_shape(text, edge)

        text = text.align().com(edge).annotate("color", "red")

        text = Utils.rotate_to_match_tangent_vector(text, v, tv)

        return text


    def _assert_edge(self, edge: Part):
        if not edge.inspect.is_edge():
            raise ValueError("Part is not an edge")


class VertexWidgets:

    def __init__(self, cache: PartCache):
        self._cache = cache
        self._factory = PartFactory(cache)

        self._position_marker = self._factory.sphere(0.5)

    def position(self, vertex: Part) -> Part:
        self._assert_vertex(vertex)
        return self._position_marker.align().by("xmidymidzmid", vertex)

    def orientation(self, vertex: Part) -> Part:
        self._assert_vertex(vertex)

        text = self._factory.text(Humanize.orientation_shorthand(vertex.shape.Orientation()),
                           "sans-serif",
                           2)

        return text.align().by("xmaxymaxzmax", vertex).annotate("color", "blue") #.print()

    def _assert_vertex(self, part: Part):
        if not part.inspect.is_vertex():
            raise ValueError("Input part is not a vertex")


class PartWidgets:

    @staticmethod
    def label_subshapes(part: Part) -> typing.Iterator[Widget]:
        for label, subshapes in part.subshapes.items():
            for subshape in subshapes:
                if subshape.set_placeable_shape != part.set_placeable_shape:
                    yield LabelWidget(label, P3DLike(*Extents(subshape.shape).xyz_mid))

    def fully_annotate(self, part: Part) -> Part:
        vert_widgets = VertexWidgets(part.cache_token.get_cache())
        edge_widgets = EdgeWidgets(part.cache_token.get_cache())
        face_widgets = FaceWidgets(part.cache_token.get_cache())

        widgets = []

        for f in part.explore.face.get():
            widgets.append(face_widgets.normals(f, 10, 10))
            widgets.append(face_widgets.orientation(f))

        for e in part.explore.edge.get():
            widgets.append(edge_widgets.endpoints(e, segments=4))
            widgets.append(edge_widgets.orientation(e))

        for v in part.explore.vertex.get():
            widgets.append(vert_widgets.orientation(v))

        return PartFactory(part.cache_token.get_cache()).compound(part, *widgets)


if __name__ == '__main__':
    cache = InMemoryPartCache()
    factory = PartFactory(cache)

    part_widgets = PartWidgets()

    wire = WireSketcher().line_to(10, 20, 30, is_relative=True)\
        .line_to(-10, -20, 30, is_relative=True)\
        .get_wire_part(cache)\
        .fillet.fillet2d_verts(10)\
        .do(lambda p: p.add(WireSketcher(*p.explore.vertex.get()[0].xts.xyz_mid)
                            .line_to(*p.explore.vertex.get()[-1].xts.xyz_mid)
                            .get_wire_part(cache).explore.edge.get()[0]))

    wire = factory.compound(*wire.explore.edge.get()).preview()

    face = wire.make.face()

    part_widgets.fully_annotate(face).preview(face)