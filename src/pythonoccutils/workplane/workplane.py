import logging
import pdb
import typing

import OCC
import OCC.Core
import OCC.Core.gp
import OCC.Core.TopAbs
import OCC.Core.BRep
import OCC.Core.GeomLib
import OCC.Core.BRepAdaptor
from OCC.Core.GeomAbs import GeomAbs_Line, GeomAbs_BSplineCurve

from pythonoccutils.humanization import Humanize
from pythonoccutils.occutils_python import InterrogateUtils
from pythonoccutils.part_manager import Part, PartFactory

logger = logging.getLogger(__name__)


class PartTransformer:

    def apply_transform(self, part: Part) -> Part:
        raise NotImplementedError()

    def reverse_transform(self, part: Part) -> Part:
        raise NotImplementedError()


class DefaultTransformer(PartTransformer):

    def __init__(self, trsf: OCC.Core.gp.gp_Trsf):
        self._trsf_apply = trsf
        self._trsf_reverse = trsf.Inverted()

    def apply_transform(self, part: Part) -> Part:
        return part.transform(self._trsf_apply)

    def reverse_transform(self, part: Part) -> Part:
        return part.transform(self._trsf_reverse)


class TransformFactory:
    """
    Based on an input part and some combination of parameters, returns a reversible part transform that can be used to
    convert back and forth to the workplane coordinate system. Certain input parts may not have sufficient DOF to
    constrain the resulting workplane. In these cases, extra arguments may need to be provided. E.g. for a planar face
    an extra angle parameter is needed to fix the resulting workplane's x/y axis rotation.
    """

    @staticmethod
    def edge_plane_transform(edge_part: Part,
                             workplane_part: Part,
                             rotation: float = 0,
                             mirror: bool = False) -> PartTransformer:

        workplane_part = workplane_part.make.face()

        # face provides normal direction
        face = workplane_part.make.face()

        # default edge to act as coordinate origin
        edge = edge_part

        br_adpt_face = OCC.Core.BRepAdaptor.BRepAdaptor_Surface(face.shape)
        br_adpt_edge = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(edge.shape)

        #if br_adpt_edge.GetType() != GeomAbs_Line and not (
        #        br_adpt_edge.GetType() == GeomAbs_BSplineCurve and br_adpt_edge.Degree() == 1):
        #    raise ValueError("Invalid input edge")

        origin = br_adpt_edge.Value(br_adpt_edge.FirstParameter())

        if not OCC.Core.GeomLib.GeomLib_IsPlanarSurface(br_adpt_face.Surface().Surface()):
            raise ValueError("Surface is non planar")

        dz_prime = InterrogateUtils.face_normal(face.shape)[1]

        dx_prime = OCC.Core.gp.gp_Vec(
            br_adpt_edge.Value(br_adpt_edge.FirstParameter()),
            br_adpt_edge.Value(br_adpt_edge.LastParameter()))
        dx_prime = OCC.Core.gp.gp_Dir(dx_prime)

        if mirror:
            dz_prime.Reverse()
            dx_prime.Reverse()

        # prepare the source/destination axis
        source_ax3 = OCC.Core.gp.gp_Ax3(
            OCC.Core.gp.gp_Origin(),
            OCC.Core.gp.gp_DZ(),
            OCC.Core.gp.gp_DX())

        logger.info(f"dx_prime: {dx_prime.X()}, {dx_prime.Y()}, {dx_prime.Z()}")
        logger.info(f"dz_prime: {dz_prime.X()}, {dz_prime.Y()}, {dz_prime.Z()}")

        br_adpt_face.GetType()
        br_adpt_face.Surface().GetType()

        dest_ax3 = OCC.Core.gp.gp_Ax3(
            origin,
            dz_prime,
            dx_prime)

        dest_ax3.Rotate(OCC.Core.gp.gp_Ax1(origin, dz_prime), rotation)

        trsf = OCC.Core.gp.gp_Trsf()
        trsf.SetTransformation(source_ax3, dest_ax3)

        return DefaultTransformer(trsf)

    @staticmethod
    def plane_transform(workplane_part: Part,
                        rotation: float = 0,
                        mirror: bool = False):

        workplane_part = workplane_part.make.face()

        # face provides normal direction
        face = workplane_part.make.face()

        # default edge to act as coordinate origin
        edge = face.explore.edge.get()[0]

        return TransformFactory.edge_plane_transform(edge, workplane_part, rotation, mirror)


class Worker:
    """
    Interface for the user-supplied worker that will carry out modifications to the part in the workplane
    """

    def __call__(self, part_map: typing.Dict[str, Part]) -> typing.List[Part]:
        raise NotImplementedError


class WorkPlane:
    """
    A workplane is a utility for performing a set of operations in a "local" coordinate system. This can be useful when
    trying to position objects on a plane, but you don't know in advance what orientation the plane will be in.

    The workplane acts as a proxy by transforming parts back and forth between the coordinate systems.
    Parts may be "Captured" and converted into the local coordinate system.
    """

    def __init__(self, part_transformer: PartTransformer):
        self._part_transformer = part_transformer

    def session(self,
                captures: typing.Dict[str, Part],
                worker: typing.Union[Worker, typing.Callable[[typing.Dict[str, Part]], typing.Union[typing.List[Part], Part]]]) -> typing.List[Part]:

        transformed_captures = {s: self._part_transformer.apply_transform(p) for s, p in captures.items()}

        result = worker(transformed_captures)

        if not isinstance(result, list):
            result = [result]

        result = [self._part_transformer.reverse_transform(p) for p in result]

        return result
