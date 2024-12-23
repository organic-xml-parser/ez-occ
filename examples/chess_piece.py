import math

from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell as mps

from ezocc.occutils_python import WireSketcher
from ezocc.part_manager import PartFactory, Part, PartCache


TITLE = "Chess Piece"
DESCRIPTION = "Creating a Chess Piece"
FILENAME = "chess_piece"


def build(cache: PartCache):
    factory = PartFactory(cache)

    base = factory.square_centered(20, 20).fillet.fillet2d_verts(1).make.face()
    top = factory.circle(7).align().com(base).tr.mv(dz=30).make.face()
    top_outer = top.tr.scale_to_x_span(top.xts.x_span + 5, scale_other_axes=True).align().com(top)

    head = factory.loft([
        top,
        top_outer.tr.mv(dz=5),
        top_outer.tr.mv(dz=10),
        top_outer.tr.scale_to_x_span(top_outer.xts.x_span - 2, scale_other_axes=True).align().com(top_outer).tr.mv(dz=10),
        top.tr.mv(dz=5)
    ], last_shape_name="top_face")

    head = head.bool.cut(
        factory.box(head.xts.x_span, 1, 1)
                     .align().by("xminmidymidzmax", head)
                     .extrude.make_thick_solid(1)
                     .pattern(range(0, 10), lambda i, p: p.tr.rz(math.radians(i * 360 / 10), offset=head.xts.xyz_mid)))

    m = mps(WireSketcher().line_to(z=30, is_relative=True).get_wire())
    m.SetMode(factory.helix(30, 10, 0.3).shape, True)

    m.Add(base.make.wire().shape)
    m.Add(top.make.wire().shape)

    body = factory.shell(*Part.of_shape(m.Shape())
        .add(base.make.face(), top.make.face()).explore.face.get())\
        .make.solid()

    base = factory.loft([
        base,
        base.tr.scale_to_x_span(base.xts.x_span + 2, scale_other_axes=True).align().com(base).tr.mv(dz=-5),
        base.tr.scale_to_x_span(base.xts.x_span + 1, scale_other_axes=True).align().com(base).tr.mv(dz=-10)
    ], last_shape_name="bottom")\
        .do(lambda f: f.fillet.chamfer_faces(1, f.sp("bottom")))

    return base.add(body, head)