import math

from OCC.Core.gp import gp

from ezocc.part_manager import PartFactory


TITLE = "Dish"
DESCRIPTION = "Creating a Parabolic Dish w. Lattice Supports"
FILENAME = "dish"


def build(cache):
    factory = PartFactory(cache)

    curve = factory.parabola(100, 0, 60)

    inner = curve.sp("curve").clear_subshape_map().revol.about(gp.OZ(), math.radians(360))
    outer = inner.extrude.make_thick_solid(4)

    rim = factory.loft([
        inner.explore.edge.get()[1].make.wire(),
        outer.explore.edge.get()[1].make.wire()
    ], is_solid=False)

    result = factory.shell(rim.explore.face.get()[0],
                         *inner.explore.face.get(),
                         *outer.explore.face.get())\
        .make.solid().cleanup.fix_solid()

    result_perimeter = factory.cylinder(inner.xts.x_span / 2,
                                        result.xts.z_span).align().by("xmidymidzmin", result)

    result = result.bool.common(result_perimeter)

    lattice_extrusion_thickness = 0.5

    support_lattice = (factory.lattice(9, 9, True, True) \
        .tr.scale_to_x_span(result.xts.x_span - lattice_extrusion_thickness, scale_other_axes=True) \
        .do(lambda p: factory.union(*[w.extrude.offset(lattice_extrusion_thickness, spine=gp.XOY()).make.face() for w in p.explore.wire.get()])) \
        .sew.faces().cleanup() \
        .align().by("xmidymidzmid", result) \
        .bool.common(result_perimeter.extrude.make_thick_solid(-2 * lattice_extrusion_thickness)) \
        .cleanup() \
        .extrude.prism(dz=result.xts.z_span + 2) \
        .align().by("zmin", result).tr.mv(dz=-1) \
        .bool.cut(result) \
        .explore.solid.get_min(lambda s: s.xts.z_min)\
        .bool.cut(factory.box_surrounding(result).align().stack_z0(result))\
        .add(factory.ring(result_perimeter.xts.x_span / 2, result_perimeter.xts.x_span / 2 - lattice_extrusion_thickness * 2, inner.xts.z_span)
                    .align().by("xmidymidzmin", result))\
        .cleanup())

    result = result.cleanup.fix_solid().add(support_lattice)

    return result.bool.cut(factory.box(10, 10, result.xts.z_span).align().by("xmidymidzmin", result))
