import typing

from OCC.Core.gp import gp_Trsf, gp_Ax3, gp, gp_Vec, gp_Pln, gp_Pnt, gp_Dir

from ezocc.occutils_python import WireSketcher
from ezocc.part_manager import Part, PartFactory


def _get_unique_pnts(part: Part) -> typing.Set[typing.Tuple[float, float, float]]:
    return {v.inspect.vertex.xyz for v in part.explore.vertex.get()}


def get_transform_to_xy_plane(part: Part) -> gp_Trsf:

    cache = part.cache_token.get_cache()

    factory = PartFactory(cache)

    v_a, v_b, v_c = [v for v in _get_unique_pnts(part)][0:3]

    local_x = gp_Vec(
        gp_Pnt(*v_a),
        gp_Pnt(*v_b))

    local_z = gp_Vec(
        gp_Pnt(*v_a),
        gp_Pnt(*v_c)
    )
    local_z.Cross(local_x)
    local_z.Normalize()

    result = gp_Trsf()
    result.SetTransformation(
        gp_Ax3(gp.XOY()),
        gp_Ax3(
            gp_Pnt(*v_a),
            gp_Dir(local_z),
            gp_Dir(local_x))
    )

    return result
