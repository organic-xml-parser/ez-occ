import typing
import OCC.Core.BRepAdaptor
from OCC.Core import gp
from scipy.stats._qmc import PoissonDisk

from ezocc.part_manager import Part, PartCache, PartFactory
from ezocc.workplane.surface_mapping import SurfaceMapper


def poisson_disk_points(cache: PartCache,
                        face: Part,
                        radius: float,
                        seed: int = 0) -> Part:
    factory = PartFactory(cache)

    adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_Surface(face.shape)
    du = adaptor.LastUParameter() - adaptor.FirstUParameter()
    dv = adaptor.LastVParameter() - adaptor.FirstVParameter()

    poisson_disk = PoissonDisk(d=2, radius=radius, seed=seed)
    points = poisson_disk.fill_space()
    points = [(adaptor.FirstUParameter() + p[0] * du, adaptor.FirstVParameter() + p[1] * dv) for p in points]

    verts = []
    for p in points:
        pnt = gp.gp_Pnt()
        adaptor.D0(p[0], p[1], pnt)
        vert = factory.vertex(pnt.X(), pnt.Y(), pnt.Z())

        if vert.bool.intersects(face):
            verts.append(vert)

    return factory.compound(*verts)
