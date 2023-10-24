from ezocc.part_manager import Part, PartFactory


def create() -> Part:
    extrusion = PartFactory.square_centered(25, 25).fillet.fillet2d_verts(2)

    extrusion = PartFactory.face(
        extrusion,
        extrusion.extrude.offset(-1.5))

    return extrusion