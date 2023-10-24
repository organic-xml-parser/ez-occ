import math
import pdb

import OCC.Core.Geom
import OCC.Core.GeomAbs
import OCC.Core.Geom2d
import OCC.Core.GeomAdaptor
import OCC.Core.BRepAdaptor
import OCC.Core.BRepBuilderAPI
import OCC.Core.GC
import OCC.Core.BRepLib
import OCC.Core.GeomLib
from OCC.Core.gp import gp_Trsf2d, gp_Vec2d, gp_GTrsf2d, gp_Ax2d, gp_Pnt2d, gp_Dir2d, gp_Lin2d

from ezocc.occutils_python import WireSketcher
from ezocc.part_cache import FileBasedPartCache, InMemoryPartCache
from ezocc.part_manager import Part, PartFactory

from util_wrapper_swig import SurfaceMapperWrapper

class SurfaceMapper:

    def __init__(self,
                 factory: PartFactory,
                 from_surface: Part,
                 to_surface: Part,
                 scale_u_bounds: bool = True,
                 scale_v_bounds: bool = True):

        from_surface.cleanup.build_curves_3d()
        to_surface.cleanup.build_curves_3d()

        self._factory = factory

        self._scale_u_bounds = scale_u_bounds
        self._scale_v_bounds = scale_v_bounds

        self._from_surface_shape = from_surface
        self._from_surface = OCC.Core.BRepAdaptor.BRepAdaptor_Surface(from_surface.shape)
        self._to_surface = OCC.Core.BRepAdaptor.BRepAdaptor_Surface(to_surface.shape)

    def map_face(self, part: Part):
        wires = [self.map_wire(w) for w in part.explore.wire.get()]

        outer_wire = wires[0]

        mkf = SurfaceMapperWrapper.create_make_face(outer_wire.shape, self._to_surface)

        for w in wires[1:]:
            mkf.Add(w.make.wire().shape.Reversed())

        return part.perform_make_shape(
            part.cache_token.mutated("map_face", self._from_surface.Face(), self._to_surface.Face()),
            mkf)

    def map_wire(self, part: Part):
        edges = [self.map_edge(e) for e in part.explore.edge.get()]

        return self._factory.compound(*edges).make.wire()

    def map_edge(self, part: Part):

        c0_u0, c0_v0 = self._from_surface.FirstUParameter(), self._from_surface.FirstVParameter()
        c0_u1, c0_v1 = self._from_surface.LastUParameter(), self._from_surface.LastVParameter()

        c1_u0, c1_v0 = self._to_surface.FirstUParameter(), self._to_surface.FirstVParameter()
        c1_u1, c1_v1 = self._to_surface.LastUParameter(), self._to_surface.LastVParameter()

        curve_2d = OCC.Core.BRepAdaptor.BRepAdaptor_Curve2d(part.shape, self._from_surface_shape.shape)

        trimmed_curve = OCC.Core.Geom2d.Geom2d_TrimmedCurve(curve_2d.Curve(),
                                                            curve_2d.FirstParameter(),
                                                            curve_2d.LastParameter())

        from_dx = c0_u1 - c0_u0
        from_dy = c0_v1 - c0_v0

        to_dx = c1_u1 - c1_u0
        to_dy = c1_v1 - c1_v0

        #print("from dx", from_dx, "from dy", from_dy)
        #print("to dx", to_dx, "to dy", to_dy)

        x_scale = to_dx / from_dx
        y_scale = to_dy / from_dy

        if self._scale_u_bounds:
            trimmed_curve.Translate(gp_Vec2d(0, -c0_v0))

        if self._scale_v_bounds:
            trimmed_curve.Translate(gp_Vec2d(-c0_u0, 0))

        if self._scale_v_bounds:
            gtrsf = gp_GTrsf2d()
            gtrsf.SetAffinity(gp_Ax2d(gp_Pnt2d(0, 0), gp_Dir2d(1, 0)), y_scale)
            trimmed_curve = OCC.Core.GeomLib.geomlib.GTransform(trimmed_curve, gtrsf)

        if self._scale_u_bounds:
            gtrsf = gp_GTrsf2d()
            gtrsf.SetAffinity(gp_Ax2d(gp_Pnt2d(0, 0), gp_Dir2d(0, 1)), x_scale)
            trimmed_curve = OCC.Core.GeomLib.geomlib.GTransform(trimmed_curve, gtrsf)

        if self._scale_u_bounds:
            trimmed_curve.Translate(gp_Vec2d(0, c1_v0))

        if self._scale_v_bounds:
            trimmed_curve.Translate(gp_Vec2d(c1_u0, 0))

        mke = SurfaceMapperWrapper.create_make_edge(trimmed_curve, self._to_surface)

        return part.perform_make_shape(
            part.cache_token.mutated("map_edge", self._from_surface.Face(), self._to_surface.Face()),
            mke
        ).cleanup.build_curves_3d()


if __name__ == '__main__':
    cache = InMemoryPartCache() # FileBasedPartCache("/wsp/cache")
    factory = PartFactory(cache)

    lattice = factory.hex_lattice(6, 6)\
        .tr.scale_to_x_span(math.pi)\
        .tr.scale_to_y_span(10) \
        .align().x_min_to(x=0)\
        .align().y_min_to(y=0)

    to_face: Part = factory.cylinder(10, 10) \
        .explore.face.order_by(lambda f: f.xts.z_mid).get()[1]

    to_face_surf = OCC.Core.BRepAdaptor.BRepAdaptor_Surface(to_face.shape)
    from_face = factory.square_centered(1, 1)

    to_face_1 = to_face.tr.scale(5).align().by("zmin", to_face)

    f0_mapper = SurfaceMapper(factory, from_face, to_face, scale_u_bounds=False, scale_v_bounds=False)
    f1_mapper = SurfaceMapper(factory, from_face, to_face_1, scale_u_bounds=False, scale_v_bounds=False)

    shapes = []
    for f in lattice.explore.face.get():
        start_face = f0_mapper.map_face(f)

        end_face = f1_mapper.map_face(f)

        body = factory.loft([
            start_face,
            end_face
        ], is_solid=True)

        body = factory.shell(start_face, end_face, *body.explore.face.get()).make.solid()

        shapes.append(body)

    factory.compound(*shapes, lattice, from_face, to_face).cleanup.build_curves_3d().preview()
